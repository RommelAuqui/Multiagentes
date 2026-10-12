"""Bucle de un agente autónomo con herramientas (function calling de Gemini).

En cada paso el modelo decide qué herramienta usar y con qué argumentos; el sistema la ejecuta y
le devuelve el resultado, hasta que el agente entrega su conclusión con la herramienta final.
"""
import json
import time
from collections.abc import Callable
from dataclasses import dataclass

from google.genai import types

from agents.gemini_client import SEMILLA, ContextoIA, obtener_cliente, registrar_consulta
from retry_utils import con_reintentos

MAX_PASOS = 6
MAX_CARACTERES_REGISTRO = 4000


@dataclass
class Herramienta:
    nombre: str
    descripcion: str
    parametros: dict  # JSON Schema de los argumentos
    funcion: Callable[..., dict] | None = None  # sin función: es la herramienta con la que el agente concluye
    resumir: Callable[[dict, dict], str] | None = None  # descripción breve del paso, para el comité

    def declaracion(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=self.nombre, description=self.descripcion, parameters_json_schema=self.parametros
        )


@dataclass
class ResultadoAgente:
    conclusion: dict | None
    pasos: list[dict]


def _json(valor) -> str:
    return json.dumps(valor, ensure_ascii=False, default=str)[:MAX_CARACTERES_REGISTRO]


def _ejecutar(herramienta: Herramienta | None, nombre: str, argumentos: dict) -> dict:
    if herramienta is None or herramienta.funcion is None:
        return {"error": f"La herramienta «{nombre}» no existe."}
    try:
        return herramienta.funcion(**argumentos)
    except Exception as e:
        # El error vuelve al agente como dato, para que corrija los argumentos o cambie de estrategia.
        return {"error": f"{type(e).__name__}: {e}"}


def ejecutar_agente(
    modelo: str,
    instrucciones: str,
    herramientas: list[Herramienta],
    final: Herramienta,
    contexto: ContextoIA,
    max_pasos: int = MAX_PASOS,
) -> ResultadoAgente:
    por_nombre = {h.nombre: h for h in herramientas}
    declaraciones = types.Tool(function_declarations=[h.declaracion() for h in [*herramientas, final]])
    conversacion = [types.Content(role="user", parts=[types.Part.from_text(text=instrucciones)])]
    pasos: list[dict] = []
    entrada = instrucciones

    for numero in range(max_pasos):
        # En el último paso solo puede concluir: el agente no puede buscar indefinidamente.
        permitidas = [final.nombre] if numero == max_pasos - 1 else None
        config = types.GenerateContentConfig(
            tools=[declaraciones],
            tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(
                mode="ANY", allowed_function_names=permitidas,
            )),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            temperature=0,
            seed=SEMILLA,
        )
        inicio = time.monotonic()
        try:
            respuesta = con_reintentos(lambda: obtener_cliente().models.generate_content(
                model=modelo, contents=conversacion, config=config,
            ))
        except Exception as e:
            registrar_consulta(contexto, modelo, entrada, 0, None, inicio, f"{type(e).__name__}: {e}")
            raise

        llamadas = respuesta.function_calls or []
        registrar_consulta(
            contexto, modelo, entrada, 0, respuesta, inicio,
            texto_respuesta=_json([{"herramienta": l.name, "argumentos": dict(l.args or {})} for l in llamadas]),
        )
        if not llamadas:
            break
        for llamada in llamadas:
            if llamada.name == final.nombre:
                return ResultadoAgente(dict(llamada.args or {}), pasos)

        conversacion.append(respuesta.candidates[0].content)
        respuestas = []
        for llamada in llamadas:
            argumentos = dict(llamada.args or {})
            herramienta = por_nombre.get(llamada.name)
            resultado = _ejecutar(herramienta, llamada.name, argumentos)
            resumen = (
                herramienta.resumir(argumentos, resultado)
                if herramienta and herramienta.resumir and "error" not in resultado
                else f"{llamada.name}: {resultado.get('error', 'ok')}"
            )
            pasos.append({"herramienta": llamada.name, "argumentos": argumentos, "resumen": resumen})
            respuestas.append(types.Part.from_function_response(name=llamada.name, response=resultado))
        conversacion.append(types.Content(role="user", parts=respuestas))
        entrada = _json([{"herramienta": p.function_response.name, "resultado": p.function_response.response}
                         for p in respuestas])

    return ResultadoAgente(None, pasos)
