from agents.gemini_client import generar_json
from config import LLM_MODEL

PROMPT_DELIBERACION = """Eres el Agente Coordinador de un comité evaluador de concursos públicos de \
consultoría en Perú, regidos por la Ley N.º 32069.

El postor ya fue evaluado de forma independiente por el Agente Legal y el Agente Técnico, y está \
legalmente habilitado para contratar (no incumple ningún requisito legal obligatorio). El postor \
cumple {puntaje_tecnico}% de los criterios técnicos evaluados.

Tu trabajo es deliberar entre ambas evaluaciones como lo haría un comité colegiado, aplicando este \
criterio de ponderación, deliberadamente permisivo con el cumplimiento técnico parcial:
- Un cumplimiento técnico parcial o razonable (aproximadamente 25% o más de los criterios técnicos \
  cumplidos) NO debe, por sí solo, causar la no admisión: para eso existe el puntaje técnico, que ya \
  refleja ese nivel de cumplimiento y permite comparar y ordenar postores entre sí en la matriz \
  comparativa. Postores con certificaciones deseables ausentes, documentos incompletos pero \
  presentes, o incluso varios criterios técnicos no acreditados, deben seguir siendo "Cumple" \
  mientras exista una base técnica mínima razonable.
- Declara "No Cumple" únicamente en casos extremos: cuando el cumplimiento técnico es muy bajo \
  (aproximadamente menos de 25%), o cuando falta por completo un elemento sin el cual el servicio \
  contratado no podría ejecutarse en absoluto (por ejemplo, el personal clave no acredita ninguna \
  experiencia relevante, o no se presentó metodología ni plan de trabajo alguno). Ante la duda, \
  prefiere "Cumple" con un puntaje bajo antes que descalificar.

Evaluación del Agente Legal:
{legal}

Evaluación del Agente Técnico:
{tecnico}

Redacta la conciliación en un párrafo claro, citando explícitamente los puntos de ambos agentes \
en los que te basas. Si detectas alguna tensión entre ambas evaluaciones, dilo explícitamente y \
explica cómo la resolviste, y qué peso le diste a cada una para llegar al veredicto final.

Responde únicamente con un JSON de la forma:
{{"veredicto": "Cumple" | "No Cumple", "conciliacion": "..."}}
"""


def _resumen_resultados(resultados: list[dict]) -> str:
    return "\n".join(
        f"- {r['criterio_descripcion']}: {r['veredicto']} — {r['justificacion']}"
        for r in resultados
    ) or "Sin criterios evaluados por este agente."


def _deliberar(resultados_legal: list[dict], resultados_tecnico: list[dict], puntaje_tecnico: float) -> dict:
    prompt = PROMPT_DELIBERACION.format(
        legal=_resumen_resultados(resultados_legal),
        tecnico=_resumen_resultados(resultados_tecnico),
        puntaje_tecnico=puntaje_tecnico,
    )
    return generar_json(LLM_MODEL, prompt)


def consolidar_dictamen(
    criterios_legales: list[dict],
    resultados_legal: list[dict],
    resultados_tecnico: list[dict],
) -> dict:
    obligatorios_incumplidos = [
        r for r, c in zip(resultados_legal, criterios_legales)
        if c["obligatorio"] and r["veredicto"] != "Cumple"
    ]

    cumplidos_tecnicos = sum(1 for r in resultados_tecnico if r["veredicto"] == "Cumple")
    puntaje = round((cumplidos_tecnicos / len(resultados_tecnico)) * 100, 2) if resultados_tecnico else 0.0

    citas = [c for r in resultados_legal + resultados_tecnico for c in r.get("citas", [])]

    if obligatorios_incumplidos:
        motivos = "; ".join(r["justificacion"] for r in obligatorios_incumplidos)
        return {
            "veredicto": "No Cumple",
            "puntaje": puntaje,
            "justificacion": f"Descalificado por incumplimiento legal (sin lugar a deliberación): {motivos}",
            "citas": citas,
        }

    deliberacion = _deliberar(resultados_legal, resultados_tecnico, puntaje)
    return {
        "veredicto": deliberacion["veredicto"],
        "puntaje": puntaje,
        "justificacion": deliberacion["conciliacion"],
        "citas": citas,
    }
