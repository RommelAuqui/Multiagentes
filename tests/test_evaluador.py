import agents.agente as agente
import agents.evaluador as evaluador
import agents.herramientas as herramientas
from tests.gemini_falso import GeminiGuionado, respuesta_con_llamadas

POSTOR = {"id": "P1", "ruc": "20131312955", "razon_social": "Consultora SAC", "archivos": [
    {"nombre": "Anexos.pdf", "path": "x/01.pdf", "paginas": 3},
    {"nombre": "CV Jefe de supervision.pdf", "path": "x/02.pdf", "paginas": 2},
]}
CRITERIO = {"id": "K1", "etapa": "calificacion", "tipo": "tecnico", "obligatorio": True,
            "descripcion": "Experiencia del jefe de supervisión: mínimo 36 meses", "acreditacion": "Constancias"}
INICIALES = [{"origen": "oferta", "documento": "Anexos.pdf", "pagina": 1, "contenido": "Declaración jurada..."}]
HALLAZGO = {"origen": "oferta", "documento": "CV Jefe de supervision.pdf", "pagina": 2,
            "contenido": "Jefe de supervisión, Provías: 01/2018 a 12/2019; Gobierno Regional: 06/2019 a 06/2021"}


def test_el_agente_investiga_calcula_y_cita_lo_que_encontro(monkeypatch, db_falsa):
    busquedas = []
    monkeypatch.setattr(herramientas, "embed_consultas", lambda textos: [[0.2]])

    def buscar(concurso_id, query_embedding, postor_id, k, documento=None):
        busquedas.append(documento)
        return [HALLAZGO] if documento else INICIALES
    monkeypatch.setattr(evaluador, "buscar_fragmentos", buscar)
    monkeypatch.setattr(herramientas, "buscar_fragmentos", buscar)

    falso = GeminiGuionado([
        respuesta_con_llamadas(("buscar_evidencia", {"consulta": "jefe de supervisión", "documento": "CV Jefe de supervision"})),
        respuesta_con_llamadas(("calcular_experiencia", {"periodos": [
            {"inicio": "2018-01", "fin": "2019-12"}, {"inicio": "2019-06", "fin": "2021-06"}]})),
        respuesta_con_llamadas(("emitir_evaluacion", {
            "veredicto": "Cumple", "justificacion": "Acredita 42 meses sin traslapes.",
            "citas": [{"documento": "CV Jefe de supervision.pdf", "pagina": 2, "extracto": "Provías 01/2018"},
                      {"documento": "Inventado.pdf", "pagina": 9}],
        })),
    ])
    monkeypatch.setattr(agente, "obtener_cliente", lambda: falso)

    resultado = evaluador.evaluar_criterio("tecnico", "Agente Técnico", "C1", POSTOR, CRITERIO, [0.1])

    assert busquedas == [None, "CV Jefe de supervision.pdf"]
    assert falso.resultado_de_herramienta(2)["meses"] == 42.0
    assert resultado["veredicto"] == "Cumple"
    # Solo se acepta la cita de una página que el agente realmente vio.
    assert resultado["citas"] == [{"documento": "CV Jefe de supervision.pdf", "pagina": 2, "extracto": "Provías 01/2018"}]
    assert [p["herramienta"] for p in resultado["pasos"]] == ["buscar_evidencia", "calcular_experiencia"]
    assert "42.0 meses" in resultado["pasos"][1]["resumen"]


def test_sin_conclusion_el_criterio_queda_para_el_comite(monkeypatch, db_falsa):
    monkeypatch.setattr(evaluador, "buscar_fragmentos", lambda **_: INICIALES)
    monkeypatch.setattr(agente, "obtener_cliente", lambda: GeminiGuionado([respuesta_con_llamadas()]))
    factor = {**CRITERIO, "etapa": "evaluacion", "puntaje_maximo": 40}

    resultado = evaluador.evaluar_criterio("tecnico", "Agente Técnico", "C1", POSTOR, factor, [0.1])

    assert (resultado["veredicto"], resultado["puntaje"]) == ("Requiere revisión", 0.0)
    assert "no llegó a una conclusión" in resultado["justificacion"]


def test_la_observacion_del_coordinador_llega_al_agente(monkeypatch, db_falsa):
    monkeypatch.setattr(evaluador, "buscar_fragmentos", lambda **_: INICIALES)
    falso = GeminiGuionado([respuesta_con_llamadas(("emitir_evaluacion", {
        "veredicto": "Requiere revisión", "justificacion": "Las fechas no coinciden.", "citas": []}))])
    monkeypatch.setattr(agente, "obtener_cliente", lambda: falso)
    anterior = {"veredicto": "Cumple", "puntaje": None, "justificacion": "Acredita 42 meses."}

    evaluador.evaluar_criterio("tecnico", "Agente Técnico", "C1", POSTOR, CRITERIO, [0.1],
                               revision={"observacion": "El CV y la constancia dan fechas distintas", "anterior": anterior})

    instrucciones = falso.llamadas[0]["contents"][0].parts[0].text
    assert "«El CV y la constancia dan fechas distintas»" in instrucciones
    assert "Tu evaluación anterior fue: Cumple — Acredita 42 meses." in instrucciones
