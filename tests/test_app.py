import pytest
from streamlit.testing.v1 import AppTest

import views.comite as comite
import views.postor as postor
from rag.ingest import DocumentoPreparado
from rag.pdf_extract import ResultadoExtraccion

PDF = ("documento.pdf", b"%PDF-1.4 de prueba", "application/pdf")


def _documento(texto: str = "Experiencia de 10 años en supervisión de obras") -> DocumentoPreparado:
    extraccion = ResultadoExtraccion(paginas=[{"pagina": 1, "texto": texto, "ocr": False}])
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
    monkeypatch.setattr(postor, "preparar_documento", lambda _contenido: _documento())

    at = _postular(_portal_postor(), " 20131312955 ")

    assert not at.exception
    assert any("Postulación registrada" in m for m in _mensajes(at.success))
    [registrado] = db_falsa.filas("postores")
    assert registrado["ruc"] == "20131312955"
    assert {f["origen"] for f in db_falsa.filas("documentos_chunks")} == {"propuesta", "cv"}
    assert sorted(db_falsa.archivos) == sorted([registrado["propuesta_pdf_path"], registrado["cv_pdf_path"]])


def test_ruc_invalido_no_registra_ni_procesa(db_falsa, concurso, monkeypatch):
    monkeypatch.setattr(postor, "preparar_documento", lambda _contenido: pytest.fail("no debe procesar"))

    at = _postular(_portal_postor(), "20131312954")

    assert any("RUC no es válido" in m for m in _mensajes(at.error))
    assert db_falsa.filas("postores") == []


def test_ruc_duplicado_en_el_mismo_concurso(db_falsa, concurso, monkeypatch):
    _registrar_postor(db_falsa, concurso, "20131312955", "Primera SAC")
    monkeypatch.setattr(postor, "preparar_documento", lambda _contenido: pytest.fail("no debe procesar"))

    at = _postular(_portal_postor(), "20131312955")

    assert any("Ya existe una postulación" in m for m in _mensajes(at.error))
    assert len(db_falsa.filas("postores")) == 1


def test_si_falla_el_procesamiento_no_queda_nada_registrado(db_falsa, concurso, monkeypatch):
    def fallar(_contenido):
        raise RuntimeError("Gemini no respondió")
    monkeypatch.setattr(postor, "preparar_documento", fallar)

    at = _postular(_portal_postor(), "20131312955")

    assert any("no se registró" in m for m in _mensajes(at.error))
    assert db_falsa.filas("postores") == [] and db_falsa.archivos == {}


def test_si_falla_el_guardado_se_revierte_la_postulacion(db_falsa, concurso, monkeypatch):
    monkeypatch.setattr(postor, "preparar_documento", lambda _contenido: _documento())

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


def test_crear_convocatoria(db_falsa, monkeypatch):
    monkeypatch.setattr(comite, "extraer_paginas", lambda _contenido: _documento("Bases").extraccion)
    monkeypatch.setattr(comite, "extraer_criterios", lambda _texto, _contexto: [
        {"tipo": "legal", "descripcion": "Declaración jurada", "referencia": "Pág. 3", "obligatorio": True},
    ])

    at = _portal_comite()
    at.text_input[0].input("Supervisión de obra")
    at.file_uploader[0].set_value(PDF)
    _boton(at, "Crear convocatoria").click().run()

    assert not at.exception
    [creado] = db_falsa.filas("concursos")
    assert creado["bases_pdf_path"] in db_falsa.archivos
    assert [c["concurso_id"] for c in db_falsa.filas("criterios")] == [creado["id"]]


def test_convocatoria_sin_criterios_no_se_crea(db_falsa, monkeypatch):
    monkeypatch.setattr(comite, "extraer_paginas", lambda _contenido: _documento("Bases").extraccion)
    monkeypatch.setattr(comite, "extraer_criterios", lambda _texto, _contexto: [])

    at = _portal_comite()
    at.text_input[0].input("Supervisión de obra")
    at.file_uploader[0].set_value(PDF)
    _boton(at, "Crear convocatoria").click().run()

    assert any("no encontró criterios" in m for m in _mensajes(at.error))
    assert db_falsa.filas("concursos") == [] and db_falsa.archivos == {}


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
