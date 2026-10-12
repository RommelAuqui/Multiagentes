from io import BytesIO

import pytest
from pypdf import PdfReader

import rag.lector as lector
from agents.gemini_client import ContextoIA
from rag.pdf_extract import dividir_en_fragmentos, extraer_paginas, texto_completo
from tests.pdfs import construir_pdf, imagen_gris

CONTEXTO = ContextoIA("lector", "C1")
TEXTO_LARGO = ["Declaracion jurada de no estar impedido para contratar con el Estado peruano."]


@pytest.fixture
def gemini_lector(monkeypatch):
    """Simula a Gemini: transcribe cada página del PDF adjunto como 'escaneo de <ancho> px'."""
    llamadas = []

    def generar(_modelo, _prompt, contexto, adjuntos):
        paginas = PdfReader(BytesIO(adjuntos[0].inline_data.data)).pages
        llamadas.append(len(paginas))
        anchos = [p["/Resources"]["/XObject"]["/Im1"].get_object()["/Width"] if "/XObject" in p["/Resources"] else 0
                  for p in paginas]
        return {"paginas": [
            {"pagina": i, "texto": f"Escaneo de {ancho} px: constancia de experiencia del postor."}
            for i, ancho in enumerate(anchos, start=1)
        ]}

    monkeypatch.setattr(lector, "generar_json", generar)
    return llamadas


def test_solo_se_leen_con_ia_las_paginas_escaneadas_o_con_imagenes_grandes(gemini_lector):
    pdf = construir_pdf([
        {"lineas": TEXTO_LARGO},                                          # 1: texto normal
        {"imagen": imagen_gris(801, 1000)},                               # 2: escaneo sin texto
        {"lineas": TEXTO_LARGO, "imagen": imagen_gris(802, 1000)},        # 3: texto + escaneo pegado
        {"lineas": TEXTO_LARGO, "imagen": imagen_gris(300, 100)},         # 4: texto + logo pequeño
    ])

    resultado = extraer_paginas(pdf, CONTEXTO)

    assert resultado.paginas_ia == [2, 3]
    textos = {p["pagina"]: p["texto"] for p in resultado.paginas}
    assert "Escaneo de 801 px" in textos[2] and "Escaneo de 802 px" in textos[3]
    assert textos[1].startswith("Declaracion jurada") and textos[4].startswith("Declaracion jurada")
    assert resultado.paginas_sin_texto == [] and resultado.error_lectura is None


def test_las_paginas_se_envian_en_lotes_y_conservan_su_numero(gemini_lector):
    pdf = construir_pdf([{"imagen": imagen_gris(1000 + n, 1000)} for n in range(12)])

    resultado = extraer_paginas(pdf, CONTEXTO)

    assert gemini_lector == [5, 5, 2]
    assert [p["pagina"] for p in resultado.paginas] == list(range(1, 13))
    assert all(f"Escaneo de {1000 + n} px" in p["texto"] for n, p in enumerate(resultado.paginas))


def test_si_la_ia_falla_se_conserva_el_texto_y_se_avisa(monkeypatch):
    def fallar(*_args, **_kwargs):
        raise RuntimeError("503 alta demanda")
    monkeypatch.setattr(lector, "generar_json", fallar)
    pdf = construir_pdf([
        {"lineas": TEXTO_LARGO},
        {"imagen": imagen_gris(900, 900)},
        {"lineas": TEXTO_LARGO, "imagen": imagen_gris(900, 900)},
    ])

    resultado = extraer_paginas(pdf, CONTEXTO)

    assert [p["pagina"] for p in resultado.paginas] == [1, 3]
    assert resultado.paginas_sin_texto == [2]
    assert resultado.paginas_imagen_sin_leer == [3]
    assert "503" in resultado.error_lectura


def test_respuestas_incompletas_de_la_ia_no_desordenan_las_paginas(monkeypatch):
    monkeypatch.setattr(lector, "generar_json", lambda *_a, **_k: {"paginas": [
        {"pagina": 2, "texto": "segunda"}, {"pagina": 9, "texto": "fuera de rango"}, {"pagina": "x"}, "basura",
    ]})
    pdf = construir_pdf([{"imagen": imagen_gris(900, 900)}, {"imagen": imagen_gris(900, 900)}])

    resultado = extraer_paginas(pdf, CONTEXTO)

    assert resultado.paginas == [{"pagina": 2, "texto": "segunda", "ia": True}]
    assert resultado.paginas_sin_texto == [1]


def test_dividir_en_fragmentos_respeta_tamano_y_pagina():
    paginas = [{"pagina": 1, "texto": "a" * 3200}, {"pagina": 2, "texto": "b" * 10}]
    fragmentos = dividir_en_fragmentos(paginas, max_caracteres=1500)

    assert [(f["pagina"], len(f["contenido"])) for f in fragmentos] == [(1, 1500), (1, 1500), (1, 200), (2, 10)]


def test_texto_completo_marca_paginas():
    assert texto_completo([{"pagina": 3, "texto": "hola"}]) == "[Página 3]\nhola"


def test_un_lote_mal_formado_se_reintenta_por_mitades(monkeypatch, gemini_lector):
    generar_original = lector.generar_json
    lotes = []

    def falla_con_lotes_grandes(modelo, prompt, contexto, adjuntos):
        total = len(PdfReader(BytesIO(adjuntos[0].inline_data.data)).pages)
        lotes.append(total)
        if total > 2:
            raise lector.RespuestaInvalidaError("JSON mal formado")
        return generar_original(modelo, prompt, contexto, adjuntos)
    monkeypatch.setattr(lector, "generar_json", falla_con_lotes_grandes)

    pdf = construir_pdf([{"imagen": imagen_gris(1000 + n, 1000)} for n in range(5)])
    resultado = extraer_paginas(pdf, CONTEXTO)

    assert lotes == [5, 2, 3, 1, 2]
    assert resultado.paginas_ia == [1, 2, 3, 4, 5] and resultado.error_lectura is None
    assert all(f"Escaneo de {1000 + n} px" in p["texto"] for n, p in enumerate(resultado.paginas))
