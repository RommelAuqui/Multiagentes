"""Métricas de la validación: compara lo que decidió el sistema con la respuesta correcta de cada caso.

Cada resultado es un dict: {"modo", "repeticion", "caso" (código), "criterios": {clave: {"veredicto",
"puntaje"}}, "resultado", "puntaje", "segundos", "consultas", "tokens"}.
"""
from collections import Counter, defaultdict

from validacion.casos import CRITERIOS

FAVORABLES = {"Cumple", "No aplica"}
DESFAVORABLES = {"No Cumple"}
DERIVADO = "Requiere revisión"


def es_requisito(clave: str) -> bool:
    return CRITERIOS[clave]["etapa"] != "evaluacion"


def _aceptables(caso, clave: str) -> list:
    return [caso.esperado[clave], *caso.aceptables.get(clave, [])]


def acierta_requisito(caso, clave: str, veredicto: str | None) -> bool:
    return veredicto in _aceptables(caso, clave)


def acierta_resultado(caso, resultado: str | None) -> bool:
    return resultado in [caso.resultado, *caso.aceptables.get("resultado", [])]


def kappa_de_cohen(esperados: list[str], obtenidos: list[str]) -> float | None:
    """Acuerdo entre dos clasificaciones descontando el que se daría por azar (1 = perfecto, 0 = azar)."""
    total = len(esperados)
    if not total:
        return None
    observado = sum(e == o for e, o in zip(esperados, obtenidos)) / total
    frecuencia_esperada, frecuencia_obtenida = Counter(esperados), Counter(obtenidos)
    azar = sum(frecuencia_esperada[c] * frecuencia_obtenida[c] for c in frecuencia_esperada) / total ** 2
    return 1.0 if azar == 1 else round((observado - azar) / (1 - azar), 4)


def _proporcion(parte: int, total: int) -> float | None:
    return round(parte / total, 4) if total else None


def metricas_de_modo(resultados: list[dict], casos: dict) -> dict:
    esperados, obtenidos, confusion = [], [], defaultdict(Counter)
    aciertos_req = aprobaciones = rechazos = derivaciones = 0
    aciertos_fac = sobrepuntajes = subpuntajes = 0
    errores_puntaje: list[float] = []
    aciertos_final = califica_indebido = 0

    for resultado in resultados:
        caso = casos[resultado["caso"]]
        for clave, obtenido in resultado["criterios"].items():
            if es_requisito(clave):
                esperado, veredicto = caso.esperado[clave], obtenido.get("veredicto")
                esperados.append(esperado)
                obtenidos.append(veredicto or "Sin respuesta")
                confusion[esperado][veredicto or "Sin respuesta"] += 1
                aceptables = _aceptables(caso, clave)
                if veredicto in aceptables:
                    aciertos_req += 1
                elif veredicto in FAVORABLES and not FAVORABLES & set(aceptables):
                    aprobaciones += 1  # el error más grave: deja pasar lo que no cumple
                elif veredicto in DESFAVORABLES and FAVORABLES & set(aceptables):
                    rechazos += 1
                elif veredicto == DERIVADO:
                    derivaciones += 1
            else:
                esperado, puntaje = float(caso.esperado[clave]), obtenido.get("puntaje")
                puntaje = float(puntaje) if puntaje is not None else 0.0
                errores_puntaje.append(abs(puntaje - esperado))
                aciertos_fac += abs(puntaje - esperado) < 0.01
                sobrepuntajes += puntaje > esperado + 0.01
                subpuntajes += puntaje < esperado - 0.01

        aciertos_final += acierta_resultado(caso, resultado["resultado"])
        califica_indebido += resultado["resultado"] == "Califica" and not acierta_resultado(caso, "Califica")

    n_req, n_fac, n_final = len(esperados), len(errores_puntaje), len(resultados)
    return {
        "postores_evaluados": n_final,
        "requisitos": {
            "total": n_req,
            "exactitud": _proporcion(aciertos_req, n_req),
            "kappa": kappa_de_cohen(esperados, obtenidos),
            "aprobaciones_indebidas": aprobaciones,
            "rechazos_indebidos": rechazos,
            "derivaciones_innecesarias": derivaciones,
            "confusion": {e: dict(o) for e, o in confusion.items()},
        },
        "factores": {
            "total": n_fac,
            "exactitud": _proporcion(aciertos_fac, n_fac),
            "error_absoluto_medio": round(sum(errores_puntaje) / n_fac, 2) if n_fac else None,
            "sobrepuntajes": sobrepuntajes,
            "subpuntajes": subpuntajes,
        },
        "resultado_final": {
            "total": n_final,
            "exactitud": _proporcion(aciertos_final, n_final),
            "califica_indebido": califica_indebido,
        },
        "eficiencia": {
            clave: round(sum(r[clave] for r in resultados) / n_final, 1) if n_final else None
            for clave in ("segundos", "consultas", "tokens")
        },
    }


def reproducibilidad(resultados: list[dict]) -> float | None:
    """Proporción de decisiones (caso, criterio) idénticas en todas las repeticiones de un modo."""
    por_decision: dict[tuple, set] = defaultdict(set)
    for resultado in resultados:
        for clave, obtenido in resultado["criterios"].items():
            por_decision[(resultado["caso"], clave)].add((obtenido.get("veredicto"), obtenido.get("puntaje")))
    repeticiones = {r["repeticion"] for r in resultados}
    if len(repeticiones) < 2 or not por_decision:
        return None
    return round(sum(len(v) == 1 for v in por_decision.values()) / len(por_decision), 4)


def calcular_metricas(resultados: list[dict], casos: dict) -> dict:
    por_modo: dict[str, list] = defaultdict(list)
    for resultado in resultados:
        por_modo[resultado["modo"]].append(resultado)
    return {
        modo: {**metricas_de_modo(lista, casos), "reproducibilidad": reproducibilidad(lista)}
        for modo, lista in por_modo.items()
    }
