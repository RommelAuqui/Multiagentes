import pytest

import agents.herramientas as herramientas
from agents.herramientas import ContextoEvaluacion, calcular_experiencia, herramientas_de_evaluacion, sumar_montos

POSTOR = {"id": "P1", "ruc": "20131312955", "razon_social": "Consultora SAC", "archivos": [
    {"nombre": "Anexo 15 - Personal clave.pdf", "path": "x/01.pdf", "paginas": 4},
    {"nombre": "Constancias.pdf", "path": "x/02.pdf", "paginas": 10},
]}


def test_la_experiencia_traslapada_se_cuenta_una_sola_vez():
    resultado = calcular_experiencia([
        {"inicio": "2018-01-01", "fin": "2018-12-31"},
        {"inicio": "2018-07-01", "fin": "2019-06-30"},  # 6 meses en paralelo con el anterior
        {"inicio": "2021-03", "fin": "2021-04"},       # sin días: meses completos
    ])
    assert resultado["meses"] == 20  # 18 meses (ene 2018 - jun 2019) + 2 meses (mar - abr 2021)
    assert resultado["anios_meses_dias"] == "1 años, 8 meses y 0 días"
    assert resultado["dias"] == 365 + 181 + 61
    assert resultado["dias_traslapados_descontados"] == 184
    assert resultado["periodos_unidos"] == [
        {"inicio": "2018-01-01", "fin": "2019-06-30"}, {"inicio": "2021-03-01", "fin": "2021-04-30"},
    ]


@pytest.mark.parametrize("periodos", [[], [{"inicio": "2020-05-01", "fin": "2020-01-01"}], [{"inicio": "mayo", "fin": "2020"}]])
def test_periodos_invalidos(periodos):
    with pytest.raises(ValueError):
        calcular_experiencia(periodos)


def test_sumar_montos_contra_la_cuantia():
    assert sumar_montos([1250000, 980500.0], referencia=1000000) == {"total": 2230500.0, "veces_referencia": 2.2305}
    assert sumar_montos([10.5, 0.25]) == {"total": 10.75}


def _herramienta(contexto, nombre):
    return next(h for h in herramientas_de_evaluacion(contexto) if h.nombre == nombre)


def test_buscar_en_un_archivo_aunque_el_agente_escriba_distinto_el_nombre(monkeypatch):
    busquedas = []
    monkeypatch.setattr(herramientas, "embed_consultas", lambda textos: [[0.1]])

    def buscar(concurso_id, embedding, postor_id, k, documento):
        busquedas.append(documento)
        return [{"documento": documento, "pagina": 2, "contenido": "Ing. Pérez, 8 años"}]
    monkeypatch.setattr(herramientas, "buscar_fragmentos", buscar)
    contexto = ContextoEvaluacion("C1", POSTOR)
    buscar_evidencia = _herramienta(contexto, "buscar_evidencia")

    resultado = buscar_evidencia.funcion(consulta="jefe de supervisión", documento="anexo 15 - personal clave")

    assert busquedas == ["Anexo 15 - Personal clave.pdf"]
    assert resultado["fragmentos"][0]["documento"] == "Anexo 15 - Personal clave.pdf"
    assert contexto.vistos == [{"documento": "Anexo 15 - Personal clave.pdf", "pagina": 2, "contenido": "Ing. Pérez, 8 años"}]
    assert "en Anexo 15" in buscar_evidencia.resumir({"consulta": "x", "documento": "Anexo 15"}, resultado)

    with pytest.raises(ValueError, match="Documentos de la oferta: Anexo 15"):
        buscar_evidencia.funcion(consulta="x", documento="Otro.pdf")


def test_leer_pagina_reconstruye_la_pagina_en_orden(db_falsa):
    db_falsa.table("documentos_chunks").insert([
        {"postor_id": "P1", "origen": "oferta", "documento": "Constancias.pdf", "pagina": 4, "orden": 9, "contenido": "fin."},
        {"postor_id": "P1", "origen": "oferta", "documento": "Constancias.pdf", "pagina": 4, "orden": 8, "contenido": "Inicio y "},
        {"postor_id": "P1", "origen": "oferta", "documento": "Anexo 15 - Personal clave.pdf", "pagina": 4, "orden": 1, "contenido": "otro"},
    ]).execute()
    contexto = ContextoEvaluacion("C1", POSTOR)

    resultado = _herramienta(contexto, "leer_pagina").funcion(documento="constancias", pagina="4")

    assert resultado == {"documento": "Constancias.pdf", "pagina": 4, "texto": "Inicio y fin."}
    assert len(contexto.vistos) == 2


def test_datos_y_documentos_del_postor():
    contexto = ContextoEvaluacion("C1", POSTOR)
    assert _herramienta(contexto, "datos_del_postor").funcion() == {"ruc": "20131312955", "razon_social": "Consultora SAC"}
    assert [d["nombre"] for d in _herramienta(contexto, "listar_documentos").funcion()["documentos"]] == [
        "Anexo 15 - Personal clave.pdf", "Constancias.pdf",
    ]


@pytest.mark.parametrize("inicio, fin, meses, texto", [
    ("2018-01-01", "2021-06-30", 42, "3 años, 6 meses y 0 días"),   # años completos, sin el error de dividir días
    ("2020-01-15", "2020-03-10", 1.83, "0 años, 1 meses y 25 días"),
    ("2020-02-01", "2020-02-29", 1, "0 años, 1 meses y 0 días"),     # febrero de un año bisiesto
])
def test_meses_calendario(inicio, fin, meses, texto):
    resultado = calcular_experiencia([{"inicio": inicio, "fin": fin}])
    assert (resultado["meses"], resultado["anios_meses_dias"]) == (meses, texto)


def test_los_dias_sueltos_de_varios_periodos_forman_meses():
    # 20 días + 15 días = 35 días = 1 mes y 5 días.
    resultado = calcular_experiencia([{"inicio": "2020-01-01", "fin": "2020-01-20"}, {"inicio": "2021-05-01", "fin": "2021-05-15"}])
    assert resultado["anios_meses_dias"] == "0 años, 1 meses y 5 días" and resultado["meses"] == 1.17
