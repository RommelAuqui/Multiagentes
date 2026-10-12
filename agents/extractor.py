from dataclasses import dataclass

from agents.gemini_client import ContextoIA, generar_json
from agents.reglas import ETAPAS, TIPOS, clave, normalizar_puntaje, normalizar_texto
from config import LLM_MODEL

MAX_CARACTERES_BASES = 300_000

PROMPT = """Eres el Agente Extractor de Bases de un comité de selección de concursos públicos de \
consultoría en Perú, regidos por la Ley N.º 32069 y las bases estándar aprobadas por el OECE.

A partir del texto de las Bases Integradas que se muestra al final, arma la matriz de evaluación de \
la propuesta técnica con tres etapas:
- "admision": documentos de presentación obligatoria para la admisión de la oferta (declaraciones \
juradas, anexos obligatorios, promesa de consorcio, etc.).
- "calificacion": requisitos de calificación (capacidad legal o habilitación, capacidad técnica y \
profesional, formación y experiencia del personal clave, experiencia del postor en la especialidad). \
Se cumplen o no se cumplen.
- "evaluacion": factores de evaluación de la propuesta técnica, cada uno con su puntaje máximo y la \
forma en que las Bases asignan el puntaje.

Reglas:
- Extrae solo lo que está escrito en las Bases: no inventes criterios ni puntajes. Si un dato no \
aparece, usa null.
- Copia la forma de acreditación (qué documento lo prueba) y, para los factores, la forma de asignar \
el puntaje (rangos, condiciones y puntos) con el detalle de las Bases.
- "tipo" es "legal" para documentos de admisión y capacidad legal, y "tecnico" para el resto.
- No incluyas la propuesta económica.
- Indica en "puntaje_minimo" el puntaje técnico mínimo para continuar en el concurso, si las Bases \
lo fijan.

Responde únicamente con un JSON de la forma:
{{"puntaje_minimo": n | null, "criterios": [{{"etapa": "admision" | "calificacion" | "evaluacion", \
"tipo": "legal" | "tecnico", "descripcion": "...", "acreditacion": "..." | null, \
"referencia": "Capítulo/numeral/página" | null, "obligatorio": true | false, \
"puntaje_maximo": n | null, "asignacion_puntaje": "..." | null}}]}}

Texto de las Bases:
{texto}
"""


@dataclass
class MatrizExtraida:
    criterios: list[dict]
    puntaje_minimo: float | None


def _a_booleano(valor, default: bool) -> bool:
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, str):
        return valor.strip().lower() not in ("false", "no", "0", "")
    return default


def _texto_opcional(valor) -> str | None:
    texto = normalizar_texto(valor)
    return texto if texto and clave(texto) not in ("null", "none") else None


def normalizar_criterio(c: dict) -> dict | None:
    etapa = clave(c.get("etapa")).replace(" ", "")
    etapa = {"factordeevaluacion": "evaluacion", "requisitodecalificacion": "calificacion"}.get(etapa, etapa)
    tipo = clave(c.get("tipo"))
    descripcion = normalizar_texto(c.get("descripcion"))
    if etapa not in ETAPAS or not descripcion:
        return None
    if tipo not in TIPOS:
        tipo = "legal" if etapa == "admision" else "tecnico"

    es_factor = etapa == "evaluacion"
    puntaje_maximo = normalizar_puntaje(c.get("puntaje_maximo"), None) if es_factor else None
    return {
        "etapa": etapa,
        "tipo": tipo,
        "descripcion": descripcion,
        "acreditacion": _texto_opcional(c.get("acreditacion")),
        "referencia": _texto_opcional(c.get("referencia")),
        "obligatorio": False if es_factor else _a_booleano(c.get("obligatorio"), default=True),
        "puntaje_maximo": puntaje_maximo or None,
        "asignacion_puntaje": _texto_opcional(c.get("asignacion_puntaje")) if es_factor else None,
    }


def extraer_criterios(texto_bases: str, contexto: ContextoIA) -> MatrizExtraida:
    prompt = PROMPT.format(texto=texto_bases[:MAX_CARACTERES_BASES])
    datos = generar_json(LLM_MODEL, prompt, contexto)

    criterios = datos.get("criterios")
    normalizados = (normalizar_criterio(c) for c in criterios if isinstance(c, dict)) if isinstance(criterios, list) else ()
    return MatrizExtraida(
        criterios=[c for c in normalizados if c is not None],
        puntaje_minimo=normalizar_puntaje(datos.get("puntaje_minimo"), None) or None,
    )
