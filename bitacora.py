"""Bitácora de cada proceso: las últimas acciones de la revisión de Bases (módulo 1) y de la convocatoria (módulo 2).

Los cambios de estado que no dejan otra huella (cerrar una ronda, publicar, cerrar postulaciones) se registran en
la tabla `bitacora`. Lo demás ya tiene fecha en su propia tabla: documentos, análisis, respuestas a los
hallazgos, ofertas, evaluaciones y firmas del comité.
"""
import logging

from db.client import get_client
from revision.catalogo import TIPOS_DOCUMENTO

MODULO_REVISION = "revision"
MODULO_CONVOCATORIA = "convocatoria"
COMITE = "Comité de selección"
SISTEMA = "Sistema"

registro = logging.getLogger(__name__)


def registrar(concurso_id: str, modulo: str, accion: str, responsable: str = COMITE) -> None:
    """La bitácora es un registro, no un paso del procedimiento: si falla (p. ej., la tabla aún no existe en
    Supabase), se deja constancia en el log y el proceso sigue."""
    try:
        get_client().table("bitacora").insert({
            "concurso_id": concurso_id, "modulo": modulo, "accion": accion, "responsable": responsable,
        }).execute()
    except Exception:
        registro.warning("No se pudo registrar en la bitácora: %s", accion, exc_info=True)


def _filas(tabla: str, concurso_id: str) -> list[dict]:
    try:
        return get_client().table(tabla).select("*").eq("concurso_id", concurso_id).execute().data
    except Exception:
        return []


def _accion(fecha: str | None, accion: str, responsable: str) -> dict | None:
    return {"fecha": fecha, "accion": accion, "responsable": responsable} if fecha else None


def _de_la_revision(concurso: dict) -> list[dict | None]:
    acciones = [_accion(concurso.get("created_at"), "Se inició la revisión de Bases", COMITE)]
    for documento in _filas("documentos_expediente", concurso["id"]):
        tipo = TIPOS_DOCUMENTO.get(documento["tipo"], documento["tipo"])
        acciones.append(_accion(documento.get("created_at"),
                                f"Se subió «{documento['nombre']}» como {tipo} (versión {documento['version']})", COMITE))
    for revision in _filas("revisiones_bases", concurso["id"]):
        hallazgos = sum(1 for r in revision.get("resultados") or [] if r.get("estado") != "cumple")
        forma = "reglas fijas y Agente Revisor" if revision.get("con_agente") else "solo reglas fijas"
        acciones.append(_accion(revision.get("created_at"),
                                f"Se analizó la ronda {revision['ronda']} ({forma}): {hallazgos} hallazgo(s)", SISTEMA))
    for hallazgo in _filas("hallazgos", concurso["id"]):
        respuesta = "se mantiene" if hallazgo["estado"] == "se_mantiene" else "corregido"
        acciones.append(_accion(hallazgo.get("revisado_en"),
                                f"Hallazgo {hallazgo['codigo']} de la ronda {hallazgo['ronda']}: {respuesta}",
                                hallazgo.get("revisado_por") or COMITE))
    return acciones


def _de_la_convocatoria(concurso: dict) -> list[dict | None]:
    acciones = [] if concurso.get("ronda_revision") else [
        _accion(concurso.get("created_at"), "Se creó la convocatoria", COMITE)]
    postores = {p["id"]: p for p in _filas("postores", concurso["id"])}
    for postor in postores.values():
        acciones.append(_accion(postor.get("created_at"), f"{postor['razon_social']} presentó su oferta", "Postor"))
    for dictamen in _filas("dictamenes", concurso["id"]):
        if dictamen.get("agente") != "coordinador":
            continue
        nombre = postores.get(dictamen["postor_id"], {}).get("razon_social", "un postor")
        acciones.append(_accion(dictamen.get("created_at"),
                                f"Se evaluó a {nombre}: {dictamen.get('veredicto')}", SISTEMA))
        acciones.append(_accion(dictamen.get("revisado_en"),
                                f"El comité revisó y firmó la evaluación de {nombre}: "
                                f"{dictamen.get('veredicto_comite') or dictamen.get('veredicto')}",
                                dictamen.get("revisado_por") or COMITE))
    return acciones


def acciones(concurso: dict, modulo: str) -> list[dict]:
    """Las acciones del proceso, de la más reciente a la más antigua."""
    derivadas = _de_la_revision(concurso) if modulo == MODULO_REVISION else _de_la_convocatoria(concurso)
    registradas = [_accion(f.get("created_at"), f["accion"], f.get("responsable") or COMITE)
                   for f in _filas("bitacora", concurso["id"]) if f.get("modulo") == modulo]
    return sorted((a for a in derivadas + registradas if a), key=lambda a: a["fecha"], reverse=True)
