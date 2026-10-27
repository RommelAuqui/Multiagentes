import pytest

from revision import seccion_general as sg
from revision.reglas import CUMPLE, FALLA, NO_VERIFICADO

OFICIAL = sg.texto_oficial("consultoria_obra")
APELACION = "como máximo, dentro de los ocho días hábiles"


def _en_paginas(texto: str, por_pagina: int = 400) -> list[dict]:
    """Reparte el texto en páginas, con encabezado y pie, como sale de un PDF."""
    palabras = texto.split(" ")
    paginas = []
    for n, i in enumerate(range(0, len(palabras), por_pagina), 1):
        cuerpo = " ".join(palabras[i:i + por_pagina])
        paginas.append({"pagina": n, "texto": f"BASES · CONCURSO PÚBLICO N.° CP-01-2026\n{cuerpo}\nPágina {n}"})
    return paginas


def test_la_seccion_general_oficial_cumple():
    estado, descripcion, cambios, _ = sg.revisar(_en_paginas(OFICIAL))
    assert estado == CUMPLE and not cambios
    assert "consultoría de obra" in descripcion and "0005-2025-EF/54.01" in descripcion


def test_la_numeracion_y_las_notas_al_pie_no_son_cambios():
    texto = OFICIAL.replace("REFERENCIAS", "1.1. REFERENCIAS").replace("ALCANCE", "1.2. ALCANCE")
    notas = " ".join(f"{i} {nota}" for i, nota in enumerate(sg.plantilla("consultoria_obra")["notas"], 1))
    texto = texto.replace("CAPÍTULO III", f"{notas}\nCAPÍTULO III", 1)
    assert sg.revisar(_en_paginas(texto))[0] == CUMPLE


def test_detecta_un_plazo_cambiado_con_su_pagina():
    paginas = _en_paginas(OFICIAL.replace(APELACION, "como máximo, dentro de los cinco días hábiles"))
    estado, descripcion, [cambio], citas = sg.revisar(paginas)

    assert estado == FALLA
    assert "cinco" in cambio.bases and "ocho" in cambio.plantilla
    assert "dice «… máximo dentro de los cinco días hábiles" in descripcion
    pagina = next(p["pagina"] for p in paginas if "cinco días hábiles" in p["texto"])
    assert citas == [pagina]


def test_detecta_texto_agregado_y_eliminado():
    consorcios = "Los integrantes de un consorcio se encuentran obligados solidariamente"
    texto = (OFICIAL.replace("Todos los demás aspectos", "La entidad puede exigir requisitos adicionales. "
                                                         "Todos los demás aspectos")
             .replace(consorcios, "Los integrantes de un consorcio"))
    estado, descripcion, cambios, _ = sg.revisar(_en_paginas(texto))

    assert estado == FALLA and len(cambios) == 2
    agregado = next(c for c in cambios if not c.plantilla)
    assert "La entidad puede exigir requisitos adicionales" in agregado.bases
    eliminado = next(c for c in cambios if not c.bases)
    assert "se encuentran obligados solidariamente" in eliminado.plantilla and "se eliminó «" in descripcion


def test_sin_seccion_general_o_sin_plantilla():
    estado, descripcion, _, _ = sg.revisar([{"pagina": 1, "texto": "CAPÍTULO I GENERALIDADES"}])
    assert estado == FALLA and "No se encontró la Sección general" in descripcion

    abreviado = OFICIAL.replace("DEL CONCURSO PÚBLICO", "DEL CONCURSO PÚBLICO ABREVIADO", 1)
    assert sg.revisar(_en_paginas(abreviado))[0] == NO_VERIFICADO


def test_elige_la_plantilla_de_consultoria_en_general():
    estado, descripcion, _, _ = sg.revisar(_en_paginas(sg.texto_oficial("consultoria_general")))
    assert estado == CUMPLE and "consultoría en general" in descripcion


def test_las_bases_de_demostracion_en_pdf():
    pytest.importorskip("reportlab")
    from io import BytesIO

    from pypdf import PdfReader

    from demo.datos import CONVOCATORIAS
    from demo.expediente import EXPEDIENTES
    from demo.generar import generar_bases

    def revisar(convocatoria):
        lector = PdfReader(BytesIO(generar_bases(convocatoria)))
        return sg.revisar([{"pagina": i, "texto": p.extract_text()} for i, p in enumerate(lector.pages, 1)])

    integradas, general = CONVOCATORIAS[4], CONVOCATORIAS[2]
    assert revisar(integradas)[0] == CUMPLE and revisar(general)[0] == CUMPLE
    # Las Bases convocadas de la convocatoria 5 acortan el plazo para apelar (falla sembrada).
    estado, descripcion, _, _ = revisar(EXPEDIENTES[integradas.carpeta].antes(integradas))
    assert estado == FALLA and "cinco días hábiles" in descripcion
