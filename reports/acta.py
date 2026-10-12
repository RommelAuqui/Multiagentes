from io import BytesIO

from docx import Document

NOMBRES_DOCUMENTO = {"propuesta": "Propuesta Técnica", "cv": "CV Documentado"}


def _texto_cita(cita: dict) -> str:
    documento = NOMBRES_DOCUMENTO.get(cita.get("documento"))
    ubicacion = f"{documento}, página {cita.get('pagina')}" if documento else f"Página {cita.get('pagina')}"
    return f"{ubicacion}: {cita.get('extracto', '')}"


def generar_acta(concurso: dict, postor: dict, resultado_evaluacion: dict) -> BytesIO:
    dictamen = resultado_evaluacion["dictamen"]

    doc = Document()
    doc.add_heading("Acta de Dictamen Técnico", level=1)
    doc.add_paragraph(f"Concurso: {concurso['nombre']}")
    doc.add_paragraph(f"Postor: {postor['razon_social']} (RUC {postor['ruc']})")
    doc.add_paragraph(f"Veredicto final: {dictamen['veredicto']}")
    doc.add_paragraph(f"Puntaje técnico: {dictamen['puntaje']}")
    doc.add_paragraph(dictamen["justificacion"])

    doc.add_heading("Evaluación Legal", level=2)
    for r in resultado_evaluacion["resultados_legal"]:
        doc.add_paragraph(f"{r['criterio_descripcion']} — {r['veredicto']}")
        doc.add_paragraph(r["justificacion"])

    doc.add_heading("Evaluación Técnica", level=2)
    for r in resultado_evaluacion["resultados_tecnico"]:
        doc.add_paragraph(f"{r['criterio_descripcion']} — {r['veredicto']}")
        doc.add_paragraph(r["justificacion"])

    doc.add_heading("Citas y Trazabilidad", level=2)
    for cita in dictamen.get("citas") or []:
        doc.add_paragraph(_texto_cita(cita))

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer
