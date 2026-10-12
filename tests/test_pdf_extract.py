from rag.pdf_extract import dividir_en_fragmentos, texto_completo


def test_dividir_en_fragmentos_respeta_tamano_y_pagina():
    paginas = [{"pagina": 1, "texto": "a" * 3200}, {"pagina": 2, "texto": "b" * 10}]
    fragmentos = dividir_en_fragmentos(paginas, max_caracteres=1500)

    assert [(f["pagina"], len(f["contenido"])) for f in fragmentos] == [(1, 1500), (1, 1500), (1, 200), (2, 10)]


def test_texto_completo_marca_paginas():
    assert texto_completo([{"pagina": 3, "texto": "hola"}]) == "[Página 3]\nhola"
