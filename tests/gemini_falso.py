from types import SimpleNamespace

from google.genai import types


def respuesta_con_llamadas(*llamadas: tuple[str, dict]):
    """Respuesta de Gemini en la que el modelo pide ejecutar las herramientas indicadas."""
    partes = [types.Part.from_function_call(name=nombre, args=argumentos) for nombre, argumentos in llamadas]
    return SimpleNamespace(
        function_calls=[SimpleNamespace(name=nombre, args=argumentos) for nombre, argumentos in llamadas],
        candidates=[SimpleNamespace(content=types.Content(role="model", parts=partes))],
        usage_metadata=SimpleNamespace(prompt_token_count=100, candidates_token_count=10),
        text=None,
    )


class GeminiGuionado:
    """Simula a Gemini con un guion fijo de respuestas y guarda lo que recibió en cada paso."""

    def __init__(self, guion: list):
        self.guion = list(guion)
        self.llamadas: list[dict] = []
        self.models = self

    def generate_content(self, model, contents, config):
        self.llamadas.append({"contents": list(contents), "config": config})
        return self.guion.pop(0)

    def resultado_de_herramienta(self, paso: int) -> dict:
        """Lo que el sistema devolvió al modelo como resultado de sus herramientas antes del paso indicado."""
        return self.llamadas[paso]["contents"][-1].parts[0].function_response.response
