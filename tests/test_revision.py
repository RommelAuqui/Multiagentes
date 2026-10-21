from datetime import date

import pytest

from revision import catalogo
from revision.extraccion import normalizar_fecha, normalizar_ficha, normalizar_monto
from revision.reglas import CUMPLE, FALLA, NO_VERIFICADO, Documento, dias_habiles, verificar


def _bases(**datos) -> Documento:
    paginas = [
        {"pagina": 1, "texto": "CAPÍTULO I GENERALIDADES\nCAPÍTULO II DEL PROCEDIMIENTO DE SELECCIÓN"},
        {"pagina": 2, "texto": "CAPÍTULO III REQUERIMIENTO\nCAPÍTULO IV EVALUACIÓN DE OFERTAS"},
        {"pagina": 3, "texto": "CAPÍTULO V PROFORMA DEL CONTRATO\nEL CONTRATISTA [NOMBRE DEL CONTRATISTA]"},
    ]
    base = {"cuantia": 480000.0, "fuente_financiamiento": "Recursos determinados",
            "fecha_aprobacion_expediente": "2026-09-28", "difusion_requerimiento": False, "elevacion_oece": True,
            "plazo_dias": 210.0, "monto_experiencia_postor": 480000.0, "puntaje_minimo": 70.0, "puntaje_total": 100.0,
            "modalidad_pago": "Suma alzada.",
            "factores": [{"nombre": "Experiencia", "puntaje": 50.0}, {"nombre": "Adicional", "puntaje": 30.0},
                         {"nombre": "Metodología", "puntaje": 20.0}],
            "cronograma": {"convocatoria": "2026-10-05", "consultas_fin": "2026-10-16", "integracion": "2026-10-23",
                           "presentacion_ofertas": "2026-11-09"}}
    return Documento("bases", "Bases.pdf", paginas, {**base, **datos})


def _expediente(**cambios) -> dict[str, Documento]:
    docs = {
        "requerimiento": Documento("requerimiento", "Requerimiento.pdf", datos={"plazo_dias": 210.0}),
        "certificacion": Documento("certificacion", "CCP.pdf",
                                   datos={"monto": 480000.0, "fuente_financiamiento": "RECURSOS DETERMINADOS"}),
        "aprobacion_expediente": Documento("aprobacion_expediente", "Aprobación.pdf",
                                           datos={"fecha_aprobacion": "2026-09-28", "cuantia": 480000.0}),
        "estrategia": Documento("estrategia", "Estrategia.pdf", datos={"cuantia": 480000.0, "modalidad_pago": "Suma alzada"}),
        "interaccion_mercado": Documento("interaccion_mercado", "Mercado.pdf", datos={"difusion_requerimiento": False}),
        "designacion_evaluadores": Documento("designacion_evaluadores", "Designación.pdf"),
    }
    for tipo, datos in cambios.items():
        docs[tipo].datos.update(datos)
    return docs


def _por_codigo(resultados):
    return {r.codigo: r for r in resultados}


def test_el_catalogo_es_coherente():
    codigos = [v.codigo for v in catalogo.VERIFICACIONES]
    assert len(codigos) == len(set(codigos)) == 39
    for v in catalogo.VERIFICACIONES:
        assert v.categoria in catalogo.CATEGORIAS and v.gravedad in catalogo.GRAVEDADES
        assert set(v.documentos) <= set(catalogo.TIPOS_DOCUMENTO)
        assert set(v.rondas) <= {catalogo.RONDA_A, catalogo.RONDA_B}
    for ronda, obligatorios in catalogo.OBLIGATORIOS.items():
        assert set(obligatorios) <= set(catalogo.DOCUMENTOS_DE_RONDA[ronda])


def test_un_expediente_coherente_cumple_todas_las_reglas_de_la_ronda_a():
    resultados = verificar("A", {**_expediente(), "bases": _bases()})

    # Cada regla fija de la ronda tiene su resultado (verificar() también lo asegura).
    reglas = {v.codigo for v in catalogo.de_ronda("A") if v.metodo == catalogo.REGLA}
    assert {r.codigo for r in resultados} == reglas
    fallas = [(r.codigo, r.descripcion) for r in resultados if r.estado != CUMPLE]
    assert fallas == []


@pytest.mark.parametrize(("cambio", "codigo", "texto"), [
    ({"certificacion": {"monto": 400000.0}}, "COH-02", "faltan S/ 80 000.00"),
    ({"aprobacion_expediente": {"cuantia": 500000.0}}, "COH-01", "indica S/ 500 000.00"),
    ({"certificacion": {"fuente_financiamiento": "Donaciones y transferencias"}}, "COH-03", "Donaciones"),
    ({"aprobacion_expediente": {"fecha_aprobacion": "2026-09-30"}}, "COH-04", "2026-09-30"),
    ({"requerimiento": {"plazo_dias": 180.0}}, "COH-08", "180 días"),
    ({"estrategia": {"modalidad_pago": "Precios unitarios"}}, "COH-09", "«Precios unitarios»"),
    ({"interaccion_mercado": {"difusion_requerimiento": True}}, "COH-10", "formato de interacción"),
])
def test_detecta_las_incoherencias_con_el_expediente(cambio, codigo, texto):
    resultado = _por_codigo(verificar("A", {**_expediente(**cambio), "bases": _bases()}))[codigo]
    assert resultado.estado == FALLA and texto in resultado.descripcion
    assert {c["documento"] for c in resultado.citas} >= {"Bases.pdf"}


@pytest.mark.parametrize(("datos", "codigo", "texto"), [
    ({"factores": [{"nombre": "Experiencia", "puntaje": 60.0}, {"nombre": "Metodología", "puntaje": 30.0}]},
     "FOR-05", "suman 90"),
    ({"puntaje_minimo": None}, "FOR-06", "puntaje técnico mínimo"),
    ({"cronograma": {"convocatoria": "2026-10-05", "consultas_fin": "2026-10-09"}}, "FOR-07", "4 días hábiles"),
    ({"monto_experiencia_postor": 1500000.0}, "PRO-01", "3.12 veces"),
    ({"factores": [{"nombre": "Experiencia", "puntaje": 80.0}, {"nombre": "Metodología", "puntaje": 20.0}]},
     "PRO-03", "«Experiencia» (80 puntos)"),
    ({"difusion_requerimiento": False, "elevacion_oece": False}, "COH-10", "solo se puede omitir la elevación"),
    ({"cui": "2561903"}, "EXP-07", "CUI 2561903"),
])
def test_detecta_las_fallas_propias_de_las_bases(datos, codigo, texto):
    resultado = _por_codigo(verificar("A", {**_expediente(), "bases": _bases(**datos)}))[codigo]
    assert resultado.estado == FALLA and texto in resultado.descripcion


def test_revisa_el_texto_de_las_bases():
    bases = _bases()
    bases.paginas = [
        {"pagina": 1, "texto": "SIMBOLOGÍA UTILIZADA: [ABC] es una indicación. Importante para la entidad contratante"},
        {"pagina": 2, "texto": "CAPÍTULO I GENERALIDADES. La cuantía asciende a [INDICAR MONTO]."},
        {"pagina": 3, "texto": "Importante para la entidad contratante: esta nota debe ser eliminada."},
        {"pagina": 4, "texto": "Entidad: [GOBIERNO REGIONAL DE LIMA]. D. MEJORA [...] puntos / NO CORRESPONDE"},
        {"pagina": 5, "texto": "CAPÍTULO V PROFORMA DEL CONTRATO: [NOMBRE DEL CONTRATISTA]"},
    ]
    resultados = _por_codigo(verificar("A", {**_expediente(), "bases": bases}))

    # La simbología, los valores ya completados, los factores que no corresponden y la proforma no cuentan.
    assert [c["pagina"] for c in resultados["FOR-02"].citas] == [2]
    assert [c["pagina"] for c in resultados["FOR-03"].citas] == [3]
    assert resultados["FOR-04"].estado == FALLA
    assert "Cap. III, requerimiento" in resultados["FOR-04"].descripcion


def test_sin_documento_la_verificacion_queda_como_no_verificada():
    docs = _expediente()
    del docs["certificacion"], docs["estrategia"]
    resultados = _por_codigo(verificar("A", {**docs, "bases": _bases()}))

    assert resultados["EXP-02"].estado == FALLA and resultados["EXP-04"].estado == FALLA
    assert resultados["COH-02"].estado == NO_VERIFICADO and "falta Certificación" in resultados["COH-02"].descripcion
    # La cuantía aún se puede comparar con la aprobación del expediente.
    assert resultados["COH-01"].estado == CUMPLE


def test_sin_bases_no_se_verifica_nada_de_las_bases():
    resultados = _por_codigo(verificar("A", _expediente()))
    assert resultados["FOR-05"].estado == NO_VERIFICADO and resultados["EXP-01"].estado == CUMPLE


def test_ronda_b_revisa_las_bases_integradas_y_el_pliego():
    integradas = _bases(cronograma={"integracion": "2026-10-23", "presentacion_ofertas": "2026-10-28"})
    integradas.tipo = "bases_integradas"
    pliego = Documento("pliego", "Pliego.pdf", datos={"consultas": [
        {"numero": "1", "tipo": "consulta", "tema": "Plazo", "tiene_respuesta": True},
        {"numero": "2", "tipo": "observación", "tema": "Experiencia", "tiene_respuesta": False},
    ]})
    resultados = verificar("B", {**_expediente(), "bases_integradas": integradas, "pliego": pliego})
    por_codigo = _por_codigo(resultados)

    assert "EXP-01" not in por_codigo  # la completitud del expediente se revisa en la ronda A
    assert por_codigo["FOR-08"].estado == FALLA and "3 días hábiles" in por_codigo["FOR-08"].descripcion
    falla = next(r for r in resultados if r.codigo == "ABS-01" and r.estado == FALLA)
    assert falla.clave == "2" and "observación N.° 2 (Experiencia)" in falla.descripcion


def test_dias_habiles_no_cuenta_fines_de_semana():
    # Del lunes 5 al viernes 16 de octubre de 2026: 9 días hábiles (no se cuenta el día de la convocatoria).
    assert dias_habiles(date(2026, 10, 5), date(2026, 10, 16)) == 9
    assert dias_habiles(date(2026, 10, 9), date(2026, 10, 12)) == 1


@pytest.mark.parametrize(("valor", "esperado"), [
    ("S/ 710,071.86", 710071.86), ("710 071,86", 710071.86), ("S/ 1 000 000,00", 1000000.0),
    ("480,000", 480000.0), ("480.000", 480000.0), (480000, 480000.0), ("1.5", 1.5), (None, None), ("sin dato", None),
])
def test_normaliza_montos(valor, esperado):
    assert normalizar_monto(valor) == esperado


def test_normaliza_fechas_y_fichas():
    assert normalizar_fecha("23/03/2026") == "2026-03-23" and normalizar_fecha("2026-3-5") == "2026-03-05"
    assert normalizar_fecha("31/02/2026") is None
    ficha = normalizar_ficha({"cuantia": "S/ 710,071.86", "difusion_requerimiento": "No", "elevacion_oece": "aplica",
                              "cronograma": {"convocatoria": "05/10/2026"},
                              "factores": [{"nombre": "A", "puntaje": "55"}, "basura"],
                              "consultas": [{"numero": 1, "tiene_respuesta": "sí", "modifica_bases": "no"}]})
    assert ficha["cuantia"] == 710071.86 and ficha["difusion_requerimiento"] is False and ficha["elevacion_oece"] is True
    assert ficha["cronograma"] == {"convocatoria": "2026-10-05"}
    assert ficha["factores"] == [{"nombre": "A", "puntaje": 55.0}]
    assert ficha["consultas"][0]["tiene_respuesta"] is True and ficha["consultas"][0]["modifica_bases"] is False
