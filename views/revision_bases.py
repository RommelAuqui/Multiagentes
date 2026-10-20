"""Pantalla de revisión de Bases (control previo) dentro del portal del comité.

Ronda A, antes de convocar: el expediente y las Bases. Ronda B, antes de recibir ofertas: el pliego de
absolución y las Bases Integradas. En cada ronda el comité sube los documentos, pulsa «Analizar» y
responde cada hallazgo; al cerrar la ronda B, las Bases Integradas revisadas pasan a la matriz.
"""
import streamlit as st

from db.client import get_client
from revision import servicio
from revision.catalogo import (
    CRITICO,
    DOCUMENTOS_DE_RONDA,
    OBLIGATORIOS,
    POR_CODIGO,
    RONDA_A,
    RONDA_B,
    SUGERENCIA,
    TIPOS_DOCUMENTO,
)
from views.componentes import mostrar_avisos_extraccion

ICONOS = {CRITICO: "🔴", "Advertencia": "🟡", SUGERENCIA: "🔵"}
ESTADOS = {"pendiente": "⏳ Pendiente", "se_mantiene": "✍️ Se mantiene", "corregido": "✅ Corregido"}
TITULOS = {RONDA_A: "Ronda A: antes de convocar", RONDA_B: "Ronda B: antes de recibir ofertas"}
EXPLICACIONES = {
    RONDA_A: "Sube el expediente que recibió el comité y las Bases que se van a convocar. El sistema comprueba que "
             "las Bases calcen con el expediente y con las Bases estándar.",
    RONDA_B: "Sube el pliego de absolución y las Bases Integradas (y el pronunciamiento del OECE, si lo hubo). El "
             "sistema comprueba que cada absolución quedó incorporada y vuelve a revisar la versión final.",
}


def _avisar(tipo: str, mensaje: str) -> None:
    st.session_state.setdefault("avisos_revision", []).append((tipo, mensaje))


def _mostrar_avisos() -> None:
    for tipo, mensaje in st.session_state.pop("avisos_revision", []):
        getattr(st, tipo)(mensaje)


def _documentos(concurso: dict, ronda: str) -> None:
    vigentes = servicio.documentos_vigentes(concurso["id"])
    st.markdown("**Documentos**")
    for tipo in DOCUMENTOS_DE_RONDA[ronda]:
        etiqueta = TIPOS_DOCUMENTO[tipo] + (" (obligatorio)" if tipo in OBLIGATORIOS[ronda] else "")
        if fila := vigentes.get(tipo):
            st.markdown(f"- ✅ {etiqueta}: «{fila['nombre']}», versión {fila['version']}")
        else:
            st.markdown(f"- ⬜ {etiqueta}: falta")

    with st.form(f"subir_documento_{ronda}", clear_on_submit=True):
        tipo = st.selectbox("Tipo de documento", DOCUMENTOS_DE_RONDA[ronda], format_func=TIPOS_DOCUMENTO.get)
        archivo = st.file_uploader("Archivo PDF (si ya existe, se guarda como una versión nueva)", type="pdf")
        enviado = st.form_submit_button("Subir documento")
    if enviado:
        if not archivo:
            st.error("Elige un archivo PDF.")
            return
        try:
            with st.spinner(f"Leyendo «{archivo.name}» y extrayendo sus datos..."):
                fila, extraccion = servicio.subir_documento(concurso["id"], tipo, archivo.name, archivo.getvalue())
        except Exception as e:
            st.error(f"No se pudo procesar «{archivo.name}»: {e}")
            return
        mostrar_avisos_extraccion(archivo.name, extraccion)
        _avisar("success", f"Se guardó «{archivo.name}» como {TIPOS_DOCUMENTO[tipo]}, versión {fila['version']}.")
        st.rerun()


def _analizar(concurso: dict, ronda: str) -> None:
    if faltan := servicio.faltantes(concurso["id"], ronda):
        st.info("Para analizar faltan: " + ", ".join(TIPOS_DOCUMENTO[t] for t in faltan) + ".")
        return
    if st.button("🔎 Analizar", key=f"analizar_{ronda}", type="primary"):
        with st.spinner("Revisando las Bases contra el expediente y el catálogo..."):
            servicio.revisar(concurso["id"], ronda)
        _avisar("success", "Revisión terminada.")
        st.rerun()


def _resumen(hallazgos: list[dict]) -> None:
    abiertos = [h for h in hallazgos if h["estado"] != "corregido"]
    por_gravedad = " · ".join(f"{ICONOS[g]} {sum(h['gravedad'] == g for h in abiertos)} {g.lower()}"
                              for g in ICONOS)
    respondidos = sum(h["estado"] != "pendiente" for h in hallazgos)
    st.markdown(f"**Hallazgos:** {por_gravedad} · respondidos {respondidos} de {len(hallazgos)}")


def _tarjeta(hallazgo: dict) -> None:
    verificacion = POR_CODIGO[hallazgo["codigo"]]
    with st.container(border=True):
        st.markdown(f"{ICONOS[hallazgo['gravedad']]} **{hallazgo['codigo']} · {verificacion.nombre}** "
                    f"— {ESTADOS[hallazgo['estado']]}")
        st.write(hallazgo["descripcion"])
        if citas := [c for c in hallazgo.get("citas") or [] if c.get("documento")]:
            st.caption("Dónde: " + "; ".join(
                c["documento"] + (f", p. {c['pagina']}" if c.get("pagina") else "") for c in citas))
        st.caption(f"Respaldo: {verificacion.respaldo}")

        if hallazgo["estado"] == "corregido":
            return
        if hallazgo["estado"] == "se_mantiene":
            st.caption(f"Justificación del comité: {hallazgo['justificacion_comite']} — "
                       f"{hallazgo['revisado_por']}, {hallazgo['revisado_en'][:10]}")
            return
        st.caption("Corrige el documento y súbelo de nuevo (luego pulsa «Analizar»), o mantenlo con una justificación."
                   if hallazgo["resultado"] == "falla" else
                   "Sube el documento que falta, o mantén el hallazgo explicando por qué no corresponde.")
        with st.form(f"mantener_{hallazgo['id']}"):
            justificacion = st.text_area("Justificación para mantenerlo", key=f"justificacion_{hallazgo['id']}")
            revisor = st.text_input("Nombre de quien firma", value=st.session_state.get("firma_revision", ""),
                                    key=f"firma_{hallazgo['id']}")
            if st.form_submit_button("Mantener con esta justificación"):
                try:
                    servicio.mantener(hallazgo["id"], justificacion, revisor)
                except servicio.RespuestaInvalida as e:
                    st.error(str(e))
                    return
                st.session_state["firma_revision"] = revisor
                st.rerun()


def _continuar(concurso: dict, ronda: str, hallazgos: list[dict], al_terminar) -> None:
    listo, motivo = servicio.puede_continuar(concurso["id"], ronda)
    criticos = [h for h in hallazgos if h["gravedad"] == CRITICO and h["estado"] == "se_mantiene"]
    etiqueta = "Cerrar la ronda A" if ronda == RONDA_A else "Cerrar la revisión y armar la matriz"
    if not listo:
        st.button(etiqueta, key=f"continuar_{ronda}", disabled=True, help=motivo)
        st.caption(motivo)
        return
    if criticos:
        st.warning(f"Se mantienen {len(criticos)} hallazgo(s) crítico(s). Quedarán registrados en el informe y en el acta.")
        if servicio.BLOQUEAR_CRITICOS:
            st.error("La configuración actual no permite continuar con hallazgos críticos mantenidos.")
            return
    if st.button(etiqueta, key=f"continuar_{ronda}", type="primary"):
        if ronda == RONDA_A:
            get_client().table("concursos").update({"ronda_revision": RONDA_B}).eq("id", concurso["id"]).execute()
            _avisar("success", "Ronda A cerrada. Cuando tengas el pliego de absolución y las Bases Integradas, "
                               "súbelos para la ronda B.")
            st.rerun()
        al_terminar(servicio.bases_de_la_ronda(concurso["id"], ronda))


def render(concurso: dict, al_terminar) -> None:
    """`al_terminar(documento_bases_integradas)` arma la matriz y deja el concurso en revisión de matriz."""
    ronda = concurso.get("ronda_revision") or RONDA_A
    _mostrar_avisos()
    st.markdown(f"### Revisión de Bases · {TITULOS[ronda]}")
    st.caption(EXPLICACIONES[ronda])
    _documentos(concurso, ronda)
    _analizar(concurso, ronda)

    hallazgos = servicio.hallazgos(concurso["id"], ronda)
    if servicio.ultima_revision(concurso["id"], ronda):
        if hallazgos:
            _resumen(hallazgos)
            for hallazgo in hallazgos:
                _tarjeta(hallazgo)
        else:
            st.success("La última revisión no encontró hallazgos.")
    _continuar(concurso, ronda, hallazgos, al_terminar)
