import pytest
from google.genai import errors

import retry_utils
from retry_utils import CuotaDiariaAgotada, con_reintentos


def _error_429(cuota: str, retraso: str | None = None) -> errors.APIError:
    detalles = [{"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [{"quotaId": cuota}]}]
    if retraso:
        detalles.append({"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": retraso})
    return errors.APIError(429, {"error": {
        "code": 429, "status": "RESOURCE_EXHAUSTED", "message": "You exceeded your current quota.", "details": detalles,
    }})


@pytest.fixture(autouse=True)
def sin_esperas(monkeypatch):
    esperas = []
    monkeypatch.setattr(retry_utils.time, "sleep", esperas.append)
    return esperas


def _falla_y_luego_responde(error, fallas):
    llamadas = []

    def funcion():
        llamadas.append(1)
        if len(llamadas) <= fallas:
            raise error
        return "respuesta"
    funcion.llamadas = llamadas
    return funcion


def test_reintenta_si_se_supera_el_limite_por_minuto(sin_esperas):
    funcion = _falla_y_luego_responde(_error_429("GenerateRequestsPerMinutePerProjectPerModel-FreeTier"), 2)

    assert con_reintentos(funcion) == "respuesta"
    assert len(funcion.llamadas) == 3 and sin_esperas == [15.0, 30.0]


def test_espera_lo_que_indica_gemini(sin_esperas):
    funcion = _falla_y_luego_responde(_error_429("GenerateRequestsPerMinutePerProjectPerModel-FreeTier", "37.5s"), 1)

    assert con_reintentos(funcion) == "respuesta"
    assert sin_esperas == [38.5]


def test_la_espera_indicada_tiene_un_tope(sin_esperas):
    funcion = _falla_y_luego_responde(_error_429("GenerateContentInputTokensPerModelPerMinute-FreeTier", "900s"), 1)

    con_reintentos(funcion)
    assert sin_esperas == [retry_utils.ESPERA_MAXIMA]


def test_no_reintenta_si_se_agoto_la_cuota_diaria(sin_esperas):
    funcion = _falla_y_luego_responde(_error_429("GenerateRequestsPerDayPerProjectPerModel-FreeTier"), 10)

    with pytest.raises(CuotaDiariaAgotada, match="cuota diaria"):
        con_reintentos(funcion)
    assert len(funcion.llamadas) == 1 and sin_esperas == []


def test_no_reintenta_errores_que_no_son_temporales(sin_esperas):
    funcion = _falla_y_luego_responde(errors.APIError(400, {"error": {"code": 400, "message": "Solicitud inválida"}}), 1)

    with pytest.raises(errors.APIError):
        con_reintentos(funcion)
    assert len(funcion.llamadas) == 1
