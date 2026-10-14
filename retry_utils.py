import re
import time

from google.genai import errors

CODIGOS_REINTENTABLES = (429, 500, 503)
ESPERA_MAXIMA = 120.0
RETRASO = re.compile(r"^(\d+(?:\.\d+)?)s$")


class CuotaDiariaAgotada(Exception):
    """Gemini rechazó la consulta porque se acabó la cuota del día: reintentar no sirve hasta que se renueve."""

    def __init__(self):
        super().__init__("Se agotó la cuota diaria de consultas de Gemini. Se renueva al día siguiente: vuelve a "
                         "intentarlo más tarde o activa la facturación de la clave de Gemini.")


def es_cuota_diaria(error: errors.APIError) -> bool:
    # El detalle del 429 nombra la cuota agotada; la diaria es, p. ej., GenerateRequestsPerDayPerProjectPerModel.
    return error.code == 429 and "PerDay" in str(error)


def espera_indicada(error: errors.APIError) -> float | None:
    """Segundos que Gemini pide esperar antes de reintentar (RetryInfo.retryDelay, p. ej., «37s»), si los indica."""
    detalles = (error.details or {}).get("error", {}).get("details", []) if isinstance(error.details, dict) else []
    for detalle in detalles:
        if isinstance(detalle, dict) and (coincidencia := RETRASO.match(str(detalle.get("retryDelay", "")))):
            return float(coincidencia.group(1))
    return None


def con_reintentos(funcion, intentos: int = 6, espera_inicial: float = 15.0):
    espera = espera_inicial
    for intento in range(intentos):
        try:
            return funcion()
        except errors.APIError as e:
            if es_cuota_diaria(e):
                raise CuotaDiariaAgotada() from e
            if e.code not in CODIGOS_REINTENTABLES or intento == intentos - 1:
                raise
            # Si Gemini dice cuánto falta para renovar el límite por minuto, se espera eso (más un margen).
            indicada = espera_indicada(e)
            time.sleep(min(indicada + 1, ESPERA_MAXIMA) if indicada is not None else espera)
            espera = min(espera * 2, 60.0)
