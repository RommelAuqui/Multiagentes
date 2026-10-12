"""Reglas de la evaluación según la estructura de las bases estándar.

El resultado final lo decide esta lógica, no la IA: los agentes solo proponen el veredicto o
el puntaje de cada criterio, y el comité puede corregirlos.
"""
import unicodedata

ETAPAS = {"admision": "Admisión", "calificacion": "Calificación", "evaluacion": "Evaluación"}
TIPOS = {"legal": "Legal", "tecnico": "Técnico"}

# Veredicto de cada criterio.
CUMPLE = "Cumple"
NO_CUMPLE = "No Cumple"
EVALUADO = "Evaluado"
REQUIERE_REVISION = "Requiere revisión"

# Resultado final del postor.
CALIFICA = "Califica"
NO_ADMITIDO = "No admitido"
NO_CALIFICA = "No califica"
PUNTAJE_INSUFICIENTE = "Puntaje insuficiente"
RESULTADOS_DESCALIFICANTES = (NO_ADMITIDO, NO_CALIFICA)


def normalizar_texto(valor) -> str:
    if isinstance(valor, float) and valor != valor:  # celda vacía (NaN) del editor de tablas
        return ""
    return str(valor or "").strip()


def normalizar_puntaje(valor, maximo: float | None) -> float | None:
    try:
        puntaje = float(valor)
    except (TypeError, ValueError):
        return None
    if puntaje != puntaje:  # NaN
        return None
    return round(min(max(puntaje, 0.0), maximo if maximo is not None else puntaje), 2)


def clave(valor) -> str:
    texto = unicodedata.normalize("NFD", str(valor or ""))
    return "".join(c for c in texto if unicodedata.category(c) != "Mn").strip().lower()


def veredicto_efectivo(fila: dict) -> str:
    return fila.get("veredicto_comite") or fila["veredicto"]


def puntaje_efectivo(fila: dict) -> float | None:
    if fila.get("puntaje_comite") is not None:
        return fila["puntaje_comite"]
    return fila.get("puntaje")


def calcular_resultado(filas: list[dict], puntaje_minimo: float | None) -> dict:
    def obligatorios_incumplidos(etapa: str) -> list[str]:
        return [
            f["criterio_descripcion"] for f in filas
            if f["etapa"] == etapa and f.get("obligatorio", True) and veredicto_efectivo(f) == NO_CUMPLE
        ]

    factores = [f for f in filas if f["etapa"] == "evaluacion"]
    puntaje = round(sum(puntaje_efectivo(f) or 0 for f in factores), 2) if factores else None
    puntaje_maximo = round(sum(f.get("puntaje_maximo") or 0 for f in factores), 2) if factores else None
    pendientes = [f["criterio_descripcion"] for f in filas if veredicto_efectivo(f) == REQUIERE_REVISION]

    if motivos := obligatorios_incumplidos("admision"):
        veredicto = NO_ADMITIDO
    elif motivos := obligatorios_incumplidos("calificacion"):
        veredicto = NO_CALIFICA
    elif motivos := pendientes:
        veredicto = REQUIERE_REVISION
    elif puntaje_minimo is not None and puntaje is not None and puntaje < puntaje_minimo:
        veredicto = PUNTAJE_INSUFICIENTE
        motivos = [f"obtuvo {puntaje} puntos y el mínimo de las Bases es {puntaje_minimo}"]
    else:
        veredicto, motivos = CALIFICA, []

    return {"veredicto": veredicto, "puntaje": puntaje, "puntaje_maximo": puntaje_maximo, "motivos": motivos}


def validar_matriz(filas: list[dict]) -> tuple[list[dict], list[str]]:
    """Convierte las filas que edita el comité (etapa y tipo con etiquetas en español) en criterios."""
    etapas = {**{clave(v): k for k, v in ETAPAS.items()}, **{k: k for k in ETAPAS}}
    tipos = {**{clave(v): k for k, v in TIPOS.items()}, **{k: k for k in TIPOS}}
    criterios, errores = [], []

    for numero, fila in enumerate(filas, start=1):
        descripcion = normalizar_texto(fila.get("descripcion"))
        textos = [normalizar_texto(fila.get(c)) for c in ("acreditacion", "referencia", "asignacion_puntaje")]
        if not descripcion and not any(textos):
            continue  # fila nueva que se dejó vacía
        etapa = etapas.get(clave(fila.get("etapa")))
        if not descripcion or etapa is None:
            errores.append(f"Fila {numero}: completa la etapa y la descripción.")
            continue

        tipo = tipos.get(clave(fila.get("tipo"))) or ("legal" if etapa == "admision" else "tecnico")
        es_factor = etapa == "evaluacion"
        puntaje_maximo = normalizar_puntaje(fila.get("puntaje_maximo"), None) if es_factor else None
        if es_factor and not puntaje_maximo:
            errores.append(f"Fila {numero}: el factor de evaluación «{descripcion[:60]}» necesita un puntaje máximo.")
            continue

        acreditacion, referencia, asignacion = (t or None for t in textos)
        criterios.append({
            "etapa": etapa,
            "tipo": tipo,
            "descripcion": descripcion,
            "acreditacion": acreditacion,
            "referencia": referencia,
            "obligatorio": False if es_factor else fila.get("obligatorio") is not False,
            "puntaje_maximo": puntaje_maximo,
            "asignacion_puntaje": asignacion if es_factor else None,
            "orden": len(criterios),
        })
    return criterios, errores


def aplicar_revision(filas: list[dict], decisiones: dict, revisor: str) -> tuple[list[dict], list[str]]:
    """Valida las decisiones del comité sobre cada criterio y devuelve los cambios a guardar."""
    errores = [] if normalizar_texto(revisor) else ["Indica el nombre del miembro del comité que revisa."]
    cambios = []

    for fila in filas:
        decision = decisiones[fila["id"]]
        justificacion = normalizar_texto(decision.get("justificacion"))
        nombre = fila["criterio_descripcion"][:80]

        if fila["etapa"] == "evaluacion":
            veredicto = EVALUADO
            puntaje = normalizar_puntaje(decision.get("puntaje"), fila.get("puntaje_maximo"))
            if puntaje is None:
                errores.append(f"Asigna el puntaje de «{nombre}».")
                continue
            difiere = puntaje != fila.get("puntaje")
        else:
            veredicto, puntaje = decision.get("veredicto"), None
            if veredicto not in (CUMPLE, NO_CUMPLE):
                errores.append(f"Decide si cumple o no cumple: «{nombre}».")
                continue
            difiere = veredicto != fila["veredicto"]

        # Cambiar la propuesta de la IA, o resolver un caso que ella dejó en duda, exige justificación.
        if (difiere or fila["veredicto"] == REQUIERE_REVISION) and not justificacion:
            errores.append(f"Justifica la decisión del comité en «{nombre}».")
            continue

        cambios.append({
            "id": fila["id"],
            "veredicto_comite": veredicto,
            "puntaje_comite": puntaje,
            "justificacion_comite": justificacion or None,
        })
    return cambios, errores
