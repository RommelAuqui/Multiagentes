"""Ejecuta la validación con Supabase y Gemini reales y genera el reporte.

Uso:
    python -m validacion.ejecutar                      # ambos modos, 1 repetición, los 10 casos
    python -m validacion.ejecutar --modos agentico --repeticiones 3 --casos P03,P05

Los documentos de cada caso se leen e indexan una sola vez; luego cada modo evalúa a los mismos
postores. Al terminar se borra la convocatoria de validación (salvo con --conservar).
"""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import agents.agente as agente
import agents.orchestrator as orquestador
from agents.gemini_client import ContextoIA
from config import LLM_MODEL
from db.client import get_client
from rag.ingest import guardar_fragmentos, preparar_documento
from validacion.casos import CASOS, CRITERIOS, PUNTAJE_MINIMO
from validacion.metricas import calcular_metricas
from validacion.reporte import escribir_reporte

MODOS = {
    "agentico": {"nombre": "Agentes autónomos (Fase 2)", "max_pasos": 6, "deliberacion": True},
    "un_paso": {"nombre": "Un solo paso (Fase 1)", "max_pasos": 1, "deliberacion": False},
}
CARPETA_RESULTADOS = Path(__file__).parent / "resultados"


def preparar(casos: list) -> tuple[dict, dict, dict]:
    """Crea la convocatoria de validación con la matriz fija e indexa la oferta de cada caso."""
    client = get_client()
    concurso = client.table("concursos").insert({
        "nombre": f"VALIDACIÓN {datetime.now():%Y-%m-%d %H:%M} (se elimina sola)",
        "estado": "cerrado", "puntaje_minimo": PUNTAJE_MINIMO,
    }).execute().data[0]
    insertados = client.table("criterios").insert([
        {**criterio, "concurso_id": concurso["id"], "orden": orden} for orden, criterio in enumerate(CRITERIOS.values())
    ]).execute().data
    claves = {fila["id"]: clave for fila, clave in zip(insertados, CRITERIOS)}

    postores = {}
    for caso in casos:
        postor = client.table("postores").insert({
            "concurso_id": concurso["id"], "ruc": caso.ruc, "razon_social": caso.razon_social, "estado": "recibido",
        }).execute().data[0]
        lector = ContextoIA("lector", concurso["id"], postor["id"])
        documentos = [preparar_documento(contenido, lector, nombre) for nombre, contenido in caso.pdfs()]
        archivos = [{"nombre": d.nombre, "path": None, "paginas": d.extraccion.total_paginas} for d in documentos]
        client.table("postores").update({"archivos": archivos}).eq("id", postor["id"]).execute()
        for documento in documentos:
            guardar_fragmentos(concurso["id"], postor["id"], "oferta", documento)
        postores[caso.codigo] = {**postor, "archivos": archivos}
        print(f"  Indexado {caso.codigo}: {len(documentos)} archivos")
    return concurso, claves, postores


def evaluar(modo: str, repeticion: int, caso, postor: dict, claves: dict) -> dict:
    client = get_client()
    agente.MAX_PASOS = MODOS[modo]["max_pasos"]
    orquestador.DELIBERACION = MODOS[modo]["deliberacion"]
    desde = datetime.now(timezone.utc).isoformat()
    inicio = time.monotonic()
    error = None
    try:
        orquestador.evaluar_postor(postor["id"])
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
    segundos = round(time.monotonic() - inicio, 1)

    filas = client.table("dictamenes").select("*").eq("postor_id", postor["id"]).execute().data if not error else []
    criterios = {clave: {"veredicto": None, "puntaje": None} for clave in CRITERIOS}
    for fila in filas:
        if fila["agente"] != "coordinador" and fila.get("criterio_id") in claves:
            criterios[claves[fila["criterio_id"]]] = {
                "veredicto": fila["veredicto"], "puntaje": fila.get("puntaje"),
                "justificacion": fila.get("justificacion"), "pasos": [p["resumen"] for p in fila.get("pasos") or []],
            }
    final = next((f for f in filas if f["agente"] == "coordinador"), {})
    consultas = (
        client.table("consultas_ia").select("tokens_entrada,tokens_salida")
        .eq("postor_id", postor["id"]).gte("created_at", desde).execute().data
    )
    return {
        "modo": modo, "repeticion": repeticion, "caso": caso.codigo,
        "criterios": criterios, "resultado": final.get("veredicto", "Error"), "puntaje": final.get("puntaje"),
        "justificacion_final": final.get("justificacion"), "error": error,
        "segundos": segundos, "consultas": len(consultas),
        "tokens": sum((c.get("tokens_entrada") or 0) + (c.get("tokens_salida") or 0) for c in consultas),
    }


def ejecutar(modos: list[str], repeticiones: int, codigos: list[str] | None, conservar: bool) -> Path:
    casos = [c for c in CASOS if not codigos or c.codigo in codigos]
    carpeta = CARPETA_RESULTADOS / f"{datetime.now():%Y-%m-%d_%H%M}"
    carpeta.mkdir(parents=True, exist_ok=True)
    configuracion = {
        "fecha": f"{datetime.now():%d/%m/%Y %H:%M}", "modelo": LLM_MODEL, "repeticiones": repeticiones,
        "modos": {m: MODOS[m]["nombre"] for m in modos}, "casos": [c.codigo for c in casos],
    }
    print(f"Validación: {len(casos)} casos × {len(modos)} modo(s) × {repeticiones} repetición(es). Modelo: {LLM_MODEL}")

    concurso, claves, postores = preparar(casos)
    resultados: list[dict] = []
    max_pasos, deliberacion = agente.MAX_PASOS, orquestador.DELIBERACION
    try:
        for repeticion in range(1, repeticiones + 1):
            for modo in modos:
                for caso in casos:
                    resultado = evaluar(modo, repeticion, caso, postores[caso.codigo], claves)
                    resultados.append(resultado)
                    print(f"  [{modo} #{repeticion}] {caso.codigo}: {resultado['resultado']} "
                          f"(esperado {caso.resultado}) · {resultado['segundos']} s · {resultado['consultas']} consultas")
                    # Se guarda en cada paso: si la ejecución se interrumpe, no se pierde lo avanzado.
                    (carpeta / "resultados.json").write_text(json.dumps(resultados, ensure_ascii=False, indent=1),
                                                             encoding="utf-8")
    finally:
        agente.MAX_PASOS, orquestador.DELIBERACION = max_pasos, deliberacion
        if not conservar:
            get_client().table("concursos").delete().eq("id", concurso["id"]).execute()

    metricas = calcular_metricas(resultados, {c.codigo: c for c in casos})
    escribir_reporte(carpeta, configuracion, resultados, metricas, casos)
    return carpeta


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--modos", default="agentico,un_paso")
    parser.add_argument("--repeticiones", type=int, default=1)
    parser.add_argument("--casos", default="", help="códigos separados por comas (por defecto, todos)")
    parser.add_argument("--conservar", action="store_true", help="no borrar la convocatoria de validación")
    args = parser.parse_args()
    modos = [m for m in args.modos.split(",") if m]
    desconocidos = set(modos) - set(MODOS)
    if desconocidos:
        parser.error(f"Modos desconocidos: {', '.join(desconocidos)}. Opciones: {', '.join(MODOS)}")
    carpeta = ejecutar(modos, args.repeticiones, [c for c in args.casos.split(",") if c] or None, args.conservar)
    print(f"Reporte: {carpeta / 'REPORTE.md'}")


if __name__ == "__main__":
    main()
