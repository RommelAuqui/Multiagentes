from contextlib import suppress
from functools import partial

import streamlit as st

from db.client import get_client
from db.storage import descargar_archivo, eliminar_archivos, subir_archivo
from rag.ingest import DocumentoPreparado, guardar_fragmentos, preparar_documento
from views.avisos import mostrar_avisos_extraccion

COLUMNAS_CRITERIOS = ["tipo", "descripcion", "referencia", "obligatorio"]


def _tabla_criterios(criterios: list[dict]) -> list[dict]:
    return [{k: c.get(k) for k in COLUMNAS_CRITERIOS} for c in criterios]


def render():
    st.title("Portal del Postor / Participante")

    client = get_client()
    concursos = client.table("concursos").select("*").eq("estado", "abierto").execute().data

    if not concursos:
        st.info("No hay concursos abiertos en este momento.")
        return

    opciones = {c["id"]: c for c in concursos}
    concurso_id_seleccionado = st.selectbox(
        "Concurso al que postulas",
        list(opciones.keys()),
        format_func=lambda cid: opciones[cid]["nombre"],
    )
    concurso = opciones[concurso_id_seleccionado]
    st.caption(concurso.get("descripcion") or "")

    if concurso.get("bases_pdf_path"):
        st.download_button(
            "📄 Descargar Bases Integradas / TDR (.pdf)",
            data=partial(descargar_archivo, concurso["bases_pdf_path"]),
            file_name=f"bases_{concurso['nombre']}.pdf",
            mime="application/pdf",
            on_click="ignore",
        )
    else:
        st.warning("Esta convocatoria todavía no tiene las Bases Integradas disponibles para descarga.")

    criterios = client.table("criterios").select("*").eq("concurso_id", concurso["id"]).execute().data
    if criterios:
        with st.expander(f"Ver requisitos de calificación ({len(criterios)} criterios)"):
            st.caption(
                "Extraídos automáticamente de las Bases. Revisa siempre el PDF completo, "
                "ya que aquí solo se resume el requisito, no el texto legal íntegro."
            )
            st.table(_tabla_criterios(criterios))

    st.markdown(
        "**Formato de presentación:** sube tu Propuesta Técnica y tu CV Documentado, cada "
        "uno como un único archivo PDF, incluyendo todas las Declaraciones Juradas y Anexos "
        "exigidos en las Bases Integradas dentro del mismo documento."
    )

    with st.form("postulacion"):
        ruc = st.text_input("RUC")
        razon_social = st.text_input("Razón Social")
        propuesta_pdf = st.file_uploader("Propuesta Técnica (PDF)", type="pdf")
        cv_pdf = st.file_uploader("CV Documentado (PDF)", type="pdf")
        enviado = st.form_submit_button("Enviar Postulación")

    if not enviado:
        return

    if not ruc or not razon_social or not propuesta_pdf or not cv_pdf:
        st.error("Todos los campos son obligatorios.")
        return

    propuesta_bytes = propuesta_pdf.getvalue()
    cv_bytes = cv_pdf.getvalue()

    # Los documentos se procesan antes de registrar al postor, para no dejar postulaciones sin evidencia.
    try:
        with st.spinner("Leyendo e indexando tus documentos para la evaluación..."):
            propuesta = preparar_documento(propuesta_bytes)
            cv = preparar_documento(cv_bytes)
    except Exception:
        st.error(
            "No se pudieron procesar tus documentos (el PDF podría estar dañado o el servicio de IA "
            "no respondió). Tu postulación no se registró; vuelve a intentarlo."
        )
        return

    mostrar_avisos_extraccion("Propuesta Técnica", propuesta.extraccion)
    mostrar_avisos_extraccion("CV Documentado", cv.extraccion)

    ilegibles = [
        nombre for nombre, documento in (("Propuesta Técnica", propuesta), ("CV Documentado", cv))
        if not documento.fragmentos
    ]
    if ilegibles:
        st.error(
            f"No se pudo leer texto de: {', '.join(ilegibles)}. Verifica que el PDF no esté "
            "protegido o dañado. Tu postulación no se registró."
        )
        return

    try:
        _registrar_postulacion(concurso["id"], ruc, razon_social, propuesta_bytes, cv_bytes, propuesta, cv)
    except Exception:
        st.error("Hubo un problema al registrar tu postulación. No se guardó nada; vuelve a intentarlo.")
        return

    st.success("Postulación registrada correctamente. El comité evaluará tu expediente.")


def _registrar_postulacion(
    concurso_id: str,
    ruc: str,
    razon_social: str,
    propuesta_bytes: bytes,
    cv_bytes: bytes,
    propuesta: DocumentoPreparado,
    cv: DocumentoPreparado,
) -> None:
    client = get_client()
    postor = client.table("postores").insert({
        "concurso_id": concurso_id,
        "ruc": ruc,
        "razon_social": razon_social,
        "estado": "recibido",
    }).execute().data[0]

    propuesta_path = f"postores/{postor['id']}/propuesta.pdf"
    cv_path = f"postores/{postor['id']}/cv.pdf"
    try:
        subir_archivo(propuesta_path, propuesta_bytes)
        subir_archivo(cv_path, cv_bytes)
        client.table("postores").update({
            "propuesta_pdf_path": propuesta_path,
            "cv_pdf_path": cv_path,
        }).eq("id", postor["id"]).execute()
        guardar_fragmentos(concurso_id, postor["id"], "propuesta", propuesta)
        guardar_fragmentos(concurso_id, postor["id"], "cv", cv)
    except Exception:
        with suppress(Exception):
            client.table("postores").delete().eq("id", postor["id"]).execute()
        with suppress(Exception):
            eliminar_archivos([propuesta_path, cv_path])
        raise
