VEREDICTO_CUMPLE = "Cumple"
VEREDICTO_NO_CUMPLE = "No Cumple"


def normalizar_texto(valor) -> str:
    return str(valor or "").strip()


def normalizar_veredicto(valor) -> str:
    if normalizar_texto(valor).lower() == "cumple":
        return VEREDICTO_CUMPLE
    return VEREDICTO_NO_CUMPLE


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
