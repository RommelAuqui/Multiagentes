from types import SimpleNamespace

import pytest

import agents.gemini_client as gemini_client
from agents.gemini_client import ContextoIA

CONTEXTO = ContextoIA("legal", "C1", "P1")


def _cliente_con_respuestas(monkeypatch, textos):
    respuestas = iter(textos)
    configuraciones = []

    def generar(**kwargs):
        configuraciones.append(kwargs["config"])
        uso = SimpleNamespace(prompt_token_count=10, candidates_token_count=5)
        return SimpleNamespace(text=next(respuestas), usage_metadata=uso)

    monkeypatch.setattr(gemini_client, "obtener_cliente", lambda: SimpleNamespace(models=SimpleNamespace(generate_content=generar)))
    return configuraciones


def test_respuesta_reproducible_y_registrada(monkeypatch, db_falsa):
    configuraciones = _cliente_con_respuestas(monkeypatch, ['{"veredicto": "Cumple"}'])

    assert gemini_client.generar_json("modelo-x", "prompt", CONTEXTO) == {"veredicto": "Cumple"}

    assert configuraciones[0]["temperature"] == 0
    [consulta] = db_falsa.filas("consultas_ia")
    assert consulta["agente"] == "legal" and consulta["concurso_id"] == "C1" and consulta["postor_id"] == "P1"
    assert consulta["modelo"] == "modelo-x" and consulta["tokens_entrada"] == 10 and consulta["error"] is None


def test_reintenta_con_otra_semilla_si_el_json_es_invalido(monkeypatch, db_falsa):
    configuraciones = _cliente_con_respuestas(monkeypatch, ["no es json", None, '{"veredicto": "Cumple"}'])

    assert gemini_client.generar_json("modelo", "prompt", CONTEXTO) == {"veredicto": "Cumple"}

    assert len({c["seed"] for c in configuraciones}) == 3
    assert len(db_falsa.filas("consultas_ia")) == 3


def test_falla_tras_varios_intentos(monkeypatch):
    _cliente_con_respuestas(monkeypatch, ["[1, 2]", "{", ""])
    with pytest.raises(gemini_client.RespuestaInvalidaError):
        gemini_client.generar_json("modelo", "prompt", CONTEXTO)


def test_si_falla_el_registro_la_consulta_sigue(monkeypatch, db_falsa):
    _cliente_con_respuestas(monkeypatch, ['{"ok": true}'])

    def tabla_rota(_nombre):
        raise ConnectionError("Supabase caído")
    monkeypatch.setattr(db_falsa, "table", tabla_rota)

    assert gemini_client.generar_json("modelo", "prompt", CONTEXTO) == {"ok": True}


def test_error_de_la_api_queda_registrado(monkeypatch, db_falsa):
    def fallar(**_):
        raise ValueError("cuota agotada")
    monkeypatch.setattr(gemini_client, "obtener_cliente", lambda: SimpleNamespace(models=SimpleNamespace(generate_content=fallar)))

    with pytest.raises(ValueError):
        gemini_client.generar_json("modelo", "prompt", CONTEXTO)

    assert "cuota agotada" in db_falsa.filas("consultas_ia")[0]["error"]
