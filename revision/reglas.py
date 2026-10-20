"""Verificaciones del catálogo que se resuelven con reglas fijas, sin IA.

Trabajan sobre los documentos ya leídos (texto por página) y sus fichas (datos clave extraídos). Cada
verificación devuelve si se cumple, si falla (con la evidencia) o si no se pudo verificar porque falta
un documento o un dato.
"""
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta

from revision.catalogo import BASES_DE_RONDA, POR_CODIGO, REGLA, TIPOS_DOCUMENTO, de_ronda

CUMPLE, FALLA, NO_VERIFICADO = "cumple", "falla", "no_verificado"
TOLERANCIA_MONTO = 0.01

# Criterios que debe confirmar el asesor (catálogo, verificaciones con ⚖️).
PARAMETROS = {
    "pro01_veces_cuantia": 2.0,
    "pro03_puntaje_maximo_factor": 60.0,
    "dias_habiles_consultas": 7,
    "dias_habiles_ofertas": 7,
}

# Indicaciones de la plantilla: corchetes vacíos, [ABC], [...] o con un verbo de instrucción. Un valor ya
# completado que quedó entre corchetes ([GOBIERNO REGIONAL DE LIMA]) no cuenta.
PLANTILLA = re.compile(
    r"\[\s*(?:ABC|\.{2,}|…|X{2,}|(?:INDICAR|CONSIGNAR|SE[ÑN]ALAR|DETALLAR|ESPECIFICAR|COMPLETAR|INCLUIR|"
    r"NOMBRE|CONSIDERAR|PRECISAR|ELIMINAR|DE SER EL CASO)[^\]]{0,150})?\s*\](?!\s*puntos\s*/\s*no\s+corresponde)",
    re.IGNORECASE)
NOTA_ENTIDAD = re.compile(r"importante\s+para\s+la\s+entidad\s+contratante", re.IGNORECASE)
# La página de simbología explica los símbolos de la plantilla: no cuenta como plantilla sin completar.
SIMBOLOGIA = re.compile(r"simbolog[ií]a\s+utilizada", re.IGNORECASE)
# Desde la proforma del contrato, los campos [..] los completan los postores o se llenan al firmar el contrato.
INICIO_PROFORMA = re.compile(r"cap[ií]tulo\s+v\s*[\-–:.]?\s*proforma", re.IGNORECASE)
_SEPARADOR = r"\s*[\-–:.]?\s*"
CAPITULOS = {
    "Cap. I, generalidades": rf"cap[ií]tulo\s+i{_SEPARADOR}generalidades",
    "Cap. II, del procedimiento de selección": rf"cap[ií]tulo\s+ii{_SEPARADOR}del\s+procedimiento\s+de\s+selecci[oó]n",
    "Cap. III, requerimiento": rf"cap[ií]tulo\s+iii{_SEPARADOR}requerimiento",
    "Cap. IV, evaluación de ofertas": rf"cap[ií]tulo\s+iv{_SEPARADOR}(?:evaluaci[oó]n|factores)",
    "Cap. V, proforma del contrato": rf"cap[ií]tulo\s+v{_SEPARADOR}proforma",
}


@dataclass
class Documento:
    tipo: str
    nombre: str
    paginas: list[dict] = field(default_factory=list)  # [{"pagina": n, "texto": "..."}]
    datos: dict = field(default_factory=dict)


@dataclass
class Resultado:
    codigo: str
    estado: str
    descripcion: str
    citas: list[dict] = field(default_factory=list)  # [{"documento": nombre, "pagina": n}]
    clave: str = ""
    pasos: list[dict] = field(default_factory=list)  # lo que hizo el agente revisor, si intervino


def _clave(texto: str) -> str:
    texto = unicodedata.normalize("NFD", str(texto or ""))
    return " ".join("".join(c for c in texto if unicodedata.category(c) != "Mn").lower().split())


def soles(monto: float) -> str:
    return f"S/ {monto:,.2f}".replace(",", " ")


def dias_habiles(desde: date, hasta: date) -> int:
    """Días de lunes a viernes contados desde el día siguiente a `desde` hasta `hasta` (sin feriados)."""
    dias, actual = 0, desde
    while actual < hasta:
        actual += timedelta(days=1)
        dias += actual.weekday() < 5
    return dias


def _faltan(codigo: str, tipos: list[str]) -> Resultado:
    nombres = ", ".join(TIPOS_DOCUMENTO[t] for t in tipos)
    return Resultado(codigo, NO_VERIFICADO, f"No se pudo verificar: falta {nombres}.")


def _sin_dato(codigo: str, dato: str, documento: Documento) -> Resultado:
    return Resultado(codigo, NO_VERIFICADO, f"No se pudo verificar: no se encontró {dato} en «{documento.nombre}».")


def _cita(documento: Documento, pagina: int | None = None) -> dict:
    return {"documento": documento.nombre, "pagina": pagina}


def _paginas_con(documento: Documento, patron: re.Pattern, hasta_proforma: bool = False) -> list[int]:
    paginas = []
    for pagina in documento.paginas:
        texto = pagina.get("texto") or ""
        if hasta_proforma and INICIO_PROFORMA.search(texto):
            break
        if not SIMBOLOGIA.search(texto) and patron.search(texto):
            paginas.append(pagina["pagina"])
    return paginas


# ---------- Completitud del expediente ----------

def _completitud(codigo: str, tipo: str, docs: dict[str, Documento]) -> Resultado:
    if tipo in docs:
        return Resultado(codigo, CUMPLE, f"Se adjuntó «{docs[tipo].nombre}».", [_cita(docs[tipo])])
    return Resultado(codigo, FALLA, f"No se adjuntó: {TIPOS_DOCUMENTO[tipo]}.")


def exp07(docs, bases: Documento) -> Resultado:
    cui = (bases.datos or {}).get("cui")
    if not cui:
        return Resultado("EXP-07", CUMPLE, "Las Bases no citan un proyecto de inversión.")
    if "viabilidad" in docs:
        return Resultado("EXP-07", CUMPLE, f"Las Bases citan el CUI {cui} y se adjuntó su viabilidad.",
                         [_cita(docs["viabilidad"])])
    return Resultado("EXP-07", FALLA, f"Las Bases citan el proyecto de inversión con CUI {cui}, pero no se adjuntó "
                                      "el documento de su viabilidad.", [_cita(bases)])


# ---------- Coherencia entre el expediente y las Bases ----------

def coh01(docs, bases: Documento) -> Resultado:
    cuantia = bases.datos.get("cuantia")
    if cuantia is None:
        return _sin_dato("COH-01", "la cuantía", bases)
    fuentes = [(d, d.datos.get("cuantia")) for t in ("aprobacion_expediente", "estrategia") if (d := docs.get(t))]
    fuentes = [(d, monto) for d, monto in fuentes if monto is not None]
    if not fuentes:
        return _faltan("COH-01", ["aprobacion_expediente", "estrategia"])
    distintas = [(d, monto) for d, monto in fuentes if abs(monto - cuantia) > TOLERANCIA_MONTO]
    if distintas:
        detalle = "; ".join(f"«{d.nombre}» indica {soles(monto)}" for d, monto in distintas)
        return Resultado("COH-01", FALLA, f"Las Bases fijan una cuantía de {soles(cuantia)}, pero {detalle}.",
                         [_cita(bases), *[_cita(d) for d, _ in distintas]])
    return Resultado("COH-01", CUMPLE, f"La cuantía de {soles(cuantia)} coincide en las Bases y el expediente.")


def coh02(docs, bases: Documento) -> Resultado:
    if "certificacion" not in docs:
        return _faltan("COH-02", ["certificacion"])
    certificacion = docs["certificacion"]
    cuantia, monto = bases.datos.get("cuantia"), certificacion.datos.get("monto")
    if cuantia is None:
        return _sin_dato("COH-02", "la cuantía", bases)
    if monto is None:
        return _sin_dato("COH-02", "el monto certificado", certificacion)
    if monto + TOLERANCIA_MONTO < cuantia:
        return Resultado("COH-02", FALLA, f"La certificación cubre {soles(monto)}, menos que la cuantía de "
                                          f"{soles(cuantia)} (faltan {soles(cuantia - monto)}).",
                         [_cita(bases), _cita(certificacion)])
    return Resultado("COH-02", CUMPLE, f"La certificación ({soles(monto)}) cubre la cuantía ({soles(cuantia)}).")


def coh03(docs, bases: Documento) -> Resultado:
    if "certificacion" not in docs:
        return _faltan("COH-03", ["certificacion"])
    en_bases, en_certificacion = bases.datos.get("fuente_financiamiento"), docs["certificacion"].datos.get(
        "fuente_financiamiento")
    if not en_bases or not en_certificacion:
        return Resultado("COH-03", NO_VERIFICADO, "No se pudo verificar: falta la fuente de financiamiento en las "
                                                  "Bases o en la certificación.")
    if _clave(en_bases) not in _clave(en_certificacion) and _clave(en_certificacion) not in _clave(en_bases):
        return Resultado("COH-03", FALLA, f"Las Bases indican «{en_bases}» como fuente de financiamiento y la "
                                          f"certificación, «{en_certificacion}».",
                         [_cita(bases), _cita(docs["certificacion"])])
    return Resultado("COH-03", CUMPLE, f"La fuente de financiamiento coincide: {en_bases}.")


def coh04(docs, bases: Documento) -> Resultado:
    if "aprobacion_expediente" not in docs:
        return _faltan("COH-04", ["aprobacion_expediente"])
    aprobacion = docs["aprobacion_expediente"]
    en_bases, real = bases.datos.get("fecha_aprobacion_expediente"), aprobacion.datos.get("fecha_aprobacion")
    if not en_bases or not real:
        return Resultado("COH-04", NO_VERIFICADO, "No se pudo verificar: falta la fecha de aprobación en las Bases "
                                                  "o en el documento de aprobación.")
    if en_bases != real:
        return Resultado("COH-04", FALLA, f"Las Bases dicen que el expediente se aprobó el {en_bases}, pero el "
                                          f"documento de aprobación tiene fecha {real}.", [_cita(bases), _cita(aprobacion)])
    convocatoria = (bases.datos.get("cronograma") or {}).get("convocatoria")
    if convocatoria and real > convocatoria:
        return Resultado("COH-04", FALLA, f"El expediente se aprobó el {real}, después de la convocatoria ({convocatoria}).",
                         [_cita(bases), _cita(aprobacion)])
    return Resultado("COH-04", CUMPLE, f"El expediente se aprobó el {real}, como dicen las Bases.")


def coh08(docs, bases: Documento) -> Resultado:
    if "requerimiento" not in docs:
        return _faltan("COH-08", ["requerimiento"])
    en_bases, en_requerimiento = bases.datos.get("plazo_dias"), docs["requerimiento"].datos.get("plazo_dias")
    if en_bases is None or en_requerimiento is None:
        return Resultado("COH-08", NO_VERIFICADO, "No se pudo verificar: falta el plazo en las Bases o en el "
                                                  "requerimiento.")
    if abs(en_bases - en_requerimiento) > TOLERANCIA_MONTO:
        return Resultado("COH-08", FALLA, f"Las Bases fijan un plazo de {en_bases:g} días y el requerimiento, de "
                                          f"{en_requerimiento:g} días.", [_cita(bases), _cita(docs["requerimiento"])])
    return Resultado("COH-08", CUMPLE, f"El plazo de {en_bases:g} días coincide con el requerimiento.")


def coh10(docs, bases: Documento) -> Resultado:
    difusion, elevacion = bases.datos.get("difusion_requerimiento"), bases.datos.get("elevacion_oece")
    if difusion is None:
        return _sin_dato("COH-10", "lo que dicen sobre la difusión del requerimiento", bases)
    if difusion is False and elevacion is False:
        return Resultado("COH-10", FALLA, "Las Bases dicen que no se hizo la difusión del requerimiento y, aun así, "
                                          "que no aplica la elevación al OECE: solo se puede omitir la elevación si "
                                          "hubo difusión.", [_cita(bases)])
    if "interaccion_mercado" in docs:
        en_expediente = docs["interaccion_mercado"].datos.get("difusion_requerimiento")
        if en_expediente is not None and en_expediente != difusion:
            return Resultado("COH-10", FALLA, f"Las Bases dicen que {'sí' if difusion else 'no'} se hizo la difusión del "
                                              f"requerimiento, pero el formato de interacción con el mercado dice que "
                                              f"{'sí' if en_expediente else 'no'}.",
                             [_cita(bases), _cita(docs["interaccion_mercado"])])
    return Resultado("COH-10", CUMPLE, "Lo declarado sobre la difusión del requerimiento y la elevación es coherente.")


# ---------- Cumplimiento formal ----------

def for02(bases: Documento) -> Resultado:
    paginas = _paginas_con(bases, PLANTILLA, hasta_proforma=True)
    if paginas:
        return Resultado("FOR-02", FALLA, f"Quedan indicaciones de la plantilla sin completar en {len(paginas)} "
                                          f"página(s): {', '.join(map(str, paginas[:10]))}.",
                         [_cita(bases, p) for p in paginas[:10]])
    return Resultado("FOR-02", CUMPLE, "No quedan indicaciones de la plantilla sin completar.")


def for03(bases: Documento) -> Resultado:
    paginas = _paginas_con(bases, NOTA_ENTIDAD)
    if paginas:
        return Resultado("FOR-03", FALLA, f"Quedan notas «Importante para la entidad contratante» en las páginas "
                                          f"{', '.join(map(str, paginas[:10]))}; debían eliminarse al terminar las Bases.",
                         [_cita(bases, p) for p in paginas[:10]])
    return Resultado("FOR-03", CUMPLE, "No quedan notas dirigidas a la entidad contratante.")


def for04(bases: Documento) -> Resultado:
    texto = "\n".join(p.get("texto") or "" for p in bases.paginas)
    faltan = [nombre for nombre, patron in CAPITULOS.items()
              if not re.search(patron, texto, re.IGNORECASE | re.MULTILINE)]
    if faltan:
        return Resultado("FOR-04", FALLA, f"No se encontraron estos capítulos de la Sección específica: "
                                          f"{', '.join(faltan)}.", [_cita(bases)])
    return Resultado("FOR-04", CUMPLE, "Están todos los capítulos de la Sección específica.")


def for05(bases: Documento) -> Resultado:
    factores = bases.datos.get("factores") or []
    if not factores:
        return _sin_dato("FOR-05", "los factores de evaluación", bases)
    suma = sum(f.get("puntaje") or 0 for f in factores)
    total = bases.datos.get("puntaje_total") or 100
    if abs(suma - total) > TOLERANCIA_MONTO:
        detalle = ", ".join(f"{f.get('nombre')}: {f.get('puntaje') or 0:g}" for f in factores)
        return Resultado("FOR-05", FALLA, f"Los factores suman {suma:g} puntos, no {total:g} ({detalle}).", [_cita(bases)])
    return Resultado("FOR-05", CUMPLE, f"Los {len(factores)} factores suman {suma:g} puntos.")


def for06(bases: Documento) -> Resultado:
    minimo = bases.datos.get("puntaje_minimo")
    if minimo is None:
        return Resultado("FOR-06", FALLA, "No se encontró el puntaje técnico mínimo en las Bases.", [_cita(bases)])
    return Resultado("FOR-06", CUMPLE, f"El puntaje técnico mínimo es {minimo:g}.")


def _plazo(codigo: str, bases: Documento, desde: str, hasta: str, minimo: int, que: str) -> Resultado:
    cronograma = bases.datos.get("cronograma") or {}
    inicio, fin = cronograma.get(desde), cronograma.get(hasta)
    if not inicio or not fin:
        return _sin_dato(codigo, f"las fechas del cronograma para {que}", bases)
    habiles = dias_habiles(date.fromisoformat(inicio), date.fromisoformat(fin))
    if habiles < minimo:
        return Resultado(codigo, FALLA, f"Entre {inicio} y {fin} hay {habiles} días hábiles para {que}; se exigen al "
                                        f"menos {minimo} (sin contar feriados).", [_cita(bases)])
    return Resultado(codigo, CUMPLE, f"Hay {habiles} días hábiles para {que} (mínimo {minimo}).")


def for07(bases: Documento) -> Resultado:
    return _plazo("FOR-07", bases, "convocatoria", "consultas_fin", PARAMETROS["dias_habiles_consultas"],
                  "consultas y observaciones")


def for08(bases: Documento) -> Resultado:
    return _plazo("FOR-08", bases, "integracion", "presentacion_ofertas", PARAMETROS["dias_habiles_ofertas"],
                  "preparar las ofertas")


# ---------- Integración de las absoluciones ----------

def abs01(docs) -> list[Resultado]:
    if "pliego" not in docs:
        return [_faltan("ABS-01", ["pliego"])]
    pliego = docs["pliego"]
    consultas = pliego.datos.get("consultas") or []
    sin_respuesta = [c for c in consultas if c.get("tiene_respuesta") is False]
    if not consultas:
        return [_sin_dato("ABS-01", "consultas ni observaciones", pliego)]
    if not sin_respuesta:
        return [Resultado("ABS-01", CUMPLE, f"Las {len(consultas)} consultas y observaciones tienen respuesta.")]
    return [Resultado("ABS-01", FALLA, f"La {c.get('tipo') or 'consulta'} N.° {c.get('numero')} "
                                       f"({c.get('tema') or 'sin tema'}) no tiene respuesta en el pliego.",
                      [_cita(pliego)], clave=str(c.get("numero"))) for c in sin_respuesta]


# ---------- Proporcionalidad ----------

def pro01(bases: Documento) -> Resultado:
    cuantia, exigido = bases.datos.get("cuantia"), bases.datos.get("monto_experiencia_postor")
    if not cuantia or exigido is None:
        return _sin_dato("PRO-01", "la cuantía o el monto de experiencia exigido", bases)
    veces, tope = exigido / cuantia, PARAMETROS["pro01_veces_cuantia"]
    if veces > tope:
        return Resultado("PRO-01", FALLA, f"Se exige una experiencia de {soles(exigido)}, {veces:.2f} veces la cuantía; "
                                          f"supera el tope de {tope:g} veces y puede limitar la competencia.", [_cita(bases)])
    return Resultado("PRO-01", CUMPLE, f"La experiencia exigida equivale a {veces:.2f} veces la cuantía.")


def pro03(bases: Documento) -> Resultado:
    factores = bases.datos.get("factores") or []
    if not factores:
        return _sin_dato("PRO-03", "los factores de evaluación", bases)
    tope = PARAMETROS["pro03_puntaje_maximo_factor"]
    excesivos = [f for f in factores if (f.get("puntaje") or 0) > tope]
    if excesivos:
        detalle = ", ".join(f"«{f.get('nombre')}» ({f.get('puntaje'):g} puntos)" for f in excesivos)
        return Resultado("PRO-03", FALLA, f"{detalle} concentra más de {tope:g} de los 100 puntos.", [_cita(bases)])
    return Resultado("PRO-03", CUMPLE, f"Ningún factor supera los {tope:g} puntos.")


# ---------- Ejecución ----------

def verificar(ronda: str, docs: dict[str, Documento]) -> list[Resultado]:
    """Aplica las reglas fijas de la ronda. `docs` tiene el documento vigente de cada tipo subido."""
    codigos = {v.codigo for v in de_ronda(ronda) if v.metodo == REGLA}
    bases = docs.get(BASES_DE_RONDA[ronda])
    resultados: list[Resultado] = []
    completitud = {"EXP-01": "requerimiento", "EXP-02": "certificacion", "EXP-03": "aprobacion_expediente",
                   "EXP-04": "estrategia", "EXP-05": "interaccion_mercado", "EXP-06": "designacion_evaluadores"}
    resultados += [_completitud(codigo, tipo, docs) for codigo, tipo in completitud.items() if codigo in codigos]
    if "ABS-01" in codigos:
        resultados += abs01(docs)
    con_bases = {
        "EXP-07": lambda: exp07(docs, bases), "COH-01": lambda: coh01(docs, bases),
        "COH-02": lambda: coh02(docs, bases), "COH-03": lambda: coh03(docs, bases),
        "COH-04": lambda: coh04(docs, bases), "COH-08": lambda: coh08(docs, bases),
        "COH-10": lambda: coh10(docs, bases), "FOR-02": lambda: for02(bases), "FOR-03": lambda: for03(bases),
        "FOR-04": lambda: for04(bases), "FOR-05": lambda: for05(bases), "FOR-06": lambda: for06(bases),
        "FOR-07": lambda: for07(bases), "FOR-08": lambda: for08(bases), "PRO-01": lambda: pro01(bases),
        "PRO-03": lambda: pro03(bases),
    }
    for codigo, verificacion in con_bases.items():
        if codigo not in codigos:
            continue
        resultados.append(verificacion() if bases else _faltan(codigo, [BASES_DE_RONDA[ronda]]))
    # Todas las reglas del catálogo de esta ronda deben tener una implementación.
    implementadas = set(completitud) | set(con_bases) | {"ABS-01"}
    assert codigos <= implementadas, f"Reglas sin implementar: {sorted(codigos - implementadas)}"
    return sorted(resultados, key=lambda r: list(POR_CODIGO).index(r.codigo))
