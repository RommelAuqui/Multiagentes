from agents.gemini_client import obtener_cliente
from config import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL
from retry_utils import con_reintentos

# Textos por solicitud: pocos miles de tokens, por debajo de los límites del plan gratuito.
TAMANO_LOTE = 20


def _embed_lote(textos: list[str], tipo: str) -> list[list[float]]:
    respuesta = con_reintentos(lambda: obtener_cliente().models.embed_content(
        model=EMBEDDING_MODEL,
        contents=textos,
        config={"output_dimensionality": EMBEDDING_DIMENSIONS, "task_type": tipo},
    ))
    return [e.values for e in respuesta.embeddings]


def _embed_textos(textos: list[str], tipo: str) -> list[list[float]]:
    embeddings = []
    for inicio in range(0, len(textos), TAMANO_LOTE):
        embeddings.extend(_embed_lote(textos[inicio:inicio + TAMANO_LOTE], tipo))
    return embeddings


def embed_documentos(textos: list[str]) -> list[list[float]]:
    return _embed_textos(textos, "RETRIEVAL_DOCUMENT")


def embed_consultas(textos: list[str]) -> list[list[float]]:
    return _embed_textos(textos, "RETRIEVAL_QUERY")
