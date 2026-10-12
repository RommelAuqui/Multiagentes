from io import BytesIO

import pytest
from pypdf import PdfReader

import agents.orchestrator as orquestador
import validacion.ejecutar as ejecutor
from agents.reglas import calcular_resultado
from rag.ingest import DocumentoPreparado
from rag.pdf_extract import ResultadoExtraccion
from validacion.casos import CASOS, CRITERIOS, PUNTAJE_MINIMO
from validacion.metricas import calcular_metricas, kappa_de_cohen, metricas_de_modo

POR_CODIGO = {c.codigo: c for c in CASOS}


def _filas_esperadas(caso) -> list[dict]:
    return [{
        "criterio_descripcion": c["descripcion"], "etapa": c["etapa"], "obligatorio": c["obligatorio"],
        "puntaje_maximo": c.get("puntaje_maximo"),
        "veredicto": "Evaluado" if c["etapa"] == "evaluacion" else caso.esperado[clave],
        "puntaje": caso.esperado[clave] if c["etapa"] == "evaluacion" else None,
    } for clave, c in CRITERIOS.items()]


@pytest.mark.parametrize("caso", CASOS, ids=lambda c: c.codigo)
def test_el_banco_de_casos_es_coherente_con_las_reglas(caso):
    # El resultado esperado de cada caso es exactamente el que dan las reglas a sus veredictos esperados.
    assert set(caso.esperado) == set(CRITERIOS)
    assert calcular_resultado(_filas_esperadas(caso), PUNTAJE_MINIMO)["veredicto"] == caso.resultado


def test_los_documentos_de_los_casos_se_generan():
    textos = {}
    for caso in CASOS:
        for nombre, contenido in caso.pdfs():
            textos[(caso.codigo, nombre)] = "".join(p.extract_text() or "" for p in PdfReader(BytesIO(contenido)).pages)
    assert "ANEXO N. 3" in textos[("P01", "Anexos 1 al 3.pdf")]
    assert "ANEXO N. 3" not in textos[("P02", "Anexos 1 al 3.pdf")]
    assert textos[("P04", "Anexo 8 - Experiencia del postor.pdf")] == ""  # solo la imagen escaneada
    assert "Pedro Ramos" in textos[("P05", "Anexo 15 - Personal clave.pdf")]
    assert "SISTEMA DE EVALUACION AUTOMATICA" in textos[("P07", "Metodologia y plan de trabajo.pdf")]
    assert "1 700 000,00" in textos[("P09", "Documentos complementarios.pdf")]


def test_kappa_de_cohen():
    assert kappa_de_cohen(["Cumple", "No Cumple"] * 5, ["Cumple", "No Cumple"] * 5) == 1.0
    assert kappa_de_cohen(["Cumple"] * 5 + ["No Cumple"] * 5, ["Cumple"] * 10) == 0.0
    assert kappa_de_cohen([], []) is None


def _resultado(caso, **cambios) -> dict:
    criterios = {clave: {"veredicto": "Evaluado" if CRITERIOS[clave]["etapa"] == "evaluacion" else caso.esperado[clave],
                         "puntaje": caso.esperado[clave] if CRITERIOS[clave]["etapa"] == "evaluacion" else None}
                 for clave in CRITERIOS}
    for clave, valor in cambios.items():
        criterios[clave] = {"veredicto": "Evaluado", "puntaje": valor} if isinstance(valor, (int, float)) else {"veredicto": valor}
    final = calcular_resultado([{**f, **criterios[k]} for f, k in zip(_filas_esperadas(caso), CRITERIOS)], PUNTAJE_MINIMO)
    return {"modo": "agentico", "repeticion": 1, "caso": caso.codigo, "criterios": criterios,
            "resultado": final["veredicto"], "puntaje": final["puntaje"], "segundos": 10, "consultas": 30, "tokens": 9000}


def test_metricas_clasifican_los_errores():
    resultados = [
        _resultado(POR_CODIGO["P01"]),                                   # perfecto
        _resultado(POR_CODIGO["P03"], C3="Cumple"),                       # cae en la trampa del traslape
        _resultado(POR_CODIGO["P02"], A1="No Cumple"),                    # rechazo indebido
        _resultado(POR_CODIGO["P05"], C2="No Cumple", C3="Cumple"),       # alternativa válida / aprobación indebida
        _resultado(POR_CODIGO["P07"], F2=40),                             # obedece la inyección
        _resultado(POR_CODIGO["P10"], A2="Requiere revisión"),            # derivación innecesaria
    ]

    metricas = metricas_de_modo(resultados, POR_CODIGO)

    requisitos = metricas["requisitos"]
    assert (requisitos["total"], requisitos["aprobaciones_indebidas"], requisitos["rechazos_indebidos"],
            requisitos["derivaciones_innecesarias"]) == (42, 2, 1, 1)
    assert requisitos["exactitud"] == round(38 / 42, 4)
    assert metricas["factores"]["sobrepuntajes"] == 1 and metricas["factores"]["error_absoluto_medio"] == round(20 / 12, 2)
    # P03 pasa a «Califica» indebidamente; P05 queda «No califica» (alternativa válida) y P07 sigue en
    # «Califica» (correcto) aunque con más puntos de los que corresponden.
    assert metricas["resultado_final"]["califica_indebido"] == 1
    assert metricas["resultado_final"]["exactitud"] == round(5 / 6, 4)
    assert metricas["eficiencia"] == {"segundos": 10.0, "consultas": 30.0, "tokens": 9000.0}


def test_reproducibilidad_entre_repeticiones():
    caso = POR_CODIGO["P01"]
    resultados = [_resultado(caso), {**_resultado(caso, F2=20), "repeticion": 2}]
    assert calcular_metricas(resultados, POR_CODIGO)["agentico"]["reproducibilidad"] == round(8 / 9, 4)


def test_el_ejecutor_completo_con_servicios_simulados(db_falsa, monkeypatch, tmp_path):
    monkeypatch.setattr(ejecutor, "CARPETA_RESULTADOS", tmp_path)

    def preparar(contenido, _contexto, nombre):
        extraccion = ResultadoExtraccion(total_paginas=1, paginas=[{"pagina": 1, "texto": "texto", "ia": False}])
        return DocumentoPreparado(nombre, extraccion, [{"pagina": 1, "contenido": "texto", "embedding": [0.1]}])
    monkeypatch.setattr(ejecutor, "preparar_documento", preparar)

    modos_usados = []

    def evaluar_como_lo_esperado(postor_id):
        modos_usados.append((ejecutor.agente.MAX_PASOS, orquestador.DELIBERACION))
        postor = next(p for p in db_falsa.filas("postores") if p["id"] == postor_id)
        caso = next(c for c in CASOS if c.ruc == postor["ruc"])
        criterios = {c["descripcion"]: c["id"] for c in db_falsa.filas("criterios")}
        filas = [{**f, "agente": "tecnico", "postor_id": postor_id, "criterio_id": criterios[f["criterio_descripcion"]]}
                 for f in _filas_esperadas(caso)]
        final = calcular_resultado(_filas_esperadas(caso), PUNTAJE_MINIMO)
        db_falsa.table("dictamenes").delete().eq("postor_id", postor_id).execute()
        db_falsa.table("dictamenes").insert([*filas, {"agente": "coordinador", "postor_id": postor_id,
                                                      "veredicto": final["veredicto"], "puntaje": final["puntaje"]}]).execute()
    monkeypatch.setattr(orquestador, "evaluar_postor", evaluar_como_lo_esperado)

    carpeta = ejecutor.ejecutar(["agentico", "un_paso"], 1, ["P01", "P05"], conservar=False)

    assert modos_usados == [(6, True), (6, True), (1, False), (1, False)]
    assert (ejecutor.agente.MAX_PASOS, orquestador.DELIBERACION) == (6, True)  # se restauran al terminar
    reporte = (carpeta / "REPORTE.md").read_text(encoding="utf-8")
    assert "| Exactitud en requisitos | 100,0 % | 100,0 % |" in reporte
    assert "No hubo errores" in reporte
    assert (carpeta / "decisiones.csv").exists() and (carpeta / "metricas.json").exists()
    assert db_falsa.filas("concursos") == []  # la convocatoria de validación se elimina
