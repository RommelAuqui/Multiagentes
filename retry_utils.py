import time

from google.genai import errors

CODIGOS_REINTENTABLES = (429, 500, 503)


def con_reintentos(funcion, intentos: int = 6, espera_inicial: float = 15.0):
    espera = espera_inicial
    for intento in range(intentos):
        try:
            return funcion()
        except errors.APIError as e:
            if e.code not in CODIGOS_REINTENTABLES or intento == intentos - 1:
                raise
            time.sleep(espera)
            espera = min(espera * 2, 60.0)
