from dataclasses import dataclass, field
from io import BytesIO

from pypdf import PdfReader

from rag.ocr import ERRORES_OCR, ocr_pagina

MIN_CARACTERES_TEXTO = 50


@dataclass
class ResultadoExtraccion:
    paginas: list[dict] = field(default_factory=list)
    paginas_ocr: list[int] = field(default_factory=list)
    paginas_sin_texto: list[int] = field(default_factory=list)
    error_ocr: str | None = None


def extraer_paginas(contenido: bytes) -> ResultadoExtraccion:
    reader = PdfReader(BytesIO(contenido))
    resultado = ResultadoExtraccion()

    for numero, pagina in enumerate(reader.pages, start=1):
        texto = (pagina.extract_text() or "").strip()
        usa_ocr = False

        if len(texto) < MIN_CARACTERES_TEXTO:
            try:
                texto_ocr = ocr_pagina(contenido, numero)
            except ERRORES_OCR as e:
                texto_ocr = ""
                resultado.error_ocr = resultado.error_ocr or f"{type(e).__name__}: {e}"
            if len(texto_ocr) > len(texto):
                texto, usa_ocr = texto_ocr, True

        if texto:
            resultado.paginas.append({"pagina": numero, "texto": texto, "ocr": usa_ocr})
            if usa_ocr:
                resultado.paginas_ocr.append(numero)
        else:
            resultado.paginas_sin_texto.append(numero)

    return resultado


def dividir_en_fragmentos(paginas: list[dict], max_caracteres: int = 1500) -> list[dict]:
    fragmentos = []
    for pagina in paginas:
        texto = pagina["texto"]
        for inicio in range(0, len(texto), max_caracteres):
            fragmentos.append({
                "pagina": pagina["pagina"],
                "contenido": texto[inicio:inicio + max_caracteres],
            })
    return fragmentos


def texto_completo(paginas: list[dict]) -> str:
    return "\n\n".join(f"[Página {p['pagina']}]\n{p['texto']}" for p in paginas)
