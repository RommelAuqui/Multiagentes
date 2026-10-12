from agents.gemini_client import ContextoIA, generar_json
from agents.reglas import ETAPAS, REQUIERE_REVISION, RESULTADOS_DESCALIFICANTES, calcular_resultado, normalizar_texto
from config import LLM_MODEL

PROMPT_REVISION = """Eres el Agente Coordinador, presidente de un comité de selección de concursos \
públicos de consultoría en Perú, regidos por la Ley N.º 32069.

Los agentes Legal y Técnico ya evaluaron al postor criterio por criterio. Aplicando las reglas de las \
Bases, el resultado preliminar es "{resultado}"{motivos}. Puntaje técnico: {puntaje}.

Tu tarea no es cambiar ese resultado, sino revisarlo como lo haría el presidente del comité:
1. Redacta la conciliación en un párrafo claro, citando los puntos de ambos agentes en los que se basa.
2. Señala las tensiones o inconsistencias que encuentres: datos que no coinciden entre documentos \
(fechas, montos, nombres, RUC), un criterio aprobado cuya justificación en realidad no lo acredita, \
o evaluaciones de ambos agentes que se contradicen. Indica el número del criterio que debe revisarse \
(o null si la tensión no corresponde a uno en particular) y una observación concreta para el agente \
responsable. No inventes tensiones: si no hay, deja la lista vacía.
{ronda}
Evaluaciones de los agentes:
{evaluaciones}

Responde únicamente con un JSON de la forma:
{{"conciliacion": "...", "tensiones": [{{"criterio": n | null, "observacion": "..."}}]}}
"""

SEGUNDA_RONDA = """
Esta es la segunda ronda: los criterios marcados con «(revisado)» ya fueron devueltos a su agente con \
tus observaciones de la primera ronda. Solo señala de nuevo una tensión si sigue sin resolverse.
"""


def _resumen(resultados: list[dict]) -> str:
    lineas = []
    for numero, r in enumerate(resultados, start=1):
        puntaje = f" ({r['puntaje']} de {r['puntaje_maximo']} puntos)" if r["etapa"] == "evaluacion" else ""
        revisado = " (revisado)" if r.get("revisado") else ""
        lineas.append(
            f"[{numero}] [{ETAPAS[r['etapa']]} | Agente {r.get('agente', '')}]{revisado} {r['criterio_descripcion']}: "
            f"{r['veredicto']}{puntaje} — {r['justificacion']}"
        )
    return "\n".join(lineas) or "No hay criterios evaluados."


def _tensiones(revision: dict, total: int) -> list[dict]:
    crudas = revision.get("tensiones") if isinstance(revision.get("tensiones"), list) else []
    tensiones = []
    for tension in crudas:
        if isinstance(tension, dict):
            observacion = normalizar_texto(tension.get("observacion"))
            try:
                indice = int(tension.get("criterio")) - 1
            except (TypeError, ValueError):
                indice = None
        else:
            observacion, indice = normalizar_texto(tension), None
        if observacion:
            tensiones.append({"criterio": indice if indice is not None and 0 <= indice < total else None,
                              "observacion": observacion})
    return tensiones


def consolidar_dictamen(
    resultados: list[dict], puntaje_minimo: float | None, contexto: ContextoIA, segunda_ronda: bool = False
) -> dict:
    preliminar = calcular_resultado(resultados, puntaje_minimo)
    motivos = f" ({'; '.join(preliminar['motivos'])})" if preliminar["motivos"] else ""
    puntaje = (
        f"{preliminar['puntaje']} de {preliminar['puntaje_maximo']}"
        if preliminar["puntaje"] is not None else "no aplica"
    )
    revision = generar_json(LLM_MODEL, PROMPT_REVISION.format(
        resultado=preliminar["veredicto"], motivos=motivos, puntaje=puntaje,
        ronda=SEGUNDA_RONDA if segunda_ronda else "", evaluaciones=_resumen(resultados),
    ), contexto)
    tensiones = _tensiones(revision, len(resultados))

    veredicto = preliminar["veredicto"]
    if tensiones and veredicto not in RESULTADOS_DESCALIFICANTES:
        veredicto = REQUIERE_REVISION

    partes = [normalizar_texto(revision.get("conciliacion"))]
    if preliminar["motivos"]:
        partes.append("Motivos: " + "; ".join(preliminar["motivos"]) + ".")
    if tensiones:
        partes.append("Tensiones detectadas por el Coordinador: " + "; ".join(
            (f"[{t['criterio'] + 1}] " if t["criterio"] is not None else "") + t["observacion"] for t in tensiones
        ))

    return {
        "veredicto": veredicto,
        "puntaje": preliminar["puntaje"],
        "puntaje_maximo": preliminar["puntaje_maximo"],
        "justificacion": "\n\n".join(p for p in partes if p),
        "tensiones": tensiones,
        "citas": [c for r in resultados for c in r.get("citas", [])],
    }
