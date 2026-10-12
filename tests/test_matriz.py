import pandas as pd

from reports.matriz import generar_matriz_comparativa


def test_matriz_usa_la_decision_del_comite_y_ordena_por_puntaje():
    postores = [
        {"id": "1", "ruc": "20131312955", "razon_social": "A", "estado": "evaluado"},
        {"id": "2", "ruc": "10123456781", "razon_social": "B", "estado": "recibido"},
        {"id": "3", "ruc": "20100000001", "razon_social": "C", "estado": "revisado"},
    ]
    dictamenes = [
        {"postor_id": "1", "veredicto": "Califica", "puntaje": 60, "puntaje_maximo": 100},
        {"postor_id": "3", "veredicto": "Requiere revisión", "puntaje": 70, "puntaje_maximo": 100,
         "veredicto_comite": "Califica", "puntaje_comite": 90, "revisado_en": "2026-10-12T10:00:00+00:00"},
    ]

    df = pd.read_excel(generar_matriz_comparativa(postores, dictamenes), dtype={"RUC": str})

    assert df["Razón Social"].tolist() == ["C", "A", "B"]
    assert df["Resultado"].tolist() == ["Califica", "Califica", "Pendiente"]
    assert df["Puntaje técnico"].tolist()[:2] == [90, 60]
    assert df["Revisado por el comité"].tolist() == ["Sí", "No", "No"]
