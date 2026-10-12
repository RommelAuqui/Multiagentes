from dataclasses import dataclass

from db.client import get_client
from rag.embeddings import embed_texto
from rag.pdf_extract import ResultadoExtraccion, dividir_en_fragmentos, extraer_paginas


@dataclass
class DocumentoPreparado:
    extraccion: ResultadoExtraccion
    fragmentos: list[dict]


def preparar_documento(contenido: bytes) -> DocumentoPreparado:
    extraccion = extraer_paginas(contenido)
    fragmentos = dividir_en_fragmentos(extraccion.paginas)
    for fragmento in fragmentos:
        fragmento["embedding"] = embed_texto(fragmento["contenido"])
    return DocumentoPreparado(extraccion, fragmentos)


def guardar_fragmentos(
    concurso_id: str, postor_id: str | None, origen: str, documento: DocumentoPreparado
) -> None:
    filas = [
        {"concurso_id": concurso_id, "postor_id": postor_id, "origen": origen, **fragmento}
        for fragmento in documento.fragmentos
    ]
    if filas:
        get_client().table("documentos_chunks").insert(filas).execute()
