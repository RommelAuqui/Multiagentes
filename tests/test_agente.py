import pytest

import agents.agente as agente
from agents.agente import Herramienta, ejecutar_agente
from agents.gemini_client import ContextoIA
from tests.gemini_falso import GeminiGuionado, respuesta_con_llamadas

CONTEXTO = ContextoIA("tecnico", "C1", "P1")
FINAL = Herramienta("emitir_evaluacion", "Concluye.", {"type": "object", "properties": {"veredicto": {"type": "string"}}})


def _sumar(montos):
    return {"total": sum(montos)}


SUMAR = Herramienta(
    "sumar_montos", "Suma.", {"type": "object", "properties": {"montos": {"type": "array"}}},
    _sumar, lambda args, r: f"Sumó {len(args['montos'])} montos: {r['total']}",
)


@pytest.fixture
def gemini(monkeypatch):
    def preparar(guion):
        falso = GeminiGuionado(guion)
        monkeypatch.setattr(agente, "obtener_cliente", lambda: falso)
        return falso
    return preparar


def test_el_agente_usa_una_herramienta_y_luego_concluye(gemini, db_falsa):
    falso = gemini([
        respuesta_con_llamadas(("sumar_montos", {"montos": [1250000, 980500]})),
        respuesta_con_llamadas(("emitir_evaluacion", {"veredicto": "Cumple"})),
    ])

    resultado = ejecutar_agente("modelo", "Evalúa.", [SUMAR], FINAL, CONTEXTO)

    assert resultado.conclusion == {"veredicto": "Cumple"}
    assert resultado.pasos == [{"herramienta": "sumar_montos", "argumentos": {"montos": [1250000, 980500]},
                                "resumen": "Sumó 2 montos: 2230500"}]
    assert falso.resultado_de_herramienta(1) == {"total": 2230500}
    # Cada paso queda registrado, con lo que pidió el modelo.
    consultas = db_falsa.filas("consultas_ia")
    assert len(consultas) == 2 and "sumar_montos" in consultas[0]["respuesta"]


def test_los_errores_de_una_herramienta_vuelven_al_agente(gemini, db_falsa):
    falso = gemini([
        respuesta_con_llamadas(("buscar_en_internet", {"q": "x"}), ("sumar_montos", {"montos": "no es lista"})),
        respuesta_con_llamadas(("emitir_evaluacion", {"veredicto": "Requiere revisión"})),
    ])

    resultado = ejecutar_agente("modelo", "Evalúa.", [SUMAR], FINAL, CONTEXTO)

    respuestas = [p.function_response.response for p in falso.llamadas[1]["contents"][-1].parts]
    assert "no existe" in respuestas[0]["error"] and "TypeError" in respuestas[1]["error"]
    assert [p["resumen"] for p in resultado.pasos][0].startswith("buscar_en_internet:")
    assert resultado.conclusion == {"veredicto": "Requiere revisión"}


def test_en_el_ultimo_paso_solo_puede_concluir(gemini, db_falsa):
    falso = gemini([respuesta_con_llamadas(("sumar_montos", {"montos": [1]}))] * 2 + [
        respuesta_con_llamadas(("emitir_evaluacion", {"veredicto": "Cumple"})),
    ])

    resultado = ejecutar_agente("modelo", "Evalúa.", [SUMAR], FINAL, CONTEXTO, max_pasos=3)

    permitidas = [l["config"].tool_config.function_calling_config.allowed_function_names for l in falso.llamadas]
    assert permitidas == [None, None, ["emitir_evaluacion"]]
    assert resultado.conclusion == {"veredicto": "Cumple"} and len(resultado.pasos) == 2


def test_sin_conclusion_devuelve_los_pasos(gemini, db_falsa):
    sin_llamadas = respuesta_con_llamadas()
    gemini([sin_llamadas])

    resultado = ejecutar_agente("modelo", "Evalúa.", [SUMAR], FINAL, CONTEXTO)

    assert resultado.conclusion is None and resultado.pasos == []
