"""Documentos ficticios del expediente y de la selección, para probar el módulo de revisión de Bases.

Por cada convocatoria de demostración se generan los documentos que recibe el comité (requerimiento,
certificación presupuestal, estrategia, interacción con el mercado, designación y aprobación del expediente),
las Bases que se convocaron y el pliego de absolución. Las Bases Integradas son las de la carpeta de la
convocatoria. Algunas convocatorias traen fallas sembradas: `esperado_a` y `esperado_b` dicen qué
verificaciones del catálogo deberían fallar en cada ronda.
"""
import re
from dataclasses import dataclass, field, replace
from pathlib import Path

from reportlab.platypus import Spacer

from demo.datos import CONVOCATORIAS, Convocatoria, soles
from demo.generar import AVISO, _ciudad, _pdf, firma, generar_bases, p, tabla, vinetas


@dataclass
class Consulta:
    numero: int
    participante: str
    tipo: str  # «Consulta» u «Observación»
    tema: str
    texto: str
    respuesta: str | None  # None: quedó sin respuesta en el pliego
    incorporacion: str = "No corresponde."


@dataclass
class Expediente:
    numero_requerimiento: str
    area_usuaria: str
    consultas: list[Consulta]
    # Las Bases que se convocaron, antes de integrar las absoluciones (None: iguales a las Integradas).
    antes: object = None
    meses_requerimiento: dict[str, int] = field(default_factory=dict)  # lo que pidió el área usuaria
    plazo_requerimiento: int | None = None
    monto_certificado: float | None = None
    fecha_aprobacion: str = "28/09/2026"
    modalidad_pago: str = "Suma alzada"
    riesgo: str = "Bajo"
    antecedente: str = "No hay procedimientos desiertos para este objeto en los dos últimos años."
    interaccion: str = "Indagación básica"
    difusion: bool = False
    esperado_a: list[str] = field(default_factory=list)
    esperado_b: list[str] = field(default_factory=list)
    descripcion: str = "Expediente coherente: no debería haber hallazgos."


def _cambiar_entregable(indice: int, plazo: str):
    def cambiar(c: Convocatoria) -> Convocatoria:
        entregables = list(c.entregables)
        entregables[indice] = (entregables[indice][0], plazo)
        return replace(c, entregables=entregables)
    return cambiar


def _plazo_de_120_dias(c: Convocatoria) -> Convocatoria:
    entregables = [*c.entregables[:-1], (c.entregables[-1][0], "a los ciento veinte (120) días calendario")]
    # Además, la Sección general (que no se puede modificar) acorta el plazo para apelar (FOR-01).
    return replace(c, plazo="ciento veinte (120) días calendario, sin contar los plazos de revisión de la entidad",
                   entregables=entregables, cambios_seccion_general=[
                       ("como máximo, dentro de los ocho días hábiles", "como máximo, dentro de los cinco días hábiles")])


_NO_SE_ACOGE = "No se acoge. Se mantiene lo establecido en las Bases."

EXPEDIENTES = {
    "convocatoria_1_supervision_agua_potable": Expediente(
        "REQUERIMIENTO N.° 045-2026-MDNA/GIDU", "Gerencia de Infraestructura y Desarrollo Urbano",
        antes=_cambiar_entregable(1, "dentro de los tres (3) primeros días de cada mes"),
        consultas=[
            Consulta(1, "Consultora del Altiplano S.A.C.", "Consulta", "Cap. III, B.2: experiencia del personal clave",
                     "¿Se acepta la experiencia como inspector de obra para acreditar la experiencia del jefe de "
                     "supervisión?", "No se acoge. Los cargos que se aceptan son los indicados en el numeral B.2."),
            Consulta(2, "Hidro Ingenieros S.R.L.", "Observación", "Cap. III, numeral 3.1: entregables",
                     "Tres días para presentar el informe mensual de supervisión es un plazo insuficiente; se "
                     "solicita ampliarlo a cinco días.",
                     "Se acoge, con la conformidad del área usuaria (Memorando N.° 120-2026-MDNA/GIDU). Los informes "
                     "mensuales se presentan dentro de los cinco (5) primeros días de cada mes.",
                     "Capítulo III, numeral 3.1: los informes mensuales se presentan dentro de los cinco (5) primeros "
                     "días de cada mes."),
        ],
    ),
    "convocatoria_2_expediente_centro_de_salud": Expediente(
        "REQUERIMIENTO N.° 012-2026-PRSSV/DI", "Dirección de Infraestructura",
        consultas=[Consulta(1, "Proyectos Médicos S.A.C.", "Consulta", "Cap. IV, factor B: metodología",
                            "¿Se puede presentar la metodología en formato de diapositivas?",
                            "Sí, siempre que desarrolle los tres elementos exigidos y esté firmada.")],
    ),
    "convocatoria_3_plan_desarrollo_urbano": Expediente(
        "REQUERIMIENTO N.° 033-2026-MPPL/GDU", "Gerencia de Desarrollo Urbano",
        consultas=[Consulta(1, "Urbanismo Integral S.A.C.", "Observación", "Cap. III, B.1: jefe de equipo",
                            "Se solicita aceptar también a ingenieros civiles como jefe de equipo.", _NO_SE_ACOGE)],
    ),
    "convocatoria_4_supervision_canal_de_riego": Expediente(
        "REQUERIMIENTO N.° 018-2026-PERVS/DO", "Dirección de Obras",
        meses_requerimiento={"ESPECIALISTA EN HIDRÁULICA": 12}, monto_certificado=500_000, fecha_aprobacion="30/09/2026",
        consultas=[
            Consulta(1, "Riegos del Sur S.A.C.", "Consulta", "Cap. III, numeral 3.1: entregables",
                     "¿Los informes mensuales deben incluir los protocolos de calidad firmados?",
                     "Sí. Los protocolos se adjuntan a cada informe mensual, según el plan de control de calidad."),
            Consulta(2, "Agua y Tierra Ingenieros S.A.C.", "Observación", "Cap. III, B.2: especialista en hidráulica",
                     "Se solicita aceptar también la experiencia como especialista en recursos hídricos.",
                     "Se acoge. Se acepta también la experiencia como especialista en recursos hídricos.",
                     "Capítulo III, numeral B.2: se agrega «especialista en recursos hídricos» a los cargos que se "
                     "aceptan para el especialista en hidráulica."),
            Consulta(3, "Ingeniería Hidráulica Andina E.I.R.L.", "Consulta", "Cap. IV, factor B",
                     "¿El tiempo como residente de obra cuenta para la experiencia adicional del jefe de supervisión?",
                     None),
        ],
        esperado_a=["COH-02", "COH-04", "COH-06", "COH-07"],
        esperado_b=["COH-02", "COH-04", "COH-06", "COH-07", "ABS-01", "ABS-02", "ABS-04"],
        descripcion="La certificación cubre S/ 500 000 de S/ 520 000; el área usuaria pidió 12 meses para el "
                    "especialista en hidráulica y las Bases exigen 24; la aprobación del expediente es del 30/09 y las "
                    "Bases dicen 28/09. En el pliego, la consulta 3 no tiene respuesta y la absolución 2 (acogida, sin "
                    "conformidad del área usuaria) no se incorporó en las Bases Integradas.",
    ),
    "convocatoria_5_expediente_puente_vehicular": Expediente(
        "REQUERIMIENTO N.° 027-2026-MPRE/GI", "Gerencia de Infraestructura",
        antes=_plazo_de_120_dias, plazo_requerimiento=150, modalidad_pago="Precios unitarios",
        riesgo="Alto", interaccion="Indagación básica", difusion=True,
        antecedente="El CP-02-2025-MPRE/CS, para el mismo objeto, fue declarado desierto en 2025.",
        consultas=[Consulta(1, "Puentes y Caminos S.A.C.", "Consulta", "Cap. II, cronograma",
                            "¿Se ampliará el plazo para presentar las ofertas?", _NO_SE_ACOGE)],
        # El plazo de 120 días está en el Cap. III: las Bases también alteran el requerimiento (COH-06).
        esperado_a=["COH-06", "COH-08", "COH-09", "COH-10", "FOR-01", "PRO-06"],
        esperado_b=["COH-09", "COH-10", "ABS-03"],
        descripcion="Las Bases convocadas fijan 120 días y el requerimiento 150, y reducen de ocho a cinco días hábiles el "
                    "plazo para apelar, en la Sección general; la estrategia decidió precios "
                    "unitarios y las Bases dicen suma alzada; la interacción con el mercado dice que sí hubo difusión "
                    "del requerimiento y las Bases que no; la contratación es de alto riesgo y solo hubo indagación. "
                    "Las Bases Integradas pasan a 150 días sin que ninguna absolución lo explique.",
    ),
}


def _dias(c: Convocatoria) -> int:
    return int(re.search(r"\((\d+)\)", c.plazo).group(1))


def _documento(c: Convocatoria, titulo: str, cuerpo: list, firmante: str, cargo: str, fecha: str) -> bytes:
    story = [p(c.entidad, "capitulo"), p(titulo, "titulo"), *cuerpo, Spacer(1, 6),
             p(f"{_ciudad(c)}, {fecha}"), firma(firmante, cargo)]
    return _pdf(story, f"{c.entidad} · {titulo.split('<br/>')[0]}", AVISO)


def requerimiento(c: Convocatoria, e: Expediente) -> bytes:
    plazo = f"{e.plazo_requerimiento} días calendario" if e.plazo_requerimiento else c.plazo
    personal = [["Cargo", "Profesión", "Experiencia mínima", "Cargos que se aceptan"],
                *[[cargo.nombre, cargo.profesiones, f"{e.meses_requerimiento.get(cargo.nombre, cargo.meses)} meses",
                   cargo.cargos_validos] for cargo in c.personal]]
    cuerpo = [
        p(f"<b>{e.numero_requerimiento}</b> · Área usuaria: {e.area_usuaria}"),
        p("TÉRMINOS DE REFERENCIA", "seccion"),
        p(f"<b>1. Objeto.</b> {c.objeto}."), p(f"<b>2. Finalidad pública.</b> {c.finalidad}"),
        p("<b>3. Actividades.</b>"), vinetas(c.actividades),
        p(f"<b>4. Plazo de prestación.</b> {plazo[0].upper() + plazo[1:]}."),
        p("<b>5. Entregables.</b>"),
        tabla([["Entregable", "Plazo de presentación"], *[[n, t] for n, t in c.entregables]], [9, 7.6]),
        p("REQUISITOS DE CALIFICACIÓN PROPUESTOS", "seccion"),
        p(f"<b>A. Experiencia del postor.</b> Monto facturado acumulado de {soles(c.cuantia)} en {c.especialidad}, "
          f"durante los {c.anios_experiencia} años anteriores a la presentación de ofertas."),
        p("<b>B. Personal clave.</b>"), tabla(personal, [4, 4, 2.6, 6]),
        p("<b>Fuente de financiamiento:</b> Recursos determinados. <b>Sistema de contratación propuesto:</b> suma alzada."),
    ]
    return _documento(c, "REQUERIMIENTO PARA LA CONTRATACIÓN", cuerpo, f"Jefe(a) de la {e.area_usuaria}",
                      "Área usuaria", "15 de septiembre de 2026")


def certificacion(c: Convocatoria, e: Expediente) -> bytes:
    monto = e.monto_certificado if e.monto_certificado is not None else c.cuantia
    filas = [["N.° de certificación", "0001284"], ["Fecha", "25/09/2026"], ["Fuente de financiamiento", "Recursos determinados"],
             ["Finalidad", c.objeto], ["Monto certificado", soles(monto)]]
    cuerpo = [p("La Oficina de Presupuesto certifica la existencia de crédito presupuestario disponible y "
                "libre de afectación para la siguiente contratación:"),
              tabla(filas, [5, 11.6], encabezado=False)]
    return _documento(c, "CERTIFICACIÓN DE CRÉDITO PRESUPUESTARIO", cuerpo, "Jefe(a) de la Oficina de Presupuesto",
                      "Oficina de Presupuesto", "25 de septiembre de 2026")


def estrategia(c: Convocatoria, e: Expediente) -> bytes:
    # Segmentación de la Guía de la DGA: la categoría sale de la cuantía y del riesgo.
    cuantia_tipo = "alta" if c.cuantia > 500_000 else "baja"
    categoria = {("baja", "Bajo"): "rutinaria", ("alta", "Bajo"): "operacional", ("baja", "Alto"): "crítica",
                 ("alta", "Alto"): "estratégica"}[(cuantia_tipo, e.riesgo)]
    factores = "; ".join(f"{f.letra}. {f.nombre.capitalize()} ({f.puntaje} puntos)" for f in c.factores)
    filas = [["Variable", "Análisis y decisión de la DEC"],
             ["Objeto", c.objeto], ["Cuantía de la contratación", soles(c.cuantia)],
             ["Tipo de procedimiento", f"Concurso público para {c.tipo.lower()}"],
             ["Segmentación", f"Cuantía {cuantia_tipo} y riesgo {e.riesgo.lower()}: contratación {categoria}."],
             ["Antecedentes del mercado", e.antecedente],
             ["Interacción con el mercado", e.interaccion],
             ["Tipo de evaluador", "Comité de selección de tres integrantes"],
             ["Requisitos de calificación", "Los propuestos en el requerimiento del área usuaria."],
             ["Factores de evaluación propuestos", factores],
             ["Modalidad de pago", e.modalidad_pago],
             ["Garantías", "Garantía de fiel cumplimiento del 10 % del monto del contrato, o retención si el postor "
                           "es micro o pequeña empresa."],
             ["Adelantos", "No se otorgan adelantos."], ["Fuente de financiamiento", "Recursos determinados"]]
    return _documento(c, "FORMATO DE ESTRATEGIA DE CONTRATACIÓN", [tabla(filas, [5, 11.6])],
                      "Responsable de la DEC", "Dependencia encargada de las contrataciones", "22 de septiembre de 2026")


def interaccion(c: Convocatoria, e: Expediente) -> bytes:
    filas = [["Tipo de interacción", e.interaccion],
             ["Fuentes de información", "SEACE de la Pladicop (procedimientos similares de 2024 a 2026) y registro de "
                                        "proveedores del RNP"],
             ["Difusión del requerimiento", "Sí: se difundió del 1 al 8 de septiembre de 2026." if e.difusion else
              "No se realizó la difusión del requerimiento."],
             ["Proveedores identificados", "6 proveedores con experiencia en la especialidad"],
             ["Cuantía", "Se mantiene la cuantía prevista en el PAC."],
             ["Conclusión", "Existe pluralidad de proveedores que pueden competir."]]
    return _documento(c, "FORMATO DE INTERACCIÓN CON EL MERCADO", [tabla(filas, [5, 11.6], encabezado=False)],
                      "Responsable de la DEC", "Dependencia encargada de las contrataciones", "10 de septiembre de 2026")


def designacion(c: Convocatoria, e: Expediente) -> bytes:
    cuerpo = [p("<b>Resolución Administrativa N.° 088-2026</b>"),
              p("SE RESUELVE: designar al comité de selección que conducirá el procedimiento de selección para la "
                f"{c.objeto}, integrado por:"),
              vinetas(["Presidente(a): Ing. Carla Mendoza Ruiz (área usuaria)",
                       "Primer miembro: Abog. Luis Torres Paz (dependencia encargada de las contrataciones)",
                       "Segundo miembro: Ing. Mario Quispe Lima (experto en el objeto de la contratación)"])]
    return _documento(c, "DESIGNACIÓN DEL COMITÉ DE SELECCIÓN", cuerpo, "Gerente(a) de Administración",
                      "Autoridad de la gestión administrativa", "20 de septiembre de 2026")


def aprobacion(c: Convocatoria, e: Expediente) -> bytes:
    filas = [["Objeto", c.objeto], ["Cuantía de la contratación", soles(c.cuantia)],
             ["Tipo de procedimiento", f"Concurso público para {c.tipo.lower()}"],
             ["Fecha de aprobación", e.fecha_aprobacion], ["Documento", "Formato de aprobación N.° 041-2026"]]
    cuerpo = [p("La autoridad de la gestión administrativa aprueba el expediente de contratación, que contiene el "
                "requerimiento, la estrategia de contratación, la interacción con el mercado, la cuantía, la "
                "designación del comité y la certificación de crédito presupuestario."),
              tabla(filas, [5, 11.6], encabezado=False)]
    return _documento(c, "FORMATO DE APROBACIÓN DEL EXPEDIENTE DE CONTRATACIÓN", cuerpo, "Gerente(a) de Administración",
                      "Autoridad de la gestión administrativa", e.fecha_aprobacion)


def pliego(c: Convocatoria, e: Expediente) -> bytes:
    filas = [["N.°", "Participante y tipo", "Numeral o tema", "Consulta u observación", "Absolución",
              "Precisión de lo que se incorpora en las Bases Integradas"]]
    for q in e.consultas:
        filas.append([str(q.numero), f"{q.participante} ({q.tipo.lower()})", q.tema, q.texto, q.respuesta or "",
                      q.incorporacion if q.respuesta else ""])
    cuerpo = [p(f"Concurso público N.° {c.nomenclatura}. El comité absuelve las consultas y observaciones "
                "presentadas por los participantes:"), tabla(filas, [0.8, 2.6, 2.4, 3.6, 3.8, 3.4])]
    return _documento(c, "PLIEGO DE ABSOLUCIÓN DE CONSULTAS Y OBSERVACIONES", cuerpo,
                      "Presidente(a) del comité de selección", "Comité de selección", "23 de octubre de 2026")


ARCHIVOS = [
    ("A1 Requerimiento.pdf", requerimiento), ("A2 Certificación presupuestal.pdf", certificacion),
    ("A3 Estrategia de contratación.pdf", estrategia), ("A4 Interacción con el mercado.pdf", interaccion),
    ("A5 Designación del comité.pdf", designacion), ("A6 Aprobación del expediente.pdf", aprobacion),
]


def generar_expedientes(carpeta_base: Path) -> None:
    for c in CONVOCATORIAS:
        e = EXPEDIENTES[c.carpeta]
        convocada = e.antes(c) if e.antes else c
        # El requerimiento es el original: anterior a las absoluciones, salvo que el error sea de las Bases
        # convocadas (plazo_requerimiento), que entonces se apartan de él.
        original = c if e.plazo_requerimiento else convocada
        destino = carpeta_base / c.carpeta / "revision_de_bases"
        destino.mkdir(parents=True, exist_ok=True)
        for nombre, funcion in ARCHIVOS:
            (destino / nombre).write_bytes(funcion(original if funcion is requerimiento else c, e))
        (destino / "A7 Bases para convocar.pdf").write_bytes(generar_bases(convocada, "BASES", "5 de octubre de 2026"))
        (destino / "B1 Pliego de absolución.pdf").write_bytes(pliego(c, e))
        print(f"{c.nomenclatura}: expediente y pliego en {destino}")

