from types import SimpleNamespace

import pytest

import agents.gemini_client as gemini_client


def _cliente_con_respuestas(monkeypatch, textos):
    respuestas = iter(textos)
    modelos = SimpleNamespace(generate_content=lambda **_: SimpleNamespace(text=next(respuestas)))
    monkeypatch.setattr(gemini_client, "obtener_cliente", lambda: SimpleNamespace(models=modelos))


def test_reintenta_si_el_json_es_invalido(monkeypatch):
    _cliente_con_respuestas(monkeypatch, ["no es json", None, '{"veredicto": "Cumple"}'])
    assert gemini_client.generar_json("modelo", "prompt") == {"veredicto": "Cumple"}


def test_falla_tras_varios_intentos(monkeypatch):
    _cliente_con_respuestas(monkeypatch, ["[1, 2]", "{", ""])
    with pytest.raises(gemini_client.RespuestaInvalidaError):
        gemini_client.generar_json("modelo", "prompt")
