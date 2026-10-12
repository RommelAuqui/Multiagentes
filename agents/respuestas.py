from agents.reglas import CUMPLE, EVALUADO, NO_APLICA, NO_CUMPLE, REQUIERE_REVISION, clave, normalizar_texto


def normalizar_veredicto(valor, etapa: str) -> str:
    # Una respuesta ambigua no puede descalificar ni aprobar: queda para el comité.
    if etapa == "evaluacion":
        return EVALUADO if clave(valor) == "evaluado" else REQUIERE_REVISION
    return {"cumple": CUMPLE, "no cumple": NO_CUMPLE, "no aplica": NO_APLICA}.get(clave(valor), REQUIERE_REVISION)


def normalizar_citas(citas, fragmentos: list[dict]) -> list[dict]:
    # Solo se aceptan citas que apuntan a un fragmento que realmente se entregó al agente.
    if not isinstance(citas, list):
        return []

    validas = {(f.get("origen"), f["pagina"]) for f in fragmentos}
    origenes_por_pagina: dict[int, set] = {}
    for origen, pagina in validas:
        origenes_por_pagina.setdefault(pagina, set()).add(origen)

    normalizadas = []
    for cita in citas:
        if not isinstance(cita, dict):
            continue
        try:
            pagina = int(cita.get("pagina"))
        except (TypeError, ValueError):
            continue

        documento = normalizar_texto(cita.get("documento")).lower()
        if (documento, pagina) not in validas:
            origenes = origenes_por_pagina.get(pagina, set())
            if len(origenes) != 1:
                continue
            documento = next(iter(origenes))

        normalizadas.append({
            "documento": documento,
            "pagina": pagina,
            "extracto": normalizar_texto(cita.get("extracto")),
        })
    return normalizadas
