"""Validación del módulo de revisión de Bases con los expedientes de demostración.

Cada convocatoria de demo/ trae fallas sembradas y la lista de verificaciones que deberían fallar en cada ronda
(demo/expediente.py). El script sube los documentos, ejecuta las dos rondas y compara lo detectado con lo
esperado: exhaustividad (fallas sembradas detectadas), precisión (hallazgos que eran fallas reales) y falsos
positivos por verificación. Usa una base de datos en memoria: no escribe en Supabase.

Uso:
    python -m validacion.revision                          # las 5 convocatorias, con el agente revisor
    python -m validacion.revision --sin-agente             # solo reglas fijas (no gasta Gemini en el agente)
    python -m validacion.revision --convocatorias convocatoria_4_supervision_canal_de_riego
"""
import argparse
import json
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import db.client
from demo.expediente import EXPEDIENTES
from revision.catalogo import AGENTE, POR_CODIGO, REGLA

CARPETA_DEMO = Path(__file__).parent.parent / "demo" / "convocatorias"
CARPETA_RESULTADOS = Path(__file__).parent / "resultados"
ARCHIVOS = {
    "A": {"requerimiento": "A1 Requerimiento.pdf", "certificacion": "A2 Certificación presupuestal.pdf",
          "estrategia": "A3 Estrategia de contratación.pdf", "interaccion_mercado": "A4 Interacción con el mercado.pdf",
          "designacion_evaluadores": "A5 Designación del comité.pdf",
          "aprobacion_expediente": "A6 Aprobación del expediente.pdf", "bases": "A7 Bases para convocar.pdf"},
    "B": {"pliego": "B1 Pliego de absolución.pdf"},
}


def _base_en_memoria():
    from tests.fakes import SupabaseFalso

    falsa = SupabaseFalso()
    db.client.create_client = lambda *_: falsa
    db.client.get_client.cache_clear()
    return falsa


def revisar_convocatoria(carpeta: str, con_agente: bool) -> list[dict]:
    from revision import servicio

    falsa = _base_en_memoria()
    concurso = falsa.table("concursos").insert({"nombre": carpeta, "estado": "revision_bases",
                                                "ronda_revision": "A"}).execute().data[0]
    origen = CARPETA_DEMO / carpeta
    filas = []
    for ronda in ("A", "B"):
        inicio = time.monotonic()
        for tipo, nombre in ARCHIVOS[ronda].items():
            servicio.subir_documento(concurso["id"], tipo, nombre, (origen / "revision_de_bases" / nombre).read_bytes())
        if ronda == "B":
            integradas = next(origen.glob("Bases Integradas *.pdf"))
            servicio.subir_documento(concurso["id"], "bases_integradas", integradas.name, integradas.read_bytes())
        revision = servicio.revisar(concurso["id"], ronda, con_agente=con_agente)
        consultas = falsa.filas("consultas_ia")
        filas.append({
            "convocatoria": carpeta, "ronda": ronda, "segundos": round(time.monotonic() - inicio, 1),
            "esperadas": sorted(getattr(EXPEDIENTES[carpeta], f"esperado_{ronda.lower()}")),
            "resultados": revision["resultados"], "consultas": len(consultas),
            "tokens": sum((c.get("tokens_entrada") or 0) + (c.get("tokens_salida") or 0) for c in consultas),
        })
        falsa.tablas["consultas_ia"] = []
        # El comité mantiene lo de la ronda A para poder seguir con la B (como en el uso real).
        for hallazgo in servicio.hallazgos(concurso["id"], ronda):
            if hallazgo["estado"] == "pendiente":
                servicio.mantener(hallazgo["id"], "Validación automática.", "Validación")
    return filas


def metricas(filas: list[dict], con_agente: bool) -> dict:
    evaluables = {codigo for codigo, v in POR_CODIGO.items() if con_agente or v.metodo == REGLA}
    vp = fn = fp = 0
    por_codigo = {c: Counter() for c in evaluables}
    no_verificadas = Counter()
    for fila in filas:
        detectadas = {r["codigo"] for r in fila["resultados"] if r["estado"] == "falla"}
        esperadas = set(fila["esperadas"]) & evaluables
        for r in fila["resultados"]:
            if r["estado"] == "no_verificado":
                no_verificadas[r["codigo"]] += 1
        for codigo in esperadas:
            por_codigo[codigo]["esperada"] += 1
            if codigo in detectadas:
                por_codigo[codigo]["detectada"] += 1
                vp += 1
            else:
                fn += 1
        for codigo in detectadas - esperadas:
            por_codigo[codigo]["falso_positivo"] += 1
            fp += 1
    return {
        "verdaderos_positivos": vp, "falsos_negativos": fn, "falsos_positivos": fp,
        "exhaustividad": round(vp / (vp + fn), 4) if vp + fn else None,
        "precision": round(vp / (vp + fp), 4) if vp + fp else None,
        "por_codigo": {c: dict(v) for c, v in por_codigo.items() if v},
        "no_verificadas": dict(no_verificadas),
        "consultas": sum(f["consultas"] for f in filas), "tokens": sum(f["tokens"] for f in filas),
        "segundos": round(sum(f["segundos"] for f in filas), 1),
    }


def _porcentaje(valor) -> str:
    return "—" if valor is None else f"{valor * 100:.1f} %".replace(".", ",")


def reporte(filas: list[dict], m: dict, con_agente: bool) -> str:
    lineas = [
        "# Validación del módulo de revisión de Bases", "",
        f"- **Fecha:** {datetime.now():%d/%m/%Y %H:%M}",
        f"- **Modo:** {'reglas fijas y agente revisor' if con_agente else 'solo reglas fijas'}",
        f"- **Convocatorias:** {len({f['convocatoria'] for f in filas})} · rondas revisadas: {len(filas)}", "",
        "## Resumen", "",
        "| Métrica | Valor |", "|---|---|",
        f"| Fallas sembradas detectadas (exhaustividad) | {_porcentaje(m['exhaustividad'])} "
        f"({m['verdaderos_positivos']} de {m['verdaderos_positivos'] + m['falsos_negativos']}) |",
        f"| Hallazgos que eran fallas reales (precisión) | {_porcentaje(m['precision'])} |",
        f"| Falsos positivos | {m['falsos_positivos']} |",
        f"| Verificaciones no verificadas | {sum(m['no_verificadas'].values())} |",
        f"| Consultas a Gemini | {m['consultas']} |",
        f"| Tokens | {m['tokens']:,} |".replace(",", " "),
        f"| Tiempo total | {m['segundos']:.0f} s |", "",
        "## Por convocatoria y ronda", "",
        "| Convocatoria | Ronda | Esperadas | Detectadas | No detectadas | De más |", "|---|---|---|---|---|---|",
    ]
    for f in filas:
        detectadas = sorted({r["codigo"] for r in f["resultados"] if r["estado"] == "falla"})
        esperadas = set(f["esperadas"])
        lineas.append(f"| {f['convocatoria']} | {f['ronda']} | {', '.join(f['esperadas']) or '—'} | "
                      f"{', '.join(detectadas) or '—'} | {', '.join(sorted(esperadas - set(detectadas))) or '—'} | "
                      f"{', '.join(sorted(set(detectadas) - esperadas)) or '—'} |")
    lineas += ["", "## Hallazgos de más (posibles falsos positivos)", ""]
    de_mas = [(f, r) for f in filas for r in f["resultados"]
              if r["estado"] == "falla" and r["codigo"] not in f["esperadas"]]
    if not de_mas:
        lineas.append("Ninguno.")
    for f, r in de_mas:
        metodo = "agente" if POR_CODIGO[r["codigo"]].metodo == AGENTE else "regla"
        lineas.append(f"- **{f['convocatoria']}, ronda {f['ronda']}, {r['codigo']}** ({metodo}): {r['descripcion']}")
    lineas += ["", "Un hallazgo de más no siempre es un error: puede ser una falla real que no se sembró a propósito. "
               "Cada uno se revisa a mano antes de reportarlo como falso positivo.", ""]
    return "\n".join(lineas)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sin-agente", action="store_true")
    parser.add_argument("--convocatorias", default="", help="carpetas separadas por comas (por defecto, todas)")
    args = parser.parse_args()
    carpetas = [c for c in args.convocatorias.split(",") if c] or list(EXPEDIENTES)
    filas = []
    for carpeta in carpetas:
        print(f"Revisando {carpeta}...", flush=True)
        filas += revisar_convocatoria(carpeta, not args.sin_agente)
    m = metricas(filas, not args.sin_agente)
    salida = CARPETA_RESULTADOS / f"{datetime.now():%Y-%m-%d_%H%M}_revision{'_reglas' if args.sin_agente else ''}"
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "resultados.json").write_text(json.dumps({"filas": filas, "metricas": m}, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
    (salida / "REPORTE_REVISION.md").write_text(reporte(filas, m, not args.sin_agente), encoding="utf-8")
    print(f"Exhaustividad {_porcentaje(m['exhaustividad'])} · precisión {_porcentaje(m['precision'])} · "
          f"{m['consultas']} consultas. Reporte: {salida / 'REPORTE_REVISION.md'}")


if __name__ == "__main__":
    main()
