from io import BytesIO

import pandas as pd


def generar_matriz_comparativa(postores: list[dict], dictamenes_coordinador: list[dict]) -> BytesIO:
    dictamenes_por_postor = {d["postor_id"]: d for d in dictamenes_coordinador}

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
