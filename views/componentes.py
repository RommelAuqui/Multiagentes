import streamlit as st

from rag.pdf_extract import ResultadoExtraccion

COLUMNAS_CRITERIOS = ["tipo", "descripcion", "referencia", "obligatorio"]


def tabla_criterios(criterios: list[dict]) -> list[dict]:
    return [{k: c.get(k) for k in COLUMNAS_CRITERIOS} for c in criterios]


def _lista_paginas(paginas: list[int]) -> str:
    return ", ".join(str(p) for p in paginas)


def mostrar_avisos_extraccion(documento: str, extraccion: ResultadoExtraccion) -> None:
    if extraccion.paginas_ia:
        st.info(
            f"{documento}: las páginas {_lista_paginas(extraccion.paginas_ia)} tenían imágenes o "
            "escaneos y se leyeron con IA. Si una cita de esas páginas parece extraña, revisa el PDF original."
        )
    causa = " El servicio de lectura con IA no respondió." if extraccion.error_lectura else ""
    if extraccion.paginas_imagen_sin_leer:
        st.warning(
            f"{documento}: no se pudieron leer las imágenes de las páginas "
            f"{_lista_paginas(extraccion.paginas_imagen_sin_leer)}.{causa} Solo se usará su texto."
        )
    if extraccion.paginas_sin_texto:
        st.warning(
            f"{documento}: no se pudo leer texto de las páginas "
            f"{_lista_paginas(extraccion.paginas_sin_texto)}.{causa} "
            "Esas páginas no serán consideradas en la evaluación."
        )
