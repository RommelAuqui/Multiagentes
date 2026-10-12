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
o evaluaciones de ambos agentes que se contradicen. No inventes tensiones: si no hay, deja la lista vacía.

Evaluaciones de los agentes:
{evaluaciones}

Responde únicamente con un JSON de la forma:
{{"conciliacion": "...", "tensiones": ["..."]}}
"""


def _resumen(resultados: list[dict]) -> str:
    lineas = []
    for r in resultados:
        puntaje = f" ({r['puntaje']} de {r['puntaje_maximo']} puntos)" if r["etapa"] == "evaluacion" else ""
        lineas.append(
            f"- [{ETAPAS[r['etapa']]} | Agente {r.get('agente', '')}] {r['criterio_descripcion']}: "
            f"{r['veredicto']}{puntaje} — {r['justificacion']}"
        )
    return "\n".join(lineas) or "No hay criterios evaluados."


def _revisar(resultados: list[dict], preliminar: dict, contexto: ContextoIA) -> dict:
    motivos = f" ({'; '.join(preliminar['motivos'])})" if preliminar["motivos"] else ""
    puntaje = (
        f"{preliminar['puntaje']} de {preliminar['puntaje_maximo']}"
        if preliminar["puntaje"] is not None else "no aplica"
    )
    prompt = PROMPT_REVISION.format(
        resultado=preliminar["veredicto"], motivos=motivos, puntaje=puntaje, evaluaciones=_resumen(resultados),
    )
    return generar_json(LLM_MODEL, prompt, contexto)


def consolidar_dictamen(resultados: list[dict], puntaje_minimo: float | None, contexto: ContextoIA) -> dict:
    preliminar = calcular_resultado(resultados, puntaje_minimo)
    revision = _revisar(resultados, preliminar, contexto)

    tensiones = revision.get("tensiones") if isinstance(revision.get("tensiones"), list) else []
    tensiones = [t for t in (normalizar_texto(t) for t in tensiones) if t]

    veredicto = preliminar["veredicto"]
    if tensiones and veredicto not in RESULTADOS_DESCALIFICANTES:
        veredicto = REQUIERE_REVISION

    partes = [normalizar_texto(revision.get("conciliacion"))]
    if preliminar["motivos"]:
        partes.append("Motivos: " + "; ".join(preliminar["motivos"]) + ".")
    if tensiones:
        partes.append("Tensiones detectadas por el Coordinador: " + "; ".join(tensiones))

    return {
        "veredicto": veredicto,
        "puntaje": preliminar["puntaje"],
        "puntaje_maximo": preliminar["puntaje_maximo"],
        "justificacion": "\n\n".join(p for p in partes if p),
        "tensiones": tensiones,
        "citas": [c for r in resultados for c in r.get("citas", [])],
    }
