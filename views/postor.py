import streamlit as st

from db.client import get_client
from db.storage import descargar_archivo, subir_archivo
from rag.ingest import indexar_documento
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
        bases_pdf_bytes = descargar_archivo(concurso["bases_pdf_path"])
        st.download_button(
            "📄 Descargar Bases Integradas / TDR (.pdf)",
            data=bases_pdf_bytes,
            file_name=f"bases_{concurso['nombre']}.pdf",
            mime="application/pdf",
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

    postor = client.table("postores").insert({
        "concurso_id": concurso["id"],
        "ruc": ruc,
        "razon_social": razon_social,
        "estado": "recibido",
    }).execute().data[0]

    propuesta_bytes = propuesta_pdf.getvalue()
    cv_bytes = cv_pdf.getvalue()

    propuesta_path = f"postores/{postor['id']}/propuesta.pdf"
    cv_path = f"postores/{postor['id']}/cv.pdf"
    subir_archivo(propuesta_path, propuesta_bytes)
    subir_archivo(cv_path, cv_bytes)

    client.table("postores").update({
        "propuesta_pdf_path": propuesta_path,
        "cv_pdf_path": cv_path,
    }).eq("id", postor["id"]).execute()

    try:
        with st.spinner("Leyendo e indexando tus documentos para la evaluación..."):
            extraccion_propuesta = indexar_documento(concurso["id"], postor["id"], "propuesta", propuesta_bytes)
            extraccion_cv = indexar_documento(concurso["id"], postor["id"], "cv", cv_bytes)
    except Exception:
        st.error(
            "Tu postulación se registró, pero hubo un problema al procesar tus documentos. "
            "Por favor contacta al comité para confirmar que tus archivos se recibieron correctamente."
        )
        return

    mostrar_avisos_extraccion("Propuesta Técnica", extraccion_propuesta)
    mostrar_avisos_extraccion("CV Documentado", extraccion_cv)

    st.success("Postulación registrada correctamente. El comité evaluará tu expediente.")
