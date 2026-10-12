from db.client import get_client


def buscar_fragmentos(
    concurso_id: str,
    query_embedding: list[float],
    postor_id: str | None = None,
    origen: str | None = None,
    k: int = 5,
    documento: str | None = None,
) -> list[dict]:
    respuesta = get_client().rpc("match_documentos", {
        "query_embedding": query_embedding,
        "match_concurso_id": concurso_id,
        "match_postor_id": postor_id,
        "match_origen": origen,
        "match_count": k,
        "match_documento": documento,
    }).execute()
    return respuesta.data


def leer_pagina(postor_id: str, documento: str, pagina: int) -> list[dict]:
    fragmentos = (
        get_client().table("documentos_chunks")
        .select("origen,documento,pagina,orden,contenido")
        .eq("postor_id", postor_id)
        .eq("pagina", pagina)
        .execute()
        .data
    )
    # Las ofertas de la versión anterior no tienen nombre de archivo: se identifican por su origen.
    de_la_pagina = [f for f in fragmentos if (f.get("documento") or f.get("origen")) == documento]
    return sorted(de_la_pagina, key=lambda f: f.get("orden") or 0)
