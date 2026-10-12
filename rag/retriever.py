from db.client import get_client
from rag.embeddings import embed_texto


def buscar_fragmentos(
    concurso_id: str,
    query: str,
    postor_id: str | None = None,
    origen: str | None = None,
    k: int = 5,
) -> list[dict]:
    query_embedding = embed_texto(query)
    respuesta = get_client().rpc("match_documentos", {
        "query_embedding": query_embedding,
        "match_concurso_id": concurso_id,
        "match_postor_id": postor_id,
        "match_origen": origen,
        "match_count": k,
    }).execute()
    return respuesta.data
