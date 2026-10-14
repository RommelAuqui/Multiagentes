import streamlit as st

from agents.reglas import CALIFICA, CUMPLE, ETAPAS, REQUIERE_REVISION, TIPOS
from rag.pdf_extract import ResultadoExtraccion
from retry_utils import CuotaDiariaAgotada
from theme import badge_html

ICONOS_RESULTADO = {CALIFICA: "🟢", CUMPLE: "🟢", REQUIERE_REVISION: "🟡"}


def ordenar_criterios(criterios: list[dict]) -> list[dict]:
    return sorted(criterios, key=lambda c: (c.get("orden") is None, c.get("orden") or 0))


def tabla_criterios(criterios: list[dict]) -> list[dict]:
    return [{
        "Etapa": ETAPAS.get(c.get("etapa"), ""),
        "Tipo": TIPOS.get(c.get("tipo"), ""),
        "Requisito o factor": c["descripcion"],
        "Acreditación": c.get("acreditacion") or "",
        "Puntaje máx.": f"{float(c['puntaje_maximo']):g}" if c.get("puntaje_maximo") else "",
        "Referencia": c.get("referencia") or "",
    } for c in ordenar_criterios(criterios)]


def badge_resultado(veredicto: str) -> str:
    icono = ICONOS_RESULTADO.get(veredicto, "🔴")
    clase = {"🟢": "ml-badge-cumple", "🟡": "ml-badge-pendiente"}.get(icono, "ml-badge-no-cumple")
    return badge_html(f"{icono} {veredicto}", clase)


def _lista_paginas(paginas: list[int]) -> str:
    return ", ".join(str(p) for p in paginas)


def mostrar_avisos_extraccion(documento: str, extraccion: ResultadoExtraccion) -> None:
    if extraccion.paginas_ia:
        st.info(
            f"{documento}: las páginas {_lista_paginas(extraccion.paginas_ia)} tenían imágenes o "
            "escaneos y se leyeron con IA. Si una cita de esas páginas parece extraña, revisa el PDF original."
        )
    causa = ""
    if extraccion.error_lectura:
        causa = (" Se agotó la cuota diaria de Gemini; vuelve a subir el archivo cuando se renueve."
                 if extraccion.error_lectura.startswith(CuotaDiariaAgotada.__name__)
                 else " El servicio de lectura con IA no respondió.")
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
