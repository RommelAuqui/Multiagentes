import pandas as pd

from reports.matriz import generar_matriz_comparativa


def test_matriz_ordena_por_puntaje_y_marca_pendientes():
    postores = [
        {"id": "1", "ruc": "20131312955", "razon_social": "A", "estado": "evaluado"},
        {"id": "2", "ruc": "10123456781", "razon_social": "B", "estado": "recibido"},
        {"id": "3", "ruc": "20100000001", "razon_social": "C", "estado": "evaluado"},
    ]
    dictamenes = [
        {"postor_id": "1", "veredicto": "Cumple", "puntaje": 60},
        {"postor_id": "3", "veredicto": "Cumple", "puntaje": 90},
    ]

    df = pd.read_excel(generar_matriz_comparativa(postores, dictamenes), dtype={"RUC": str})

    assert df["Razón Social"].tolist() == ["C", "A", "B"]
    assert df["Veredicto"].tolist() == ["Cumple", "Cumple", "Pendiente"]
