"""Reporte de la validación: REPORTE.md (tablas para la tesis), decisiones.csv y metricas.json."""
import csv
import json
from pathlib import Path

from validacion.casos import CRITERIOS
from validacion.metricas import acierta_requisito, acierta_resultado, es_requisito

ETIQUETAS_CRITERIOS = {
    "A1": "Anexo 1", "A2": "Anexo 2", "A3": "Anexo 3", "A4": "Promesa de consorcio",
    "C1": "Facturación del postor", "C2": "Título del jefe", "C3": "Experiencia del jefe",
    "F1": "Puntaje experiencia", "F2": "Puntaje metodología",
}


def _porcentaje(valor) -> str:
    return "—" if valor is None else f"{valor * 100:.1f} %".replace(".", ",")


def _numero(valor) -> str:
    return "—" if valor is None else f"{valor:,.1f}".replace(",", " ").replace(".", ",")


def _acierta(caso, clave: str, obtenido: dict) -> bool:
    if es_requisito(clave):
        return acierta_requisito(caso, clave, obtenido.get("veredicto"))
    return obtenido.get("puntaje") is not None and abs(float(obtenido["puntaje"]) - float(caso.esperado[clave])) < 0.01


def _valor(clave: str, obtenido: dict) -> str:
    if es_requisito(clave):
        return obtenido.get("veredicto") or "Sin respuesta"
    return "—" if obtenido.get("puntaje") is None else f"{float(obtenido['puntaje']):g} pts"


def _tabla(encabezados: list[str], filas: list[list[str]]) -> str:
    lineas = ["| " + " | ".join(encabezados) + " |", "|" + "---|" * len(encabezados)]
    lineas += ["| " + " | ".join(str(c) for c in fila) + " |" for fila in filas]
    return "\n".join(lineas)


def _resumen(metricas: dict, modos: dict) -> str:
    def fila(nombre, extraer, formato):
        return [nombre, *(formato(extraer(metricas[m])) for m in modos if m in metricas)]

    filas = [
        fila("Exactitud en requisitos", lambda m: m["requisitos"]["exactitud"], _porcentaje),
        fila("Kappa de Cohen (requisitos)", lambda m: m["requisitos"]["kappa"], lambda v: "—" if v is None else f"{v:.2f}".replace(".", ",")),
        fila("Aprobaciones indebidas", lambda m: m["requisitos"]["aprobaciones_indebidas"], str),
        fila("Rechazos indebidos", lambda m: m["requisitos"]["rechazos_indebidos"], str),
        fila("Derivaciones innecesarias al comité", lambda m: m["requisitos"]["derivaciones_innecesarias"], str),
        fila("Exactitud en puntajes", lambda m: m["factores"]["exactitud"], _porcentaje),
        fila("Error absoluto medio del puntaje", lambda m: m["factores"]["error_absoluto_medio"], _numero),
        fila("Sobrepuntajes (más de lo que corresponde)", lambda m: m["factores"]["sobrepuntajes"], str),
        fila("Exactitud del resultado final", lambda m: m["resultado_final"]["exactitud"], _porcentaje),
        fila("«Califica» indebido", lambda m: m["resultado_final"]["califica_indebido"], str),
        fila("Tiempo promedio por postor (s)", lambda m: m["eficiencia"]["segundos"], _numero),
        fila("Consultas a la IA por postor", lambda m: m["eficiencia"]["consultas"], _numero),
        fila("Tokens por postor", lambda m: m["eficiencia"]["tokens"], _numero),
        fila("Reproducibilidad entre repeticiones", lambda m: m["reproducibilidad"], _porcentaje),
    ]
    return _tabla(["Métrica", *(modos[m] for m in modos if m in metricas)], filas)


def _por_caso(resultados: list[dict], casos: list, modos: dict) -> str:
    primera = {(r["modo"], r["caso"]): r for r in resultados if r["repeticion"] == 1}
    filas = []
    for caso in casos:
        esperado = caso.resultado + (f" ({sum(caso.esperado[k] for k in caso.esperado if not es_requisito(k)):g} pts)")
        celdas = []
        for modo in modos:
            r = primera.get((modo, caso.codigo))
            if r is None:
                continue
            puntaje = f" ({float(r['puntaje']):g} pts)" if r.get("puntaje") is not None else ""
            celdas.append(f"{'✅' if acierta_resultado(caso, r['resultado']) else '❌'} {r['resultado']}{puntaje}")
        filas.append([f"**{caso.codigo}** {caso.titulo}", caso.dificultad, esperado, *celdas])
    return _tabla(["Caso", "Dificultad", "Esperado", *modos.values()], filas)


def _errores(resultados: list[dict], casos: dict, modos: dict) -> str:
    filas = []
    for r in sorted(resultados, key=lambda r: (r["caso"], r["modo"], r["repeticion"])):
        caso = casos[r["caso"]]
        for clave, obtenido in r["criterios"].items():
            if not _acierta(caso, clave, obtenido):
                esperado = caso.esperado[clave] if es_requisito(clave) else f"{caso.esperado[clave]:g} pts"
                justificacion = (obtenido.get("justificacion") or r.get("error") or "").replace("\n", " ")[:220]
                filas.append([r["caso"], modos[r["modo"]] + (f" #{r['repeticion']}" if r["repeticion"] > 1 else ""),
                              ETIQUETAS_CRITERIOS[clave], esperado, _valor(clave, obtenido), justificacion])
    if not filas:
        return "No hubo errores: todas las decisiones coinciden con la respuesta correcta."
    return _tabla(["Caso", "Modo", "Criterio", "Esperado", "Obtenido", "Justificación del agente"], filas)


def _confusion(metricas: dict, modos: dict) -> str:
    secciones = []
    for modo, nombre in modos.items():
        if modo not in metricas:
            continue
        confusion = metricas[modo]["requisitos"]["confusion"]
        columnas = sorted({o for fila in confusion.values() for o in fila})
        filas = [[esperado, *(confusion[esperado].get(c, 0) for c in columnas)] for esperado in sorted(confusion)]
        secciones.append(f"**{nombre}** (filas: respuesta correcta; columnas: decisión del sistema)\n\n"
                         + _tabla(["Correcto \\ Sistema", *columnas], filas))
    return "\n\n".join(secciones)


def _banco(casos: list) -> str:
    filas = [[f"**{c.codigo}** {c.titulo}", *(
        (c.esperado[k] if es_requisito(k) else f"{c.esperado[k]:g}") for k in CRITERIOS
    ), c.resultado] for c in casos]
    return _tabla(["Caso", *(ETIQUETAS_CRITERIOS[k] for k in CRITERIOS), "Resultado"], filas)


DEFINICIONES = """- **Exactitud en requisitos**: proporción de decisiones de admisión y calificación iguales a la
  respuesta correcta (o a una alternativa igualmente válida, como en P05).
- **Kappa de Cohen**: acuerdo con la respuesta correcta descontando el que se daría por azar
  (1 = perfecto; 0 = no mejor que el azar; > 0,8 se considera casi perfecto).
- **Aprobación indebida**: el sistema declara «Cumple» o «No aplica» un requisito que no se cumple o
  que debía revisar el comité. Es el error más grave, porque deja pasar una oferta deficiente.
- **Rechazo indebido**: el sistema declara «No Cumple» un requisito que sí se cumple.
- **Derivación innecesaria**: el sistema pide revisión del comité en un caso que tenía respuesta clara.
  No es un error grave, pero le cuesta tiempo al comité.
- **Error absoluto medio del puntaje**: diferencia promedio, en puntos, entre el puntaje asignado y el
  correcto en cada factor de evaluación.
- **Reproducibilidad**: proporción de decisiones idénticas al repetir la evaluación de los mismos casos."""


def escribir_reporte(carpeta: Path, configuracion: dict, resultados: list[dict], metricas: dict, casos: list) -> None:
    modos = configuracion["modos"]
    por_codigo = {c.codigo: c for c in casos}
    (carpeta / "metricas.json").write_text(json.dumps(metricas, ensure_ascii=False, indent=1), encoding="utf-8")

    with open(carpeta / "decisiones.csv", "w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["modo", "repeticion", "caso", "criterio", "esperado", "obtenido", "correcto",
                           "pasos_del_agente", "justificacion"])
        for r in resultados:
            for clave, obtenido in r["criterios"].items():
                escritor.writerow([
                    modos[r["modo"]], r["repeticion"], r["caso"], ETIQUETAS_CRITERIOS[clave],
                    por_codigo[r["caso"]].esperado[clave], _valor(clave, obtenido),
                    "sí" if _acierta(por_codigo[r["caso"]], clave, obtenido) else "no",
                    len(obtenido.get("pasos") or []), (obtenido.get("justificacion") or "").replace("\n", " "),
                ])

    reporte = f"""# Validación del sistema multiagente

- **Fecha:** {configuracion['fecha']}
- **Modelo:** `{configuracion['modelo']}`
- **Casos:** {len(casos)} ({', '.join(configuracion['casos'])}) · **Repeticiones:** {configuracion['repeticiones']}
- **Modos comparados:** {' · '.join(modos.values())}

## Resumen

{_resumen(metricas, modos)}

## Resultado final por caso

{_por_caso(resultados, casos, modos)}

## Decisiones incorrectas

{_errores(resultados, por_codigo, modos)}

## Matriz de confusión de los requisitos

{_confusion(metricas, modos)}

## Banco de casos (respuesta correcta)

{_banco(casos)}

El detalle de cada caso y su dificultad está en `validacion/casos.py`; todas las decisiones, con la
justificación de los agentes, en `decisiones.csv`.

## Definiciones

{DEFINICIONES}
"""
    (carpeta / "REPORTE.md").write_text(reporte, encoding="utf-8")
