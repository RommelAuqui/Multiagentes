from contextlib import suppress
from functools import partial
from io import BytesIO

import streamlit as st

from agents.extractor import MAX_CARACTERES_BASES, extraer_criterios
from agents.gemini_client import ContextoIA
from agents.orchestrator import evaluar_postor
from db.client import get_client
from db.storage import descargar_archivo, eliminar_archivos, subir_archivo
from rag.pdf_extract import extraer_paginas, texto_completo
from reports.acta import generar_acta
from reports.matriz import generar_matriz_comparativa
from theme import badge_html
from views.componentes import mostrar_avisos_extraccion, tabla_criterios

MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


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

    contenido = bases_pdf.getvalue()

    # Primero se analiza el PDF: la convocatoria solo se guarda si se obtuvo la matriz de requisitos.
    try:
        with st.spinner("Leyendo las Bases y generando la matriz de requisitos..."):
            extraccion = extraer_paginas(contenido, ContextoIA("lector"))
            texto_bases = texto_completo(extraccion.paginas)
            criterios = extraer_criterios(texto_bases, ContextoIA("extractor")) if extraccion.paginas else []
    except Exception:
        st.error(
            "El Agente Extractor no pudo generar la matriz de requisitos (el PDF podría estar "
            "dañado o el servicio de IA no respondió). La convocatoria no se creó; vuelve a intentarlo."
        )
        return

    mostrar_avisos_extraccion("Bases", extraccion)

    if not extraccion.paginas:
        st.error(
            "No se pudo leer texto de las Bases. Verifica que el PDF no esté protegido o dañado. "
            "La convocatoria no se creó."
        )
        return

    if len(texto_bases) > MAX_CARACTERES_BASES:
        st.warning(
            f"Las Bases son muy extensas: solo se analizaron los primeros {MAX_CARACTERES_BASES:,} "
            "caracteres. Revisa que la matriz incluya todos los requisitos."
        )

    if not criterios:
        st.error(
            "El Agente Extractor no encontró criterios de evaluación en las Bases. "
            "La convocatoria no se creó."
        )
        return

    try:
        _registrar_concurso(nombre, descripcion, contenido, criterios)
    except Exception:
        st.error("Hubo un problema al guardar la convocatoria. No se guardó nada; vuelve a intentarlo.")
        return

    st.success(f"Convocatoria '{nombre}' creada con {len(criterios)} criterios extraídos.")
    st.table(tabla_criterios(criterios))


def _registrar_concurso(nombre: str, descripcion: str, contenido: bytes, criterios: list[dict]) -> dict:
    client = get_client()
    concurso = client.table("concursos").insert({
        "nombre": nombre,
        "descripcion": descripcion,
        "estado": "abierto",
    }).execute().data[0]

    path = f"bases/{concurso['id']}.pdf"
    try:
        subir_archivo(path, contenido)
        client.table("concursos").update({"bases_pdf_path": path}).eq("id", concurso["id"]).execute()
        client.table("criterios").insert([
            {**c, "concurso_id": concurso["id"]} for c in criterios
        ]).execute()
    except Exception:
        with suppress(Exception):
            client.table("concursos").delete().eq("id", concurso["id"]).execute()
        with suppress(Exception):
            eliminar_archivos([path])
        raise

    return concurso


def _avisar(tipo: str, mensaje: str) -> None:
    # Mensajes que deben sobrevivir al st.rerun() posterior a una acción.
    st.session_state.setdefault("avisos_comite", []).append((tipo, mensaje))


def _mostrar_avisos() -> None:
    for tipo, mensaje in st.session_state.pop("avisos_comite", []):
        getattr(st, tipo)(mensaje)


def _evaluar(postores: list[dict]) -> None:
    progreso = st.progress(0.0, text="Los agentes Legal y Técnico están deliberando...")
    for numero, postor in enumerate(postores, start=1):
        try:
            evaluar_postor(postor["id"])
        except Exception as e:
            _avisar("error", f"No se pudo completar la evaluación de {postor['razon_social']}: {e}")
        progreso.progress(numero / len(postores), text=f"Evaluados {numero} de {len(postores)} postores...")
    st.rerun()


def _cambiar_estado(concurso: dict, estado: str) -> None:
    get_client().table("concursos").update({"estado": estado}).eq("id", concurso["id"]).execute()
    st.rerun()


def _eliminar_concurso(concurso: dict, postores: list[dict]) -> None:
    archivos = [concurso.get("bases_pdf_path")] + [
        p.get(campo) for p in postores for campo in ("propuesta_pdf_path", "cv_pdf_path")
    ]
    # Al borrar el concurso se eliminan en cascada criterios, postores, fragmentos y dictámenes.
    get_client().table("concursos").delete().eq("id", concurso["id"]).execute()
    try:
        eliminar_archivos(archivos)
        _avisar("success", f"Convocatoria '{concurso['nombre']}' eliminada.")
    except Exception:
        _avisar("warning", f"Convocatoria '{concurso['nombre']}' eliminada, pero algunos PDF no se pudieron borrar del Storage.")
    st.rerun()


def _administrar_concurso(concurso: dict, postores: list[dict]) -> None:
    abierto = concurso["estado"] == "abierto"
    with st.expander("Administrar convocatoria"):
        if abierto:
            st.write("La convocatoria está **abierta**: los postores pueden enviar sus propuestas.")
            if st.button("🔒 Cerrar postulaciones", key=f"cerrar_{concurso['id']}"):
                _cambiar_estado(concurso, "cerrado")
        else:
            st.write("La convocatoria está **cerrada**: ya no aparece en el Portal del Postor.")
            if st.button("🔓 Reabrir postulaciones", key=f"reabrir_{concurso['id']}"):
                _cambiar_estado(concurso, "abierto")

        st.divider()
        st.write(
            f"Eliminar la convocatoria borra también sus {len(postores)} postulaciones, documentos "
            "y dictámenes. Esta acción no se puede deshacer."
        )
        confirmado = st.checkbox("Entiendo, quiero eliminarla", key=f"confirmar_eliminar_{concurso['id']}")
        if st.button("🗑️ Eliminar convocatoria", disabled=not confirmado, key=f"eliminar_{concurso['id']}"):
            _eliminar_concurso(concurso, postores)


def _badge_veredicto(veredicto: str) -> str:
    if veredicto == "Cumple":
        return badge_html("🟢 Cumple", "ml-badge-cumple")
    return badge_html("🔴 No Cumple", "ml-badge-no-cumple")


def _gestionar_concursos():
    st.subheader("Gestión de Concursos")
    _mostrar_avisos()

    client = get_client()
    concursos = client.table("concursos").select("*").order("created_at", desc=True).execute().data

    if not concursos:
        st.info("Aún no hay concursos creados.")
        return

    opciones = {c["id"]: c for c in concursos}
    concurso_id_seleccionado = st.selectbox(
        "Selecciona un concurso",
        list(opciones.keys()),
        format_func=lambda cid: opciones[cid]["nombre"] + (
            "" if opciones[cid]["estado"] == "abierto" else " (cerrada)"
        ),
    )
    concurso = opciones[concurso_id_seleccionado]

    st.caption(concurso.get("descripcion") or "")

    postores = client.table("postores").select("*").eq("concurso_id", concurso["id"]).execute().data
    _administrar_concurso(concurso, postores)

    if concurso.get("bases_pdf_path"):
        st.download_button(
            "📄 Descargar Bases Integradas (.pdf)",
            data=partial(descargar_archivo, concurso["bases_pdf_path"]),
            file_name=f"bases_{concurso['nombre']}.pdf",
            mime="application/pdf",
            on_click="ignore",
        )

    criterios = client.table("criterios").select("*").eq("concurso_id", concurso["id"]).execute().data
    with st.expander(f"Matriz de requisitos ({len(criterios)} criterios)"):
        st.table(tabla_criterios(criterios))

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
    pendientes = [p for p in postores if p["id"] not in dictamenes_por_postor]
    if len(pendientes) > 1 and st.button(f"Evaluar los {len(pendientes)} postores pendientes"):
        _evaluar(pendientes)

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
                    st.caption(f"Puntaje técnico: {dictamen['puntaje']}")
                columnas[2].download_button(
                    "Descargar Acta (.docx)",
                    data=partial(_acta_docx, concurso, postor, dictamen),
                    file_name=f"acta_{postor['ruc']}.docx",
                    mime=MIME_DOCX,
                    key=f"acta_{postor['id']}",
                    on_click="ignore",
                )
                if columnas[3].button("Reevaluar", key=f"reevaluar_{postor['id']}"):
                    _evaluar([postor])
            else:
                with columnas[1]:
                    st.markdown(badge_html("⏳ Pendiente", "ml-badge-pendiente"), unsafe_allow_html=True)
                if columnas[2].button("Evaluar", key=f"evaluar_{postor['id']}"):
                    _evaluar([postor])

    st.markdown("### Matriz Comparativa")
    st.download_button(
        "Descargar Matriz Comparativa (.xlsx)",
        data=partial(generar_matriz_comparativa, postores, dictamenes),
        file_name=f"matriz_{concurso['nombre']}.xlsx",
        mime=MIME_XLSX,
        on_click="ignore",
    )


def _acta_docx(concurso: dict, postor: dict, dictamen: dict) -> BytesIO:
    filas = (
        get_client().table("dictamenes")
        .select("*")
        .eq("postor_id", postor["id"])
        .in_("agente", ["legal", "tecnico"])
        .execute()
        .data
    )
    return generar_acta(concurso, postor, {
        "resultados_legal": [f for f in filas if f["agente"] == "legal"],
        "resultados_tecnico": [f for f in filas if f["agente"] == "tecnico"],
        "dictamen": dictamen,
    })


def render():
    st.title("Portal del Comité / Administrador")
    tab_nuevo, tab_gestion = st.tabs(["Nueva Convocatoria", "Concursos en Curso"])

    with tab_nuevo:
        _crear_concurso()

    with tab_gestion:
        _gestionar_concursos()
