import streamlit as st

from agents.extractor import extraer_criterios
from agents.orchestrator import evaluar_postor
from db.client import get_client
from db.storage import descargar_archivo, subir_archivo
from rag.pdf_extract import extraer_paginas, texto_completo
from reports.acta import generar_acta
from reports.matriz import generar_matriz_comparativa
from theme import badge_html
from views.avisos import mostrar_avisos_extraccion

COLUMNAS_CRITERIOS = ["tipo", "descripcion", "referencia", "obligatorio"]


def _tabla_criterios(criterios: list[dict]) -> list[dict]:
    return [{k: c.get(k) for k in COLUMNAS_CRITERIOS} for c in criterios]


def _crear_concurso():
    st.subheader("Nueva Convocatoria")

    with st.form("nuevo_concurso"):
        nombre = st.text_input("Nombre del concurso")
        descripcion = st.text_area("Descripción")
        bases_pdf = st.file_uploader("Bases Integradas / TDR (PDF)", type="pdf")
        enviado = st.form_submit_button("Crear convocatoria")

    if not enviado:
        return

    if not nombre or not bases_pdf:
        st.error("El nombre y las bases en PDF son obligatorios.")
        return

    client = get_client()
    concurso = client.table("concursos").insert({
        "nombre": nombre,
        "descripcion": descripcion,
        "estado": "abierto",
    }).execute().data[0]

    contenido = bases_pdf.getvalue()
    path = f"bases/{concurso['id']}.pdf"
    subir_archivo(path, contenido)
    client.table("concursos").update({"bases_pdf_path": path}).eq("id", concurso["id"]).execute()

    try:
        with st.spinner("Leyendo las Bases y generando la matriz de requisitos..."):
            extraccion = extraer_paginas(contenido)
            criterios = (
                extraer_criterios(texto_completo(extraccion.paginas)) if extraccion.paginas else []
            )
    except Exception:
        st.error(
            f"La convocatoria '{nombre}' se creó, pero el Agente Extractor no pudo generar "
            "la matriz de requisitos (el PDF podría estar dañado o el servicio de IA no "
            "respondió). Puedes eliminar esta convocatoria y volver a intentarlo."
        )
        return

    mostrar_avisos_extraccion("Bases", extraccion)

    if not extraccion.paginas:
        st.error(
            f"La convocatoria '{nombre}' se creó, pero no se pudo leer texto de las Bases. "
            "Verifica que el PDF no esté protegido o dañado, y vuelve a intentarlo."
        )
        return

    if criterios:
        client.table("criterios").insert([
            {**c, "concurso_id": concurso["id"]} for c in criterios
        ]).execute()

    st.success(f"Convocatoria '{nombre}' creada con {len(criterios)} criterios extraídos.")
    st.table(_tabla_criterios(criterios))


def _badge_veredicto(veredicto: str) -> str:
    if veredicto == "Cumple":
        return badge_html("🟢 Cumple", "ml-badge-cumple")
    return badge_html("🔴 No Cumple", "ml-badge-no-cumple")


def _gestionar_concursos():
    st.subheader("Gestión de Concursos")

    client = get_client()
    concursos = client.table("concursos").select("*").order("created_at", desc=True).execute().data

    if not concursos:
        st.info("Aún no hay concursos creados.")
        return

    opciones = {c["id"]: c for c in concursos}
    concurso_id_seleccionado = st.selectbox(
        "Selecciona un concurso",
        list(opciones.keys()),
        format_func=lambda cid: opciones[cid]["nombre"],
    )
    concurso = opciones[concurso_id_seleccionado]

    st.caption(concurso.get("descripcion") or "")

    if concurso.get("bases_pdf_path"):
        bases_pdf_bytes = descargar_archivo(concurso["bases_pdf_path"])
        st.download_button(
            "📄 Descargar Bases Integradas (.pdf)",
            data=bases_pdf_bytes,
            file_name=f"bases_{concurso['nombre']}.pdf",
            mime="application/pdf",
        )

    criterios = client.table("criterios").select("*").eq("concurso_id", concurso["id"]).execute().data
    with st.expander(f"Matriz de requisitos ({len(criterios)} criterios)"):
        st.table(_tabla_criterios(criterios))

    postores = client.table("postores").select("*").eq("concurso_id", concurso["id"]).execute().data

    if not postores:
        st.info("Todavía no hay postores registrados en este concurso.")
        return

    dictamenes = (
        client.table("dictamenes")
        .select("*")
        .eq("concurso_id", concurso["id"])
        .eq("agente", "coordinador")
        .execute()
        .data
    )
    dictamenes_por_postor = {d["postor_id"]: d for d in dictamenes}

    st.markdown("### Postores")
    for postor in postores:
        dictamen = dictamenes_por_postor.get(postor["id"])

        with st.container(border=True):
            columnas = st.columns([3, 2, 2, 2])
            with columnas[0]:
                st.markdown(f"**{postor['razon_social']}**")
                st.caption(f"RUC {postor['ruc']}")

            if dictamen:
                with columnas[1]:
                    st.markdown(_badge_veredicto(dictamen["veredicto"]), unsafe_allow_html=True)
                columnas[2].write(f"Puntaje: {dictamen['puntaje']}")
                if columnas[3].button("Ver / Descargar Acta", key=f"acta_{postor['id']}"):
                    st.session_state["postor_para_acta"] = postor["id"]
            else:
                with columnas[1]:
                    st.markdown(badge_html("⏳ Pendiente", "ml-badge-pendiente"), unsafe_allow_html=True)
                if columnas[2].button("Evaluar", key=f"evaluar_{postor['id']}"):
                    with st.spinner("Los agentes Legal y Técnico están deliberando..."):
                        evaluar_postor(postor["id"])
                    st.rerun()

    postor_id_acta = st.session_state.get("postor_para_acta")
    postor_acta = next((p for p in postores if p["id"] == postor_id_acta), None)

    if postor_id_acta and not postor_acta:
        del st.session_state["postor_para_acta"]

    if postor_acta:
        postor_id = postor_id_acta
        postor = postor_acta

        legal_rows = (
            client.table("dictamenes")
            .select("*")
            .eq("postor_id", postor_id)
            .eq("agente", "legal")
            .execute()
            .data
        )
        tecnico_rows = (
            client.table("dictamenes")
            .select("*")
            .eq("postor_id", postor_id)
            .eq("agente", "tecnico")
            .execute()
            .data
        )
        resultado = {
            "resultados_legal": legal_rows,
            "resultados_tecnico": tecnico_rows,
            "dictamen": dictamenes_por_postor[postor_id],
        }
        acta = generar_acta(concurso, postor, resultado)
        st.download_button(
            "Descargar Acta de Dictamen (.docx)",
            data=acta,
            file_name=f"acta_{postor['ruc']}.docx",
        )

    st.markdown("### Matriz Comparativa")
    matriz = generar_matriz_comparativa(concurso["id"])
    st.download_button(
        "Descargar Matriz Comparativa (.xlsx)",
        data=matriz,
        file_name=f"matriz_{concurso['nombre']}.xlsx",
    )


def render():
    st.title("Portal del Comité / Administrador")
    tab_nuevo, tab_gestion = st.tabs(["Nueva Convocatoria", "Concursos en Curso"])

    with tab_nuevo:
        _crear_concurso()

    with tab_gestion:
        _gestionar_concursos()
