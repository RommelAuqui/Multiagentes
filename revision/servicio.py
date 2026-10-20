"""Operaciones del módulo de revisión de Bases sobre Supabase.

- Cada documento se guarda por versión: subir una corrección crea la versión siguiente y la anterior
  queda como historial.
- Cada «Analizar» crea una revisión con los documentos vigentes y el resultado de cada verificación.
- Los hallazgos son únicos por concurso, ronda y verificación: una nueva revisión los actualiza. El
  comité no marca un hallazgo como corregido; lo confirma el sistema cuando la verificación pasa.
"""
from dataclasses import asdict
from datetime import datetime, timezone

from agents.gemini_client import ContextoIA
from db.client import get_client
from db.storage import subir_archivo
from rag.pdf_extract import ResultadoExtraccion, extraer_paginas, texto_completo
from revision.catalogo import BASES_DE_RONDA, OBLIGATORIOS, POR_CODIGO, RONDA_A, RONDA_B, TIPOS_DOCUMENTO
from revision.extraccion import extraer_ficha
from revision.reglas import CUMPLE, Documento, Resultado, verificar

PENDIENTE, SE_MANTIENE, CORREGIDO = "pendiente", "se_mantiene", "corregido"
# Decisión pendiente del asesor: con True no se puede continuar si se mantiene un hallazgo crítico.
BLOQUEAR_CRITICOS = False


class RespuestaInvalida(ValueError):
    pass


# ---------- Documentos ----------

def documentos_vigentes(concurso_id: str) -> dict[str, dict]:
    """La versión más reciente de cada tipo de documento subido."""
    filas = (
        get_client().table("documentos_expediente").select("*").eq("concurso_id", concurso_id)
        .order("version").execute().data
    )
    return {fila["tipo"]: fila for fila in filas}


def subir_documento(concurso_id: str, tipo: str, nombre: str, contenido: bytes) -> tuple[dict, ResultadoExtraccion]:
    """Lee el PDF, extrae sus datos clave y lo guarda como la versión siguiente de su tipo."""
    anterior = documentos_vigentes(concurso_id).get(tipo)
    version = (anterior["version"] + 1) if anterior else 1
    extraccion = extraer_paginas(contenido, ContextoIA("lector", concurso_id))
    datos = extraer_ficha(tipo, texto_completo(extraccion.paginas), ContextoIA("revisor", concurso_id)) \
        if extraccion.paginas else {}
    path = f"expediente/{concurso_id}/{tipo}_v{version}.pdf"
    subir_archivo(path, contenido)
    fila = get_client().table("documentos_expediente").insert({
        "concurso_id": concurso_id, "tipo": tipo, "version": version, "nombre": nombre, "path": path,
        "paginas": extraccion.paginas, "datos": datos, "error_lectura": extraccion.error_lectura,
    }).execute().data[0]
    return fila, extraccion


def faltantes(concurso_id: str, ronda: str) -> list[str]:
    vigentes = documentos_vigentes(concurso_id)
    return [tipo for tipo in OBLIGATORIOS[ronda] if tipo not in vigentes]


def _documentos(vigentes: dict[str, dict]) -> dict[str, Documento]:
    return {tipo: Documento(tipo, f["nombre"], f.get("paginas") or [], f.get("datos") or {})
            for tipo, f in vigentes.items()}


# ---------- Revisión ----------

def conciliar(anteriores: list[dict], resultados: list[Resultado], revision_id: str) -> tuple[list[dict], list[tuple]]:
    """Compara la nueva revisión con los hallazgos existentes. Devuelve (nuevos, cambios por id)."""
    por_clave = {(h["codigo"], h["clave"]): h for h in anteriores}
    revisados = {r.codigo for r in resultados}
    vistos, nuevos, cambios = set(), [], []
    for resultado in resultados:
        clave = (resultado.codigo, resultado.clave)
        vistos.add(clave)
        existente = por_clave.get(clave)
        if resultado.estado == CUMPLE:
            if existente and existente["estado"] != CORREGIDO:
                cambios.append((existente["id"], {"estado": CORREGIDO, "resultado": CUMPLE, "resuelto_en": revision_id,
                                                  "ultima_revision": revision_id, "descripcion": resultado.descripcion}))
            continue
        datos = {"resultado": resultado.estado, "descripcion": resultado.descripcion, "citas": resultado.citas,
                 "ultima_revision": revision_id}
        if existente is None:
            nuevos.append({**datos, "codigo": resultado.codigo, "clave": resultado.clave,
                           "gravedad": POR_CODIGO[resultado.codigo].gravedad, "estado": PENDIENTE,
                           "detectado_en": revision_id})
        elif existente["estado"] == CORREGIDO:
            # Volvió a aparecer: se pide una nueva respuesta del comité.
            cambios.append((existente["id"], {**datos, "estado": PENDIENTE, "resuelto_en": None,
                                              "justificacion_comite": None, "revisado_por": None, "revisado_en": None}))
        else:
            cambios.append((existente["id"], datos))
    # Un hallazgo con clave (p. ej., una consulta sin respuesta) que ya no aparece quedó corregido.
    for clave, existente in por_clave.items():
        if clave not in vistos and clave[0] in revisados and existente["estado"] != CORREGIDO:
            cambios.append((existente["id"], {"estado": CORREGIDO, "resultado": CUMPLE, "resuelto_en": revision_id,
                                              "ultima_revision": revision_id}))
    return nuevos, cambios


def heredar_decisiones(nuevos: list[dict], de_la_ronda_a: list[dict]) -> list[dict]:
    """Si en la ronda B reaparece una falla que el comité ya mantuvo en la ronda A, la decisión se conserva."""
    mantenidos = {(h["codigo"], h["clave"]): h for h in de_la_ronda_a if h["estado"] == SE_MANTIENE}
    heredados = []
    for nuevo in nuevos:
        previo = mantenidos.get((nuevo["codigo"], nuevo["clave"]))
        if previo and nuevo["resultado"] == previo["resultado"]:
            nuevo = {**nuevo, "estado": SE_MANTIENE, "revisado_por": previo["revisado_por"],
                     "revisado_en": previo["revisado_en"],
                     "justificacion_comite": f"{previo['justificacion_comite']} (decisión mantenida desde la ronda A)"}
        heredados.append(nuevo)
    return heredados


def revisar(concurso_id: str, ronda: str) -> dict:
    """Aplica el catálogo a los documentos vigentes y actualiza los hallazgos de la ronda."""
    client = get_client()
    vigentes = documentos_vigentes(concurso_id)
    resultados = verificar(ronda, _documentos(vigentes))
    revision = client.table("revisiones_bases").insert({
        "concurso_id": concurso_id, "ronda": ronda, "documentos": {t: f["id"] for t, f in vigentes.items()},
        "resultados": [asdict(r) for r in resultados],
    }).execute().data[0]
    anteriores = client.table("hallazgos").select("*").eq("concurso_id", concurso_id).eq("ronda", ronda).execute().data
    nuevos, cambios = conciliar(anteriores, resultados, revision["id"])
    if ronda == RONDA_B and nuevos:
        nuevos = heredar_decisiones(nuevos, hallazgos(concurso_id, RONDA_A))
    if nuevos:
        client.table("hallazgos").insert([{**h, "concurso_id": concurso_id, "ronda": ronda} for h in nuevos]).execute()
    for hallazgo_id, datos in cambios:
        client.table("hallazgos").update(datos).eq("id", hallazgo_id).execute()
    return revision


def hallazgos(concurso_id: str, ronda: str | None = None) -> list[dict]:
    consulta = get_client().table("hallazgos").select("*").eq("concurso_id", concurso_id)
    if ronda:
        consulta = consulta.eq("ronda", ronda)
    orden = list(POR_CODIGO)
    return sorted(consulta.execute().data, key=lambda h: (h["ronda"], orden.index(h["codigo"]), h["clave"]))


def ultima_revision(concurso_id: str, ronda: str) -> dict | None:
    filas = (
        get_client().table("revisiones_bases").select("*").eq("concurso_id", concurso_id).eq("ronda", ronda)
        .order("created_at", desc=True).limit(1).execute().data
    )
    return filas[0] if filas else None


def mantener(hallazgo_id: str, justificacion: str, revisor: str) -> None:
    """El comité decide no corregir: queda la justificación y quién la firmó."""
    if not (justificacion or "").strip():
        raise RespuestaInvalida("Para mantener un hallazgo hay que explicar por qué.")
    if not (revisor or "").strip():
        raise RespuestaInvalida("Indica el nombre de quien firma la decisión.")
    get_client().table("hallazgos").update({
        "estado": SE_MANTIENE, "justificacion_comite": justificacion.strip(), "revisado_por": revisor.strip(),
        "revisado_en": datetime.now(timezone.utc).isoformat(),
    }).eq("id", hallazgo_id).execute()


def puede_continuar(concurso_id: str, ronda: str) -> tuple[bool, str]:
    """La ronda se cierra cuando la última revisión usó los documentos vigentes y no hay hallazgos pendientes."""
    if faltan := faltantes(concurso_id, ronda):
        return False, "Faltan documentos obligatorios: " + ", ".join(TIPOS_DOCUMENTO[t] for t in faltan) + "."
    revision = ultima_revision(concurso_id, ronda)
    vigentes = {t: f["id"] for t, f in documentos_vigentes(concurso_id).items()}
    if revision is None or revision["documentos"] != vigentes:
        return False, "Hay documentos nuevos sin analizar: pulsa «Analizar»."
    pendientes = [h for h in hallazgos(concurso_id, ronda) if h["estado"] == PENDIENTE]
    if pendientes:
        return False, f"Quedan {len(pendientes)} hallazgo(s) sin responder."
    return True, ""


def bases_de_la_ronda(concurso_id: str, ronda: str) -> dict | None:
    return documentos_vigentes(concurso_id).get(BASES_DE_RONDA[ronda])
