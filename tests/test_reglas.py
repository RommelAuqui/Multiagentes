import pytest

from agents.reglas import aplicar_revision, calcular_resultado, validar_matriz


def _fila(etapa, veredicto, puntaje=None, maximo=None, obligatorio=True, **comite):
    return {"id": f"{etapa}-{veredicto}-{puntaje}", "criterio_descripcion": f"criterio {etapa}", "etapa": etapa,
            "veredicto": veredicto, "puntaje": puntaje, "puntaje_maximo": maximo, "obligatorio": obligatorio, **comite}


FACTORES = [_fila("evaluacion", "Evaluado", 50, 60), _fila("evaluacion", "Evaluado", 35, 40)]


@pytest.mark.parametrize("filas, minimo, esperado", [
    ([_fila("admision", "Cumple"), _fila("calificacion", "Cumple"), *FACTORES], 80, "Califica"),
    ([_fila("admision", "No Cumple"), _fila("calificacion", "No Cumple"), *FACTORES], 80, "No admitido"),
    ([_fila("admision", "Cumple"), _fila("calificacion", "No Cumple"), *FACTORES], 80, "No califica"),
    ([_fila("admision", "Cumple"), _fila("calificacion", "Requiere revisión"), *FACTORES], 80, "Requiere revisión"),
    ([_fila("admision", "Cumple"), *FACTORES], 90, "Puntaje insuficiente"),
    # Un requisito no obligatorio no descalifica.
    ([_fila("calificacion", "No Cumple", obligatorio=False), *FACTORES], None, "Califica"),
])
def test_resultado_segun_las_reglas_de_las_bases(filas, minimo, esperado):
    resultado = calcular_resultado(filas, minimo)
    assert resultado["veredicto"] == esperado
    assert (resultado["puntaje"], resultado["puntaje_maximo"]) == (85, 100)


def test_la_decision_del_comite_prevalece_sobre_la_ia():
    filas = [
        _fila("calificacion", "Requiere revisión", veredicto_comite="Cumple"),
        _fila("evaluacion", "Requiere revisión", 20, 60, veredicto_comite="Evaluado", puntaje_comite=45),
    ]
    resultado = calcular_resultado(filas, 40)
    assert resultado["veredicto"] == "Califica" and resultado["puntaje"] == 45


def test_validar_matriz_del_editor():
    criterios, errores = validar_matriz([
        {"etapa": "admision", "tipo": "legal", "descripcion": "Anexo 2", "obligatorio": True},
        {"etapa": "Evaluación", "tipo": None, "descripcion": "Metodología", "puntaje_maximo": 40.0,
         "asignacion_puntaje": "Desarrolla todos los ítems: 40", "acreditacion": float("nan")},
        {"etapa": None, "tipo": None, "descripcion": None},  # fila agregada y dejada vacía
        {"etapa": "evaluacion", "tipo": "tecnico", "descripcion": "Experiencia", "puntaje_maximo": None},
        {"etapa": None, "tipo": "tecnico", "descripcion": "Sin etapa"},
    ])

    assert [(c["etapa"], c["tipo"], c["orden"]) for c in criterios] == [("admision", "legal", 0), ("evaluacion", "tecnico", 1)]
    assert criterios[1]["acreditacion"] is None and criterios[1]["obligatorio"] is False
    assert len(errores) == 2 and "puntaje máximo" in errores[0] and "Fila 5" in errores[1]


def test_revision_exige_justificar_cambios_y_dudas():
    requisito = {**_fila("calificacion", "Cumple"), "id": "r1"}
    dudoso = {**_fila("admision", "Requiere revisión"), "id": "r2"}
    factor = {**_fila("evaluacion", "Evaluado", 30, 60), "id": "f1"}

    cambios, errores = aplicar_revision(
        [requisito, dudoso, factor],
        {"r1": {"veredicto": "No Cumple"}, "r2": {"veredicto": "Cumple"}, "f1": {"puntaje": 30}},
        revisor="",
    )

    assert len(errores) == 3  # falta el revisor y las justificaciones de r1 (cambio) y r2 (duda)
    assert [c["id"] for c in cambios] == ["f1"]


def test_revision_valida():
    factor = {**_fila("evaluacion", "Evaluado", 30, 60), "id": "f1"}
    cambios, errores = aplicar_revision(
        [factor], {"f1": {"puntaje": 99, "justificacion": "Se acreditan 4 servicios"}}, revisor="Ing. Ana Torres",
    )
    assert errores == []
    assert cambios == [{"id": "f1", "veredicto_comite": "Evaluado", "puntaje_comite": 60.0,
                        "justificacion_comite": "Se acreditan 4 servicios"}]
