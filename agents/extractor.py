from agents.gemini_client import ContextoIA, generar_json
from config import LLM_MODEL

MAX_CARACTERES_BASES = 300_000

PROMPT = """Eres el Agente Extractor de Bases de un comité evaluador de concursos públicos de \
consultoría en Perú, regidos por la Ley N.º 32069.

A partir del siguiente texto de las Bases Integradas / Términos de Referencia, identifica los \
criterios de evaluación legales (documentación, declaraciones juradas, habilitación para \
contratar) y técnicos (perfil profesional, años de experiencia, metodología, plan de trabajo).

Responde únicamente con un JSON de la forma:
{{"criterios": [{{"tipo": "legal" | "tecnico", "descripcion": "...", "referencia": "Página/Artículo", "obligatorio": true | false}}]}}

Texto de las bases:
{texto}
"""


def _a_booleano(valor, default: bool) -> bool:
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, str):
        return valor.strip().lower() not in ("false", "no", "0", "")
    return default


def _normalizar_criterio(c: dict) -> dict | None:
    tipo = str(c.get("tipo", "")).strip().lower()
    descripcion = str(c.get("descripcion", "")).strip()
    if tipo not in ("legal", "tecnico") or not descripcion:
        return None
    return {
        "tipo": tipo,
        "descripcion": descripcion,
        "referencia": str(c.get("referencia") or "").strip() or None,
        "obligatorio": _a_booleano(c.get("obligatorio"), default=True),
    }


def extraer_criterios(texto_bases: str, contexto: ContextoIA) -> list[dict]:
    prompt = PROMPT.format(texto=texto_bases[:MAX_CARACTERES_BASES])
    datos = generar_json(LLM_MODEL, prompt, contexto)
    criterios = datos.get("criterios")
    if not isinstance(criterios, list):
        return []
    normalizados = (_normalizar_criterio(c) for c in criterios if isinstance(c, dict))
    return [c for c in normalizados if c is not None]
