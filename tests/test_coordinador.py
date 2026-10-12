import agents.coordinador as coordinador
from agents.gemini_client import ContextoIA

CONTEXTO = ContextoIA("coordinador", "C1", "P1")


def _resultado(veredicto, citas=()):
    return {"criterio_descripcion": "c", "veredicto": veredicto, "justificacion": "j", "citas": list(citas)}


def _no_debe_deliberar(*_):
    raise AssertionError("Un incumplimiento legal obligatorio no pasa a deliberación.")


def test_incumplimiento_legal_obligatorio_descalifica_sin_deliberar(monkeypatch):
    monkeypatch.setattr(coordinador, "_deliberar", _no_debe_deliberar)

    dictamen = coordinador.consolidar_dictamen(
        criterios_legales=[{"obligatorio": True}, {"obligatorio": False}],
        resultados_legal=[_resultado("No Cumple"), _resultado("Cumple")],
        resultados_tecnico=[_resultado("Cumple"), _resultado("No Cumple")],
        contexto=CONTEXTO,
    )

    assert dictamen["veredicto"] == "No Cumple"
    assert dictamen["puntaje"] == 50.0
    assert dictamen["justificacion"].startswith("Descalificado")


def test_delibera_y_normaliza_la_respuesta(monkeypatch):
    monkeypatch.setattr(coordinador, "_deliberar", lambda *_: {"veredicto": "cumple", "conciliacion": " ok "})
    cita = {"documento": "cv", "pagina": 2, "extracto": "x"}

    dictamen = coordinador.consolidar_dictamen(
        criterios_legales=[{"obligatorio": False}],
        resultados_legal=[_resultado("No Cumple")],
        resultados_tecnico=[_resultado("Cumple", [cita]), _resultado("Cumple"), _resultado("No Cumple")],
        contexto=CONTEXTO,
    )

    assert dictamen == {"veredicto": "Cumple", "puntaje": 66.67, "justificacion": "ok", "citas": [cita]}
