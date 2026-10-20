import pytest

import agents.agente as agente
from agents.gemini_client import ContextoIA
from retry_utils import CuotaDiariaAgotada
from revision import agente_revisor
from revision.catalogo import AGENTE, POR_CODIGO, VERIFICACIONES
from revision.reglas import FALLA, NO_VERIFICADO, Documento
from tests.gemini_falso import GeminiGuionado, respuesta_con_llamadas

CONTEXTO = ContextoIA("revisor", "C1")
REQUERIMIENTO = Documento("requerimiento", "Requerimiento.pdf", [
    {"pagina": 1, "texto": "TÉRMINOS DE REFERENCIA. Jefe de supervisión: 36 meses como supervisor de obras."},
])
BASES = Documento("bases", "Bases.pdf", [
    {"pagina": 1, "texto": "CAPÍTULO I GENERALIDADES. Objeto: supervisión de la obra."},
    {"pagina": 2, "texto": "CAPÍTULO III REQUERIMIENTO. Jefe de supervisión: 60 meses como supervisor de obras."},
], {"cuantia": 480000.0})
DOCS = {"requerimiento": REQUERIMIENTO, "bases": BASES}


@pytest.fixture
def gemini(monkeypatch):
    def preparar(guion):
        falso = GeminiGuionado(guion)
        monkeypatch.setattr(agente, "obtener_cliente", lambda: falso)
        return falso
    return preparar


def _herramienta(nombre):
    return next(h for h in agente_revisor.herramientas(DOCS) if h.nombre == nombre)


def test_cada_verificacion_del_agente_tiene_su_guia():
    assert {v.codigo for v in VERIFICACIONES if v.metodo == AGENTE} == set(agente_revisor.GUIAS)


def test_buscar_sin_tildes_ni_mayusculas_y_leer_una_pagina():
    resultado = _herramienta("buscar_texto").funcion(documento="bases", palabras="capitulo requerimiento")
    assert resultado["total"] == 1 and resultado["resultados"][0]["pagina"] == 2
    assert "60 meses" in _herramienta("leer_pagina").funcion(documento="bases", pagina=2)["texto"]
    with pytest.raises(ValueError):
        _herramienta("leer_pagina").funcion(documento="bases", pagina=9)


def test_comparar_textos_muestra_el_cambio():
    resultado = _herramienta("comparar_textos").funcion(documento_a="requerimiento", documento_b="bases",
                                                        desde_b=2, hasta_b=2)
    cambios = [(c["texto_a"], c["texto_b"]) for c in resultado["cambios"]]
    assert ("36", "60") in cambios and resultado["similitud"] < 1


def test_el_agente_compara_y_concluye_con_citas(gemini, db_falsa):
    falso = gemini([
        respuesta_con_llamadas(("comparar_textos", {"documento_a": "requerimiento", "documento_b": "bases",
                                                    "desde_b": 2, "hasta_b": 2})),
        respuesta_con_llamadas(("emitir_resultado", {
            "estado": "falla", "descripcion": "Las Bases exigen 60 meses al jefe; el requerimiento, 36.",
            "citas": [{"documento": "bases", "pagina": 2}, {"documento": "requerimiento", "pagina": 1},
                      {"documento": "inventado", "pagina": 5}]})),
    ])

    resultado = agente_revisor.revisar_verificacion(POR_CODIGO["COH-06"], DOCS, CONTEXTO)

    assert resultado.estado == FALLA and "60 meses" in resultado.descripcion
    # Solo se citan documentos que existen, con su nombre de archivo.
    assert resultado.citas == [{"documento": "Bases.pdf", "pagina": 2}, {"documento": "Requerimiento.pdf", "pagina": 1}]
    assert resultado.pasos[0]["resumen"].startswith("Comparó requerimiento con bases")
    # El agente recibió la guía de la verificación y los cambios encontrados.
    assert "Capítulo III" in falso.llamadas[0]["contents"][0].parts[0].text
    assert falso.resultado_de_herramienta(1)["cambios"]


def test_sin_los_documentos_necesarios_no_se_consulta_a_gemini(gemini, db_falsa):
    falso = gemini([])
    resultado = agente_revisor.revisar_verificacion(POR_CODIGO["COH-09"], DOCS, CONTEXTO)
    assert resultado.estado == NO_VERIFICADO and "Formato de estrategia" in resultado.descripcion
    assert falso.llamadas == []


def test_si_se_agota_la_cuota_el_resto_queda_no_verificado(monkeypatch):
    llamadas = []

    def sin_cuota(verificacion, docs, contexto):
        llamadas.append(verificacion.codigo)
        raise CuotaDiariaAgotada()

    monkeypatch.setattr(agente_revisor, "revisar_verificacion", sin_cuota)
    resultados = agente_revisor.revisar("A", DOCS, CONTEXTO)

    assert len(llamadas) == 1  # después de la primera ya no se intenta
    assert resultados and all(r.estado == NO_VERIFICADO and "cuota diaria" in r.descripcion for r in resultados)
    assert {r.codigo for r in resultados} == {v.codigo for v in VERIFICACIONES if v.metodo == AGENTE and "A" in v.rondas}
