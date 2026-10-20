"""Catálogo de verificaciones del módulo de revisión de Bases.

Es la fuente única del módulo: las reglas fijas, el agente revisor, el banco de casos de validación y el
documento para el asesor salen de esta lista. Las verificaciones con `criterio` necesitan que el asesor
defina un umbral o una regla de decisión que la normativa no fija.

Respaldo: Guía de actuaciones preparatorias de la DGA (MEF) y Bases estándar del concurso público, que
citan los artículos de la Ley N.° 32069 y de su Reglamento (D. S. N.° 009-2025-EF).
"""
from dataclasses import dataclass

CRITICO, ADVERTENCIA, SUGERENCIA = "Crítico", "Advertencia", "Sugerencia"
GRAVEDADES = (CRITICO, ADVERTENCIA, SUGERENCIA)
REGLA, AGENTE = "Regla fija", "Agente revisor"
RONDA_A, RONDA_B = "A", "B"

# Documentos que sube el comité. Ronda A: antes de convocar. Ronda B: antes de recibir ofertas.
TIPOS_DOCUMENTO = {
    "requerimiento": "Requerimiento del área usuaria (términos de referencia)",
    "certificacion": "Certificación de crédito presupuestario o previsión presupuestal",
    "aprobacion_expediente": "Aprobación del expediente de contratación",
    "estrategia": "Formato de estrategia de contratación",
    "interaccion_mercado": "Formato de interacción con el mercado",
    "designacion_evaluadores": "Designación de los evaluadores",
    "viabilidad": "Viabilidad del proyecto de inversión (CUI)",
    "bases": "Bases (versión para convocar)",
    "pliego": "Pliego de absolución de consultas y observaciones",
    "bases_integradas": "Bases Integradas",
    "pronunciamiento": "Pronunciamiento del OECE",
}
OBLIGATORIOS = {
    RONDA_A: ("requerimiento", "certificacion", "aprobacion_expediente", "bases"),
    RONDA_B: ("pliego", "bases_integradas"),
}
DOCUMENTOS_DE_RONDA = {
    RONDA_A: ("requerimiento", "certificacion", "aprobacion_expediente", "estrategia", "interaccion_mercado",
              "designacion_evaluadores", "viabilidad", "bases"),
    RONDA_B: ("pliego", "bases_integradas", "pronunciamiento"),
}
# En la ronda B se revisan las Bases Integradas; en la A, las Bases que se van a convocar.
BASES_DE_RONDA = {RONDA_A: "bases", RONDA_B: "bases_integradas"}


@dataclass(frozen=True)
class Verificacion:
    codigo: str
    categoria: str
    nombre: str
    respaldo: str
    metodo: str
    documentos: tuple[str, ...]
    gravedad: str
    rondas: tuple[str, ...] = (RONDA_A, RONDA_B)
    criterio: str | None = None


GUIA = "Guía de actuaciones preparatorias (DGA)"
GENERAL = "Bases estándar, Sección general"
BASES = "Bases estándar, Sección específica"

COMPLETITUD = "Completitud del expediente"
COHERENCIA = "Coherencia entre el expediente y las Bases"
FORMAL = "Cumplimiento formal de las Bases estándar"
ABSOLUCION = "Integración de las absoluciones"
PROPORCIONALIDAD = "Proporcionalidad y riesgos para la competencia"
CATEGORIAS = (COMPLETITUD, COHERENCIA, FORMAL, ABSOLUCION, PROPORCIONALIDAD)

VERIFICACIONES = [
    # --- Completitud del expediente ---
    Verificacion("EXP-01", COMPLETITUD, "Se adjunta el requerimiento del área usuaria",
                 f"{GUIA}, Cap. V (contenido del expediente)", REGLA, ("requerimiento",), CRITICO, (RONDA_A,)),
    Verificacion("EXP-02", COMPLETITUD, "Se adjunta la certificación de crédito presupuestario o la previsión",
                 f"{GUIA}, Cap. V", REGLA, ("certificacion",), CRITICO, (RONDA_A,)),
    Verificacion("EXP-03", COMPLETITUD, "Se adjunta la aprobación del expediente de contratación",
                 f"{GUIA}, Cap. V", REGLA, ("aprobacion_expediente",), CRITICO, (RONDA_A,)),
    Verificacion("EXP-04", COMPLETITUD, "Se adjunta el formato de estrategia de contratación suscrito por la DEC",
                 f"{GUIA}, Cap. III y V", REGLA, ("estrategia",), ADVERTENCIA, (RONDA_A,)),
    Verificacion("EXP-05", COMPLETITUD, "Se adjunta el formato de interacción con el mercado, cuando corresponde",
                 f"{GUIA}, Cap. IV y V", REGLA, ("interaccion_mercado",), ADVERTENCIA, (RONDA_A,)),
    Verificacion("EXP-06", COMPLETITUD, "Se adjunta el documento que designa a los evaluadores",
                 f"{GUIA}, Cap. V", REGLA, ("designacion_evaluadores",), SUGERENCIA, (RONDA_A,)),
    Verificacion("EXP-07", COMPLETITUD, "Si las Bases citan un proyecto de inversión (CUI), se adjunta su viabilidad",
                 f"{GUIA}, Cap. III, variable c)", REGLA, ("bases", "viabilidad"), ADVERTENCIA, (RONDA_A,)),

    # --- Coherencia entre el expediente y las Bases ---
    Verificacion("COH-01", COHERENCIA, "La cuantía de las Bases es la misma del expediente y de la estrategia",
                 f"{BASES}, Cap. I (nota sobre la cuantía) y {GUIA}, Cap. V", REGLA,
                 ("bases", "aprobacion_expediente", "estrategia"), CRITICO),
    Verificacion("COH-02", COHERENCIA, "La certificación presupuestal cubre la cuantía de la contratación",
                 f"{GUIA}, Cap. III, variable k) y Cap. V", REGLA, ("bases", "certificacion"), CRITICO),
    Verificacion("COH-03", COHERENCIA, "La fuente de financiamiento de las Bases coincide con la certificación",
                 f"{GUIA}, Cap. III, variable k)", REGLA, ("bases", "certificacion"), ADVERTENCIA),
    Verificacion("COH-04", COHERENCIA, "La fecha de aprobación del expediente que citan las Bases es la del "
                 "documento de aprobación", f"{BASES}, Cap. I (expediente de contratación)", REGLA,
                 ("bases", "aprobacion_expediente"), ADVERTENCIA),
    Verificacion("COH-05", COHERENCIA, "El objeto de la convocatoria es el mismo del requerimiento",
                 f"{GUIA}, Cap. II", AGENTE, ("bases", "requerimiento"), CRITICO),
    Verificacion("COH-06", COHERENCIA, "El Capítulo III de las Bases reproduce el requerimiento sin cambios",
                 f"{GUIA}, Cap. II: los evaluadores no pueden modificar directamente el requerimiento", AGENTE,
                 ("bases", "requerimiento"), CRITICO),
    Verificacion("COH-07", COHERENCIA, "Los requisitos de calificación de las Bases son los del requerimiento",
                 f"{GUIA}, Cap. III, variable f)", AGENTE, ("bases", "requerimiento"), CRITICO),
    Verificacion("COH-08", COHERENCIA, "El plazo de prestación de las Bases es el del requerimiento",
                 f"{GUIA}, Cap. II", REGLA, ("bases", "requerimiento"), ADVERTENCIA),
    Verificacion("COH-09", COHERENCIA, "La modalidad de pago, las garantías y los adelantos coinciden con la "
                 "estrategia de contratación", f"{GUIA}, Cap. III, variables h) y l)", AGENTE,
                 ("bases", "estrategia"), ADVERTENCIA),
    Verificacion("COH-10", COHERENCIA, "Lo que declaran las Bases sobre la difusión del requerimiento coincide con "
                 "la interacción con el mercado, y si no hubo difusión se prevé la elevación al OECE",
                 f"{BASES}, Cap. I, numeral 1.5 y {GENERAL}, numeral 2.1 c) (artículo 67 del Reglamento)", REGLA,
                 ("bases", "interaccion_mercado"), ADVERTENCIA),

    # --- Cumplimiento formal de las Bases estándar ---
    Verificacion("FOR-01", FORMAL, "La Sección general no fue modificada",
                 f"{GENERAL}: «no debe ser modificada en ningún extremo, bajo sanción de nulidad»", AGENTE,
                 ("bases",), CRITICO),
    Verificacion("FOR-02", FORMAL, "No quedan indicaciones de la plantilla sin completar ([ABC])",
                 "Bases estándar, simbología utilizada", REGLA, ("bases",), ADVERTENCIA),
    Verificacion("FOR-03", FORMAL, "Se eliminaron las notas «Importante para la entidad contratante»",
                 "Bases estándar, simbología utilizada", REGLA, ("bases",), SUGERENCIA),
    Verificacion("FOR-04", FORMAL, "Están todos los capítulos de la Sección específica (generalidades, "
                 "procedimiento, requerimiento, evaluación y proforma del contrato)",
                 f"{GUIA}, Cap. VI (contenido mínimo de las Bases)", REGLA, ("bases",), CRITICO),
    Verificacion("FOR-05", FORMAL, "Los factores de evaluación suman 100 puntos",
                 f"{BASES}, Cap. IV", REGLA, ("bases",), CRITICO),
    Verificacion("FOR-06", FORMAL, "Se fija un puntaje técnico mínimo",
                 f"{BASES}, Cap. IV, numeral 4.1", REGLA, ("bases",), CRITICO),
    Verificacion("FOR-07", FORMAL, "El cronograma da al menos 7 días hábiles para consultas y observaciones",
                 f"{GENERAL}, numeral 2.1 c)", REGLA, ("bases",), ADVERTENCIA, (RONDA_A,)),
    Verificacion("FOR-08", FORMAL, "La presentación de ofertas es al menos 7 días hábiles después de la "
                 "integración de las Bases", f"{GENERAL}, numeral 2.1 d)", REGLA, ("bases",), ADVERTENCIA, (RONDA_B,)),
    Verificacion("FOR-09", FORMAL, "No se exigen para la admisión documentos distintos de los previstos en las "
                 "Bases estándar", f"{BASES}, Cap. II (advertencia sobre documentos no previstos)", AGENTE,
                 ("bases",), ADVERTENCIA),
    Verificacion("FOR-10", FORMAL, "Los requisitos para perfeccionar el contrato no se piden como parte de la oferta",
                 f"{BASES}, Cap. II, numeral 2.3", AGENTE, ("bases",), ADVERTENCIA),

    # --- Integración de las absoluciones (solo ronda B) ---
    Verificacion("ABS-01", ABSOLUCION, "Cada consulta y observación del pliego tiene respuesta",
                 f"{GENERAL}, numeral 2.1 c)", REGLA, ("pliego",), ADVERTENCIA, (RONDA_B,)),
    Verificacion("ABS-02", ABSOLUCION, "Cada absolución que modifica las Bases está incorporada en las Bases "
                 "Integradas", f"{GENERAL}, numeral 2.1 c)", AGENTE, ("pliego", "bases_integradas"), CRITICO,
                 (RONDA_B,)),
    Verificacion("ABS-03", ABSOLUCION, "Las Bases Integradas no tienen cambios que no provengan del pliego",
                 f"{GENERAL}, numeral 2.1 c)", AGENTE, ("bases", "pliego", "bases_integradas"), CRITICO, (RONDA_B,)),
    Verificacion("ABS-04", ABSOLUCION, "Los cambios al requerimiento hechos en la absolución cuentan con la "
                 "conformidad del área usuaria", f"{GUIA}, Cap. II (no objeción del área usuaria)", AGENTE,
                 ("pliego", "requerimiento"), ADVERTENCIA, (RONDA_B,)),
    Verificacion("ABS-05", ABSOLUCION, "Si hubo pronunciamiento del OECE, sus disposiciones están incorporadas",
                 f"{GENERAL}, numeral 2.1 c) (artículo 67 del Reglamento)", AGENTE,
                 ("pronunciamiento", "bases_integradas"), CRITICO, (RONDA_B,)),

    # --- Proporcionalidad y riesgos para la competencia ---
    Verificacion("PRO-01", PROPORCIONALIDAD, "El monto de experiencia exigido al postor es proporcional a la cuantía",
                 f"{GUIA}, Cap. III, variable f): excluir requisitos que limitan la concurrencia", REGLA,
                 ("bases",), ADVERTENCIA,
                 criterio="Tope del monto exigido, en veces la cuantía (propuesta: más de 2 veces es advertencia)"),
    Verificacion("PRO-02", PROPORCIONALIDAD, "La experiencia exigida al personal clave es razonable para el objeto "
                 "y el plazo", f"{GUIA}, Cap. III, variable f)", AGENTE, ("bases", "requerimiento"), ADVERTENCIA,
                 criterio="Cuándo una exigencia de meses es excesiva para el cargo y el plazo"),
    Verificacion("PRO-03", PROPORCIONALIDAD, "Ningún factor concentra una parte desmedida del puntaje",
                 "Buena práctica de evaluación (valor por dinero)", REGLA, ("bases",), SUGERENCIA,
                 criterio="Peso máximo de un solo factor (propuesta: más de 60 puntos de 100)"),
    Verificacion("PRO-04", PROPORCIONALIDAD, "Los factores de evaluación no repiten un requisito de calificación sin "
                 "aportar valor adicional", f"{GUIA}, Cap. III, variable g)", AGENTE, ("bases",), SUGERENCIA),
    Verificacion("PRO-05", PROPORCIONALIDAD, "No hay requisitos tan específicos que parezcan dirigidos a un postor "
                 "(marcas, certificaciones poco comunes, experiencias muy particulares)",
                 f"{GUIA}, Cap. II: evitar características que no impactan en la funcionalidad", AGENTE,
                 ("bases", "requerimiento"), ADVERTENCIA),
    Verificacion("PRO-06", PROPORCIONALIDAD, "Una contratación de alto riesgo (desierta antes o con pocos postores) "
                 "tuvo una consulta al mercado", f"{GUIA}, Cap. I (segmentación) y Cap. IV (nivel de interacción)",
                 AGENTE, ("estrategia", "interaccion_mercado"), ADVERTENCIA, (RONDA_A,)),
    Verificacion("PRO-07", PROPORCIONALIDAD, "El plazo, los entregables y la forma de pago son coherentes entre sí",
                 f"{GUIA}, Cap. III", AGENTE, ("bases",), SUGERENCIA),
]

POR_CODIGO = {v.codigo: v for v in VERIFICACIONES}


def de_ronda(ronda: str) -> list[Verificacion]:
    return [v for v in VERIFICACIONES if ronda in v.rondas]
