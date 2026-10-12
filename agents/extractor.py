from dataclasses import dataclass

from agents.gemini_client import ContextoIA, generar_json
from agents.reglas import ETAPAS, TIPOS, clave, normalizar_puntaje, normalizar_texto
from config import LLM_MODEL

# Unas Bases Integradas de ~100 páginas, con las escaneadas transcritas, rondan los 300 000 caracteres.
MAX_CARACTERES_BASES = 500_000

PROMPT = """Eres el Agente Extractor de Bases de un comité de selección de concursos públicos de \
consultoría en Perú, regidos por la Ley N.º 32069 y las bases estándar aprobadas por el OECE.

A partir del texto de las Bases Integradas que se muestra al final, arma la matriz de evaluación de \
la oferta técnica con tres etapas:
- "admision": documentos de presentación obligatoria para la admisión de la oferta (declaraciones \
juradas, anexos obligatorios, documento de representación, promesa de consorcio, etc.).
- "calificacion": requisitos de calificación (experiencia del postor en la especialidad, \
calificaciones y experiencia del personal clave, y demás requisitos que se acrediten en la oferta). \
Se cumplen o no se cumplen.
- "evaluacion": factores de evaluación de la oferta técnica, cada uno con su puntaje máximo y la \
forma en que las Bases asignan el puntaje.

Reglas:
- Usa solo la Sección Específica de las Bases: la Sección General repite reglas comunes a todos los \
concursos y no define los criterios de este.
- Extrae solo lo que está escrito en las Bases: no inventes criterios ni puntajes. Si un dato no \
aparece, usa null.
- Las Bases Integradas incorporan la absolución de consultas y observaciones: si una nota indica que \
un requisito, factor o ítem fue suprimido o modificado, aplica ese cambio y no incluyas lo suprimido.
- No incluyas los factores marcados como "no corresponde" o sin puntaje, ni la oferta económica.
- No incluyas los requisitos que, según las Bases, se acreditan recién para la suscripción del \
contrato (por ejemplo, equipamiento o infraestructura estratégica), porque no se evalúan en la \
oferta; salvo que las Bases indiquen que en este concurso sí se acreditan en la oferta.
- Si un requisito solo se exige en ciertos casos ("de ser el caso", "de corresponder", "en caso de \
consorcio"), empieza la descripción con la condición, por ejemplo: "Solo si el postor se presenta en \
consorcio: ...". Sigue siendo obligatorio cuando la condición se cumple. Los requisitos de \
participación en consorcio son siempre condicionales.
- Si un requisito o factor enumera varios cargos del personal clave con exigencias distintas, crea \
un criterio por cada cargo.
- Copia la forma de acreditación (qué documento lo prueba) y, para los factores, la forma de asignar \
el puntaje (rangos, condiciones y puntos) con el detalle de las Bases.
- Cada criterio debe poder evaluarse por sí solo: si depende de un dato que aparece en otra parte de \
las Bases (por ejemplo, la cuantía de la contratación o valor referencial, el plazo o la \
especialidad), escribe ese dato con su valor dentro de la descripción o de la forma de asignación.
- "tipo" es "legal" para documentos de admisión y capacidad legal, y "tecnico" para el resto.
- Indica en "puntaje_minimo" el puntaje técnico mínimo para continuar en el concurso, si las Bases \
lo fijan.

- Indica en "puntaje_total" el puntaje total de la evaluación técnica que declaran las Bases (la \
suma de todos los factores de evaluación), si lo indican.

Responde únicamente con un JSON de la forma:
{{"puntaje_minimo": n | null, "puntaje_total": n | null, "criterios": [{{"etapa": "admision" | \
"calificacion" | "evaluacion", "tipo": "legal" | "tecnico", "descripcion": "...", \
"acreditacion": "..." | null, "referencia": "Capítulo/numeral/página" | null, \
"obligatorio": true | false, "puntaje_maximo": n | null, "asignacion_puntaje": "..." | null}}]}}

Texto de las Bases:
{texto}
"""

CORRECCION = """

Revisión de un intento anterior: la suma de los puntajes máximos de los factores de evaluación fue \
{suma:g}, pero las Bases declaran un puntaje total de {total:g}. Factores de ese intento:
{factores}
Revisa que no haya factores duplicados, subfactores contados además de su factor, ni factores que \
no corresponden o que fueron suprimidos, y devuelve la matriz completa corregida con el mismo formato.
"""


@dataclass
class MatrizExtraida:
    criterios: list[dict]
    puntaje_minimo: float | None
    puntaje_total: float | None = None

    @property
    def suma_factores(self) -> float:
        return sum(c["puntaje_maximo"] or 0 for c in self.criterios if c["etapa"] == "evaluacion")

    @property
    def cuadra(self) -> bool:
        return self.puntaje_total is None or abs(self.suma_factores - self.puntaje_total) < 0.01


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


def _matriz(datos: dict) -> MatrizExtraida:
    criterios = datos.get("criterios")
    normalizados = (normalizar_criterio(c) for c in criterios if isinstance(c, dict)) if isinstance(criterios, list) else ()
    return MatrizExtraida(
        criterios=[c for c in normalizados if c is not None],
        puntaje_minimo=normalizar_puntaje(datos.get("puntaje_minimo"), None) or None,
        puntaje_total=normalizar_puntaje(datos.get("puntaje_total"), None) or None,
    )


def extraer_criterios(texto_bases: str, contexto: ContextoIA) -> MatrizExtraida:
    prompt = PROMPT.format(texto=texto_bases[:MAX_CARACTERES_BASES])
    matriz = _matriz(generar_json(LLM_MODEL, prompt, contexto))
    if matriz.cuadra:
        return matriz

    # Autoverificación: si los factores no suman el total que declaran las Bases, el agente se corrige una vez.
    factores = "\n".join(
        f"- {c['descripcion'][:150]} ({c['puntaje_maximo']:g} puntos)"
        for c in matriz.criterios if c["etapa"] == "evaluacion" and c["puntaje_maximo"]
    )
    correccion = CORRECCION.format(suma=matriz.suma_factores, total=matriz.puntaje_total, factores=factores)
    corregida = _matriz(generar_json(LLM_MODEL, prompt + correccion, contexto))
    corregida.puntaje_total = corregida.puntaje_total or matriz.puntaje_total
    if abs(corregida.suma_factores - matriz.puntaje_total) <= abs(matriz.suma_factores - matriz.puntaje_total):
        return corregida
    return matriz
