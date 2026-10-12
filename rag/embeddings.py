from google import genai

from config import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL, GEMINI_API_KEY
from retry_utils import con_reintentos

_client = genai.Client(api_key=GEMINI_API_KEY)


def embed_texto(texto: str) -> list[float]:
    respuesta = con_reintentos(lambda: _client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texto,
        config={"output_dimensionality": EMBEDDING_DIMENSIONS},
    ))
    return respuesta.embeddings[0].values
