"""Datos de las convocatorias de demostración: Bases, ofertas y resultado esperado de cada oferta.

Todo es ficticio: entidades, empresas, personas, RUC, DNI, colegiaturas y montos. Los RUC usan el
prefijo 2098, que SUNAT no ha asignado, y llevan un dígito verificador válido para que el portal
del postor los acepte.
"""
from dataclasses import dataclass, field

PESOS_RUC = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def ruc(base: str) -> str:
    suma = sum(int(d) * p for d, p in zip(base, PESOS_RUC))
    return base + str((11 - suma % 11) % 10)


@dataclass
class Cargo:
    """Personal clave que exigen las Bases."""
    nombre: str
    profesiones: str
    meses: int
    cargos_validos: str


@dataclass
class Factor:
    letra: str
    nombre: str
    puntaje: int
    evaluacion: str
    acreditacion: str
    asignacion: list[str]


@dataclass
class Servicio:
    """Una contratación que el postor presenta como experiencia."""
    cliente: str
    objeto: str
    contrato: str
    monto: float
    conformidad: str
    escaneada: bool = False


@dataclass
class Experiencia:
    cargo: str
    lugar: str
    inicio: str
    fin: str
    emisor: str
    escaneada: bool = False


@dataclass
class Profesional:
    cargo: str
    nombre: str
    dni: str
    profesion: str
    universidad: str
    colegiatura: str
    experiencias: list[Experiencia]


@dataclass
class Oferta:
    carpeta: str
    razon_social: str
    ruc: str
    representante: str
    dni_representante: str
    domicilio: str
    servicios: list[Servicio]
    personal: list[Profesional]
    resultado: str
    motivo: str
    esperado: dict[str, str]  # criterio → decisión o puntaje esperados
    consorcio: list[str] = field(default_factory=list)
    con_anexo3: bool = True
    con_promesa: bool = True


@dataclass
class Convocatoria:
    carpeta: str
    tipo: str  # «CONSULTORÍA DE OBRA» o «SERVICIO DE CONSULTORÍA EN GENERAL»
    nomenclatura: str
    entidad: str
    ruc_entidad: str
    domicilio: str
    objeto: str
    cuantia: float
    cuantia_letras: str
    plazo: str
    finalidad: str
    actividades: list[str]
    entregables: list[tuple[str, str]]
    especialidad: str
    anios_experiencia: int
    personal: list[Cargo]
    factores: list[Factor]
    no_aplican: str
    puntaje_minimo: int
    metodologia: list[tuple[str, list[str]]]  # secciones de la metodología de las ofertas
    ofertas: list[Oferta]


def soles(monto: float) -> str:
    entero, decimales = f"{monto:,.2f}".split(".")
    return f"S/ {entero.replace(',', ' ')},{decimales}"


def _factor_experiencia(letra: str, puntaje: int, cuantia: float, tramos: list[tuple[str, int]]) -> Factor:
    return Factor(
        letra, "EXPERIENCIA DEL POSTOR EN LA ESPECIALIDAD", puntaje,
        f"Se evalúa considerando el monto facturado acumulado por el postor en la especialidad, durante el "
        f"periodo indicado en los requisitos de calificación. M = monto facturado acumulado / cuantía de la "
        f"contratación ({soles(cuantia)}).",
        "Mediante los mismos documentos que acreditan la experiencia del postor en los requisitos de "
        "calificación (contratos u órdenes de servicio con su conformidad o constancia de prestación), "
        "detallados en el Anexo N.° 10.",
        [f"{condicion}: {puntos} puntos" for condicion, puntos in tramos],
    )


# ---------------------------------------------------------------------------------------------
# Convocatoria 1: supervisión de una obra de agua potable (consultoría de obra)
# ---------------------------------------------------------------------------------------------

JEFE_C1_A = Profesional(
    "Jefe de supervisión", "Ing. Rosa Elena Quispe Mamani", "99010101", "Ingeniera Sanitaria",
    "Universidad Nacional del Altiplano Andino", "CIP N.° 999101", [
        Experiencia("Residente de obra", "Obra «Ampliación del sistema de agua potable de Villa Rica Alta»",
                    "01/02/2014", "31/07/2016", "Municipalidad Distrital de Villa Rica Alta"),
        Experiencia("Supervisora de obra", "Obra «Mejoramiento del alcantarillado del barrio San Martín de Pampas»",
                    "01/09/2016", "31/12/2018", "Municipalidad Provincial de Pampas Verdes"),
        Experiencia("Jefa de supervisión", "Obra «Creación del sistema de saneamiento básico de Laguna Azul»",
                    "01/03/2019", "30/06/2021", "Programa Regional de Agua Rural Sierra Verde"),
    ])
SST_C1 = Profesional(
    "Especialista en seguridad y salud en el trabajo", "Ing. Miguel Ángel Torres Condori", "99010102",
    "Ingeniero Industrial", "Universidad Nacional de Ingeniería del Sur", "CIP N.° 999102", [
        Experiencia("Especialista en seguridad y salud en el trabajo",
                    "Obra «Mejoramiento del sistema de agua potable de Santa Lucía de Cerros»",
                    "01/01/2019", "31/12/2021", "Consorcio Supervisor Santa Lucía"),
    ])

CONVOCATORIA_1 = Convocatoria(
    carpeta="convocatoria_1_supervision_agua_potable",
    tipo="CONSULTORÍA DE OBRA",
    nomenclatura="CP-03-2026-MDNA/CS",
    entidad="MUNICIPALIDAD DISTRITAL DE NUEVA AURORA",
    ruc_entidad=ruc("2098000001"),
    domicilio="Plaza de Armas N.° 100, distrito de Nueva Aurora",
    objeto="CONTRATACIÓN DE LA CONSULTORÍA DE OBRA PARA LA SUPERVISIÓN DE LA EJECUCIÓN DE LA OBRA "
           "«MEJORAMIENTO Y AMPLIACIÓN DEL SERVICIO DE AGUA POTABLE Y SANEAMIENTO BÁSICO EN EL CENTRO "
           "POBLADO SANTA ROSA, DISTRITO DE NUEVA AURORA»",
    cuantia=480_000,
    cuantia_letras="CUATROCIENTOS OCHENTA MIL CON 00/100 SOLES",
    plazo="doscientos diez (210) días calendario, más treinta (30) días calendario para la liquidación",
    finalidad="Garantizar que la obra de agua potable y saneamiento del centro poblado Santa Rosa se ejecute "
              "conforme al expediente técnico aprobado, en el plazo, costo y calidad previstos.",
    actividades=[
        "Controlar la ejecución de la obra según el expediente técnico, las especificaciones técnicas y la normativa vigente.",
        "Revisar y aprobar los metrados y las valorizaciones mensuales del contratista.",
        "Verificar la calidad de los materiales y de los trabajos mediante ensayos de laboratorio.",
        "Supervisar el cumplimiento del plan de seguridad y salud en el trabajo de la obra.",
        "Absolver consultas del contratista y emitir informes técnicos sobre adicionales y ampliaciones de plazo.",
        "Participar en la recepción de la obra y elaborar el informe final de supervisión.",
    ],
    entregables=[
        ("Informe inicial", "a los quince (15) días calendario del inicio del servicio"),
        ("Informes mensuales de supervisión", "dentro de los cinco (5) primeros días de cada mes"),
        ("Informe final y liquidación de la obra", "a los treinta (30) días calendario de la recepción"),
    ],
    especialidad="supervisión de obras de saneamiento (sistemas de agua potable, alcantarillado o plantas de "
                 "tratamiento de agua), correspondiente a la especialidad OBRAS DE SANEAMIENTO Y AFINES",
    anios_experiencia=15,
    personal=[
        Cargo("JEFE DE SUPERVISIÓN", "Ingeniero Sanitario y/o Ingeniero Civil", 36,
              "jefe de supervisión y/o supervisor de obra y/o residente de obra, en obras de saneamiento"),
        Cargo("ESPECIALISTA EN SEGURIDAD Y SALUD EN EL TRABAJO", "Ingeniero Industrial y/o Ingeniero Civil", 24,
              "especialista y/o responsable y/o ingeniero de seguridad y salud en el trabajo, en obras"),
    ],
    factores=[
        _factor_experiencia("A", 50, 480_000, [
            ("M mayor o igual a 3", 50), ("M mayor o igual a 2 y menor que 3", 35),
            ("M mayor o igual a 1 y menor que 2", 20), ("M menor que 1", 0)]),
        Factor("B", "EXPERIENCIA ESPECÍFICA ADICIONAL DEL PERSONAL CLAVE", 30,
               "Se evalúa si el JEFE DE SUPERVISIÓN acredita al menos veinticuatro (24) meses de experiencia "
               "adicionales a los treinta y seis (36) meses exigidos en los requisitos de calificación, es decir, "
               "sesenta (60) meses o más en los cargos válidos. El tiempo traslapado se computa una sola vez.",
               "Con los mismos documentos que acreditan la experiencia del personal clave (contratos con su "
               "conformidad, constancias o certificados de trabajo).",
               ["Acredita 60 meses o más: 30 puntos", "No acredita 60 meses: 0 puntos"]),
        Factor("C", "METODOLOGÍA PROPUESTA", 20,
               "Se evalúa la metodología que propone el postor para la supervisión. Debe desarrollar: (i) la "
               "metodología de supervisión de la obra; (ii) un plan de trabajo con cronograma de actividades; y "
               "(iii) un plan de control de calidad con los ensayos a realizar.",
               "Documento «Metodología y plan de trabajo» firmado por el representante legal.",
               ["Desarrolla los tres elementos (i), (ii) y (iii): 20 puntos",
                "Desarrolla la metodología (i) pero le falta (ii) o (iii): 10 puntos",
                "No presenta metodología: 0 puntos"]),
    ],
    no_aplican="Los factores de sostenibilidad ambiental, sostenibilidad social e integridad en la contratación "
               "pública NO CORRESPONDEN en el presente procedimiento y no otorgan puntaje.",
    puntaje_minimo=70,
    metodologia=[
        ("1. Metodología de supervisión de la obra", [
            "La supervisión se organiza en tres frentes: captación y línea de conducción, reservorio y redes de "
            "distribución, y conexiones domiciliarias con unidades básicas de saneamiento.",
            "Cada frente tiene un ingeniero responsable que verifica diariamente los trabajos contra los planos "
            "y las especificaciones técnicas, registra las ocurrencias en el cuaderno de obra digital y reporta "
            "al jefe de supervisión.",
            "Las valorizaciones se revisan con metrados verificados en campo y se aprueban dentro del plazo de ley.",
        ]),
        ("2. Plan de trabajo y cronograma de actividades", [
            "El servicio se ejecuta en 210 días calendario de obra y 30 días de liquidación, con el siguiente "
            "cronograma mensual (meses 1 a 8): mes 1, revisión del expediente e informe inicial; meses 2 a 7, "
            "control de ejecución, valorizaciones e informes mensuales; mes 8, pruebas hidráulicas, recepción de "
            "obra, informe final y liquidación.",
        ]),
        ("3. Plan de control de calidad", [
            "Ensayos de compactación de zanjas cada 50 metros, resistencia del concreto en probetas por cada "
            "vaciado, prueba hidráulica de las tuberías por tramos y análisis bacteriológico del agua antes de la "
            "puesta en servicio. Los resultados se registran en protocolos firmados y se adjuntan a cada informe "
            "mensual.",
        ]),
    ],
    ofertas=[],
)

CONVOCATORIA_1.ofertas = [
    Oferta(
        carpeta="oferta_A_cumple_todo", razon_social="HIDROCONSULT ANDINA S.A.C.", ruc=ruc("2098100001"),
        representante="Carlos Alberto Mendoza Ríos", dni_representante="99100001",
        domicilio="Av. Los Ingenieros N.° 450, Nueva Aurora",
        servicios=[
            Servicio("Municipalidad Provincial de Pampas Verdes",
                     "Supervisión de la obra «Ampliación del sistema de agua potable de Pampas Verdes»",
                     "Contrato N.° 015-2021-MPPV", 620_000, "15/03/2022", escaneada=True),
            Servicio("Programa Regional de Agua Rural Sierra Verde",
                     "Supervisión de la obra «Creación del sistema de saneamiento básico de Laguna Azul»",
                     "Contrato N.° 008-2019-PRARSV", 540_000, "20/08/2021"),
            Servicio("Municipalidad Distrital de Villa Rica Alta",
                     "Supervisión de la obra «Mejoramiento del alcantarillado de Villa Rica Alta»",
                     "Contrato N.° 031-2023-MDVRA", 410_000, "05/11/2024"),
        ],
        personal=[JEFE_C1_A, SST_C1],
        resultado="Califica (100 puntos)",
        motivo="Cumple todos los requisitos. Una constancia de experiencia está escaneada y la lee el Agente Lector.",
        esperado={"Anexos 1, 2 y 3": "Cumple", "Promesa de consorcio": "No aplica",
                  "Experiencia del postor (S/ 1 570 000)": "Cumple", "Título del jefe de supervisión": "Cumple",
                  "Título del especialista SST": "Cumple", "Experiencia del jefe (86 meses)": "Cumple",
                  "Experiencia del especialista SST (36 meses)": "Cumple",
                  "Factor A (M = 3,27)": "50", "Factor B": "30", "Factor C": "20"},
    ),
    Oferta(
        carpeta="oferta_B_falta_anexo_3", razon_social="SANEAMIENTO Y OBRAS DEL SUR S.A.C.", ruc=ruc("2098100002"),
        representante="Lucía Fernanda Paredes Soto", dni_representante="99100002",
        domicilio="Jr. Las Retamas N.° 210, Nueva Aurora",
        servicios=[
            Servicio("Municipalidad Distrital de Cerro Dorado",
                     "Supervisión de la obra «Mejoramiento del servicio de agua potable de Cerro Dorado»",
                     "Contrato N.° 044-2020-MDCD", 1_000_000, "10/02/2022"),
            Servicio("Municipalidad Provincial de Río Claro",
                     "Supervisión de la obra «Construcción de la planta de tratamiento de aguas residuales de Río Claro»",
                     "Contrato N.° 012-2022-MPRC", 600_000, "30/06/2024"),
        ],
        personal=[
            Profesional("Jefe de supervisión", "Ing. Jorge Luis Salazar Puma", "99100003", "Ingeniero Civil",
                        "Universidad Nacional del Altiplano Andino", "CIP N.° 999103", [
                            Experiencia("Supervisor de obra", "Obra «Mejoramiento del servicio de agua potable de Cerro Dorado»",
                                        "01/01/2017", "31/12/2019", "Municipalidad Distrital de Cerro Dorado"),
                            Experiencia("Jefe de supervisión", "Obra «Construcción de la PTAR de Río Claro»",
                                        "01/02/2020", "31/05/2022", "Municipalidad Provincial de Río Claro"),
                        ]),
            Profesional("Especialista en seguridad y salud en el trabajo", "Ing. Ana María Choque Lima", "99100004",
                        "Ingeniera Civil", "Universidad Nacional de Ingeniería del Sur", "CIP N.° 999104", [
                            Experiencia("Responsable de seguridad y salud en el trabajo",
                                        "Obra «Construcción de la PTAR de Río Claro»",
                                        "01/02/2020", "31/05/2022", "Consorcio PTAR Río Claro"),
                        ]),
        ],
        resultado="No admitido",
        motivo="No presenta el Anexo N.° 3 (declaración jurada de veracidad y de no estar impedido), que es "
               "obligatorio para la admisión. El resto de la oferta es sólida: tendría 100 puntos.",
        esperado={"Anexos 1 y 2": "Cumple", "Anexo 3": "No Cumple", "Promesa de consorcio": "No aplica",
                  "Experiencia del postor (S/ 1 600 000)": "Cumple", "Títulos del personal": "Cumple",
                  "Experiencia del jefe (64 meses)": "Cumple", "Experiencia del especialista SST (28 meses)": "Cumple",
                  "Factor A (M = 3,33)": "50", "Factor B": "30", "Factor C": "20"},
        con_anexo3=False,
    ),
    Oferta(
        carpeta="oferta_C_experiencia_traslapada", razon_social="CONSULTORES INTEGRALES AYLLU S.A.C.",
        ruc=ruc("2098100003"), representante="Raúl Ernesto Vilca Huanca", dni_representante="99100005",
        domicilio="Calle Comercio N.° 78, Nueva Aurora",
        servicios=[
            Servicio("Municipalidad Distrital de San Pedro de Lagunillas",
                     "Supervisión de la obra «Ampliación de redes de agua potable de San Pedro de Lagunillas»",
                     "Contrato N.° 021-2021-MDSPL", 700_000, "18/04/2023"),
            Servicio("Municipalidad Provincial de Pampas Verdes",
                     "Supervisión de la obra «Mejoramiento del sistema de alcantarillado del sector Norte»",
                     "Contrato N.° 019-2023-MPPV", 560_000, "22/01/2025"),
        ],
        personal=[
            Profesional("Jefe de supervisión", "Ing. Pedro Pablo Ccama Ramos", "99100006", "Ingeniero Sanitario",
                        "Universidad Nacional del Altiplano Andino", "CIP N.° 999105", [
                            Experiencia("Supervisor de obra", "Obra «Ampliación de redes de agua potable de San Pedro de Lagunillas»",
                                        "01/03/2020", "31/08/2021", "Municipalidad Distrital de San Pedro de Lagunillas"),
                            Experiencia("Jefe de supervisión", "Obra «Mejoramiento del sistema de alcantarillado del sector Norte»",
                                        "01/02/2021", "30/09/2022", "Municipalidad Provincial de Pampas Verdes"),
                        ]),
            Profesional("Especialista en seguridad y salud en el trabajo", "Ing. Silvia Roxana Apaza Flores",
                        "99100007", "Ingeniera Industrial", "Universidad Nacional de Ingeniería del Sur",
                        "CIP N.° 999106", [
                            Experiencia("Ingeniera de seguridad y salud en el trabajo",
                                        "Obra «Ampliación de redes de agua potable de San Pedro de Lagunillas»",
                                        "01/01/2020", "30/06/2022", "Consorcio Lagunillas"),
                        ]),
        ],
        resultado="No califica",
        motivo="El jefe de supervisión presenta dos periodos que se superponen 7 meses: sumados a ojo dan 38 "
               "meses, pero el tiempo real es de 31 meses y las Bases exigen 36.",
        esperado={"Anexos 1, 2 y 3": "Cumple", "Promesa de consorcio": "No aplica",
                  "Experiencia del postor (S/ 1 260 000)": "Cumple", "Títulos del personal": "Cumple",
                  "Experiencia del jefe (31 meses, no 38)": "No Cumple",
                  "Experiencia del especialista SST (30 meses)": "Cumple",
                  "Factor A (M = 2,63)": "35", "Factor B": "0", "Factor C": "20"},
    ),
]

# ---------------------------------------------------------------------------------------------
# Convocatoria 2: expediente técnico de un centro de salud (consultoría de obra)
# ---------------------------------------------------------------------------------------------

def _personal_c2(prefijo: str, nombres: tuple[str, str, str], profesiones: tuple[str, str, str],
                 estructuras_colegiatura: str = "CIP") -> list[Profesional]:
    jefe, estructuras, electricas = nombres
    profesion_jefe, profesion_estructuras, profesion_electricas = profesiones
    return [
        Profesional("Jefe de proyecto", jefe, f"{prefijo}01", profesion_jefe, "Universidad Nacional del Centro Andino",
                    f"CAP N.° 99{prefijo[-2:]}1", [
                        Experiencia("Jefe de proyecto", "Expediente técnico «Creación del puesto de salud de Llanura Grande»",
                                    "01/03/2018", "31/12/2019", "Dirección Regional de Salud Sierra Verde"),
                        Experiencia("Coordinador de proyecto", "Expediente técnico «Mejoramiento de la institución educativa N.° 501»",
                                    "01/02/2021", "31/03/2022", "Municipalidad Provincial de Río Claro"),
                    ]),
        Profesional("Especialista en estructuras", estructuras, f"{prefijo}02", profesion_estructuras,
                    "Universidad Nacional del Centro Andino", f"{estructuras_colegiatura} N.° 99{prefijo[-2:]}2", [
                        Experiencia("Especialista en estructuras", "Expediente técnico «Creación del puesto de salud de Llanura Grande»",
                                    "01/03/2018", "31/12/2019", "Dirección Regional de Salud Sierra Verde"),
                        Experiencia("Proyectista de estructuras", "Expediente técnico «Mejoramiento del centro de salud de Cerro Dorado»",
                                    "01/04/2021", "31/10/2021", "Municipalidad Distrital de Cerro Dorado"),
                    ]),
        Profesional("Especialista en instalaciones eléctricas", electricas, f"{prefijo}03", profesion_electricas,
                    "Universidad Nacional de Ingeniería del Sur", f"CIP N.° 99{prefijo[-2:]}3", [
                        Experiencia("Especialista en instalaciones eléctricas",
                                    "Expediente técnico «Mejoramiento de la institución educativa N.° 501»",
                                    "01/02/2021", "31/03/2022", "Municipalidad Provincial de Río Claro"),
                    ]),
    ]


CONVOCATORIA_2 = Convocatoria(
    carpeta="convocatoria_2_expediente_centro_de_salud",
    tipo="CONSULTORÍA DE OBRA",
    nomenclatura="CP-02-2026-PRSSV/CS",
    entidad="PROGRAMA REGIONAL DE SALUD SIERRA VERDE",
    ruc_entidad=ruc("2098000002"),
    domicilio="Av. Independencia N.° 1200, ciudad de Sierra Verde",
    objeto="CONTRATACIÓN DE LA CONSULTORÍA DE OBRA PARA LA ELABORACIÓN DEL EXPEDIENTE TÉCNICO DEL PROYECTO "
           "«CREACIÓN DEL CENTRO DE SALUD DE CATEGORÍA I-3 EN LA LOCALIDAD DE VALLE ESCONDIDO»",
    cuantia=360_000,
    cuantia_letras="TRESCIENTOS SESENTA MIL CON 00/100 SOLES",
    plazo="ciento veinte (120) días calendario, sin contar los plazos de revisión de la entidad",
    finalidad="Contar con un expediente técnico completo y compatibilizado que permita ejecutar la obra del "
              "centro de salud de Valle Escondido y ampliar el acceso de la población a servicios de salud.",
    actividades=[
        "Elaborar los estudios básicos: levantamiento topográfico, estudio de mecánica de suelos e impacto ambiental.",
        "Desarrollar el proyecto de arquitectura conforme a la norma técnica de establecimientos de salud del primer nivel.",
        "Desarrollar los proyectos de estructuras, instalaciones sanitarias, eléctricas y mecánicas.",
        "Compatibilizar todas las especialidades y elaborar los metrados, el presupuesto y la fórmula polinómica.",
        "Levantar las observaciones de la entidad en cada entregable.",
    ],
    entregables=[
        ("Primer entregable: estudios básicos y anteproyecto", "a los cuarenta (40) días calendario"),
        ("Segundo entregable: proyecto de todas las especialidades", "a los noventa (90) días calendario"),
        ("Tercer entregable: expediente técnico completo", "a los ciento veinte (120) días calendario"),
    ],
    especialidad="elaboración de expedientes técnicos o estudios definitivos de obras de edificación de salud o "
                 "de educación, correspondiente a la especialidad EDIFICACIONES Y AFINES",
    anios_experiencia=15,
    personal=[
        Cargo("JEFE DE PROYECTO", "Arquitecto y/o Ingeniero Civil", 24,
              "jefe de proyecto y/o coordinador de proyecto y/o proyectista, en la elaboración de expedientes "
              "técnicos de edificaciones"),
        Cargo("ESPECIALISTA EN ESTRUCTURAS", "Ingeniero Civil", 24,
              "especialista en estructuras y/o proyectista de estructuras, en la elaboración de expedientes "
              "técnicos de edificaciones"),
        Cargo("ESPECIALISTA EN INSTALACIONES ELÉCTRICAS", "Ingeniero Electricista y/o Ingeniero Mecánico Electricista", 12,
              "especialista en instalaciones eléctricas y/o proyectista de instalaciones eléctricas"),
    ],
    factores=[
        _factor_experiencia("A", 60, 360_000, [
            ("M mayor o igual a 2", 60), ("M mayor o igual a 1,5 y menor que 2", 40),
            ("M mayor o igual a 1 y menor que 1,5", 20), ("M menor que 1", 0)]),
        Factor("B", "METODOLOGÍA PROPUESTA", 40,
               "Se evalúa la metodología que propone el postor para elaborar el expediente técnico. Debe "
               "desarrollar: (i) la metodología de elaboración de los estudios y del proyecto; (ii) un plan de "
               "trabajo con cronograma de entregables; y (iii) un plan de compatibilización entre especialidades.",
               "Documento «Metodología y plan de trabajo» firmado por el representante legal.",
               ["Desarrolla los tres elementos (i), (ii) y (iii): 40 puntos",
                "Desarrolla dos de los tres elementos: 20 puntos",
                "Desarrolla uno o ninguno: 0 puntos"]),
    ],
    no_aplican="Los factores de sostenibilidad ambiental, sostenibilidad social e integridad en la contratación "
               "pública NO CORRESPONDEN en el presente procedimiento y no otorgan puntaje.",
    puntaje_minimo=70,
    metodologia=[
        ("1. Metodología de elaboración del expediente técnico", [
            "El expediente se elabora en tres etapas: estudios básicos, anteproyecto y proyecto definitivo. Cada "
            "etapa termina con una revisión interna del jefe de proyecto antes de entregarla a la entidad.",
            "El proyecto de arquitectura sigue la norma técnica de infraestructura y equipamiento de "
            "establecimientos de salud del primer nivel de atención, con los ambientes de la cartera de servicios "
            "de la categoría I-3.",
        ]),
        ("2. Plan de trabajo y cronograma de entregables", [
            "Días 1 a 40: topografía, mecánica de suelos, evaluación ambiental y anteproyecto (primer entregable). "
            "Días 41 a 90: proyecto de arquitectura, estructuras e instalaciones (segundo entregable). Días 91 a "
            "120: metrados, presupuesto, especificaciones técnicas y expediente completo (tercer entregable).",
        ]),
        ("3. Plan de compatibilización entre especialidades", [
            "Se trabaja con un modelo BIM federado. Cada quince días se realiza una reunión de compatibilización "
            "en la que se detectan interferencias entre arquitectura, estructuras e instalaciones; cada "
            "interferencia se registra en una matriz con su responsable y su fecha de solución.",
        ]),
    ],
    ofertas=[],
)

CONVOCATORIA_2.ofertas = [
    Oferta(
        carpeta="oferta_A_cumple_todo", razon_social="ARQUITECTURA Y SALUD PROYECTOS S.A.C.", ruc=ruc("2098200001"),
        representante="Mariela Susana Gutiérrez Arce", dni_representante="99200001",
        domicilio="Av. Grau N.° 315, ciudad de Sierra Verde",
        servicios=[
            Servicio("Dirección Regional de Salud Sierra Verde",
                     "Elaboración del expediente técnico «Creación del puesto de salud de Llanura Grande»",
                     "Contrato N.° 004-2018-DIRESA-SV", 380_000, "28/02/2020", escaneada=True),
            Servicio("Municipalidad Provincial de Río Claro",
                     "Elaboración del expediente técnico «Mejoramiento de la institución educativa N.° 501»",
                     "Contrato N.° 009-2021-MPRC", 260_000, "15/04/2022"),
            Servicio("Municipalidad Distrital de Cerro Dorado",
                     "Elaboración del expediente técnico «Mejoramiento del centro de salud de Cerro Dorado»",
                     "Contrato N.° 017-2021-MDCD", 180_000, "30/11/2021"),
        ],
        personal=_personal_c2("992001", ("Arq. Daniel Esteban Rojas Medina", "Ing. Patricia Lorena Huamán Castro",
                                         "Ing. Víctor Hugo Chambi Luna"),
                            ("Arquitecto", "Ingeniera Civil", "Ingeniero Mecánico Electricista")),
        resultado="Califica (100 puntos)",
        motivo="Cumple todos los requisitos. Una constancia de experiencia está escaneada y la lee el Agente Lector.",
        esperado={"Anexos 1, 2 y 3": "Cumple", "Promesa de consorcio": "No aplica",
                  "Experiencia del postor (S/ 820 000)": "Cumple", "Títulos del personal (3)": "Cumple",
                  "Experiencia del jefe de proyecto (36 meses)": "Cumple",
                  "Experiencia del especialista en estructuras (29 meses)": "Cumple",
                  "Experiencia del especialista eléctrico (14 meses)": "Cumple",
                  "Factor A (M = 2,28)": "60", "Factor B": "40"},
    ),
    Oferta(
        carpeta="oferta_B_facturacion_insuficiente", razon_social="ESTUDIOS Y DISEÑOS VALLE ALTO S.A.C.",
        ruc=ruc("2098200002"), representante="Hernán Rodrigo Pinto Valdez", dni_representante="99200002",
        domicilio="Jr. Ayacucho N.° 88, ciudad de Sierra Verde",
        servicios=[
            Servicio("Municipalidad Distrital de Llanura Grande",
                     "Elaboración del expediente técnico «Mejoramiento de la institución educativa N.° 214»",
                     "Contrato N.° 006-2022-MDLG", 170_000, "12/09/2022"),
            Servicio("Municipalidad Distrital de Cerro Dorado",
                     "Elaboración del expediente técnico «Creación del puesto de salud de Alto Cerro»",
                     "Contrato N.° 023-2023-MDCD", 120_000, "03/05/2024"),
        ],
        personal=_personal_c2("992002", ("Arq. Gabriela Inés Nina Paucar", "Ing. Fernando José Quispe Alvarado",
                                         "Ing. Óscar Iván Mamani Ccori"),
                            ("Arquitecta", "Ingeniero Civil", "Ingeniero Electricista")),
        resultado="No califica",
        motivo="Su facturación acumulada es S/ 290 000, menor que la cuantía de S/ 360 000 que exige el "
               "requisito de experiencia del postor.",
        esperado={"Anexos 1, 2 y 3": "Cumple", "Promesa de consorcio": "No aplica",
                  "Experiencia del postor (S/ 290 000)": "No Cumple", "Títulos del personal (3)": "Cumple",
                  "Experiencia del personal clave (3)": "Cumple",
                  "Factor A (M = 0,81)": "0", "Factor B": "40"},
    ),
    Oferta(
        carpeta="oferta_C_profesion_no_corresponde", razon_social="DISEÑO HOSPITALARIO INTEGRAL S.A.C.",
        ruc=ruc("2098200003"), representante="Claudia Beatriz Ramos Tito", dni_representante="99200003",
        domicilio="Av. Panamericana N.° 2040, ciudad de Sierra Verde",
        servicios=[
            Servicio("Dirección Regional de Salud Sierra Verde",
                     "Elaboración del expediente técnico «Mejoramiento del centro de salud de Pampa Alegre»",
                     "Contrato N.° 011-2020-DIRESA-SV", 450_000, "20/10/2021"),
            Servicio("Municipalidad Provincial de Pampas Verdes",
                     "Elaboración del expediente técnico «Creación del hospital de día de Pampas Verdes»",
                     "Contrato N.° 027-2022-MPPV", 330_000, "14/08/2023"),
        ],
        personal=_personal_c2("992003", ("Arq. Ricardo Manuel Luque Benavides", "Arq. Sofía Valeria Cárdenas Poma",
                                         "Ing. Julio César Yupanqui Soto"),
                            ("Arquitecto", "Arquitecta", "Ingeniero Mecánico Electricista"),
                            estructuras_colegiatura="CAP"),
        resultado="No califica",
        motivo="La especialista en estructuras propuesta es arquitecta; las Bases exigen el título de "
               "Ingeniero Civil para ese cargo. Su experiencia como proyectista sí alcanza los 24 meses.",
        esperado={"Anexos 1, 2 y 3": "Cumple", "Promesa de consorcio": "No aplica",
                  "Experiencia del postor (S/ 780 000)": "Cumple",
                  "Título del especialista en estructuras (arquitecta)": "No Cumple",
                  "Títulos del jefe y del especialista eléctrico": "Cumple",
                  "Experiencia del personal clave (3)": "Cumple",
                  "Factor A (M = 2,17)": "60", "Factor B": "40"},
    ),
]

# ---------------------------------------------------------------------------------------------
# Convocatoria 3: plan de desarrollo urbano (consultoría en general)
# ---------------------------------------------------------------------------------------------

def _sig(nombre: str, dni: str, cip: str, escaneada: bool = False) -> Profesional:
    return Profesional("Especialista en sistemas de información geográfica", nombre, dni, "Ingeniero Geógrafo",
                       "Universidad Nacional del Centro Andino", cip, [
                           Experiencia("Especialista SIG", "Plan de Acondicionamiento Territorial de la provincia de Río Claro",
                                       "01/01/2020", "31/12/2021", "Municipalidad Provincial de Río Claro",
                                       escaneada=escaneada),
                           Experiencia("Analista SIG", "Esquema de Ordenamiento Urbano de Villa Rica Alta",
                                       "01/03/2022", "31/12/2022", "Municipalidad Distrital de Villa Rica Alta"),
                       ])


CONVOCATORIA_3 = Convocatoria(
    carpeta="convocatoria_3_plan_desarrollo_urbano",
    tipo="SERVICIO DE CONSULTORÍA EN GENERAL",
    nomenclatura="CP-01-2026-MPPL/CS",
    entidad="MUNICIPALIDAD PROVINCIAL DE PUERTO LIBERTAD",
    ruc_entidad=ruc("2098000003"),
    domicilio="Malecón Bolognesi N.° 1, ciudad de Puerto Libertad",
    objeto="CONTRATACIÓN DEL SERVICIO DE CONSULTORÍA PARA LA ELABORACIÓN DEL PLAN DE DESARROLLO URBANO DE LA "
           "CIUDAD DE PUERTO LIBERTAD 2027-2037",
    cuantia=400_000,
    cuantia_letras="CUATROCIENTOS MIL CON 00/100 SOLES",
    plazo="doscientos cuarenta (240) días calendario",
    finalidad="Contar con un instrumento de planificación urbana que oriente el crecimiento ordenado de la "
              "ciudad de Puerto Libertad, reduzca la exposición a riesgos de desastre y priorice la inversión "
              "pública en los próximos diez años.",
    actividades=[
        "Elaborar el diagnóstico urbano: población, usos de suelo, equipamiento, vivienda, movilidad y riesgos.",
        "Construir la cartografía base y temática en un sistema de información geográfica.",
        "Realizar talleres de participación ciudadana en cada sector de la ciudad.",
        "Formular la propuesta de zonificación, el sistema vial y la cartera de inversiones priorizada.",
        "Acompañar a la municipalidad en la exhibición pública y la aprobación del plan.",
    ],
    entregables=[
        ("Primer entregable: plan de trabajo y diagnóstico preliminar", "a los sesenta (60) días calendario"),
        ("Segundo entregable: diagnóstico urbano y talleres", "a los ciento cuarenta (140) días calendario"),
        ("Tercer entregable: propuesta final del plan", "a los doscientos cuarenta (240) días calendario"),
    ],
    especialidad="servicios de consultoría en planificación urbana o territorial (planes de desarrollo urbano, "
                 "planes de acondicionamiento territorial o esquemas de ordenamiento urbano)",
    anios_experiencia=8,
    personal=[
        Cargo("JEFE DE EQUIPO", "Arquitecto", 36,
              "jefe de equipo y/o coordinador y/o planificador urbano, en la elaboración de planes de desarrollo "
              "urbano o de instrumentos de planificación territorial"),
        Cargo("ESPECIALISTA EN SISTEMAS DE INFORMACIÓN GEOGRÁFICA", "Ingeniero Geógrafo y/o Geógrafo", 24,
              "especialista SIG y/o analista SIG, en estudios de planificación urbana o territorial"),
    ],
    factores=[
        _factor_experiencia("A", 40, 400_000, [
            ("M mayor o igual a 3", 40), ("M mayor o igual a 2 y menor que 3", 25),
            ("M mayor o igual a 1 y menor que 2", 10), ("M menor que 1", 0)]),
        Factor("B", "METODOLOGÍA PROPUESTA", 40,
               "Se evalúa la metodología que propone el postor. Debe desarrollar: (i) la metodología del "
               "diagnóstico urbano; (ii) la estrategia de participación ciudadana con talleres; y (iii) un plan de "
               "trabajo con cronograma.",
               "Documento «Metodología y plan de trabajo» firmado por el representante legal.",
               ["Desarrolla los tres elementos (i), (ii) y (iii): 40 puntos",
                "Desarrolla dos de los tres elementos: 20 puntos",
                "Desarrolla uno o ninguno: 0 puntos"]),
        Factor("C", "EXPERIENCIA ESPECÍFICA ADICIONAL DEL JEFE DE EQUIPO", 20,
               "Se evalúa si el JEFE DE EQUIPO acredita al menos veinticuatro (24) meses adicionales a los treinta "
               "y seis (36) meses exigidos en los requisitos de calificación, es decir, sesenta (60) meses o más. "
               "El tiempo traslapado se computa una sola vez.",
               "Con los mismos documentos que acreditan la experiencia del personal clave.",
               ["Acredita 60 meses o más: 20 puntos", "No acredita 60 meses: 0 puntos"]),
    ],
    no_aplican="Los factores de sostenibilidad ambiental, sostenibilidad social e integridad en la contratación "
               "pública NO CORRESPONDEN en el presente procedimiento y no otorgan puntaje.",
    puntaje_minimo=70,
    metodologia=[
        ("1. Metodología del diagnóstico urbano", [
            "El diagnóstico combina información secundaria (censos, catastro y estudios de riesgo) con trabajo de "
            "campo por sectores. Se levantan fichas de uso de suelo lote por lote en la zona consolidada y se "
            "analizan la vivienda, el equipamiento, la movilidad y la exposición a inundaciones y tsunamis.",
        ]),
        ("2. Estrategia de participación ciudadana", [
            "Se realizan seis talleres: uno de lanzamiento, cuatro sectoriales con juntas vecinales y "
            "organizaciones sociales, y uno de validación de la propuesta. Cada taller tiene acta, lista de "
            "asistencia y una matriz de aportes que se incorpora al diagnóstico y a la propuesta.",
        ]),
        ("3. Plan de trabajo y cronograma", [
            "Días 1 a 60: plan de trabajo, recopilación de información y cartografía base. Días 61 a 140: trabajo "
            "de campo, talleres sectoriales y diagnóstico. Días 141 a 240: propuesta de zonificación, sistema vial, "
            "cartera de inversiones, taller de validación y documento final.",
        ]),
    ],
    ofertas=[],
)

CONVOCATORIA_3.ofertas = [
    Oferta(
        carpeta="oferta_A_cumple_todo", razon_social="CIUDAD Y TERRITORIO CONSULTORES S.A.C.", ruc=ruc("2098300001"),
        representante="Andrés Felipe Salinas Ugarte", dni_representante="99300001",
        domicilio="Av. del Puerto N.° 560, ciudad de Puerto Libertad",
        servicios=[
            Servicio("Municipalidad Provincial de Río Claro",
                     "Elaboración del Plan de Acondicionamiento Territorial de la provincia de Río Claro",
                     "Contrato N.° 003-2020-MPRC", 520_000, "30/12/2021"),
            Servicio("Municipalidad Provincial de Pampas Verdes",
                     "Elaboración del Plan de Desarrollo Urbano de la ciudad de Pampas Verdes",
                     "Contrato N.° 014-2022-MPPV", 480_000, "20/06/2023"),
            Servicio("Municipalidad Distrital de Villa Rica Alta",
                     "Elaboración del Esquema de Ordenamiento Urbano de Villa Rica Alta",
                     "Contrato N.° 029-2022-MDVRA", 350_000, "15/01/2023"),
        ],
        personal=[
            Profesional("Jefe de equipo", "Arq. Valeria Cristina Montes Lozano", "99300002", "Arquitecta",
                        "Universidad Nacional del Centro Andino", "CAP N.° 993001", [
                            Experiencia("Planificadora urbana", "Plan de Desarrollo Urbano de Cerro Dorado",
                                        "01/01/2016", "31/12/2017", "Municipalidad Distrital de Cerro Dorado"),
                            Experiencia("Coordinadora", "Plan de Acondicionamiento Territorial de la provincia de Río Claro",
                                        "01/01/2020", "31/12/2021", "Municipalidad Provincial de Río Claro"),
                            Experiencia("Jefa de equipo", "Plan de Desarrollo Urbano de la ciudad de Pampas Verdes",
                                        "01/01/2022", "28/02/2023", "Municipalidad Provincial de Pampas Verdes"),
                            Experiencia("Jefa de equipo", "Esquema de Ordenamiento Urbano de Villa Rica Alta",
                                        "01/03/2023", "31/12/2023", "Municipalidad Distrital de Villa Rica Alta"),
                        ]),
            _sig("Ing. Tomás Eduardo Sánchez Vera", "99300003", "CIP N.° 993002", escaneada=True),
        ],
        resultado="Califica (100 puntos)",
        motivo="Cumple todos los requisitos. Un certificado de trabajo del especialista SIG está escaneado y lo "
               "lee el Agente Lector.",
        esperado={"Anexos 1, 2 y 3": "Cumple", "Promesa de consorcio": "No aplica",
                  "Experiencia del postor (S/ 1 350 000)": "Cumple", "Títulos del personal (2)": "Cumple",
                  "Experiencia del jefe de equipo (72 meses)": "Cumple",
                  "Experiencia del especialista SIG (34 meses)": "Cumple",
                  "Factor A (M = 3,38)": "40", "Factor B": "40", "Factor C": "20"},
    ),
    Oferta(
        carpeta="oferta_B_puntaje_insuficiente", razon_social="URBANISTAS DEL PACÍFICO S.A.C.", ruc=ruc("2098300002"),
        representante="Natalia Isabel Córdova Ruiz", dni_representante="99300004",
        domicilio="Jr. Libertad N.° 77, ciudad de Puerto Libertad",
        servicios=[
            Servicio("Municipalidad Distrital de Cerro Dorado",
                     "Elaboración del Plan de Desarrollo Urbano de Cerro Dorado",
                     "Contrato N.° 010-2021-MDCD", 280_000, "18/03/2022"),
            Servicio("Municipalidad Distrital de Llanura Grande",
                     "Elaboración del Esquema de Ordenamiento Urbano de Llanura Grande",
                     "Contrato N.° 005-2023-MDLG", 240_000, "09/02/2024"),
        ],
        personal=[
            Profesional("Jefe de equipo", "Arq. Martín Alonso Guzmán Peña", "99300005", "Arquitecto",
                        "Universidad Nacional del Centro Andino", "CAP N.° 993003", [
                            Experiencia("Planificador urbano", "Plan de Desarrollo Urbano de Cerro Dorado",
                                        "01/04/2020", "31/03/2022", "Municipalidad Distrital de Cerro Dorado"),
                            Experiencia("Jefe de equipo", "Esquema de Ordenamiento Urbano de Llanura Grande",
                                        "01/04/2022", "30/11/2023", "Municipalidad Distrital de Llanura Grande"),
                        ]),
            _sig("Ing. Lorena Patricia Vargas Ticona", "99300006", "CIP N.° 993004"),
        ],
        resultado="Puntaje insuficiente (50 de 70 puntos)",
        motivo="Cumple todos los requisitos, pero tiene poca experiencia: M = 1,3 da 10 puntos y su jefe de "
               "equipo no llega a 60 meses (0 puntos). Con la metodología completa suma 50, menos que el mínimo de 70.",
        esperado={"Anexos 1, 2 y 3": "Cumple", "Promesa de consorcio": "No aplica",
                  "Experiencia del postor (S/ 520 000)": "Cumple", "Títulos del personal (2)": "Cumple",
                  "Experiencia del jefe de equipo (44 meses)": "Cumple",
                  "Experiencia del especialista SIG (34 meses)": "Cumple",
                  "Factor A (M = 1,30)": "10", "Factor B": "40", "Factor C": "0"},
    ),
    Oferta(
        carpeta="oferta_C_consorcio_sin_promesa", razon_social="CONSORCIO PLAN URBANO LIBERTAD",
        ruc=ruc("2098300003"), representante="Gonzalo Martín Herrera Quiroz", dni_representante="99300007",
        domicilio="Av. Costanera N.° 900, ciudad de Puerto Libertad",
        servicios=[
            Servicio("Municipalidad Provincial de Río Claro",
                     "Elaboración del Plan de Desarrollo Urbano de la ciudad de Río Claro",
                     "Contrato N.° 021-2021-MPRC", 700_000, "10/10/2022"),
            Servicio("Municipalidad Provincial de Pampas Verdes",
                     "Elaboración del Plan de Acondicionamiento Territorial de la provincia de Pampas Verdes",
                     "Contrato N.° 002-2023-MPPV", 650_000, "25/04/2024"),
        ],
        personal=[
            Profesional("Jefe de equipo", "Arq. Elena Margarita Ríos Chávez", "99300008", "Arquitecta",
                        "Universidad Nacional del Centro Andino", "CAP N.° 993005", [
                            Experiencia("Coordinadora", "Plan de Desarrollo Urbano de Cerro Dorado",
                                        "01/01/2017", "31/12/2019", "Municipalidad Distrital de Cerro Dorado"),
                            Experiencia("Jefa de equipo", "Plan de Desarrollo Urbano de la ciudad de Río Claro",
                                        "01/01/2021", "30/09/2022", "Municipalidad Provincial de Río Claro"),
                            Experiencia("Jefa de equipo", "Plan de Acondicionamiento Territorial de Pampas Verdes",
                                        "01/10/2022", "31/03/2024", "Municipalidad Provincial de Pampas Verdes"),
                        ]),
            _sig("Ing. Ramiro Alfredo Cusi Mendoza", "99300009", "CIP N.° 993006"),
        ],
        resultado="No admitido",
        motivo="Declara en el Anexo N.° 1 que se presenta en consorcio, pero no adjunta la promesa de consorcio "
               "(Anexo N.° 4), obligatoria en ese caso. El resto de la oferta es sólida: tendría 100 puntos.",
        esperado={"Anexos 1, 2 y 3": "Cumple", "Promesa de consorcio": "No Cumple",
                  "Experiencia del postor (S/ 1 350 000)": "Cumple", "Títulos del personal (2)": "Cumple",
                  "Experiencia del jefe de equipo (75 meses)": "Cumple",
                  "Experiencia del especialista SIG (34 meses)": "Cumple",
                  "Factor A (M = 3,38)": "40", "Factor B": "40", "Factor C": "20"},
        consorcio=["TERRITORIO SOSTENIBLE S.A.C. (RUC " + ruc("2098300004") + "), 60 %",
                   "GEOMÁTICA APLICADA E.I.R.L. (RUC " + ruc("2098300005") + "), 40 %"],
        con_promesa=False,
    ),
]

CONVOCATORIAS = [CONVOCATORIA_1, CONVOCATORIA_2, CONVOCATORIA_3]
