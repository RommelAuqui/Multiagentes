from dataclasses import dataclass

from db.client import get_client
from rag.embeddings import embed_documentos
from rag.pdf_extract import ResultadoExtraccion, dividir_en_fragmentos, extraer_paginas

FILAS_POR_INSERCION = 100


@dataclass
class DocumentoPreparado:
    extraccion: ResultadoExtraccion
    fragmentos: list[dict]


def preparar_documento(contenido: bytes) -> DocumentoPreparado:
    extraccion = extraer_paginas(contenido)
    fragmentos = dividir_en_fragmentos(extraccion.paginas)
    embeddings = embed_documentos([f["contenido"] for f in fragmentos])
    for fragmento, embedding in zip(fragmentos, embeddings):
        fragmento["embedding"] = embedding
    return DocumentoPreparado(extraccion, fragmentos)


def guardar_fragmentos(
    concurso_id: str, postor_id: str | None, origen: str, documento: DocumentoPreparado
) -> None:
    filas = [
        {"concurso_id": concurso_id, "postor_id": postor_id, "origen": origen, **fragmento}
        for fragmento in documento.fragmentos
    ]
    for inicio in range(0, len(filas), FILAS_POR_INSERCION):
        get_client().table("documentos_chunks").insert(filas[inicio:inicio + FILAS_POR_INSERCION]).execute()
