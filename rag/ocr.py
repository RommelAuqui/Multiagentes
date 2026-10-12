import pytesseract
from pdf2image import convert_from_bytes
from pdf2image.exceptions import PDFInfoNotInstalledError, PDFPageCountError, PDFSyntaxError

from config import OCR_DPI, OCR_IDIOMA, POPPLER_PATH, TESSERACT_CMD

if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

ERRORES_OCR = (
    pytesseract.TesseractNotFoundError,
    pytesseract.TesseractError,
    PDFInfoNotInstalledError,
    PDFPageCountError,
    PDFSyntaxError,
)


def ocr_pagina(contenido: bytes, numero_pagina: int) -> str:
    imagenes = convert_from_bytes(
        contenido,
        dpi=OCR_DPI,
        first_page=numero_pagina,
        last_page=numero_pagina,
        poppler_path=POPPLER_PATH or None,
    )
    if not imagenes:
        return ""
    return pytesseract.image_to_string(imagenes[0], lang=OCR_IDIOMA).strip()
