import json
from functools import cache

from google import genai

from config import GEMINI_API_KEY
from retry_utils import con_reintentos

INTENTOS_JSON = 3


class RespuestaInvalidaError(Exception):
    pass


@cache
def obtener_cliente() -> genai.Client:
    return genai.Client(api_key=GEMINI_API_KEY)


def generar_json(modelo: str, prompt: str) -> dict:
    for _ in range(INTENTOS_JSON):
        respuesta = con_reintentos(lambda: obtener_cliente().models.generate_content(
            model=modelo,
            contents=prompt,
            config={"response_mime_type": "application/json"},
        ))
        try:
            datos = json.loads(respuesta.text or "")
        except json.JSONDecodeError:
            continue
        if isinstance(datos, dict):
            return datos
    raise RespuestaInvalidaError("El modelo no devolvió un JSON válido tras varios intentos.")
