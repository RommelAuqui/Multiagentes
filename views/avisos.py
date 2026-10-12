import streamlit as st

from rag.pdf_extract import ResultadoExtraccion


def _lista_paginas(paginas: list[int]) -> str:
    return ", ".join(str(p) for p in paginas)


def mostrar_avisos_extraccion(documento: str, extraccion: ResultadoExtraccion) -> None:
    if extraccion.paginas_ocr:
        st.info(
            f"{documento}: se aplicó OCR a las páginas {_lista_paginas(extraccion.paginas_ocr)} "
            "porque contenían imágenes escaneadas. El texto reconocido puede tener errores."
        )
    if extraccion.paginas_sin_texto:
        causa = " El servicio de OCR no está disponible." if extraccion.error_ocr else ""
        st.warning(
            f"{documento}: no se pudo leer texto de las páginas "
            f"{_lista_paginas(extraccion.paginas_sin_texto)}.{causa} "
            "Esas páginas no serán consideradas en la evaluación."
        )
