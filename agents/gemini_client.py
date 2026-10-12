import json
import logging
import re
import time
from dataclasses import dataclass
from functools import cache

from google import genai

from config import GEMINI_API_KEY
from db.client import get_client
from retry_utils import con_reintentos

INTENTOS_JSON = 3
# Con temperatura 0 y semilla fija, una misma consulta devuelve (casi siempre) la misma respuesta.
SEMILLA = 2026
ESCAPE_INVALIDO = re.compile(r'\\(?!["\\/bfnrtu])')

registro = logging.getLogger(__name__)


class RespuestaInvalidaError(Exception):
    pass


@dataclass(frozen=True)
class ContextoIA:
    agente: str
    concurso_id: str | None = None
    postor_id: str | None = None


@cache
def obtener_cliente() -> genai.Client:
    return genai.Client(api_key=GEMINI_API_KEY)


def _registrar_consulta(
    contexto: ContextoIA, modelo: str, prompt: str, adjuntos: int, respuesta, inicio: float, error: str | None = None
) -> None:
    uso = getattr(respuesta, "usage_metadata", None)
    try:
        get_client().table("consultas_ia").insert({
            "concurso_id": contexto.concurso_id,
            "postor_id": contexto.postor_id,
            "agente": contexto.agente,
            "modelo": modelo,
            "prompt": prompt,
            "adjuntos": adjuntos,
            "respuesta": getattr(respuesta, "text", None),
            "tokens_entrada": getattr(uso, "prompt_token_count", None),
            "tokens_salida": getattr(uso, "candidates_token_count", None),
            "duracion_ms": round((time.monotonic() - inicio) * 1000),
            "error": error,
        }).execute()
    except Exception:
        # La trazabilidad no debe detener una evaluación: el fallo queda en el log del servidor.
        registro.warning("No se pudo registrar la consulta a la IA", exc_info=True)


def generar_json(modelo: str, prompt: str, contexto: ContextoIA, adjuntos: tuple = ()) -> dict:
    for intento in range(INTENTOS_JSON):
        inicio = time.monotonic()
        try:
            respuesta = con_reintentos(lambda: obtener_cliente().models.generate_content(
                model=modelo,
                contents=[*adjuntos, prompt],
                config={
                    "response_mime_type": "application/json",
                    "temperature": 0,
                    # Si la respuesta vino mal formada, repetir la misma semilla daría el mismo error.
                    "seed": SEMILLA + intento,
                },
            ))
        except Exception as e:
            _registrar_consulta(contexto, modelo, prompt, len(adjuntos), None, inicio, f"{type(e).__name__}: {e}")
            raise
        _registrar_consulta(contexto, modelo, prompt, len(adjuntos), respuesta, inicio)

        datos = _cargar_json(respuesta.text or "")
        if isinstance(datos, dict):
            return datos
    raise RespuestaInvalidaError("El modelo no devolvió un JSON válido tras varios intentos.")


def _cargar_json(texto: str):
    # Al transcribir Markdown, el modelo a veces deja escapes inválidos (\_ \*) o tabulaciones sin escapar.
    for candidato in (texto, ESCAPE_INVALIDO.sub(r"\\\\", texto)):
        try:
            return json.loads(candidato, strict=False)
        except json.JSONDecodeError:
            continue
    return None
