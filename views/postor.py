from contextlib import suppress
from functools import partial

import streamlit as st

from agents.gemini_client import ContextoIA
from db.client import get_client
from db.storage import descargar_archivo, eliminar_archivos, subir_archivo
from rag.ingest import DocumentoPreparado, guardar_fragmentos, preparar_documento
from validaciones import ruc_valido
from views.componentes import mostrar_avisos_extraccion, tabla_criterios

# Máximo de archivos por oferta que admite el SEACE.
MAX_ARCHIVOS = 10


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
            st.table(tabla_criterios(criterios))

    st.markdown(
        f"**Formato de presentación:** sube tu oferta técnica en PDF, en uno o varios archivos (hasta "
        f"{MAX_ARCHIVOS}): anexos, declaraciones juradas, CV del personal clave, contratos, constancias, "
        "etc. Ponles nombres claros (por ejemplo, «Anexo 15 - Personal clave.pdf»): las citas de la "
        "evaluación indicarán el archivo y la página de cada evidencia."
    )

    with st.form("postulacion"):
        ruc = st.text_input("RUC")
        razon_social = st.text_input("Razón Social")
        archivos = st.file_uploader(
            f"Oferta técnica (PDF, hasta {MAX_ARCHIVOS} archivos)", type="pdf", accept_multiple_files=True
        )
        enviado = st.form_submit_button("Enviar Postulación")

    if not enviado:
        return

    ruc = ruc.strip()
    razon_social = razon_social.strip()

    if not ruc or not razon_social or not archivos:
        st.error("Todos los campos son obligatorios: RUC, Razón Social y al menos un PDF de la oferta.")
        return

    if len(archivos) > MAX_ARCHIVOS:
        st.error(f"Puedes subir hasta {MAX_ARCHIVOS} archivos; subiste {len(archivos)}. Junta algunos en un solo PDF.")
        return

    if not ruc_valido(ruc):
        st.error("El RUC no es válido. Debe tener 11 dígitos y un dígito verificador correcto.")
        return

    ya_postulo = (
        client.table("postores")
        .select("id")
        .eq("concurso_id", concurso["id"])
        .eq("ruc", ruc)
        .limit(1)
        .execute()
        .data
    )
    if ya_postulo:
        st.error(
            "Ya existe una postulación con este RUC en este concurso. "
            "Si necesitas corregirla, comunícate con el comité."
        )
        return

    oferta = list(zip(_nombres_unicos([a.name for a in archivos]), (a.getvalue() for a in archivos)))

    # Los documentos se procesan antes de registrar al postor, para no dejar postulaciones sin evidencia.
    lector = ContextoIA("lector", concurso["id"])
    progreso = st.progress(0.0, text="Leyendo e indexando tus documentos para la evaluación...")
    documentos = []
    for numero, (nombre, contenido) in enumerate(oferta, start=1):
        progreso.progress((numero - 1) / len(oferta), text=f"Leyendo {nombre} ({numero} de {len(oferta)})...")
        try:
            documentos.append(preparar_documento(contenido, lector, nombre))
        except Exception:
            progreso.empty()
            st.error(
                f"No se pudo procesar «{nombre}» (el PDF podría estar dañado o el servicio de IA no respondió). "
                "Tu postulación no se registró; vuelve a intentarlo."
            )
            return
    progreso.empty()

    for documento in documentos:
        mostrar_avisos_extraccion(documento.nombre, documento.extraccion)

    if ilegibles := [d.nombre for d in documentos if not d.fragmentos]:
        st.error(
            f"No se pudo leer texto de: {', '.join(ilegibles)}. Verifica que el PDF no esté "
            "protegido o dañado. Tu postulación no se registró."
        )
        return

    try:
        _registrar_postulacion(concurso["id"], ruc, razon_social, oferta, documentos)
    except Exception:
        st.error("Hubo un problema al registrar tu postulación. No se guardó nada; vuelve a intentarlo.")
        return

    st.success(
        f"Postulación registrada correctamente con {len(documentos)} archivo(s). El comité evaluará tu expediente."
    )


def _nombres_unicos(nombres: list[str]) -> list[str]:
    vistos: dict[str, int] = {}
    unicos = []
    for nombre in nombres:
        vistos[nombre] = vistos.get(nombre, 0) + 1
        if vistos[nombre] > 1:
            base, punto, extension = nombre.rpartition(".")
            nombre = f"{base} ({vistos[nombre]}).{extension}" if punto else f"{nombre} ({vistos[nombre]})"
        unicos.append(nombre)
    return unicos


def _registrar_postulacion(
    concurso_id: str, ruc: str, razon_social: str, oferta: list[tuple[str, bytes]], documentos: list[DocumentoPreparado]
) -> None:
    client = get_client()
    postor = client.table("postores").insert({
        "concurso_id": concurso_id,
        "ruc": ruc,
        "razon_social": razon_social,
        "estado": "recibido",
    }).execute().data[0]

    # Las rutas del Storage no llevan el nombre original, que puede tener tildes o símbolos no permitidos.
    paths = [f"postores/{postor['id']}/{numero:02d}.pdf" for numero in range(1, len(oferta) + 1)]
    try:
        for path, (_, contenido) in zip(paths, oferta):
            subir_archivo(path, contenido)
        client.table("postores").update({"archivos": [
            {"nombre": documento.nombre, "path": path, "paginas": documento.extraccion.total_paginas}
            for documento, path in zip(documentos, paths)
        ]}).eq("id", postor["id"]).execute()
        for documento in documentos:
            guardar_fragmentos(concurso_id, postor["id"], "oferta", documento)
    except Exception:
        with suppress(Exception):
            client.table("postores").delete().eq("id", postor["id"]).execute()
        with suppress(Exception):
            eliminar_archivos(paths)
        raise
