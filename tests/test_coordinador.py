import agents.coordinador as coordinador
from agents.gemini_client import ContextoIA

CONTEXTO = ContextoIA("coordinador", "C1", "P1")


def _resultado(etapa, veredicto, puntaje=None, maximo=None, citas=()):
    return {"criterio_descripcion": f"criterio de {etapa}", "etapa": etapa, "obligatorio": True,
            "veredicto": veredicto, "puntaje": puntaje, "puntaje_maximo": maximo, "justificacion": "j",
            "citas": list(citas), "agente": "tecnico"}


def test_el_coordinador_no_puede_aprobar_a_quien_no_cumple(monkeypatch):
    # Aunque el LLM no vea problemas, la regla de las Bases manda.
    monkeypatch.setattr(coordinador, "generar_json", lambda *_: {"conciliacion": "Todo en orden.", "tensiones": []})

    dictamen = coordinador.consolidar_dictamen(
        [_resultado("admision", "No Cumple"), _resultado("evaluacion", "Evaluado", 60, 60)], None, CONTEXTO
    )

    assert dictamen["veredicto"] == "No admitido"
    assert "Motivos: criterio de admision" in dictamen["justificacion"]


def test_las_tensiones_mandan_el_caso_al_comite(monkeypatch):
    prompts = []
    monkeypatch.setattr(coordinador, "generar_json", lambda _m, prompt, _c: prompts.append(prompt) or {
        "conciliacion": " Ambos agentes coinciden. ",
        "tensiones": [
            {"criterio": 1, "observacion": "El RUC del CV no coincide con el de la propuesta"},
            {"criterio": 99, "observacion": "Número de criterio inexistente"},
            "Formato antiguo: texto suelto",
            {"criterio": 2, "observacion": ""},
        ],
    })
    cita = {"documento": "cv", "pagina": 2, "extracto": "x"}

    dictamen = coordinador.consolidar_dictamen(
        [_resultado("calificacion", "Cumple", citas=[cita]), _resultado("evaluacion", "Evaluado", 45, 60)], 40, CONTEXTO
    )

    assert "[1] [Calificación | Agente tecnico] criterio de calificacion: Cumple" in prompts[0]
    assert dictamen["veredicto"] == "Requiere revisión"
    assert dictamen["tensiones"] == [
        {"criterio": 0, "observacion": "El RUC del CV no coincide con el de la propuesta"},
        {"criterio": None, "observacion": "Número de criterio inexistente"},
        {"criterio": None, "observacion": "Formato antiguo: texto suelto"},
    ]
    assert dictamen["justificacion"].startswith("Ambos agentes coinciden.")
    assert "[1] El RUC del CV no coincide" in dictamen["justificacion"]
    assert (dictamen["puntaje"], dictamen["puntaje_maximo"], dictamen["citas"]) == (45, 60, [cita])


def test_la_segunda_ronda_marca_los_criterios_revisados(monkeypatch):
    prompts = []
    monkeypatch.setattr(coordinador, "generar_json", lambda _m, prompt, _c: prompts.append(prompt) or {"tensiones": []})

    coordinador.consolidar_dictamen([{**_resultado("calificacion", "Cumple"), "revisado": True}], None, CONTEXTO,
                                    segunda_ronda=True)

    assert "Esta es la segunda ronda" in prompts[0] and "(revisado)" in prompts[0]


def test_sin_tensiones_se_mantiene_el_resultado_de_las_reglas(monkeypatch):
    monkeypatch.setattr(coordinador, "generar_json", lambda *_: {"conciliacion": "ok", "tensiones": "no es lista"})

    dictamen = coordinador.consolidar_dictamen([_resultado("evaluacion", "Evaluado", 30, 60)], 40, CONTEXTO)

    assert dictamen["veredicto"] == "Puntaje insuficiente"
