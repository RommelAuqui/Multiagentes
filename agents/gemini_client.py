import json

from google import genai

from config import GEMINI_API_KEY
from retry_utils import con_reintentos

_client = genai.Client(api_key=GEMINI_API_KEY)


def generar_json(modelo: str, prompt: str) -> dict:
    respuesta = con_reintentos(lambda: _client.models.generate_content(
        model=modelo,
        contents=prompt,
        config={"response_mime_type": "application/json"},
    ))
    return json.loads(respuesta.text)
