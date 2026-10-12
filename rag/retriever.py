from db.client import get_client


def buscar_fragmentos(
    concurso_id: str,
    query_embedding: list[float],
    postor_id: str | None = None,
    origen: str | None = None,
    k: int = 5,
) -> list[dict]:
    respuesta = get_client().rpc("match_documentos", {
        "query_embedding": query_embedding,
        "match_concurso_id": concurso_id,
        "match_postor_id": postor_id,
        "match_origen": origen,
        "match_count": k,
    }).execute()
    return respuesta.data
