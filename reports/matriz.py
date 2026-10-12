from io import BytesIO

import pandas as pd

from agents.reglas import puntaje_efectivo, veredicto_efectivo


def generar_matriz_comparativa(postores: list[dict], dictamenes_coordinador: list[dict]) -> BytesIO:
    dictamenes_por_postor = {d["postor_id"]: d for d in dictamenes_coordinador}

    filas = []
    for p in postores:
        d = dictamenes_por_postor.get(p["id"])
        filas.append({
            "RUC": p["ruc"],
            "Razón Social": p["razon_social"],
            "Estado": p["estado"],
            "Resultado": veredicto_efectivo(d) if d else "Pendiente",
            "Puntaje técnico": puntaje_efectivo(d) if d else None,
            "Puntaje máximo": d.get("puntaje_maximo") if d else None,
            "Revisado por el comité": "Sí" if d and d.get("revisado_en") else "No",
        })

    df = pd.DataFrame(filas)
    if not df.empty:
        df = df.sort_values("Puntaje técnico", ascending=False, na_position="last")

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Matriz Comparativa")
    buffer.seek(0)
    return buffer
