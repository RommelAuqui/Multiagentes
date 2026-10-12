from agents.gemini_client import obtener_cliente
from config import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL
from retry_utils import con_reintentos


def embed_texto(texto: str) -> list[float]:
    respuesta = con_reintentos(lambda: obtener_cliente().models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texto,
        config={"output_dimensionality": EMBEDDING_DIMENSIONS},
    ))
    return respuesta.embeddings[0].values
