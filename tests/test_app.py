import pytest
from streamlit.testing.v1 import AppTest

import views.comite as comite
import views.postor as postor
from agents.extractor import MatrizExtraida
from rag.ingest import DocumentoPreparado
from rag.pdf_extract import ResultadoExtraccion

PDF = ("documento.pdf", b"%PDF-1.4 de prueba", "application/pdf")
CRITERIO_ADMISION = {"etapa": "admision", "tipo": "legal", "descripcion": "Declaración jurada (Anexo 2)",
                     "acreditacion": "Anexo 2", "referencia": "Cap. II", "obligatorio": True,
                     "puntaje_maximo": None, "asignacion_puntaje": None}
CRITERIO_FACTOR = {"etapa": "evaluacion", "tipo": "tecnico", "descripcion": "Experiencia del postor",
                   "acreditacion": "Contratos y conformidades", "referencia": "Cap. IV", "obligatorio": False,
                   "puntaje_maximo": 60, "asignacion_puntaje": "M >= 3 veces: 60 puntos"}


def _documento(texto: str = "Experiencia de 10 años en supervisión de obras") -> DocumentoPreparado:
    extraccion = ResultadoExtraccion(paginas=[{"pagina": 1, "texto": texto, "ia": False}])
    return DocumentoPreparado(extraccion, [{"pagina": 1, "contenido": texto, "embedding": [0.1, 0.2]}])


def _boton(at: AppTest, etiqueta: str):
    return next(b for b in at.button if b.label == etiqueta)


def _mensajes(elementos) -> list[str]:
    return [e.value for e in elementos]


@pytest.fixture
def concurso(db_falsa):
    return db_falsa.table("concursos").insert({
        "nombre": "Consultoría vial", "descripcion": "Tramo norte", "estado": "abierto",
    }).execute().data[0]


def _registrar_postor(db_falsa, concurso: dict, ruc: str, razon_social: str) -> dict:
    return db_falsa.table("postores").insert({
        "concurso_id": concurso["id"], "ruc": ruc, "razon_social": razon_social, "estado": "recibido",
        "propuesta_pdf_path": f"postores/{ruc}/propuesta.pdf", "cv_pdf_path": f"postores/{ruc}/cv.pdf",
    }).execute().data[0]


# ---------- Portal del Postor ----------

def _portal_postor() -> AppTest:
    at = AppTest.from_file("../app.py", default_timeout=30).run()
    at.sidebar.radio[0].set_value("Postor / Participante").run()
    return at


def _postular(at: AppTest, ruc: str, razon_social: str = "Consultora Andina SAC") -> AppTest:
    at.text_input[0].input(ruc)
    at.text_input[1].input(razon_social)
    at.file_uploader[0].set_value(PDF)
    at.file_uploader[1].set_value(PDF)
    return _boton(at, "Enviar Postulación").click().run()


def test_postulacion_exitosa(db_falsa, concurso, monkeypatch):
    monkeypatch.setattr(postor, "preparar_documento", lambda _contenido, _contexto: _documento())

    at = _postular(_portal_postor(), " 20131312955 ")

    assert not at.exception
    assert any("Postulación registrada" in m for m in _mensajes(at.success))
    [registrado] = db_falsa.filas("postores")
    assert registrado["ruc"] == "20131312955"
    assert {f["origen"] for f in db_falsa.filas("documentos_chunks")} == {"propuesta", "cv"}
    assert sorted(db_falsa.archivos) == sorted([registrado["propuesta_pdf_path"], registrado["cv_pdf_path"]])


def test_ruc_invalido_no_registra_ni_procesa(db_falsa, concurso, monkeypatch):
    monkeypatch.setattr(postor, "preparar_documento", lambda _contenido, _contexto: pytest.fail("no debe procesar"))

    at = _postular(_portal_postor(), "20131312954")

    assert any("RUC no es válido" in m for m in _mensajes(at.error))
    assert db_falsa.filas("postores") == []


def test_ruc_duplicado_en_el_mismo_concurso(db_falsa, concurso, monkeypatch):
    _registrar_postor(db_falsa, concurso, "20131312955", "Primera SAC")
    monkeypatch.setattr(postor, "preparar_documento", lambda _contenido, _contexto: pytest.fail("no debe procesar"))

    at = _postular(_portal_postor(), "20131312955")

    assert any("Ya existe una postulación" in m for m in _mensajes(at.error))
    assert len(db_falsa.filas("postores")) == 1


def test_si_falla_el_procesamiento_no_queda_nada_registrado(db_falsa, concurso, monkeypatch):
    def fallar(_contenido, _contexto):
        raise RuntimeError("Gemini no respondió")
    monkeypatch.setattr(postor, "preparar_documento", fallar)

    at = _postular(_portal_postor(), "20131312955")

    assert any("no se registró" in m for m in _mensajes(at.error))
    assert db_falsa.filas("postores") == [] and db_falsa.archivos == {}


def test_si_falla_el_guardado_se_revierte_la_postulacion(db_falsa, concurso, monkeypatch):
    monkeypatch.setattr(postor, "preparar_documento", lambda _contenido, _contexto: _documento())

    def fallar_fragmentos(*_):
        raise RuntimeError("Supabase caído")
    monkeypatch.setattr(postor, "guardar_fragmentos", fallar_fragmentos)

    at = _postular(_portal_postor(), "20131312955")

    assert any("No se guardó nada" in m for m in _mensajes(at.error))
    assert db_falsa.filas("postores") == [] and db_falsa.archivos == {}


def test_concurso_cerrado_no_recibe_postulaciones(db_falsa, concurso):
    db_falsa.table("concursos").update({"estado": "cerrado"}).eq("id", concurso["id"]).execute()

    at = _portal_postor()

    assert any("No hay concursos abiertos" in m for m in _mensajes(at.info))


# ---------- Portal del Comité ----------

def _portal_comite() -> AppTest:
    at = AppTest.from_file("../app.py", default_timeout=30)
    at.session_state["admin_autenticado"] = True
    return at.run()


def test_contrasena_del_comite(db_falsa):
    at = AppTest.from_file("../app.py", default_timeout=30).run()

    at.text_input[0].input("incorrecta")
    _boton(at, "Ingresar").click().run()
    assert any("Contraseña incorrecta" in m for m in _mensajes(at.error))

    at.text_input[0].input("clave-comite")
    _boton(at, "Ingresar").click().run()
    assert at.session_state["admin_autenticado"]


def _stub_extraccion(monkeypatch, criterios, puntaje_minimo=None):
    monkeypatch.setattr(comite, "extraer_paginas", lambda _contenido, _contexto: _documento("Bases").extraccion)
    monkeypatch.setattr(comite, "extraer_criterios", lambda _texto, _contexto: MatrizExtraida(criterios, puntaje_minimo))


def _crear(at: AppTest, nombre: str = "Supervisión de obra") -> AppTest:
    at.text_input[0].input(nombre)
    at.file_uploader[0].set_value(PDF)
    return _boton(at, "Crear convocatoria").click().run()


def test_crear_convocatoria_queda_en_revision(db_falsa, monkeypatch):
    _stub_extraccion(monkeypatch, [CRITERIO_ADMISION, CRITERIO_FACTOR], puntaje_minimo=80)

    at = _crear(_portal_comite())

    assert not at.exception
    [creado] = db_falsa.filas("concursos")
    assert creado["estado"] == "borrador" and creado["puntaje_minimo"] == 80
    assert creado["bases_pdf_path"] in db_falsa.archivos
    assert [(c["etapa"], c["orden"]) for c in db_falsa.filas("criterios")] == [("admision", 0), ("evaluacion", 1)]


def test_si_no_se_extraen_criterios_la_convocatoria_queda_para_completar(db_falsa, monkeypatch):
    _stub_extraccion(monkeypatch, [])

    at = _crear(_portal_comite())

    assert any("no encontró criterios" in m for m in _mensajes(at.warning))
    assert db_falsa.filas("concursos")[0]["estado"] == "borrador"


def test_publicar_la_matriz_revisada(db_falsa, monkeypatch):
    _stub_extraccion(monkeypatch, [CRITERIO_ADMISION, CRITERIO_FACTOR])
    at = _crear(_portal_comite())

    at = _portal_comite()
    _boton(at, "📢 Publicar convocatoria").click().run()

    assert db_falsa.filas("concursos")[0]["estado"] == "abierto"
    assert len(db_falsa.filas("criterios")) == 2
    assert any("publicada" in m for m in _mensajes(at.success))


def test_no_se_publica_un_factor_sin_puntaje(db_falsa):
    concurso = db_falsa.table("concursos").insert({"nombre": "Borrador", "estado": "borrador"}).execute().data[0]
    db_falsa.table("criterios").insert({**CRITERIO_FACTOR, "puntaje_maximo": None, "concurso_id": concurso["id"]}).execute()

    at = _portal_comite()
    _boton(at, "📢 Publicar convocatoria").click().run()

    assert any("necesita un puntaje máximo" in m for m in _mensajes(at.error))
    assert db_falsa.filas("concursos")[0]["estado"] == "borrador"


def test_cerrar_y_reabrir_postulaciones(db_falsa, concurso):
    at = _portal_comite()

    _boton(at, "🔒 Cerrar postulaciones").click().run()
    assert db_falsa.filas("concursos")[0]["estado"] == "cerrado"

    _boton(at, "🔓 Reabrir postulaciones").click().run()
    assert db_falsa.filas("concursos")[0]["estado"] == "abierto"


def test_eliminar_convocatoria_requiere_confirmacion(db_falsa, concurso):
    registrado = _registrar_postor(db_falsa, concurso, "20131312955", "Consultora SAC")
    db_falsa.archivos.update({registrado["propuesta_pdf_path"]: b"pdf", registrado["cv_pdf_path"]: b"pdf"})

    at = _portal_comite()
    assert _boton(at, "🗑️ Eliminar convocatoria").disabled

    next(c for c in at.checkbox if c.label.startswith("Entiendo")).check().run()
    _boton(at, "🗑️ Eliminar convocatoria").click().run()

    assert db_falsa.filas("concursos") == [] and db_falsa.filas("postores") == []
    assert db_falsa.archivos == {}
    assert any("eliminada" in m for m in _mensajes(at.success))


def test_evaluar_pendientes_muestra_errores_individuales(db_falsa, concurso, monkeypatch):
    primero = _registrar_postor(db_falsa, concurso, "20131312955", "Primera SAC")
    segundo = _registrar_postor(db_falsa, concurso, "10123456781", "Segunda EIRL")
    evaluados = []

    def evaluar(postor_id):
        evaluados.append(postor_id)
        if postor_id == segundo["id"]:
            raise RuntimeError("cuota de Gemini agotada")
    monkeypatch.setattr(comite, "evaluar_postor", evaluar)

    at = _portal_comite()
    _boton(at, "Evaluar los 2 postores pendientes").click().run()

    assert evaluados == [primero["id"], segundo["id"]]
    assert any("Segunda EIRL" in m and "cuota" in m for m in _mensajes(at.error))


def _evaluacion_de_la_ia(db_falsa, concurso, postor):
    filas = db_falsa.table("dictamenes").insert([
        {"postor_id": postor["id"], "concurso_id": concurso["id"], "agente": "legal", "etapa": "admision",
         "obligatorio": True, "criterio_descripcion": "Declaración jurada (Anexo 2)", "veredicto": "Requiere revisión",
         "justificacion": "La firma es ilegible.", "citas": [{"documento": "propuesta", "pagina": 2, "extracto": "Anexo 2"}]},
        {"postor_id": postor["id"], "concurso_id": concurso["id"], "agente": "tecnico", "etapa": "evaluacion",
         "obligatorio": False, "criterio_descripcion": "Experiencia del postor", "veredicto": "Evaluado",
         "puntaje": 40, "puntaje_maximo": 60, "justificacion": "Acredita 2 servicios.", "citas": []},
        {"postor_id": postor["id"], "concurso_id": concurso["id"], "agente": "coordinador",
         "veredicto": "Requiere revisión", "puntaje": 40, "puntaje_maximo": 60, "justificacion": "Falta verificar la firma."},
    ]).execute().data
    return filas


def test_revision_del_comite_corrige_y_firma_el_dictamen(db_falsa, concurso):
    postor = _registrar_postor(db_falsa, concurso, "20131312955", "Consultora SAC")
    admision, factor, final = _evaluacion_de_la_ia(db_falsa, concurso, postor)

    at = _portal_comite()
    assert any("Requiere revisión" in m.value for m in at.markdown)

    at.selectbox(key=f"veredicto_{admision['id']}").select("Cumple")
    at.number_input(key=f"puntaje_{factor['id']}").set_value(50.0)
    at.text_input(key=f"revisor_{postor['id']}").input("Ing. Ana Torres")
    _boton(at, "Guardar revisión del comité").click().run()

    # Sin justificar la duda resuelta ni el cambio de puntaje, no se guarda.
    assert len(_mensajes(at.error)) == 2
    assert db_falsa.filas("dictamenes")[2].get("revisado_en") is None

    at.text_input(key=f"justificacion_{admision['id']}").input("Se verificó la firma en el original.")
    at.text_input(key=f"justificacion_{factor['id']}").input("Se acredita un tercer servicio en la página 7.")
    _boton(at, "Guardar revisión del comité").click().run()

    filas = {f["id"]: f for f in db_falsa.filas("dictamenes")}
    assert filas[admision["id"]]["veredicto_comite"] == "Cumple"
    assert filas[factor["id"]]["puntaje_comite"] == 50
    assert (filas[final["id"]]["veredicto_comite"], filas[final["id"]]["puntaje_comite"]) == ("Califica", 50)
    assert filas[final["id"]]["revisado_por"] == "Ing. Ana Torres"
    assert db_falsa.filas("postores")[0]["estado"] == "revisado"
    # Ya revisado: la IA no puede reemplazar la decisión del comité.
    assert not [b for b in at.button if b.label == "Reevaluar"]
