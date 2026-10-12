from agents.reglas import CUMPLE, EVALUADO, NO_APLICA, NO_CUMPLE, REQUIERE_REVISION, clave, normalizar_texto


def normalizar_veredicto(valor, etapa: str) -> str:
    # Una respuesta ambigua no puede descalificar ni aprobar: queda para el comité.
    if etapa == "evaluacion":
        return EVALUADO if clave(valor) == "evaluado" else REQUIERE_REVISION
    return {"cumple": CUMPLE, "no cumple": NO_CUMPLE, "no aplica": NO_APLICA}.get(clave(valor), REQUIERE_REVISION)


def nombre_documento(fragmento: dict) -> str | None:
    # Los fragmentos de ofertas en varios archivos llevan el nombre del archivo; los antiguos, su origen.
    return fragmento.get("documento") or fragmento.get("origen")


def _clave_documento(nombre) -> str:
    return clave(nombre).removesuffix(".pdf")


def normalizar_citas(citas, fragmentos: list[dict]) -> list[dict]:
    # Solo se aceptan citas que apuntan a un fragmento que realmente se entregó al agente.
    if not isinstance(citas, list):
        return []

    validas = {(_clave_documento(nombre_documento(f)), f["pagina"]): nombre_documento(f) for f in fragmentos}
    documentos_por_pagina: dict[int, set] = {}
    for f in fragmentos:
        documentos_por_pagina.setdefault(f["pagina"], set()).add(nombre_documento(f))

    normalizadas = []
    for cita in citas:
        if not isinstance(cita, dict):
            continue
        try:
            pagina = int(cita.get("pagina"))
        except (TypeError, ValueError):
            continue

        documento = validas.get((_clave_documento(cita.get("documento")), pagina))
        if documento is None:
            documentos = documentos_por_pagina.get(pagina, set())
            if len(documentos) != 1:
                continue
            documento = next(iter(documentos))

        normalizadas.append({
            "documento": documento,
            "pagina": pagina,
            "extracto": normalizar_texto(cita.get("extracto")),
        })
    return normalizadas
