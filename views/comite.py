from contextlib import suppress
from datetime import datetime, timezone
from functools import partial
from io import BytesIO

import pandas as pd
import streamlit as st

from agents.extractor import MAX_CARACTERES_BASES, extraer_criterios
from agents.gemini_client import ContextoIA
from agents.orchestrator import evaluar_postor
from agents.reglas import (
    DECISIONES_REQUISITO,
    ETAPAS,
    REQUIERE_REVISION,
    TIPOS,
    aplicar_revision,
    calcular_resultado,
    puntaje_efectivo,
    validar_matriz,
    veredicto_efectivo,
)
from db.client import get_client
from db.storage import descargar_archivo, eliminar_archivos, subir_archivo
from rag.pdf_extract import extraer_paginas, texto_completo
from reports.acta import generar_acta, nombre_legible
from reports.matriz import generar_matriz_comparativa
from theme import badge_html
from views.componentes import badge_resultado, mostrar_avisos_extraccion, ordenar_criterios, tabla_criterios

MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ESTADOS = {"borrador": " (en revisión)", "abierto": "", "cerrado": " (cerrada)"}
COLUMNAS_EDITOR = [
    "etapa", "tipo", "descripcion", "acreditacion", "obligatorio", "puntaje_maximo", "asignacion_puntaje", "referencia",
]


# ---------- Mensajes que sobreviven al st.rerun() ----------

def _avisar(tipo: str, mensaje: str) -> None:
    st.session_state.setdefault("avisos_comite", []).append((tipo, mensaje))


def _mostrar_avisos() -> None:
    for tipo, mensaje in st.session_state.pop("avisos_comite", []):
        getattr(st, tipo)(mensaje)


def _numero(valor) -> str:
    return f"{float(valor):g}"


# ---------- Nueva convocatoria ----------

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
    try:
        concurso = _registrar_concurso(nombre, descripcion, contenido)
    except Exception:
        st.error("Hubo un problema al guardar la convocatoria. No se guardó nada; vuelve a intentarlo.")
        return

    criterios = _extraer_matriz(concurso, contenido)
    if criterios:
        st.success(
            f"Convocatoria '{nombre}' guardada en revisión con {len(criterios)} criterios extraídos de las Bases. "
            "Revísalos en «Concursos en Curso» y publícala cuando estén correctos."
        )
        st.table(tabla_criterios(criterios))


def _registrar_concurso(nombre: str, descripcion: str, contenido: bytes) -> dict:
    client = get_client()
    concurso = client.table("concursos").insert({
        "nombre": nombre,
        "descripcion": descripcion,
        "estado": "borrador",
    }).execute().data[0]

    path = f"bases/{concurso['id']}.pdf"
    try:
        subir_archivo(path, contenido)
        client.table("concursos").update({"bases_pdf_path": path}).eq("id", concurso["id"]).execute()
    except Exception:
        with suppress(Exception):
            client.table("concursos").delete().eq("id", concurso["id"]).execute()
        with suppress(Exception):
            eliminar_archivos([path])
        raise

    return {**concurso, "bases_pdf_path": path}


def _extraer_matriz(concurso: dict, contenido: bytes) -> list[dict]:
    aviso_manual = "En «Concursos en Curso» puedes volver a intentarlo o ingresar los criterios a mano."
    try:
        with st.spinner("Leyendo las Bases y armando la matriz de evaluación..."):
            extraccion = extraer_paginas(contenido, ContextoIA("lector", concurso["id"]))
            texto_bases = texto_completo(extraccion.paginas)
            matriz = extraer_criterios(texto_bases, ContextoIA("extractor", concurso["id"])) if extraccion.paginas else None
    except Exception:
        st.warning(
            "La convocatoria se guardó en revisión, pero el Agente Extractor no pudo armar la matriz (el PDF "
            f"podría estar dañado o el servicio de IA no respondió). {aviso_manual}"
        )
        return []

    mostrar_avisos_extraccion("Bases", extraccion)

    if not extraccion.paginas:
        st.warning(f"La convocatoria se guardó en revisión, pero no se pudo leer texto de las Bases. {aviso_manual}")
        return []

    if len(texto_bases) > MAX_CARACTERES_BASES:
        st.warning(
            f"Las Bases son muy extensas: solo se analizaron los primeros {MAX_CARACTERES_BASES:,} "
            "caracteres. Revisa que la matriz incluya todos los requisitos."
        )

    if not matriz.cuadra:
        st.warning(
            f"Los factores extraídos suman {matriz.suma_factores:g} puntos, pero las Bases declaran "
            f"{matriz.puntaje_total:g}. Revisa en la matriz si falta o sobra algún factor antes de publicar."
        )

    if not matriz.criterios:
        st.warning(f"El Agente Extractor no encontró criterios en las Bases. {aviso_manual}")
        return []

    criterios = [{**c, "orden": orden} for orden, c in enumerate(matriz.criterios)]
    _guardar_matriz(concurso["id"], criterios, matriz.puntaje_minimo)
    return criterios


def _guardar_matriz(concurso_id: str, criterios: list[dict], puntaje_minimo: float | None) -> None:
    client = get_client()
    # Se insertan los nuevos antes de borrar los anteriores: si algo falla, no se pierde la matriz previa.
    nuevos = client.table("criterios").insert([{**c, "concurso_id": concurso_id} for c in criterios]).execute().data
    client.table("criterios").delete().eq("concurso_id", concurso_id).not_.in_(
        "id", [c["id"] for c in nuevos]
    ).execute()
    client.table("concursos").update({"puntaje_minimo": puntaje_minimo}).eq("id", concurso_id).execute()


# ---------- Revisión de la matriz (convocatoria en revisión) ----------

def _filas_del_editor(df: pd.DataFrame) -> list[dict]:
    return df.astype(object).where(df.notna(), None).to_dict("records")


def _revisar_matriz(concurso: dict, criterios: list[dict]) -> None:
    st.info(
        "📝 Esta convocatoria está **en revisión**: los postores todavía no la ven. Revisa la matriz que "
        "la IA extrajo de las Bases, corrígela si hace falta (puedes editar, agregar o borrar filas) y publícala. "
        "Después de publicarla, la matriz ya no se puede cambiar."
    )

    df = pd.DataFrame([{
        "etapa": c["etapa"],
        "tipo": c["tipo"],
        "descripcion": c["descripcion"],
        "acreditacion": c.get("acreditacion"),
        "obligatorio": bool(c.get("obligatorio", True)),
        "puntaje_maximo": c.get("puntaje_maximo"),
        "asignacion_puntaje": c.get("asignacion_puntaje"),
        "referencia": c.get("referencia"),
    } for c in ordenar_criterios(criterios)], columns=COLUMNAS_EDITOR)

    editado = st.data_editor(
        df,
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        key=f"matriz_{concurso['id']}",
        column_config={
            "etapa": st.column_config.SelectboxColumn(
                "Etapa", options=list(ETAPAS), format_func=ETAPAS.get, required=True, default="calificacion"
            ),
            "tipo": st.column_config.SelectboxColumn(
                "Agente", options=list(TIPOS), format_func=TIPOS.get, required=True, default="tecnico"
            ),
            "descripcion": st.column_config.TextColumn("Requisito o factor", required=True, width="large"),
            "acreditacion": st.column_config.TextColumn("Acreditación", width="medium"),
            "obligatorio": st.column_config.CheckboxColumn("Obligatorio", default=True),
            "puntaje_maximo": st.column_config.NumberColumn("Puntaje máx.", min_value=0, step=0.5),
            "asignacion_puntaje": st.column_config.TextColumn("Forma de asignar el puntaje", width="large"),
            "referencia": st.column_config.TextColumn("Referencia en las Bases"),
        },
    )
    puntaje_minimo = st.number_input(
        "Puntaje técnico mínimo que fijan las Bases (0 si no hay mínimo)",
        min_value=0.0, value=float(concurso.get("puntaje_minimo") or 0), step=1.0, key=f"minimo_{concurso['id']}",
    )

    nuevos, errores = validar_matriz(_filas_del_editor(editado))
    suma = sum(c["puntaje_maximo"] for c in nuevos if c["etapa"] == "evaluacion")
    st.caption(f"{len(nuevos)} criterios · suma de puntajes de los factores de evaluación: {suma:g}")
    if suma and suma != 100:
        st.warning(f"Los factores suman {suma:g} puntos; en las bases estándar la evaluación técnica suma 100.")

    columnas = st.columns(2)
    guardar = columnas[0].button("💾 Guardar cambios", key=f"guardar_matriz_{concurso['id']}")
    publicar = columnas[1].button("📢 Publicar convocatoria", type="primary", key=f"publicar_{concurso['id']}")
    if guardar or publicar:
        if errores or (publicar and not nuevos):
            for error in errores or ["La matriz está vacía: agrega al menos un criterio antes de publicar."]:
                st.error(error)
            return
        _guardar_matriz(concurso["id"], nuevos, puntaje_minimo or None)
        if publicar:
            get_client().table("concursos").update({"estado": "abierto"}).eq("id", concurso["id"]).execute()
            _avisar("success", f"Convocatoria '{concurso['nombre']}' publicada: ya aparece en el Portal del Postor.")
        else:
            _avisar("success", "Cambios de la matriz guardados.")
        st.rerun()

    if not criterios and concurso.get("bases_pdf_path"):
        if st.button("🔄 Volver a extraer la matriz de las Bases", key=f"reextraer_{concurso['id']}"):
            if _extraer_matriz(concurso, descargar_archivo(concurso["bases_pdf_path"])):
                _avisar("success", "Matriz extraída de las Bases. Revísala antes de publicar.")
                st.rerun()


# ---------- Administración ----------

def _cambiar_estado(concurso: dict, estado: str) -> None:
    get_client().table("concursos").update({"estado": estado}).eq("id", concurso["id"]).execute()
    st.rerun()


def _eliminar_concurso(concurso: dict, postores: list[dict]) -> None:
    archivos = [concurso.get("bases_pdf_path")] + [a["path"] for p in postores for a in _archivos_oferta(p)]
    # Al borrar el concurso se eliminan en cascada criterios, postores, fragmentos, dictámenes y consultas.
    get_client().table("concursos").delete().eq("id", concurso["id"]).execute()
    try:
        eliminar_archivos(archivos)
        _avisar("success", f"Convocatoria '{concurso['nombre']}' eliminada.")
    except Exception:
        _avisar("warning", f"Convocatoria '{concurso['nombre']}' eliminada, pero algunos PDF no se pudieron borrar del Storage.")
    st.rerun()


def _administrar_concurso(concurso: dict, postores: list[dict]) -> None:
    with st.expander("Administrar convocatoria"):
        if concurso["estado"] == "abierto":
            st.write("La convocatoria está **abierta**: los postores pueden enviar sus propuestas.")
            if st.button("🔒 Cerrar postulaciones", key=f"cerrar_{concurso['id']}"):
                _cambiar_estado(concurso, "cerrado")
        elif concurso["estado"] == "cerrado":
            st.write("La convocatoria está **cerrada**: ya no aparece en el Portal del Postor.")
            if st.button("🔓 Reabrir postulaciones", key=f"reabrir_{concurso['id']}"):
                _cambiar_estado(concurso, "abierto")
        else:
            st.write("La convocatoria está **en revisión**: se publica desde la matriz de abajo.")

        st.divider()
        st.write(
            f"Eliminar la convocatoria borra también sus {len(postores)} postulaciones, documentos "
            "y dictámenes. Esta acción no se puede deshacer."
        )
        confirmado = st.checkbox("Entiendo, quiero eliminarla", key=f"confirmar_eliminar_{concurso['id']}")
        if st.button("🗑️ Eliminar convocatoria", disabled=not confirmado, key=f"eliminar_{concurso['id']}"):
            _eliminar_concurso(concurso, postores)


# ---------- Evaluación y revisión del comité ----------

def _evaluar(postores: list[dict]) -> None:
    progreso = st.progress(0.0, text="Los agentes Legal y Técnico están evaluando...")
    for numero, postor in enumerate(postores, start=1):
        try:
            evaluar_postor(postor["id"])
        except Exception as e:
            _avisar("error", f"No se pudo completar la evaluación de {postor['razon_social']}: {e}")
        progreso.progress(numero / len(postores), text=f"Evaluados {numero} de {len(postores)} postores...")
    st.rerun()


def _texto_citas(citas: list[dict]) -> str:
    return "; ".join(
        f"{nombre_legible(c.get('documento')) or 'Documento'}, p. {c.get('pagina')}" for c in citas or []
    )


def _propuesta_ia(fila: dict) -> str:
    if fila["etapa"] == "evaluacion":
        texto = f"{_numero(fila.get('puntaje') or 0)} de {_numero(fila.get('puntaje_maximo') or 0)} puntos"
        return f"{texto} ({REQUIERE_REVISION.lower()})" if fila["veredicto"] == REQUIERE_REVISION else texto
    return fila["veredicto"]


def _decision_del_comite(fila: dict) -> dict:
    marca = "⚠️ " if fila["veredicto"] == REQUIERE_REVISION else ""
    st.markdown(f"{marca}**{fila['criterio_descripcion']}**")
    st.caption(
        f"Propuesta de la IA (Agente {TIPOS.get(fila.get('agente'), '')}): {_propuesta_ia(fila)}. "
        f"{fila.get('justificacion') or ''}"
    )
    if citas := _texto_citas(fila.get("citas")):
        st.caption(f"Citas: {citas}")

    columnas = st.columns([1, 2])
    if fila["etapa"] == "evaluacion":
        maximo = float(fila.get("puntaje_maximo") or 0)
        decision = {"puntaje": columnas[0].number_input(
            "Puntaje del comité", min_value=0.0, max_value=maximo,
            value=min(float(puntaje_efectivo(fila) or 0), maximo), step=0.5, key=f"puntaje_{fila['id']}",
        )}
    else:
        opciones = list(DECISIONES_REQUISITO)
        actual = veredicto_efectivo(fila)
        decision = {"veredicto": columnas[0].selectbox(
            "Decisión del comité", opciones, index=opciones.index(actual) if actual in opciones else None,
            placeholder="Elige...", key=f"veredicto_{fila['id']}",
        )}

    obligatoria = " (obligatoria)" if fila["veredicto"] == REQUIERE_REVISION else " (obligatoria si cambias la propuesta)"
    decision["justificacion"] = columnas[1].text_input(
        f"Justificación del comité{obligatoria}", value=fila.get("justificacion_comite") or "",
        key=f"justificacion_{fila['id']}",
    )
    return decision


def _archivos_oferta(postor: dict) -> list[dict]:
    if postor.get("archivos"):
        return postor["archivos"]
    # Ofertas de la versión anterior: propuesta y CV en columnas fijas.
    return [
        {"nombre": nombre, "path": postor[campo]}
        for campo, nombre in (("propuesta_pdf_path", "Propuesta Técnica.pdf"), ("cv_pdf_path", "CV Documentado.pdf"))
        if postor.get(campo)
    ]


def _descargas_oferta(postor: dict) -> None:
    archivos = _archivos_oferta(postor)
    st.markdown(f"**Oferta del postor ({len(archivos)} archivo(s))**")
    for numero, archivo in enumerate(archivos):
        paginas = f" · {archivo['paginas']} páginas" if archivo.get("paginas") else ""
        st.download_button(
            f"📄 {archivo['nombre']}{paginas}",
            data=partial(descargar_archivo, archivo["path"]),
            file_name=archivo["nombre"],
            mime="application/pdf",
            key=f"oferta_{postor['id']}_{numero}",
            on_click="ignore",
        )


def _revisar_evaluacion(concurso: dict, postor: dict, dictamen: dict, filas: list[dict]) -> None:
    _descargas_oferta(postor)
    st.markdown("**Conciliación del Agente Coordinador**")
    st.write(dictamen.get("justificacion") or "")

    with st.form(f"revision_{postor['id']}"):
        decisiones = {}
        for etapa, nombre in ETAPAS.items():
            de_la_etapa = [f for f in filas if f.get("etapa") == etapa]
            if de_la_etapa:
                st.markdown(f"##### {nombre}")
                for fila in de_la_etapa:
                    decisiones[fila["id"]] = _decision_del_comite(fila)

        observaciones = st.text_area(
            "Observaciones generales del comité (opcional)", value=dictamen.get("justificacion_comite") or "",
            key=f"observaciones_{postor['id']}",
        )
        revisor = st.text_input(
            "Nombre del miembro del comité que revisa", value=dictamen.get("revisado_por") or "",
            key=f"revisor_{postor['id']}",
        )
        enviado = st.form_submit_button("Guardar revisión del comité")

    if enviado:
        _guardar_revision(concurso, postor, dictamen, filas, decisiones, observaciones, revisor)


def _guardar_revision(
    concurso: dict, postor: dict, dictamen: dict, filas: list[dict], decisiones: dict, observaciones: str, revisor: str
) -> None:
    cambios, errores = aplicar_revision(filas, decisiones, revisor)
    if errores:
        for error in errores:
            st.error(error)
        return

    client = get_client()
    firma = {"revisado_por": revisor.strip(), "revisado_en": datetime.now(timezone.utc).isoformat()}
    for cambio in cambios:
        datos = {campo: valor for campo, valor in cambio.items() if campo != "id"}
        client.table("dictamenes").update({**datos, **firma}).eq("id", cambio["id"]).execute()

    por_id = {c["id"]: c for c in cambios}
    resultado = calcular_resultado([{**f, **por_id[f["id"]]} for f in filas], concurso.get("puntaje_minimo"))
    client.table("dictamenes").update({
        "veredicto_comite": resultado["veredicto"],
        "puntaje_comite": resultado["puntaje"],
        "justificacion_comite": observaciones.strip() or None,
        **firma,
    }).eq("id", dictamen["id"]).execute()
    client.table("postores").update({"estado": "revisado"}).eq("id", postor["id"]).execute()

    _avisar("success", f"Revisión del comité guardada: {postor['razon_social']} — {resultado['veredicto']}.")
    st.rerun()


def _tarjeta_postor(concurso: dict, postor: dict, dictamen: dict | None, filas: list[dict]) -> None:
    with st.container(border=True):
        columnas = st.columns([3, 3, 2, 2])
        with columnas[0]:
            st.markdown(f"**{postor['razon_social']}**")
            st.caption(f"RUC {postor['ruc']}")

        if not dictamen:
            with columnas[1]:
                st.markdown(badge_html("⏳ Pendiente", "ml-badge-pendiente"), unsafe_allow_html=True)
            if columnas[2].button("Evaluar", key=f"evaluar_{postor['id']}"):
                _evaluar([postor])
            return

        revisado = bool(dictamen.get("revisado_en"))
        with columnas[1]:
            st.markdown(badge_resultado(veredicto_efectivo(dictamen)), unsafe_allow_html=True)
            if dictamen.get("puntaje_maximo"):
                st.caption(
                    f"Puntaje técnico: {_numero(puntaje_efectivo(dictamen) or 0)} de {_numero(dictamen['puntaje_maximo'])}"
                )
            st.caption(f"✔️ Revisado por {dictamen['revisado_por']}" if revisado else "Propuesta de la IA · falta revisión del comité")
        columnas[2].download_button(
            "Descargar Acta (.docx)",
            data=partial(_acta_docx, concurso, postor, dictamen),
            file_name=f"acta_{postor['ruc']}.docx",
            mime=MIME_DOCX,
            key=f"acta_{postor['id']}",
            on_click="ignore",
        )
        if not revisado and columnas[3].button("Reevaluar", key=f"reevaluar_{postor['id']}"):
            _evaluar([postor])

        with st.expander("Ver detalle y revisión del comité"):
            _revisar_evaluacion(concurso, postor, dictamen, filas)


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
        format_func=lambda cid: opciones[cid]["nombre"] + ESTADOS.get(opciones[cid]["estado"], ""),
    )
    concurso = opciones[concurso_id_seleccionado]

    st.caption(concurso.get("descripcion") or "")

    postores = client.table("postores").select("*").eq("concurso_id", concurso["id"]).execute().data
    criterios = client.table("criterios").select("*").eq("concurso_id", concurso["id"]).execute().data
    _administrar_concurso(concurso, postores)

    if concurso.get("bases_pdf_path"):
        st.download_button(
            "📄 Descargar Bases Integradas (.pdf)",
            data=partial(descargar_archivo, concurso["bases_pdf_path"]),
            file_name=f"bases_{concurso['nombre']}.pdf",
            mime="application/pdf",
            on_click="ignore",
        )

    if concurso["estado"] == "borrador":
        _revisar_matriz(concurso, criterios)
        return

    with st.expander(f"Matriz de evaluación ({len(criterios)} criterios)"):
        if concurso.get("puntaje_minimo"):
            st.caption(f"Puntaje técnico mínimo: {_numero(concurso['puntaje_minimo'])}")
        st.table(tabla_criterios(criterios))

    if not postores:
        st.info("Todavía no hay postores registrados en este concurso.")
        return

    todos = client.table("dictamenes").select("*").eq("concurso_id", concurso["id"]).execute().data
    dictamenes = [d for d in todos if d["agente"] == "coordinador"]
    dictamenes_por_postor = {d["postor_id"]: d for d in dictamenes}

    st.markdown("### Postores")
    pendientes = [p for p in postores if p["id"] not in dictamenes_por_postor]
    if len(pendientes) > 1 and st.button(f"Evaluar los {len(pendientes)} postores pendientes"):
        _evaluar(pendientes)

    for postor in postores:
        filas = [d for d in todos if d["postor_id"] == postor["id"] and d["agente"] != "coordinador"]
        _tarjeta_postor(concurso, postor, dictamenes_por_postor.get(postor["id"]), filas)

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
    return generar_acta(concurso, postor, filas, dictamen)


def render():
    st.title("Portal del Comité / Administrador")
    tab_nuevo, tab_gestion = st.tabs(["Nueva Convocatoria", "Concursos en Curso"])

    with tab_nuevo:
        _crear_concurso()

    with tab_gestion:
        _gestionar_concursos()
