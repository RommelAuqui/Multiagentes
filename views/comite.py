from contextlib import suppress
from datetime import datetime, time, timezone
from functools import partial
from io import BytesIO

import pandas as pd
import streamlit as st

import bitacora
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
from automatizacion import evaluar_registrando
from bitacora import MODULO_CONVOCATORIA, MODULO_REVISION
from config import LIMITE_DIARIO_CONSULTAS, REVISION_BASES
from consumo import ZONA_HORARIA, consultas_de_hoy, consumo_por_postor, hay_cupo
from db.client import get_client
from db.storage import descargar_archivo, eliminar_archivos, subir_archivo
from rag.pdf_extract import extraer_paginas, texto_completo
from reports.acta import generar_acta, nombre_legible
from reports.matriz import generar_matriz_comparativa
from revision import servicio as revision_servicio
from revision.catalogo import CRITICO, RONDA_A, RONDA_B
from rag.pdf_extract import ResultadoExtraccion
from theme import badge_html
from views import revision_bases
from views.componentes import badge_resultado, mostrar_avisos_extraccion, ordenar_criterios, tabla_criterios

MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ESTADOS = {"revision_bases": " (revisión de Bases)", "bases_revisadas": " (Bases revisadas)", "borrador": " (en revisión)",
           "abierto": "", "cerrado": " (cerrada)"}
MODULO_1 = "Módulo 1 · Revisión de Bases"
MODULO_2 = "Módulo 2 · Convocatoria y evaluación"
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


# ---------- Módulo 1: nueva revisión de Bases ----------

def _crear_revision():
    st.subheader("Nueva revisión de Bases")
    st.caption("En «Revisiones en curso» subirás el expediente y las Bases (ronda A) y luego el pliego y las Bases "
               "Integradas (ronda B). El resultado son unas Bases Integradas revisadas, listas para el módulo 2.")
    with st.form("nueva_revision"):
        nombre = st.text_input("Nombre del concurso")
        descripcion = st.text_area("Descripción")
        enviado = st.form_submit_button("Iniciar revisión de Bases")
    if not enviado:
        return
    if not nombre:
        st.error("El nombre es obligatorio.")
        return
    get_client().table("concursos").insert({
        "nombre": nombre, "descripcion": descripcion, "estado": "revision_bases", "ronda_revision": RONDA_A,
    }).execute()
    st.success(f"Revisión de '{nombre}' iniciada. Continúa en «Revisiones en curso».")


# ---------- Módulo 2: nueva convocatoria ----------

def _crear_desde_revision():
    """La convocatoria toma las Bases Integradas revisadas en el módulo 1: con el texto ya leído (sin volver a
    gastar en el Lector), el Agente Extractor arma la matriz."""
    client = get_client()
    revisadas = client.table("concursos").select("*").eq("estado", "bases_revisadas").execute().data
    if not revisadas:
        st.info("No hay revisiones de Bases terminadas esperando convocatoria. Termina una en el módulo 1 o sube "
                "directamente las Bases Integradas.")
        return
    opciones = {c["id"]: c for c in revisadas}
    elegida = st.selectbox("Revisión de Bases terminada", list(opciones), format_func=lambda cid: opciones[cid]["nombre"],
                           key="revision_para_convocar")
    concurso = opciones[elegida]
    if not st.button("Crear la convocatoria y armar la matriz", type="primary"):
        return
    documento = revision_servicio.bases_de_la_ronda(concurso["id"], RONDA_B)
    client.table("concursos").update({"bases_pdf_path": documento["path"], "estado": "borrador"}).eq(
        "id", concurso["id"]).execute()
    bitacora.registrar(concurso["id"], MODULO_CONVOCATORIA,
                       "Se creó la convocatoria con las Bases Integradas revisadas en el módulo 1")
    paginas = documento.get("paginas") or []
    criterios = _extraer_matriz(concurso, b"", ResultadoExtraccion(total_paginas=len(paginas), paginas=paginas))
    if criterios:
        st.success(f"Convocatoria creada. La matriz tiene {len(criterios)} criterios: revísala y publícala en "
                   "«Convocatorias en curso».")
    st.button("Ver la matriz", key=f"ver_matriz_{concurso['id']}")


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

    bitacora.registrar(concurso["id"], MODULO_CONVOCATORIA, "Se creó la convocatoria subiendo las Bases Integradas")
    criterios = _extraer_matriz(concurso, contenido)
    if criterios:
        st.success(
            f"Convocatoria '{nombre}' guardada en revisión con {len(criterios)} criterios extraídos de las Bases. "
            "Revísalos en «Convocatorias en curso» y publícala cuando estén correctos."
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


def _extraer_matriz(concurso: dict, contenido: bytes, extraccion: ResultadoExtraccion | None = None) -> list[dict]:
    """Lee las Bases (salvo que ya se hayan leído) y arma la matriz con el Agente Extractor."""
    aviso_manual = "En «Concursos en Curso» puedes volver a intentarlo o ingresar los criterios a mano."
    try:
        with st.spinner("Leyendo las Bases y armando la matriz de evaluación..."):
            extraccion = extraccion or extraer_paginas(contenido, ContextoIA("lector", concurso["id"]))
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


def _terminar_revision(concurso: dict, documento: dict) -> None:
    """Cierra el módulo 1: su resultado son las Bases Integradas revisadas, que el módulo 2 toma para convocar."""
    get_client().table("concursos").update({"bases_pdf_path": documento["path"], "estado": "bases_revisadas"}).eq(
        "id", concurso["id"]).execute()
    bitacora.registrar(concurso["id"], MODULO_REVISION,
                       "Se cerró la revisión de Bases: las Bases Integradas quedaron revisadas")
    _avisar("success", f"Revisión de Bases de '{concurso['nombre']}' terminada. Su resultado está en «Revisiones "
                       "terminadas» y sus Bases Integradas ya se pueden convocar en el módulo 2.")
    st.rerun()


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
            bitacora.registrar(concurso["id"], MODULO_CONVOCATORIA, "Se publicó la convocatoria con su matriz")
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
    accion = "Se cerraron las postulaciones" if estado == "cerrado" else "Se reabrieron las postulaciones"
    bitacora.registrar(concurso["id"], MODULO_CONVOCATORIA, accion)
    st.rerun()


def _eliminar_concurso(concurso: dict, postores: list[dict]) -> None:
    client = get_client()
    expediente = []
    # La tabla existe desde el módulo de revisión de Bases: si aún no se creó en Supabase, no hay nada que borrar.
    with suppress(Exception):
        expediente = client.table("documentos_expediente").select("path").eq("concurso_id", concurso["id"]).execute().data
    archivos = ([concurso.get("bases_pdf_path")] + [a["path"] for p in postores for a in _archivos_oferta(p)]
                + [d["path"] for d in expediente])
    # Al borrar el concurso se eliminan en cascada criterios, postores, fragmentos, dictámenes, consultas y la
    # revisión de Bases (documentos, revisiones y hallazgos).
    client.table("concursos").delete().eq("id", concurso["id"]).execute()
    try:
        eliminar_archivos(archivos)
        _avisar("success", f"Convocatoria '{concurso['nombre']}' eliminada.")
    except Exception:
        _avisar("warning", f"Convocatoria '{concurso['nombre']}' eliminada, pero algunos PDF no se pudieron borrar del Storage.")
    st.rerun()


def _fecha_local(valor: str | None) -> datetime | None:
    return datetime.fromisoformat(valor).astimezone(ZONA_HORARIA) if valor else None


def _programar(concurso: dict) -> None:
    st.markdown("**Cierre y evaluación automática**")
    cierre = _fecha_local(concurso.get("fecha_cierre"))
    with st.form(f"programacion_{concurso['id']}"):
        columnas = st.columns(2)
        dia = columnas[0].date_input(
            "Fecha de cierre", value=cierre.date() if cierre else None, format="DD/MM/YYYY", key=f"dia_{concurso['id']}",
        )
        hora = columnas[1].time_input(
            "Hora de cierre (hora de Lima)", value=cierre.time() if cierre else time(18, 0), key=f"hora_{concurso['id']}",
        )
        automatica = st.checkbox(
            "Evaluar automáticamente a los postores cuando se cierre la convocatoria",
            value=bool(concurso.get("evaluacion_automatica")), key=f"automatica_{concurso['id']}",
        )
        guardar = st.form_submit_button("Guardar programación")

    if guardar:
        fecha = datetime.combine(dia, hora, tzinfo=ZONA_HORARIA).astimezone(timezone.utc).isoformat() if dia else None
        get_client().table("concursos").update({
            "fecha_cierre": fecha, "evaluacion_automatica": automatica,
        }).eq("id", concurso["id"]).execute()
        _avisar("success", "Programación guardada.")
        st.rerun()

    cierre_texto = f"se cierra el {cierre:%d/%m/%Y a las %H:%M}" if cierre else "sin fecha de cierre (se cierra a mano)"
    automatica_texto = (
        f"los postores se evalúan solos al cerrarse (revisión cada hora, máximo {LIMITE_DIARIO_CONSULTAS} "
        "consultas a la IA por día)" if concurso.get("evaluacion_automatica") else "la evaluación se hace con el botón «Evaluar»"
    )
    st.caption(f"La convocatoria {cierre_texto}; {automatica_texto}.")


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
        _programar(concurso)

        st.divider()
        st.write(
            f"Eliminar la convocatoria borra también sus {len(postores)} postulaciones, documentos "
            "y dictámenes. Esta acción no se puede deshacer."
        )
        confirmado = st.checkbox("Entiendo, quiero eliminarla", key=f"confirmar_eliminar_{concurso['id']}")
        if st.button("🗑️ Eliminar convocatoria", disabled=not confirmado, key=f"eliminar_{concurso['id']}"):
            _eliminar_concurso(concurso, postores)


# ---------- Evaluación y revisión del comité ----------

def _evaluar(postores: list[dict], criterios: int) -> None:
    progreso = st.progress(0.0, text="Los agentes Legal y Técnico están evaluando...")
    for numero, postor in enumerate(postores, start=1):
        if not hay_cupo(criterios):
            _avisar("warning", (
                f"Se alcanzó el límite diario de {LIMITE_DIARIO_CONSULTAS} consultas a la IA: los postores restantes "
                "quedan pendientes hasta mañana. El límite se cambia con LIMITE_DIARIO_CONSULTAS."
            ))
            break
        try:
            evaluar_registrando(postor, evaluar_postor)
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
    if pasos := fila.get("pasos"):
        st.caption("🔎 Cómo llegó el agente: " + " → ".join(p["resumen"] for p in pasos))

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
    for paso in dictamen.get("pasos") or []:
        st.caption(f"🔁 {paso['resumen']}")

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


def _estado_sin_dictamen(postor: dict) -> None:
    if postor.get("estado") == "evaluando":
        st.markdown(badge_html("⏳ Evaluando…", "ml-badge-pendiente"), unsafe_allow_html=True)
        if inicio := _fecha_local(postor.get("evaluacion_iniciada_en")):
            st.caption(f"Desde las {inicio:%H:%M}")
    elif postor.get("estado") == "error":
        st.markdown(badge_html("⚠️ Error en la evaluación", "ml-badge-no-cumple"), unsafe_allow_html=True)
        st.caption(postor.get("error_evaluacion") or "")
    else:
        st.markdown(badge_html("⏳ Pendiente", "ml-badge-pendiente"), unsafe_allow_html=True)


def _tarjeta_postor(
    concurso: dict, postor: dict, dictamen: dict | None, filas: list[dict], criterios: int, consumo: dict | None
) -> None:
    with st.container(border=True):
        columnas = st.columns([3, 3, 2, 2])
        with columnas[0]:
            st.markdown(f"**{postor['razon_social']}**")
            st.caption(f"RUC {postor['ruc']}")
            if consumo:
                st.caption(f"🤖 IA: {consumo['consultas']} consultas · {consumo['tokens'] / 1000:,.0f} mil tokens")

        if not dictamen:
            with columnas[1]:
                _estado_sin_dictamen(postor)
            etiqueta = "Reintentar" if postor.get("estado") == "error" else "Evaluar"
            if postor.get("estado") != "evaluando" and columnas[2].button(etiqueta, key=f"evaluar_{postor['id']}"):
                _evaluar([postor], criterios)
            return

        revisado = bool(dictamen.get("revisado_en"))
        with columnas[1]:
            st.markdown(badge_resultado(veredicto_efectivo(dictamen)), unsafe_allow_html=True)
            if dictamen.get("puntaje_maximo"):
                st.caption(
                    f"Puntaje técnico: {_numero(puntaje_efectivo(dictamen) or 0)} de {_numero(dictamen['puntaje_maximo'])}"
                )
            st.caption(f"✔️ Revisado por {dictamen['revisado_por']}" if revisado else "Propuesta de la IA · falta revisión del comité")
            if postor.get("estado") == "error":
                st.caption(f"⚠️ La última reevaluación falló: {postor.get('error_evaluacion') or ''}")
        columnas[2].download_button(
            "Descargar Acta (.docx)",
            data=partial(_acta_docx, concurso, postor, dictamen),
            file_name=f"acta_{postor['ruc']}.docx",
            mime=MIME_DOCX,
            key=f"acta_{postor['id']}",
            on_click="ignore",
        )
        if not revisado and columnas[3].button("Reevaluar", key=f"reevaluar_{postor['id']}"):
            _evaluar([postor], criterios)

        with st.expander("Ver detalle y revisión del comité"):
            _revisar_evaluacion(concurso, postor, dictamen, filas)


def _estado_automatizacion() -> None:
    ultima = (
        get_client().table("ejecuciones_automaticas").select("*").order("inicio", desc=True).limit(1).execute().data
    )
    texto = f"🤖 Consultas a la IA hoy: {consultas_de_hoy()} de {LIMITE_DIARIO_CONSULTAS}"
    if ultima:
        ejecucion = ultima[0]
        texto += (
            f" · Última revisión automática: {_fecha_local(ejecucion['inicio']):%d/%m %H:%M} — "
            f"{ejecucion['postores_evaluados']} evaluados, {ejecucion['postores_con_error']} con error"
            + (", pausada por el límite diario" if ejecucion["pausada_por_limite"] else "")
        )
    st.caption(texto)


# ---------- Listas de concursos por módulo ----------

def _concursos(estados: list[str] | None = None) -> list[dict]:
    concursos = get_client().table("concursos").select("*").order("created_at", desc=True).execute().data
    return [c for c in concursos if estados is None or c["estado"] in estados]


def _concluido(concurso: dict, postores: list[dict]) -> bool:
    """Un concurso está terminado al 100 % cuando se cerró y el comité revisó y firmó a todos sus postores."""
    return concurso["estado"] == "cerrado" and bool(postores) and all(p.get("estado") == "revisado" for p in postores)


def _postores_por_concurso() -> dict[str, list[dict]]:
    por_concurso: dict[str, list[dict]] = {}
    for postor in get_client().table("postores").select("*").execute().data:
        por_concurso.setdefault(postor["concurso_id"], []).append(postor)
    return por_concurso


def _elegir(concursos: list[dict], etiqueta: str, key: str) -> dict:
    opciones = {c["id"]: c for c in concursos}
    elegido = st.selectbox(etiqueta, list(opciones), key=key,
                           format_func=lambda cid: opciones[cid]["nombre"] + ESTADOS.get(opciones[cid]["estado"], ""))
    return opciones[elegido]


def _ultimas_acciones(concurso: dict, modulo: str) -> None:
    acciones = bitacora.acciones(concurso, modulo)
    st.markdown("**Últimas acciones**")
    if not acciones:
        st.caption("Todavía no hay acciones registradas.")
        return
    st.dataframe(pd.DataFrame([{
        "Fecha": f"{_fecha_local(a['fecha']):%d/%m/%Y %H:%M}", "Acción": a["accion"], "Responsable": a["responsable"],
    } for a in acciones]), hide_index=True, width="stretch")


# ---------- Módulo 1: revisiones en curso y terminadas ----------

def _revisiones_en_curso() -> None:
    concursos = _concursos(["revision_bases"])
    if not concursos:
        st.info("No hay revisiones de Bases en curso. Inicia una en «Nueva revisión».")
        return
    concurso = _elegir(concursos, "Selecciona una revisión", "sel_revision")
    st.caption(concurso.get("descripcion") or "")
    _administrar_concurso(concurso, [])
    revision_bases.render(concurso, lambda documento: _terminar_revision(concurso, documento))


def _resultado_revision(concurso: dict) -> None:
    hallazgos = revision_servicio.hallazgos(concurso["id"])
    final = [h for h in hallazgos if h["ronda"] == RONDA_B] or hallazgos
    columnas = st.columns(4)
    columnas[0].metric("Hallazgos ronda A", sum(h["ronda"] == RONDA_A for h in hallazgos))
    columnas[1].metric("Hallazgos ronda B", sum(h["ronda"] == RONDA_B for h in hallazgos))
    columnas[2].metric("Corregidos", sum(h["estado"] == "corregido" for h in final))
    columnas[3].metric("Críticos mantenidos", sum(h["gravedad"] == CRITICO and h["estado"] == "se_mantiene" for h in final))
    st.markdown("**Resultado:** Bases Integradas revisadas"
                + (", listas para convocar en el módulo 2." if concurso["estado"] == "bases_revisadas"
                   else ", ya convocadas en el módulo 2."))
    columnas = st.columns(2)
    columnas[0].download_button(
        "📄 Informe de revisión de Bases (.docx)", data=partial(revision_servicio.informe, concurso),
        file_name=f"revision_bases_{concurso['nombre']}.docx", mime=MIME_DOCX, on_click="ignore",
        key=f"informe_historial_{concurso['id']}",
    )
    if documento := revision_servicio.bases_de_la_ronda(concurso["id"], RONDA_B):
        columnas[1].download_button(
            "📄 Bases Integradas revisadas (.pdf)", data=partial(descargar_archivo, documento["path"]),
            file_name=documento["nombre"], mime="application/pdf", on_click="ignore",
            key=f"bases_historial_{concurso['id']}",
        )


def _revisiones_terminadas() -> None:
    terminadas = [c for c in _concursos() if c.get("ronda_revision") and c["estado"] != "revision_bases"]
    if not terminadas:
        st.info("Todavía no hay revisiones de Bases terminadas.")
        return
    st.caption(f"{len(terminadas)} revisión(es) terminada(s), de la más reciente a la más antigua.")
    for concurso in terminadas:
        etiqueta = "lista para convocar" if concurso["estado"] == "bases_revisadas" else "convocada en el módulo 2"
        with st.expander(f"{concurso['nombre']} · {etiqueta}"):
            _resultado_revision(concurso)
            _ultimas_acciones(concurso, MODULO_REVISION)


# ---------- Módulo 2: convocatorias en curso y concursos terminados ----------

def _convocatorias_en_curso() -> None:
    postores = _postores_por_concurso()
    concursos = [c for c in _concursos(["borrador", "abierto", "cerrado"]) if not _concluido(c, postores.get(c["id"], []))]
    if not concursos:
        st.info("No hay convocatorias en curso. Crea una en «Nueva convocatoria».")
        return
    _gestionar_concurso(_elegir(concursos, "Selecciona un concurso", "sel_convocatoria"))


def _gestionar_concurso(concurso: dict) -> None:
    client = get_client()
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
    pendientes = [p for p in postores if p["id"] not in dictamenes_por_postor and p.get("estado") != "evaluando"]
    if len(pendientes) > 1 and st.button(f"Evaluar los {len(pendientes)} postores pendientes"):
        _evaluar(pendientes, len(criterios))

    consumo = consumo_por_postor(concurso["id"])
    for postor in postores:
        filas = [d for d in todos if d["postor_id"] == postor["id"] and d["agente"] != "coordinador"]
        _tarjeta_postor(
            concurso, postor, dictamenes_por_postor.get(postor["id"]), filas, len(criterios), consumo.get(postor["id"]),
        )

    st.markdown("### Matriz Comparativa")
    st.download_button(
        "Descargar Matriz Comparativa (.xlsx)",
        data=partial(generar_matriz_comparativa, postores, dictamenes),
        file_name=f"matriz_{concurso['nombre']}.xlsx",
        mime=MIME_XLSX,
        on_click="ignore",
    )


def _resultado_convocatoria(concurso: dict, postores: list[dict]) -> None:
    dictamenes = [d for d in get_client().table("dictamenes").select("*").eq("concurso_id", concurso["id"]).execute().data
                  if d["agente"] == "coordinador"]
    por_postor = {d["postor_id"]: d for d in dictamenes}
    filas = []
    for postor in postores:
        dictamen = por_postor.get(postor["id"]) or {}
        puntaje = puntaje_efectivo(dictamen) if dictamen.get("puntaje_maximo") else None
        filas.append({
            "Postor": postor["razon_social"], "RUC": postor["ruc"],
            "Resultado": veredicto_efectivo(dictamen) if dictamen else "Sin evaluar",
            "Puntaje": f"{_numero(puntaje or 0)} de {_numero(dictamen['puntaje_maximo'])}" if puntaje is not None else "—",
            "Firmado por": dictamen.get("revisado_por") or "—",
        })
    st.markdown("**Resultado del concurso**")
    st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
    st.download_button(
        "📊 Matriz comparativa (.xlsx)", data=partial(generar_matriz_comparativa, postores, dictamenes),
        file_name=f"matriz_{concurso['nombre']}.xlsx", mime=MIME_XLSX, on_click="ignore",
        key=f"matriz_historial_{concurso['id']}",
    )
    columnas = st.columns(min(len(postores), 3))
    for numero, postor in enumerate(postores):
        if dictamen := por_postor.get(postor["id"]):
            columnas[numero % len(columnas)].download_button(
                f"📄 Acta de {postor['razon_social']}", data=partial(_acta_docx, concurso, postor, dictamen),
                file_name=f"acta_{postor['ruc']}.docx", mime=MIME_DOCX, on_click="ignore",
                key=f"acta_historial_{postor['id']}",
            )


def _concursos_terminados() -> None:
    postores = _postores_por_concurso()
    terminados = [c for c in _concursos(["cerrado"]) if _concluido(c, postores.get(c["id"], []))]
    if not terminados:
        st.info("Todavía no hay concursos terminados. Un concurso termina cuando se cierra y el comité revisa y firma "
                "la evaluación de todos sus postores.")
        return
    st.caption(f"{len(terminados)} concurso(s) terminado(s), del más reciente al más antiguo.")
    for concurso in terminados:
        de_este = postores.get(concurso["id"], [])
        with st.expander(f"{concurso['nombre']} · {len(de_este)} postor(es) evaluado(s) y firmado(s)"):
            _resultado_convocatoria(concurso, de_este)
            _ultimas_acciones(concurso, MODULO_CONVOCATORIA)


def _acta_docx(concurso: dict, postor: dict, dictamen: dict) -> BytesIO:
    filas = (
        get_client().table("dictamenes")
        .select("*")
        .eq("postor_id", postor["id"])
        .in_("agente", ["legal", "tecnico"])
        .execute()
        .data
    )
    return generar_acta(concurso, postor, filas, dictamen, revision_servicio.resumen_para_el_acta(concurso["id"]))


# ---------- Portal ----------

def _modulo_revision() -> None:
    st.caption("Control previo: antes de convocar se revisan el expediente y las Bases. El resultado son unas Bases "
               "Integradas revisadas.")
    nueva, en_curso, terminadas = st.tabs(["Nueva revisión", "Revisiones en curso", "Revisiones terminadas"])
    with nueva:
        _crear_revision()
    with en_curso:
        _revisiones_en_curso()
    with terminadas:
        _revisiones_terminadas()


def _modulo_convocatoria() -> None:
    st.caption("Con las Bases Integradas se arma la matriz, se reciben las ofertas y se evalúan. El resultado es el "
               "dictamen firmado de cada postor.")
    nueva, en_curso, terminados = st.tabs(["Nueva convocatoria", "Convocatorias en curso", "Concursos terminados"])
    with nueva:
        origen = "subir"
        if REVISION_BASES:
            origen = st.radio("¿Con qué Bases se convoca?", ["revision", "subir"], key="origen_convocatoria",
                              format_func={"revision": "Desde una revisión de Bases terminada",
                                           "subir": "Subiendo las Bases Integradas"}.get)
        if origen == "revision":
            _crear_desde_revision()
        else:
            _crear_concurso()
    with en_curso:
        _estado_automatizacion()
        _convocatorias_en_curso()
    with terminados:
        _concursos_terminados()


def render():
    st.title("Portal del Comité / Administrador")
    _mostrar_avisos()
    if REVISION_BASES and st.radio("Módulo", [MODULO_1, MODULO_2], horizontal=True, key="modulo_comite") == MODULO_1:
        _modulo_revision()
    else:
        _modulo_convocatoria()
