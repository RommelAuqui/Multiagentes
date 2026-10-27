import pytest

import views.comite as comite
from agents.extractor import MatrizExtraida
from rag.pdf_extract import ResultadoExtraccion
from revision import servicio
from revision.seccion_general import texto_oficial
from tests.test_app import CRITERIO_ADMISION, CRITERIO_FACTOR, _boton, _mensajes, _portal_comite

BASES = {
    "cuantia": 480000.0, "fuente_financiamiento": "Recursos determinados", "fecha_aprobacion_expediente": "2026-09-28",
    "difusion_requerimiento": False, "elevacion_oece": True, "plazo_dias": 210.0, "monto_experiencia_postor": 480000.0,
    "puntaje_minimo": 70.0, "puntaje_total": 100.0, "modalidad_pago": "Suma alzada",
    "factores": [{"nombre": "Experiencia", "puntaje": 60.0}, {"nombre": "Metodología", "puntaje": 40.0}],
    "cronograma": {"convocatoria": "2026-10-05", "consultas_fin": "2026-10-16", "integracion": "2026-10-23",
                   "presentacion_ofertas": "2026-11-09"},
}
FICHAS = {
    "requerimiento": {"plazo_dias": 210.0},
    "certificacion": {"monto": 400000.0, "fuente_financiamiento": "Recursos determinados"},
    "aprobacion_expediente": {"fecha_aprobacion": "2026-09-28", "cuantia": 480000.0},
    "estrategia": {"cuantia": 480000.0, "modalidad_pago": "Suma alzada"},
    "interaccion_mercado": {"difusion_requerimiento": False},
    "designacion_evaluadores": {},
    "bases": BASES,
    "bases_integradas": BASES,
    "pliego": {"consultas": [{"numero": "1", "tipo": "consulta", "tema": "Plazo", "tiene_respuesta": True}]},
}
PAGINAS = [{"pagina": 1, "texto": texto_oficial("consultoria_obra")},
           {"pagina": 2, "texto": "CAPÍTULO I GENERALIDADES CAPÍTULO II DEL PROCEDIMIENTO DE SELECCIÓN "
                                  "CAPÍTULO III REQUERIMIENTO CAPÍTULO IV EVALUACIÓN CAPÍTULO V PROFORMA"}]


@pytest.fixture(autouse=True)
def con_revision(monkeypatch):
    monkeypatch.setattr(comite, "REVISION_BASES", True)
    monkeypatch.setattr(servicio, "extraer_paginas",
                        lambda _contenido, _contexto: ResultadoExtraccion(total_paginas=2, paginas=PAGINAS))
    monkeypatch.setattr(servicio, "extraer_ficha", lambda tipo, _texto, _contexto: dict(FICHAS[tipo]))
    monkeypatch.setattr(servicio.agente_revisor, "revisar", lambda _ronda, _docs, _contexto: [])


def _subir(concurso_id, *tipos):
    for tipo in tipos:
        servicio.subir_documento(concurso_id, tipo, f"{tipo}.pdf", b"%PDF-1.4")


def test_crear_convocatoria_empieza_por_la_revision_de_bases(db_falsa):
    at = _portal_comite()
    at.text_input[0].input("Supervisión de obra")
    _boton(at, "Crear convocatoria").click().run()

    [creado] = db_falsa.filas("concursos")
    assert creado["estado"] == "revision_bases" and creado["ronda_revision"] == "A"
    assert not db_falsa.filas("criterios")  # la matriz se arma recién con las Bases revisadas


def test_revision_de_bases_de_punta_a_punta(db_falsa, monkeypatch):
    concurso = db_falsa.table("concursos").insert({"nombre": "Supervisión", "estado": "revision_bases",
                                                   "ronda_revision": "A"}).execute().data[0]
    at = _portal_comite()
    assert any("Para analizar faltan" in m for m in _mensajes(at.info))

    # Ronda A: el expediente con una certificación que no alcanza.
    _subir(concurso["id"], "requerimiento", "certificacion", "aprobacion_expediente", "estrategia",
           "interaccion_mercado", "designacion_evaluadores", "bases")
    at = _portal_comite()
    _boton(at, "🔎 Analizar").click().run()
    assert any("COH-02" in m and "certificación presupuestal" in m for m in _mensajes(at.markdown))
    assert _boton(at, "Cerrar la ronda A").disabled

    # El comité mantiene el hallazgo, con justificación y firma, desde la pantalla.
    [pendiente] = servicio.hallazgos(concurso["id"], "A")
    at.text_area(key=f"justificacion_{pendiente['id']}").input(
        "Se gestiona la ampliación de la certificación antes de la buena pro.")
    at.text_input(key=f"firma_{pendiente['id']}").input("Ana Pérez")
    _boton(at, "Mantener con esta justificación").click().run()
    [hallazgo] = servicio.hallazgos(concurso["id"], "A")
    assert hallazgo["estado"] == "se_mantiene" and hallazgo["revisado_por"] == "Ana Pérez"
    assert any("1 hallazgo(s) crítico(s)" in m for m in _mensajes(at.warning))

    _boton(at, "Cerrar la ronda A").click().run()
    assert db_falsa.filas("concursos")[0]["ronda_revision"] == "B"

    # Ronda B: pliego y Bases Integradas; al cerrarla se arma la matriz con las Bases revisadas.
    _subir(concurso["id"], "pliego", "bases_integradas")
    monkeypatch.setattr(comite, "extraer_criterios",
                        lambda _texto, _contexto: MatrizExtraida([CRITERIO_ADMISION, CRITERIO_FACTOR], 70))
    at = _portal_comite()
    _boton(at, "🔎 Analizar").click().run()
    # La certificación sigue sin alcanzar: la decisión firmada en la ronda A se conserva, no se pide de nuevo.
    [heredado] = servicio.hallazgos(concurso["id"], "B")
    assert heredado["codigo"] == "COH-02" and heredado["estado"] == "se_mantiene"
    assert heredado["revisado_por"] == "Ana Pérez" and "desde la ronda A" in heredado["justificacion_comite"]
    _boton(at, "Cerrar la revisión y armar la matriz").click().run()

    [actualizado] = db_falsa.filas("concursos")
    assert actualizado["estado"] == "borrador"
    assert actualizado["bases_pdf_path"] == f"expediente/{concurso['id']}/bases_integradas_v1.pdf"
    assert len(db_falsa.filas("criterios")) == 2 and actualizado["puntaje_minimo"] == 70


def test_eliminar_el_concurso_borra_los_documentos_del_expediente(db_falsa):
    concurso = db_falsa.table("concursos").insert({"nombre": "Supervisión", "estado": "revision_bases",
                                                   "ronda_revision": "A"}).execute().data[0]
    _subir(concurso["id"], "requerimiento")
    assert db_falsa.archivos

    at = _portal_comite()
    next(c for c in at.checkbox if c.label.startswith("Entiendo")).check().run()
    _boton(at, "🗑️ Eliminar convocatoria").click().run()

    assert not db_falsa.filas("concursos") and not db_falsa.filas("documentos_expediente")
    assert not db_falsa.archivos


def test_la_revision_rapida_no_basta_para_cerrar_la_ronda(db_falsa, monkeypatch):
    concurso = db_falsa.table("concursos").insert({"nombre": "Supervisión", "estado": "revision_bases",
                                                   "ronda_revision": "A"}).execute().data[0]
    FICHAS_OK = {**FICHAS, "certificacion": {"monto": 480000.0, "fuente_financiamiento": "Recursos determinados"}}
    monkeypatch.setattr(servicio, "extraer_ficha", lambda tipo, _texto, _contexto: dict(FICHAS_OK[tipo]))
    _subir(concurso["id"], "requerimiento", "certificacion", "aprobacion_expediente", "estrategia",
           "interaccion_mercado", "designacion_evaluadores", "bases")

    at = _portal_comite()
    _boton(at, "⚡ Solo reglas fijas").click().run()
    assert any("solo reglas fijas" in m for m in _mensajes(at.success))
    assert _boton(at, "Cerrar la ronda A").disabled
    assert any("falta la revisión con el agente" in m for m in _mensajes(at.caption))

    _boton(at, "🔎 Analizar").click().run()
    assert not _boton(at, "Cerrar la ronda A").disabled


def test_en_la_ronda_b_se_puede_ver_lo_que_paso_en_la_ronda_a(db_falsa):
    concurso = db_falsa.table("concursos").insert({"nombre": "Supervisión", "estado": "revision_bases",
                                                   "ronda_revision": "A"}).execute().data[0]
    _subir(concurso["id"], "requerimiento", "certificacion", "aprobacion_expediente", "estrategia",
           "interaccion_mercado", "designacion_evaluadores", "bases")
    servicio.revisar(concurso["id"], "A")
    db_falsa.table("concursos").update({"ronda_revision": "B"}).eq("id", concurso["id"]).execute()

    at = _portal_comite()
    interruptor = next(t for t in at.toggle if t.label.startswith("Ver la ronda A"))
    assert "1 hallazgo(s)" in interruptor.label
    interruptor.set_value(True).run()

    assert any("COH-02" in m for m in _mensajes(at.markdown))
    assert any("sin respuesta del comité" in m for m in _mensajes(at.caption))
    assert not [b for b in at.button if b.label == "Mantener con esta justificación"]  # solo lectura
