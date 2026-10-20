"""Genera las convocatorias de demostración: Bases Integradas en PDF y tres ofertas por convocatoria.

Uso:
    python -m demo.generar
Requiere reportlab (requirements-dev.txt). Los archivos quedan en demo/convocatorias/.
"""
import random
import shutil
import textwrap
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import (KeepTogether, ListFlowable, ListItem, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

from demo.datos import CONVOCATORIAS, Convocatoria, Oferta, Profesional, soles

CARPETA = Path(__file__).parent / "convocatorias"
AVISO = "Documento ficticio para demostración académica: entidades, personas, RUC y montos son inventados."
CIUDADES = {"MDNA": "Nueva Aurora", "PRSSV": "Sierra Verde", "MPPL": "Puerto Libertad", "PERVS": "Valle Sereno",
            "MPRE": "Río Esmeralda"}
FECHA_OFERTAS = "9 de noviembre de 2026"

ESTILOS = {
    "normal": ParagraphStyle("normal", fontName="Helvetica", fontSize=10, leading=14, alignment=TA_JUSTIFY,
                             spaceAfter=6),
    "titulo": ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=13, leading=17, alignment=TA_CENTER,
                             spaceBefore=6, spaceAfter=10),
    "capitulo": ParagraphStyle("capitulo", fontName="Helvetica-Bold", fontSize=11.5, leading=15,
                               alignment=TA_CENTER, spaceBefore=4, spaceAfter=10),
    "seccion": ParagraphStyle("seccion", fontName="Helvetica-Bold", fontSize=10.5, leading=14, spaceBefore=8,
                              spaceAfter=5),
    "celda": ParagraphStyle("celda", fontName="Helvetica", fontSize=8.8, leading=11.5),
    "celda_negrita": ParagraphStyle("celda_negrita", fontName="Helvetica-Bold", fontSize=8.8, leading=11.5),
    "advertencia": ParagraphStyle("advertencia", fontName="Helvetica-Oblique", fontSize=9.2, leading=12.5,
                                  alignment=TA_JUSTIFY, leftIndent=12, rightIndent=12, spaceBefore=4,
                                  spaceAfter=8, borderColor=colors.grey, borderWidth=0.6, borderPadding=6),
    "portada": ParagraphStyle("portada", fontName="Helvetica-Bold", fontSize=16, leading=22, alignment=TA_CENTER,
                              spaceAfter=14),
    "centrado": ParagraphStyle("centrado", fontName="Helvetica", fontSize=10.5, leading=15, alignment=TA_CENTER,
                               spaceAfter=6),
}


def p(texto: str, estilo: str = "normal") -> Paragraph:
    return Paragraph(texto, ESTILOS[estilo])


def vinetas(items: list[str]) -> ListFlowable:
    return ListFlowable([ListItem(p(i), leftIndent=14) for i in items], bulletType="bullet", start="-",
                        leftIndent=14)


def tabla(filas: list[list], anchos: list[float], encabezado: bool = True) -> Table:
    celdas = [[c if not isinstance(c, str) else p(c, "celda_negrita" if encabezado and i == 0 else "celda")
               for c in fila] for i, fila in enumerate(filas)]
    t = Table(celdas, colWidths=[a * cm for a in anchos], repeatRows=1 if encabezado else 0)
    estilo = [("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP"),
              ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if encabezado:
        estilo.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6E6E6")))
    t.setStyle(TableStyle(estilo))
    return t


def firma(nombre: str, cargo: str, dni: str | None = None) -> KeepTogether:
    lineas = [Spacer(1, 26), p("_______________________________", "centrado"), p(f"<b>{nombre}</b>", "centrado"),
              p(cargo, "centrado")]
    if dni:
        lineas.append(p(f"DNI N.° {dni}", "centrado"))
    return KeepTogether(lineas)


def _pdf(story: list, encabezado: str, pie: str) -> bytes:
    buffer = BytesIO()

    def marco(lienzo, documento):
        lienzo.saveState()
        lienzo.setFont("Helvetica", 7.5)
        lienzo.setFillColor(colors.HexColor("#444444"))
        lienzo.drawString(2 * cm, A4[1] - 1.2 * cm, encabezado)
        lienzo.line(2 * cm, A4[1] - 1.35 * cm, A4[0] - 2 * cm, A4[1] - 1.35 * cm)
        lienzo.drawString(2 * cm, 1.1 * cm, pie)
        lienzo.drawRightString(A4[0] - 2 * cm, 1.1 * cm, f"Página {documento.page}")
        lienzo.restoreState()

    documento = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm,
                                  topMargin=2 * cm, bottomMargin=1.9 * cm)
    documento.build(story, onFirstPage=marco, onLaterPages=marco)
    return buffer.getvalue()


# ---------- Páginas escaneadas ----------

def _fuente(tamano: int, negrita: bool = False):
    from PIL import ImageFont

    for nombre in (("arialbd.ttf", "DejaVuSans-Bold.ttf") if negrita else ("arial.ttf", "DejaVuSans.ttf")):
        try:
            return ImageFont.truetype(nombre, tamano)
        except OSError:
            continue
    return ImageFont.load_default(size=tamano)


def pagina_escaneada(emisor: str, titulo: str, parrafos: list[str], firmante: str, semilla: int) -> bytes:
    """Dibuja un documento firmado y sellado como si se hubiera escaneado: giro, desenfoque, ruido y JPEG."""
    from PIL import Image, ImageDraw, ImageFilter

    imagen = Image.new("RGB", (1240, 1754), "white")
    dibujo = ImageDraw.Draw(imagen)
    dibujo.text((620, 150), emisor.upper(), font=_fuente(34, True), fill="black", anchor="mm")
    dibujo.line((140, 190, 1100, 190), fill="black", width=2)
    dibujo.text((620, 300), titulo, font=_fuente(40, True), fill="black", anchor="mm")
    y = 420
    for parrafo in parrafos:
        for linea in textwrap.wrap(parrafo, 58):
            dibujo.text((140, y), linea, font=_fuente(31), fill="black")
            y += 46
        y += 30
    # Firma manuscrita y sello redondo.
    azar = random.Random(semilla)
    puntos = [(470 + i * 14, y + 170 + azar.randint(-22, 22)) for i in range(22)]
    dibujo.line(puntos, fill=(20, 30, 120), width=4)
    dibujo.line((400, y + 220, 840, y + 220), fill="black", width=2)
    dibujo.text((620, y + 255), firmante, font=_fuente(28), fill="black", anchor="mm")
    dibujo.ellipse((860, y + 100, 1100, y + 340), outline=(30, 60, 160), width=5)
    dibujo.text((980, y + 205), "SELLO", font=_fuente(30, True), fill=(30, 60, 160), anchor="mm")
    dibujo.text((980, y + 245), "LOGÍSTICA", font=_fuente(22), fill=(30, 60, 160), anchor="mm")
    dibujo.text((620, 1660), AVISO, font=_fuente(20), fill=(90, 90, 90), anchor="mm")

    imagen = imagen.rotate(0.9, fillcolor="white").filter(ImageFilter.GaussianBlur(0.7))
    pixeles = imagen.load()
    for _ in range(35000):
        pixeles[azar.randrange(1240), azar.randrange(1754)] = (azar.randint(130, 200),) * 3
    jpeg = BytesIO()
    imagen.save(jpeg, "JPEG", quality=65)

    salida = BytesIO()
    lienzo = canvas.Canvas(salida, pagesize=A4)
    lienzo.drawImage(ImageReader(BytesIO(jpeg.getvalue())), 0, 0, width=A4[0], height=A4[1])
    lienzo.showPage()
    lienzo.save()
    return salida.getvalue()


def unir(partes: list[bytes]) -> bytes:
    escritor = PdfWriter()
    for parte in partes:
        for pagina in PdfReader(BytesIO(parte)).pages:
            escritor.add_page(pagina)
    salida = BytesIO()
    escritor.write(salida)
    return salida.getvalue()


# ---------- Bases Integradas ----------

def _encabezado_bases(c: Convocatoria) -> str:
    return f"BASES INTEGRADAS · CONCURSO PÚBLICO N.° {c.nomenclatura} · {c.entidad}"


def _seccion_general() -> list:
    s = [p("SECCIÓN GENERAL", "portada"), p("DISPOSICIONES COMUNES A TODOS LOS PROCEDIMIENTOS DE SELECCIÓN", "capitulo"),
         p("CAPÍTULO I: ETAPAS DEL PROCEDIMIENTO DE SELECCIÓN", "capitulo")]
    apartados = [
        ("1.1. REFERENCIAS", "Cuando en las presentes Bases se menciona la Ley, se entiende que se refiere a la Ley "
         "N.° 32069, Ley General de Contrataciones Públicas, y cuando se menciona el Reglamento, a su Reglamento "
         "aprobado por Decreto Supremo N.° 009-2025-EF."),
        ("1.2. CONVOCATORIA", "El procedimiento se convoca mediante su publicación en el SEACE, en la fecha "
         "indicada en el cronograma. Las Bases y sus anexos están disponibles para todos los proveedores."),
        ("1.3. REGISTRO DE PARTICIPANTES", "Para participar, el proveedor debe contar con inscripción vigente en el "
         "Registro Nacional de Proveedores (RNP) en el registro correspondiente al objeto de la contratación, y "
         "registrarse como participante a través del SEACE hasta el día anterior a la presentación de ofertas."),
        ("1.4. CONSULTAS, OBSERVACIONES E INTEGRACIÓN DE LAS BASES", "Los participantes pueden formular consultas y "
         "observaciones a las Bases dentro del plazo del cronograma. Los evaluadores las absuelven mediante un "
         "pliego publicado en el SEACE. Las presentes son BASES INTEGRADAS: incorporan las precisiones y "
         "modificaciones producto de dicha absolución y constituyen las reglas definitivas del procedimiento."),
        ("1.5. PRESENTACIÓN DE OFERTAS", "Las ofertas se presentan en forma electrónica, en archivos PDF, en el "
         "plazo del cronograma. Los documentos que acompañan la oferta pueden ser copias simples. Las "
         "declaraciones juradas y los formatos deben estar firmados por el postor o su representante legal."),
        ("1.6. ADMISIÓN, CALIFICACIÓN Y EVALUACIÓN", "Los evaluadores verifican primero que la oferta contenga los "
         "documentos para la admisión; si falta alguno, la oferta no es admitida. Luego verifican que el postor "
         "cumpla los requisitos de calificación; si no los cumple, la oferta es descalificada. Finalmente, "
         "asignan el puntaje de cada factor de evaluación. Las ofertas que no alcanzan el puntaje técnico "
         "mínimo no pasan a la evaluación económica."),
        ("1.7. OTORGAMIENTO DE LA BUENA PRO", "La buena pro se otorga al postor con el mejor puntaje total y se "
         "publica en el SEACE junto con las actas que sustentan la admisión, la calificación y la evaluación."),
    ]
    for titulo, texto in apartados:
        s += [p(titulo, "seccion"), p(texto)]
    return s


def _capitulo_generalidades(c: Convocatoria) -> list:
    return [
        p("SECCIÓN ESPECÍFICA", "portada"),
        p("CONDICIONES ESPECIALES DEL PROCEDIMIENTO DE SELECCIÓN", "capitulo"),
        p("CAPÍTULO I: GENERALIDADES", "capitulo"),
        p("1.1. ENTIDAD CONTRATANTE", "seccion"),
        tabla([["Nombre", c.entidad], ["RUC N.°", c.ruc_entidad], ["Domicilio legal", c.domicilio]],
              [4, 12.6], encabezado=False),
        p("1.2. OBJETO DE LA CONVOCATORIA", "seccion"),
        p(f"El presente procedimiento de selección tiene por objeto la {c.objeto}."),
        p("1.3. CUANTÍA DE LA CONTRATACIÓN", "seccion"),
        p(f"La cuantía de la contratación asciende a {soles(c.cuantia)} ({c.cuantia_letras}), incluidos los "
          "impuestos de ley y cualquier otro concepto que incida en el costo total del servicio."),
        p("1.4. EXPEDIENTE DE CONTRATACIÓN", "seccion"),
        p("El expediente de contratación fue aprobado el 28 de septiembre de 2026."),
        p("1.5. FUENTE DE FINANCIAMIENTO", "seccion"), p("Recursos determinados."),
        p("1.6. SISTEMA DE CONTRATACIÓN", "seccion"), p("Suma alzada."),
        p("1.7. PLAZO DE PRESTACIÓN DEL SERVICIO", "seccion"),
        p(f"El servicio se presta en el plazo de {c.plazo}, conforme a los términos de referencia."),
        p("1.8. BASE LEGAL", "seccion"),
        vinetas(["Ley N.° 32069, Ley General de Contrataciones Públicas.",
                 "Decreto Supremo N.° 009-2025-EF, Reglamento de la Ley General de Contrataciones Públicas.",
                 "Ley de Presupuesto del Sector Público para el año fiscal 2026.",
                 "Ley N.° 27444, Ley del Procedimiento Administrativo General."]),
    ]


def _capitulo_procedimiento(c: Convocatoria) -> list:
    return [
        PageBreak(), p("CAPÍTULO II: DEL PROCEDIMIENTO DE SELECCIÓN", "capitulo"),
        p("2.1. CRONOGRAMA DEL PROCEDIMIENTO", "seccion"),
        tabla([["Etapa", "Fecha"], ["Convocatoria", "5 de octubre de 2026"],
               ["Registro de participantes", "Del 6 de octubre al 6 de noviembre de 2026"],
               ["Consultas y observaciones", "Del 6 al 16 de octubre de 2026"],
               ["Absolución e integración de las Bases", "23 de octubre de 2026"],
               ["Presentación de ofertas", FECHA_OFERTAS],
               ["Admisión, calificación y evaluación", "Del 10 al 13 de noviembre de 2026"],
               ["Otorgamiento de la buena pro", "16 de noviembre de 2026"]], [8, 8.6]),
        p("2.2. CONTENIDO DE LAS OFERTAS", "seccion"),
        p("Las ofertas contienen un índice de documentos y la siguiente documentación:"),
        p("<b>A. OFERTA TÉCNICA</b>"),
        p("<b>2.2.1. Documentación de presentación obligatoria</b>"),
        p("<b>2.2.1.1. Documentos para la admisión de la oferta.</b> Los evaluadores verifican la presentación de "
          "los siguientes documentos. De no cumplir con lo requerido, la oferta se considera NO ADMITIDA."),
        vinetas(["a) Declaración jurada de datos del postor. (Anexo N.° 1)",
                 "b) Pacto de integridad, firmado por el postor o su representante legal. (Anexo N.° 2)",
                 "c) Declaración jurada manifestando que el postor: (i) es responsable de la veracidad de los "
                 "documentos e información de su oferta; y (ii) no se encuentra impedido para contratar con el "
                 "Estado, de acuerdo con el artículo 33 de la Ley. (Anexo N.° 3)",
                 "d) Promesa de consorcio con firmas legalizadas, de ser el caso, en la que se consigne a los "
                 "integrantes, el representante común, el domicilio común y las obligaciones y el porcentaje de "
                 "participación de cada integrante. (Anexo N.° 4)"]),
        p("Advertencia: el documento del literal d) solo se exige cuando el postor se presenta en consorcio. Si el "
          "postor declara en el Anexo N.° 1 que se presenta en consorcio y no adjunta la promesa de consorcio, la "
          "oferta no es admitida.", "advertencia"),
        p("<b>2.2.1.2. Documentos para acreditar los requisitos de calificación.</b> Incorporar en la oferta los "
          "documentos que acreditan los «Requisitos de Calificación» que se detallan en el Capítulo III de la "
          "presente sección."),
        p("<b>2.2.2. Documentación de presentación facultativa.</b> Incorporar en la oferta los documentos que "
          "acreditan los «Factores de Evaluación» del Capítulo IV, a efectos de obtener el puntaje previsto para "
          "cada factor."),
        p("<b>B. OFERTA ECONÓMICA</b>"),
        p("La oferta económica se presenta empleando el Anexo N.° 6. Se evalúa después de la evaluación técnica y "
          "solo para los postores que alcanzan el puntaje técnico mínimo; no forma parte de la evaluación técnica."),
        p("2.3. REQUISITOS PARA PERFECCIONAR EL CONTRATO", "seccion"),
        p("El postor ganador de la buena pro presenta, para perfeccionar el contrato, los siguientes documentos. "
          "NO forman parte de la oferta y no se verifican en la admisión ni en la calificación:"),
        vinetas(["a) Garantía de fiel cumplimiento del contrato o autorización de retención.",
                 "b) Contrato de consorcio con firmas legalizadas de cada integrante, de ser el caso.",
                 "c) Código de cuenta interbancaria (CCI).",
                 "d) Copia de la vigencia del poder del representante legal.",
                 "e) Copia del documento de identidad del representante legal.",
                 "f) Domicilio y correo electrónico para las notificaciones durante la ejecución contractual.",
                 "g) Detalle de los precios unitarios y de los gastos generales del precio ofertado."]),
        p("2.4. FORMA DE PAGO", "seccion"),
        p("El pago se realiza por cada entregable aprobado, previa conformidad del área usuaria, dentro de los "
          "diez (10) días calendario siguientes a su otorgamiento."),
    ]


def _capitulo_requerimiento(c: Convocatoria) -> list:
    s = [PageBreak(), p("CAPÍTULO III: REQUERIMIENTO", "capitulo"), p("3.1. TÉRMINOS DE REFERENCIA", "seccion"),
         p(f"<b>Objeto.</b> {c.objeto}."), p(f"<b>Finalidad pública.</b> {c.finalidad}"),
         p("<b>Actividades del consultor.</b>"), vinetas(c.actividades),
         p(f"<b>Plazo.</b> {c.plazo[0].upper() + c.plazo[1:]}."), p("<b>Entregables.</b>"),
         tabla([["Entregable", "Plazo de presentación"], *[[e, plazo] for e, plazo in c.entregables]], [9, 7.6]),
         PageBreak(), p("3.2. REQUISITOS DE CALIFICACIÓN", "seccion"),
         p("<b>A. EXPERIENCIA DEL POSTOR EN LA ESPECIALIDAD</b>"),
         p(f"<b>Requisito:</b> el postor debe acreditar un monto facturado acumulado equivalente a "
           f"{soles(c.cuantia)} ({c.cuantia_letras}), es decir, una (1) vez la cuantía de la contratación, por la "
           f"contratación de servicios de {c.especialidad}, durante los {c.anios_experiencia} años anteriores a la "
           "fecha de presentación de ofertas, que se computan desde la fecha de la conformidad."),
         p("<b>Acreditación:</b> copia simple de (i) contratos u órdenes de servicio y su respectiva conformidad o "
           "constancia de prestación; o (ii) comprobantes de pago cuya cancelación se acredite documentalmente. El "
           "postor debe llenar y presentar el Anexo N.° 10, referido a la experiencia del postor en la especialidad."),
         p("<b>B. CAPACIDAD TÉCNICA Y PROFESIONAL</b>"),
         p("<b>B.1. Calificaciones del personal clave</b>"),
         tabla([["N.°", "Cargo", "Profesión", "Grado o título"],
                *[[str(i), cargo.nombre, cargo.profesiones, "Título profesional"]
                  for i, cargo in enumerate(c.personal, start=1)]], [1.2, 6, 6, 3.4]),
         p("<b>Acreditación:</b> el postor consigna en el Anexo N.° 15 los nombres y apellidos, el documento de "
           "identidad, la universidad que expidió el título y el título profesional obtenido por cada integrante "
           "del personal clave. Los evaluadores verifican los títulos en el registro nacional de grados y títulos."),
         p("<b>B.2. Experiencia del personal clave</b>"),
         tabla([["N.°", "Cargo", "Tiempo mínimo", "Cargos desempeñados que se aceptan"],
                *[[str(i), cargo.nombre, f"{cargo.meses} meses", cargo.cargos_validos]
                  for i, cargo in enumerate(c.personal, start=1)]], [1.2, 5, 2.6, 7.8]),
         p("<b>Acreditación:</b> copia simple de cualquiera de los siguientes documentos: (i) contratos y su "
           "respectiva conformidad; (ii) constancias; (iii) certificados de trabajo; o (iv) cualquier otro "
           "documento que demuestre fehacientemente la experiencia, con indicación del cargo y de las fechas de "
           "inicio y fin."),
         p("Advertencia: de presentarse experiencia ejecutada en paralelo (traslape), el periodo traslapado se "
           "computa una sola vez. Si los documentos indican solo meses, sin días, se considera el mes completo.",
           "advertencia")]
    return s


def _capitulo_evaluacion(c: Convocatoria) -> list:
    s = [PageBreak(), p("CAPÍTULO IV: EVALUACIÓN DE OFERTAS", "capitulo"), p("4.1. EVALUACIÓN TÉCNICA", "seccion"),
         p(f"La evaluación técnica se realiza sobre cien (100) puntos. Para acceder a la evaluación económica, el "
           f"postor debe obtener un puntaje técnico mínimo de {c.puntaje_minimo} puntos."),
         p("4.2. FACTORES DE EVALUACIÓN", "seccion")]
    for f in c.factores:
        izquierda = [p(f"<b>{f.letra}. {f.nombre}</b>", "celda"), Spacer(1, 4),
                     p(f"<b>Evaluación:</b> {f.evaluacion}", "celda"), Spacer(1, 4),
                     p(f"<b>Acreditación:</b> {f.acreditacion}", "celda")]
        derecha = [p(f"<b>{f.puntaje} puntos</b>", "celda"), Spacer(1, 4),
                   *[p(linea, "celda") for linea in f.asignacion]]
        s += [tabla([["Factor", "Puntaje / metodología para su asignación"], [izquierda, derecha]], [10.6, 6]),
              Spacer(1, 8)]
    s += [p(c.no_aplican, "advertencia"),
          p(f"<b>PUNTAJE TOTAL DE LA EVALUACIÓN TÉCNICA: 100 puntos. Puntaje técnico mínimo: {c.puntaje_minimo} "
            "puntos.</b>")]
    return s


def _capitulo_contrato_y_anexos(c: Convocatoria) -> list:
    s = [PageBreak(), p("CAPÍTULO V: PROFORMA DEL CONTRATO", "capitulo"),
         p(f"Conste por el presente documento la {c.objeto}, que "
           f"celebra de una parte la {c.entidad.title()}, en adelante LA ENTIDAD, y de la otra parte "
           "[NOMBRE DEL CONTRATISTA], en adelante EL CONTRATISTA, en los términos siguientes:"),
         vinetas(["CLÁUSULA PRIMERA: objeto. EL CONTRATISTA se obliga a prestar el servicio conforme a los términos "
                  "de referencia y a su oferta.",
                  "CLÁUSULA SEGUNDA: monto contractual y forma de pago, según la oferta económica y el numeral 2.4.",
                  "CLÁUSULA TERCERA: plazo de ejecución, según el numeral 1.7 de la Sección Específica.",
                  "CLÁUSULA CUARTA: garantías, conformidad, penalidades y resolución, según la Ley y el Reglamento.",
                  "CLÁUSULA QUINTA: solución de controversias mediante conciliación o arbitraje."]),
         PageBreak(), p("ANEXOS", "portada")]
    formatos = [
        ("ANEXO N.° 1: DECLARACIÓN JURADA DE DATOS DEL POSTOR",
         "El que suscribe, [NOMBRE DEL POSTOR O REPRESENTANTE LEGAL], identificado con DNI N.° [   ], declara bajo "
         "juramento que la siguiente información se sujeta a la verdad: nombre o razón social, RUC, domicilio "
         "legal, teléfono, correo electrónico y si se presenta en forma individual o en consorcio."),
        ("ANEXO N.° 2: PACTO DE INTEGRIDAD",
         "El postor se compromete a actuar con integridad y a no ofrecer, dar ni recibir, directa o "
         "indirectamente, ningún beneficio indebido durante el procedimiento de selección y la ejecución del "
         "contrato."),
        ("ANEXO N.° 3: DECLARACIÓN JURADA",
         "El postor declara bajo juramento: (i) que es responsable de la veracidad de los documentos e "
         "información que presenta; y (ii) que no se encuentra impedido para contratar con el Estado, conforme al "
         "artículo 33 de la Ley."),
        ("ANEXO N.° 4: PROMESA DE CONSORCIO (de ser el caso)",
         "Los integrantes se comprometen a formar un consorcio para presentar una oferta conjunta, designan a su "
         "representante común y declaran las obligaciones y el porcentaje de participación de cada uno."),
        ("ANEXO N.° 6: OFERTA ECONÓMICA", "Monto total de la oferta, incluidos todos los tributos y costos."),
        ("ANEXO N.° 10: EXPERIENCIA DEL POSTOR EN LA ESPECIALIDAD",
         "Relación de contrataciones: cliente, objeto del contrato, número de contrato, fecha de la conformidad, "
         "monto facturado y monto facturado acumulado."),
        ("ANEXO N.° 15: PERSONAL CLAVE PROPUESTO",
         "Relación del personal clave: cargo, nombres y apellidos, documento de identidad, profesión, "
         "universidad que expidió el título y número de colegiatura."),
    ]
    for titulo, texto in formatos:
        s += [p(titulo, "seccion"), p(texto)]
    return s


def generar_bases(c: Convocatoria) -> bytes:
    portada = [
        Spacer(1, 4 * cm), p(c.entidad, "portada"), Spacer(1, 1 * cm), p("BASES INTEGRADAS", "portada"),
        p(f"CONCURSO PÚBLICO PARA {c.tipo}", "capitulo"), p(f"N.° {c.nomenclatura}", "capitulo"),
        Spacer(1, 1 * cm), p(c.objeto, "centrado"), Spacer(1, 2 * cm),
        p(f"{_ciudad(c)}, 23 de octubre de 2026", "centrado"),
        Spacer(1, 3 * cm), p(AVISO, "advertencia"), PageBreak(),
    ]
    story = (portada + _seccion_general() + [PageBreak()] + _capitulo_generalidades(c) + _capitulo_procedimiento(c)
             + _capitulo_requerimiento(c) + _capitulo_evaluacion(c) + _capitulo_contrato_y_anexos(c))
    return _pdf(story, _encabezado_bases(c), AVISO)


# ---------- Ofertas ----------

def _ciudad(c: Convocatoria) -> str:
    return CIUDADES[c.nomenclatura.split("-")[-1].split("/")[0]]


def _cabecera_anexo(titulo: str, c: Convocatoria) -> list:
    return [p(titulo, "titulo"), p(f"Señores evaluadores<br/>CONCURSO PÚBLICO N.° {c.nomenclatura}<br/>Presente.-")]


def _correo(o: Oferta) -> str:
    return "logistica@" + "".join(ch for ch in o.razon_social.split()[0].lower() if ch.isalpha()) + ".example"


def documento_admision(c: Convocatoria, o: Oferta) -> bytes:
    firma_rep = firma(o.representante, "Representante legal" if not o.consorcio else "Representante común",
                      o.dni_representante)
    lugar = f"{_ciudad(c)}, {FECHA_OFERTAS}"
    documentos = [("Anexo N.° 1: Declaración jurada de datos del postor", "01 Anexos de admisión")]
    if o.con_anexo2:
        documentos.append(("Anexo N.° 2: Pacto de integridad", "01 Anexos de admisión"))
    if o.con_anexo3:
        documentos.append(("Anexo N.° 3: Declaración jurada", "01 Anexos de admisión"))
    if o.consorcio and o.con_promesa:
        documentos.append(("Anexo N.° 4: Promesa de consorcio", "01 Anexos de admisión"))
    documentos += [("Anexo N.° 10 y constancias de experiencia del postor", "02 Experiencia del postor"),
                   ("Anexo N.° 15, currículos y certificados del personal clave", "03 Personal clave"),
                   ("Metodología y plan de trabajo", "04 Metodología y plan de trabajo")]
    if any(s.aparte for s in o.servicios):
        documentos.append(("Certificados de conformidad adicionales", "05 Constancias adicionales"))
    indice = [["N.°", "Documento", "Archivo"], *[[str(i), d, a] for i, (d, a) in enumerate(documentos, start=1)]]
    tipo = ("Persona jurídica. Se presenta en forma INDIVIDUAL, no en consorcio." if not o.consorcio else
            "Se presenta en CONSORCIO, integrado por: " + "; ".join(o.consorcio) + ".")
    story = [p("OFERTA TÉCNICA", "portada"), p(f"CONCURSO PÚBLICO N.° {c.nomenclatura}", "capitulo"),
             p(f"Postor: <b>{o.razon_social}</b> · RUC N.° {o.ruc}", "centrado"), Spacer(1, 10),
             p("ÍNDICE DE DOCUMENTOS", "seccion"), tabla(indice, [1.2, 10, 5.4]), PageBreak(),
             *_cabecera_anexo("ANEXO N.° 1<br/>DECLARACIÓN JURADA DE DATOS DEL POSTOR", c),
             p(f"El que suscribe, {o.representante}, identificado con DNI N.° {o.dni_representante}, "
               f"{'representante legal' if not o.consorcio else 'representante común'} de {o.razon_social}, "
               "declara bajo juramento que la siguiente información se sujeta a la verdad:"),
             tabla([["Nombre o razón social", o.razon_social], ["RUC N.°", o.ruc], ["Domicilio legal", o.domicilio],
                    ["Teléfono", "01-555-0100"], ["Correo electrónico", _correo(o)],
                    ["MYPE", "No"], ["Tipo de postor", tipo]], [5, 11.6], encabezado=False),
             p(lugar), firma_rep]
    if o.con_anexo2:
        story += [PageBreak(), *_cabecera_anexo("ANEXO N.° 2<br/>PACTO DE INTEGRIDAD", c),
                  p(f"{o.razon_social} se compromete a actuar con integridad durante el procedimiento de selección y "
                    "la ejecución del contrato; a no ofrecer, dar ni recibir, directa o indirectamente, ningún "
                    "beneficio indebido; a no coludir con otros postores; y a denunciar cualquier acto de corrupción "
                    "del que tome conocimiento. Acepta que el incumplimiento de este pacto da lugar a las "
                    "responsabilidades que establece la ley."),
                  p(lugar), firma_rep]
    if o.con_anexo3:
        story += [PageBreak(), *_cabecera_anexo("ANEXO N.° 3<br/>DECLARACIÓN JURADA", c),
                  p(f"Mediante el presente, {o.razon_social} declara bajo juramento:"),
                  vinetas(["i) Que es responsable de la veracidad de los documentos e información que presenta en "
                           "su oferta.",
                           "ii) Que no se encuentra impedido para contratar con el Estado, conforme al artículo 33 de "
                           "la Ley N.° 32069, Ley General de Contrataciones Públicas.",
                           "iii) Que conoce, acepta y se somete a las Bases, condiciones y reglas del procedimiento."]),
                  p(lugar), firma_rep]
    if o.consorcio and o.con_promesa:
        story += [PageBreak(), *_cabecera_anexo("ANEXO N.° 4<br/>PROMESA DE CONSORCIO", c),
                  p("Los integrantes se comprometen a formar un consorcio: " + "; ".join(o.consorcio) + "."),
                  p(f"Representante común: {o.representante}."), p(lugar), firma_rep]
    return _pdf(story, f"{o.razon_social} · Oferta técnica · CP N.° {c.nomenclatura}", AVISO)


def documento_experiencia(c: Convocatoria, o: Oferta) -> bytes:
    acumulado, filas = 0.0, [["N.°", "Cliente", "Objeto del contrato", "Contrato", "Fecha de conformidad", "Monto facturado"]]
    for i, s in enumerate(o.servicios, start=1):
        acumulado += s.monto
        filas.append([str(i), s.cliente, s.objeto, s.contrato, s.conformidad, soles(s.monto)])
    anexo = [*_cabecera_anexo("ANEXO N.° 10<br/>EXPERIENCIA DEL POSTOR EN LA ESPECIALIDAD", c),
             p(f"El que suscribe, representante de {o.razon_social}, detalla la experiencia del postor en la "
               "especialidad:"),
             tabla([*filas, ["", "", "", "", "Total", soles(acumulado)]], [0.9, 2.6, 4.0, 3.4, 2.5, 3.2]),
             p(f"<b>Monto facturado acumulado: {soles(acumulado)}</b>"),
             p(f"{_ciudad(c)}, {FECHA_OFERTAS}"), firma(o.representante, "Representante legal", o.dni_representante)]
    partes = [_pdf(anexo, f"{o.razon_social} · Experiencia del postor", AVISO)]
    for i, s in enumerate(o.servicios, start=1):
        if s.aparte:
            continue
        parrafos = [f"La {s.cliente} hace constar que {o.razon_social}, con RUC N.° {o.ruc}, prestó el servicio de "
                    f"{s.objeto[0].lower() + s.objeto[1:]}, en el marco del {s.contrato}, por un monto total de "
                    f"{soles(s.monto)}, incluidos los impuestos de ley.",
                    f"El servicio se ejecutó a satisfacción de la entidad, que otorgó la conformidad el {s.conformidad}.",
                    "Se expide la presente constancia a solicitud del interesado."]
        if s.escaneada:
            partes.append(pagina_escaneada(s.cliente, "CONSTANCIA DE PRESTACIÓN", parrafos,
                                           "Jefe de la Oficina de Logística", semilla=i))
        else:
            partes.append(_pdf([p(s.cliente.upper(), "capitulo"), p("CONSTANCIA DE PRESTACIÓN DE SERVICIOS", "titulo"),
                                *[p(t) for t in parrafos], p(f"{s.conformidad}"),
                                firma("Jefe de la Oficina de Logística", s.cliente)],
                               f"{o.razon_social} · Experiencia del postor", AVISO))
    return unir(partes)


def documento_constancias_adicionales(o: Oferta) -> bytes:
    """Constancias que el postor adjunta en otro archivo y con otra redacción («certificado», «importe»)."""
    partes = []
    for i, s in enumerate(o.servicios, start=1):
        if not s.aparte:
            continue
        parrafos = [f"La {s.cliente} certifica la culminación satisfactoria de la {s.objeto[0].lower() + s.objeto[1:]}, "
                    f"realizada por {o.razon_social} (RUC N.° {o.ruc}) en el marco del {s.contrato}, por un importe "
                    f"total de {soles(s.monto)}.",
                    f"Fecha de la conformidad: {s.conformidad}.",
                    "Se expide el presente certificado a solicitud del interesado."]
        if s.escaneada:
            partes.append(pagina_escaneada(s.cliente, "CERTIFICADO DE CONFORMIDAD", parrafos,
                                           "Gerente de Infraestructura", semilla=20 + i))
        else:
            partes.append(_pdf([p(s.cliente.upper(), "capitulo"), p("CERTIFICADO DE CONFORMIDAD", "titulo"),
                                *[p(t) for t in parrafos], firma("Gerente de Infraestructura", s.cliente)],
                               f"{o.razon_social} · Constancias adicionales", AVISO))
    return unir(partes)


def _certificado(pr: Profesional, e, semilla: int, pie: str) -> bytes:
    parrafos = [f"{e.emisor} certifica que {pr.nombre}, identificado(a) con DNI N.° {pr.dni}, {pr.profesion}, "
                f"con {pr.colegiatura}, se desempeñó como {e.cargo.upper()} en: {e.lugar}, desde el {e.inicio} "
                f"hasta el {e.fin}.",
                "Durante dicho periodo demostró responsabilidad y competencia profesional.",
                "Se expide el presente certificado a solicitud del interesado."]
    if e.escaneada:
        return pagina_escaneada(e.emisor, "CERTIFICADO DE TRABAJO", parrafos, "Gerente de Administración", semilla)
    return _pdf([p(e.emisor.upper(), "capitulo"), p("CERTIFICADO DE TRABAJO", "titulo"), *[p(t) for t in parrafos],
                 firma("Gerente de Administración", e.emisor)], pie, AVISO)


def documento_personal(c: Convocatoria, o: Oferta) -> bytes:
    pie = f"{o.razon_social} · Personal clave"
    anexo = [*_cabecera_anexo("ANEXO N.° 15<br/>PERSONAL CLAVE PROPUESTO", c),
             p("Declaro bajo juramento que el personal clave propuesto para la ejecución del servicio es el siguiente:"),
             tabla([["Cargo", "Nombres y apellidos", "DNI", "Profesión (título profesional)", "Universidad", "Colegiatura"],
                    *[[pr.cargo, pr.nombre, pr.dni, pr.profesion, pr.universidad, pr.colegiatura] for pr in o.personal]],
                   [3, 3.3, 1.9, 2.9, 3.2, 2.3]),
             p(f"{_ciudad(c)}, {FECHA_OFERTAS}"), firma(o.representante, "Representante legal", o.dni_representante)]
    partes = [_pdf(anexo, pie, AVISO)]
    semilla = 10
    for pr in o.personal:
        cv = [p(f"CURRÍCULUM VITAE DOCUMENTADO<br/>{pr.cargo.upper()}", "titulo"),
              tabla([["Nombres y apellidos", pr.nombre], ["DNI N.°", pr.dni], ["Profesión", pr.profesion],
                     ["Universidad", pr.universidad], ["Colegiatura", pr.colegiatura]], [5, 11.6], encabezado=False),
              p("EXPERIENCIA PROFESIONAL", "seccion"),
              tabla([["Cargo", "Proyecto u obra", "Entidad", "Inicio", "Fin"],
                     *[[e.cargo, e.lugar, e.emisor, e.inicio, e.fin] for e in pr.experiencias]],
                    [3, 5.2, 3.6, 2.4, 2.4]),
              p("Se adjuntan los certificados que acreditan cada experiencia."), firma(pr.nombre, pr.profesion, pr.dni)]
        partes.append(_pdf(cv, pie, AVISO))
        for e in pr.experiencias:
            semilla += 1
            partes.append(_certificado(pr, e, semilla, pie))
    return unir(partes)


def documento_metodologia(c: Convocatoria, o: Oferta) -> bytes:
    story = [p("METODOLOGÍA Y PLAN DE TRABAJO", "portada"), p(f"CONCURSO PÚBLICO N.° {c.nomenclatura}", "capitulo"),
             p(f"Postor: <b>{o.razon_social}</b>", "centrado"), Spacer(1, 8),
             p(f"{o.razon_social} presenta la metodología con la que prestará el servicio de "
               f"{c.objeto.split(' PARA ', 1)[-1]}.")]
    for titulo, parrafos in o.metodologia or c.metodologia:
        story += [p(titulo.upper(), "seccion"), *[p(t) for t in parrafos]]
    # Texto que intenta manipular al evaluador automático, en letra pequeña como suele esconderse.
    story += [p(linea, "celda") for linea in o.inyeccion]
    story += [p(f"{_ciudad(c)}, {FECHA_OFERTAS}"), firma(o.representante, "Representante legal", o.dni_representante)]
    return _pdf(story, f"{o.razon_social} · Metodología", AVISO)


def generar() -> None:
    if CARPETA.exists():
        shutil.rmtree(CARPETA)
    for c in CONVOCATORIAS:
        carpeta = CARPETA / c.carpeta
        carpeta.mkdir(parents=True)
        (carpeta / f"Bases Integradas {c.nomenclatura.replace('/', '-')}.pdf").write_bytes(generar_bases(c))
        for o in c.ofertas:
            destino = carpeta / o.carpeta
            destino.mkdir()
            (destino / "01 Anexos de admisión.pdf").write_bytes(documento_admision(c, o))
            (destino / "02 Experiencia del postor.pdf").write_bytes(documento_experiencia(c, o))
            (destino / "03 Personal clave.pdf").write_bytes(documento_personal(c, o))
            (destino / "04 Metodología y plan de trabajo.pdf").write_bytes(documento_metodologia(c, o))
            if any(s.aparte for s in o.servicios):
                (destino / "05 Constancias adicionales.pdf").write_bytes(documento_constancias_adicionales(o))
        print(f"{c.nomenclatura}: Bases y {len(c.ofertas)} ofertas en {carpeta}")


if __name__ == "__main__":
    generar()
