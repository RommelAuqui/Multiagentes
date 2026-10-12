"""Herramientas que los agentes Legal y Técnico pueden usar mientras evalúan un criterio."""
import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta

from agents.agente import Herramienta
from agents.respuestas import clave_documento, nombre_documento
from rag.embeddings import embed_consultas
from rag.retriever import buscar_fragmentos, leer_pagina

RESULTADOS_POR_BUSQUEDA = 5
DIAS_POR_MES = 30


@dataclass
class ContextoEvaluacion:
    concurso_id: str
    postor: dict
    vistos: list[dict] = field(default_factory=list)  # fragmentos entregados al agente: lo único que puede citar

    @property
    def postor_id(self) -> str:
        return self.postor["id"]


def documentos_de_la_oferta(postor: dict) -> list[dict]:
    if postor.get("archivos"):
        return [{"nombre": a["nombre"], "paginas": a.get("paginas")} for a in postor["archivos"]]
    # Ofertas de la versión anterior: sus fragmentos se identifican por el origen.
    return [{"nombre": origen} for origen, campo in (("propuesta", "propuesta_pdf_path"), ("cv", "cv_pdf_path"))
            if postor.get(campo)]


# ---------- Cálculos deterministas: el modelo no debe sumar ni contar meses de memoria ----------

def _fecha(texto, es_fin: bool) -> date:
    partes = str(texto).strip()[:10].split("-")
    if len(partes) == 2:
        anio, mes = int(partes[0]), int(partes[1])
        return date(anio, mes, calendar.monthrange(anio, mes)[1] if es_fin else 1)
    if len(partes) == 3:
        return date(*(int(p) for p in partes))
    raise ValueError(f"Fecha no válida: «{texto}». Usa AAAA-MM-DD, o AAAA-MM si el documento no indica el día.")


def calcular_experiencia(periodos: list[dict]) -> dict:
    intervalos = sorted((_fecha(p["inicio"], es_fin=False), _fecha(p["fin"], es_fin=True)) for p in periodos)
    if not intervalos:
        raise ValueError("Indica al menos un periodo.")
    for inicio, fin in intervalos:
        if fin < inicio:
            raise ValueError(f"El periodo que empieza el {inicio} termina antes ({fin}).")

    # Los periodos traslapados o contiguos se unen: el tiempo en paralelo se cuenta una sola vez.
    unidos: list[list[date]] = []
    for inicio, fin in intervalos:
        if unidos and inicio <= unidos[-1][1] + timedelta(days=1):
            unidos[-1][1] = max(unidos[-1][1], fin)
        else:
            unidos.append([inicio, fin])

    # Meses calendario por periodo (como se computa a mano); los días sueltos se convierten a meses de 30 días.
    meses, dias_sueltos = 0, 0
    for inicio, fin in unidos:
        periodo_meses, periodo_dias = _meses_y_dias(inicio, fin + timedelta(days=1))
        meses, dias_sueltos = meses + periodo_meses, dias_sueltos + periodo_dias
    meses, dias_sueltos = meses + dias_sueltos // DIAS_POR_MES, dias_sueltos % DIAS_POR_MES

    dias = sum((fin - inicio).days + 1 for inicio, fin in unidos)
    dias_sin_unir = sum((fin - inicio).days + 1 for inicio, fin in intervalos)
    return {
        "meses": round(meses + dias_sueltos / DIAS_POR_MES, 2),
        "anios_meses_dias": f"{meses // 12} años, {meses % 12} meses y {dias_sueltos} días",
        "dias": dias,
        "dias_traslapados_descontados": dias_sin_unir - dias,
        "periodos_unidos": [{"inicio": i.isoformat(), "fin": f.isoformat()} for i, f in unidos],
    }


def _sumar_meses(fecha: date, meses: int) -> date:
    anio, mes = divmod(fecha.month - 1 + meses, 12)
    anio, mes = fecha.year + anio, mes + 1
    return date(anio, mes, min(fecha.day, calendar.monthrange(anio, mes)[1]))


def _meses_y_dias(inicio: date, fin_exclusivo: date) -> tuple[int, int]:
    meses = (fin_exclusivo.year - inicio.year) * 12 + fin_exclusivo.month - inicio.month
    if _sumar_meses(inicio, meses) > fin_exclusivo:
        meses -= 1
    return meses, (fin_exclusivo - _sumar_meses(inicio, meses)).days


def sumar_montos(montos: list[float], referencia: float | None = None) -> dict:
    total = round(sum(float(m) for m in montos), 2)
    resultado = {"total": total}
    if referencia:
        resultado["veces_referencia"] = round(total / float(referencia), 4)
    return resultado


# ---------- Herramientas sobre la oferta del postor ----------

def _resolver_documento(contexto: ContextoEvaluacion, nombre: str) -> str:
    documentos = [d["nombre"] for d in documentos_de_la_oferta(contexto.postor)]
    for documento in documentos:
        if clave_documento(documento) == clave_documento(nombre):
            return documento
    raise ValueError(f"No existe el documento «{nombre}». Documentos de la oferta: {', '.join(documentos)}.")


def _para_el_agente(fragmento: dict) -> dict:
    return {"documento": nombre_documento(fragmento), "pagina": fragmento["pagina"], "contenido": fragmento["contenido"]}


def herramientas_de_evaluacion(contexto: ContextoEvaluacion) -> list[Herramienta]:
    def buscar_evidencia(consulta: str, documento: str | None = None) -> dict:
        nombre = _resolver_documento(contexto, documento) if documento else None
        fragmentos = buscar_fragmentos(
            contexto.concurso_id, embed_consultas([consulta])[0], postor_id=contexto.postor_id,
            k=RESULTADOS_POR_BUSQUEDA, documento=nombre,
        )
        contexto.vistos.extend(fragmentos)
        return {"fragmentos": [_para_el_agente(f) for f in fragmentos]}

    def leer_pagina_completa(documento: str, pagina: int) -> dict:
        nombre = _resolver_documento(contexto, documento)
        fragmentos = leer_pagina(contexto.postor_id, nombre, int(pagina))
        if not fragmentos:
            raise ValueError(f"No hay texto en «{nombre}», página {pagina}.")
        contexto.vistos.extend(fragmentos)
        return {"documento": nombre, "pagina": int(pagina), "texto": "".join(f["contenido"] for f in fragmentos)}

    def listar_documentos() -> dict:
        return {"documentos": documentos_de_la_oferta(contexto.postor)}

    def datos_del_postor() -> dict:
        return {"ruc": contexto.postor["ruc"], "razon_social": contexto.postor["razon_social"]}

    def resumir_busqueda(args: dict, resultado: dict) -> str:
        donde = f" en {args['documento']}" if args.get("documento") else " en toda la oferta"
        hallazgos = ", ".join(f"{f['documento']} p. {f['pagina']}" for f in resultado["fragmentos"][:3])
        return f"Buscó «{args['consulta']}»{donde}: {len(resultado['fragmentos'])} resultado(s)" + (
            f" ({hallazgos})" if hallazgos else "")

    def resumir_experiencia(_args: dict, r: dict) -> str:
        traslape = f", descontando {r['dias_traslapados_descontados']} días traslapados" if r["dias_traslapados_descontados"] else ""
        return f"Calculó la experiencia: {r['meses']} meses ({r['dias']} días{traslape})"

    def resumir_montos(args: dict, r: dict) -> str:
        veces = f" = {r['veces_referencia']} veces la referencia" if "veces_referencia" in r else ""
        return f"Sumó {len(args['montos'])} monto(s): S/ {r['total']:,.2f}{veces}"

    documento = {"type": "string", "description": "Nombre del archivo, tal como aparece en la evidencia o en listar_documentos."}
    return [
        Herramienta(
            "buscar_evidencia",
            "Busca en la oferta del postor los fragmentos más relacionados con la consulta. Úsala cuando la "
            "evidencia inicial no baste: reformula con otras palabras (cargos, nombres, números de anexo) o "
            "limita la búsqueda a un archivo.",
            {"type": "object", "properties": {"consulta": {"type": "string"}, "documento": documento},
             "required": ["consulta"]},
            buscar_evidencia, resumir_busqueda,
        ),
        Herramienta(
            "leer_pagina",
            "Devuelve el texto completo de una página de un archivo de la oferta (por ejemplo, una tabla que "
            "quedó cortada en un fragmento).",
            {"type": "object", "properties": {"documento": documento, "pagina": {"type": "integer"}},
             "required": ["documento", "pagina"]},
            leer_pagina_completa, lambda _a, r: f"Leyó {r['documento']}, página {r['pagina']}",
        ),
        Herramienta(
            "listar_documentos", "Lista los archivos de la oferta del postor y su número de páginas.",
            {"type": "object", "properties": {}},
            listar_documentos, lambda _a, r: f"Revisó la lista de archivos de la oferta ({len(r['documentos'])})",
        ),
        Herramienta(
            "datos_del_postor", "Devuelve el RUC y la razón social con que el postor se registró en la convocatoria.",
            {"type": "object", "properties": {}},
            datos_del_postor, lambda _a, _r: "Consultó el RUC y la razón social registrados",
        ),
        Herramienta(
            "calcular_experiencia",
            "Suma periodos de experiencia contando una sola vez el tiempo traslapado y devuelve el total en "
            "meses calendario (los días sueltos se convierten a meses de 30 días). Fechas en formato "
            "AAAA-MM-DD, o AAAA-MM si el documento no indica el día (se toma el mes completo).",
            {"type": "object", "properties": {"periodos": {"type": "array", "items": {
                "type": "object", "properties": {"inicio": {"type": "string"}, "fin": {"type": "string"}},
                "required": ["inicio", "fin"]}}}, "required": ["periodos"]},
            calcular_experiencia, resumir_experiencia,
        ),
        Herramienta(
            "sumar_montos",
            "Suma montos en soles y, si se indica un monto de referencia (cuantía o valor referencial), "
            "calcula cuántas veces lo equivale el total.",
            {"type": "object", "properties": {"montos": {"type": "array", "items": {"type": "number"}},
                                              "referencia": {"type": "number"}}, "required": ["montos"]},
            sumar_montos, resumir_montos,
        ),
    ]
