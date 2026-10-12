from io import BytesIO

import pandas as pd

from db.client import get_client


def generar_matriz_comparativa(concurso_id: str) -> BytesIO:
    client = get_client()
    postores = client.table("postores").select("*").eq("concurso_id", concurso_id).execute().data
    dictamenes = (
        client.table("dictamenes")
        .select("*")
        .eq("concurso_id", concurso_id)
        .eq("agente", "coordinador")
        .execute()
        .data
    )
    dictamenes_por_postor = {d["postor_id"]: d for d in dictamenes}

    filas = []
    for p in postores:
        d = dictamenes_por_postor.get(p["id"], {})
        filas.append({
            "RUC": p["ruc"],
            "Razón Social": p["razon_social"],
            "Estado": p["estado"],
            "Veredicto": d.get("veredicto", "Pendiente"),
            "Puntaje": d.get("puntaje", None),
        })

    df = pd.DataFrame(filas)
    if not df.empty:
        df = df.sort_values("Puntaje", ascending=False, na_position="last")

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Matriz Comparativa")
    buffer.seek(0)
    return buffer
