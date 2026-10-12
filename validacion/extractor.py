"""Validación del Agente Extractor con Bases Integradas reales.

Compara la matriz extraída con la matriz correcta anotada a mano (validacion/bases/*.json).

Uso:
    python -m validacion.extractor --bases validacion/bases/meta_iv.json=RUTA.pdf \\
        --bases validacion/bases/golf.json=RUTA.pdf --repeticiones 3

El texto leído de cada PDF se guarda en validacion/.cache para no volver a transcribir los escaneados.
"""
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

from agents.extractor import extraer_criterios
from agents.gemini_client import ContextoIA
from agents.reglas import clave
from rag.pdf_extract import extraer_paginas, texto_completo

CACHE = Path(__file__).parent / ".cache"
CARPETA_RESULTADOS = Path(__file__).parent / "resultados"


def _contiene(criterio: dict, palabras: list[str]) -> bool:
    texto = clave(criterio["descripcion"])
    return all(clave(p) in texto for p in palabras)


def comparar_matriz(esperada: dict, criterios: list[dict], puntaje_minimo: float | None) -> dict:
    """Empareja cada criterio esperado con los extraídos de la misma etapa que contienen sus palabras clave."""
    usados: set[int] = set()
    emparejados: dict[int, list[int]] = {}
    # Primero los criterios únicos y luego los que pueden venir divididos («varios»), para que estos
    # no se queden con un criterio que corresponde a otro.
    orden = sorted(range(len(esperada["criterios"])), key=lambda i: esperada["criterios"][i].get("varios", False))
    for i in orden:
        esperado = esperada["criterios"][i]
        candidatos = [j for j, c in enumerate(criterios)
                      if j not in usados and c["etapa"] == esperado["etapa"] and _contiene(c, esperado["palabras"])]
        elegidos = candidatos if esperado.get("varios") else candidatos[:1]
        emparejados[i] = elegidos
        usados.update(elegidos)

    encontrados = [i for i, j in emparejados.items() if j]
    condicionales = [i for i, e in enumerate(esperada["criterios"]) if e.get("condicional")]
    factores = [i for i, e in enumerate(esperada["criterios"]) if "puntaje" in e]

    def marcado_condicional(i):
        return emparejados[i] and all(clave(criterios[j]["descripcion"]).startswith("solo si") for j in emparejados[i])

    def puntaje_correcto(i):
        return emparejados[i] and abs(sum(criterios[j]["puntaje_maximo"] or 0 for j in emparejados[i])
                                      - esperada["criterios"][i]["puntaje"]) < 0.01

    violaciones = [
        {"motivo": e["motivo"], "criterio": c["descripcion"][:120]}
        for e in esperada["excluidos"] for c in criterios if _contiene(c, e["palabras"])
    ]
    excluidos_incluidos = sum(any(_contiene(c, e["palabras"]) for c in criterios) for e in esperada["excluidos"])
    suma = sum(c["puntaje_maximo"] or 0 for c in criterios if c["etapa"] == "evaluacion")
    return {
        "esperados": len(esperada["criterios"]),
        "encontrados": len(encontrados),
        "exhaustividad": round(len(encontrados) / len(esperada["criterios"]), 4),
        "extraidos": len(criterios),
        "precision": round(len(usados) / len(criterios), 4) if criterios else None,
        "condicionales_marcados": f"{sum(bool(marcado_condicional(i)) for i in condicionales)}/{len(condicionales)}",
        "puntajes_correctos": f"{sum(bool(puntaje_correcto(i)) for i in factores)}/{len(factores)}",
        "exclusiones_respetadas": f"{len(esperada['excluidos']) - excluidos_incluidos}/{len(esperada['excluidos'])}",
        "puntaje_minimo_correcto": puntaje_minimo == esperada["puntaje_minimo"],
        "suma_factores": suma,
        "suma_correcta": abs(suma - esperada["puntaje_total"]) < 0.01,
        "no_encontrados": [esperada["criterios"][i]["palabras"] for i in emparejados if not emparejados[i]],
        "sobrantes": [criterios[j]["descripcion"][:120] for j in range(len(criterios)) if j not in usados],
        "violaciones": violaciones,
    }


def _texto_de_bases(ruta_pdf: Path) -> str:
    contenido = ruta_pdf.read_bytes()
    cache = CACHE / f"{hashlib.sha256(contenido).hexdigest()[:16]}.json"
    if cache.exists():
        paginas = json.loads(cache.read_text(encoding="utf-8"))
    else:
        paginas = extraer_paginas(contenido, ContextoIA("validacion")).paginas
        CACHE.mkdir(exist_ok=True)
        cache.write_text(json.dumps(paginas, ensure_ascii=False), encoding="utf-8")
    return texto_completo(paginas)


def _reporte(filas: list[dict]) -> str:
    encabezados = ["Bases", "Corrida", "Exhaustividad", "Precisión", "Extraídos", "Condicionales",
                   "Puntajes", "Exclusiones", "Mínimo", "Suma factores"]
    lineas = ["| " + " | ".join(encabezados) + " |", "|" + "---|" * len(encabezados)]
    for f in filas:
        r = f["resultado"]
        lineas.append("| " + " | ".join([
            f["bases"], str(f["corrida"]), f"{r['exhaustividad'] * 100:.1f} %".replace(".", ","),
            f"{r['precision'] * 100:.1f} %".replace(".", ",") if r["precision"] is not None else "—",
            str(r["extraidos"]), r["condicionales_marcados"], r["puntajes_correctos"], r["exclusiones_respetadas"],
            "✅" if r["puntaje_minimo_correcto"] else "❌", f"{r['suma_factores']:g} {'✅' if r['suma_correcta'] else '❌'}",
        ]) + " |")
    detalle = []
    for f in filas:
        r = f["resultado"]
        for etiqueta, lista in (("No encontrados", r["no_encontrados"]), ("Sobrantes", r["sobrantes"]),
                                ("Exclusiones no respetadas", [f"{v['motivo']}: {v['criterio']}" for v in r["violaciones"]])):
            if lista:
                detalle.append(f"- **{f['bases']}, corrida {f['corrida']} — {etiqueta}:** " + "; ".join(map(str, lista)))
    return ("# Validación del Agente Extractor\n\n"
            "Comparación de la matriz extraída de Bases Integradas reales con la matriz anotada a mano "
            "(`validacion/bases/*.json`).\n\n" + "\n".join(lineas) + "\n\n"
            + ("## Diferencias\n\n" + "\n".join(detalle) if detalle else "Sin diferencias en ninguna corrida.") + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bases", action="append", required=True, help="matriz.json=ruta_del_pdf")
    parser.add_argument("--repeticiones", type=int, default=3)
    args = parser.parse_args()

    filas = []
    for par in args.bases:
        ruta_matriz, ruta_pdf = par.split("=", 1)
        esperada = json.loads(Path(ruta_matriz).read_text(encoding="utf-8"))
        texto = _texto_de_bases(Path(ruta_pdf))
        for corrida in range(1, args.repeticiones + 1):
            matriz = extraer_criterios(texto, ContextoIA("validacion"))
            resultado = comparar_matriz(esperada, matriz.criterios, matriz.puntaje_minimo)
            filas.append({"bases": Path(ruta_matriz).stem, "corrida": corrida, "resultado": resultado,
                          "criterios": matriz.criterios})
            print(f"{Path(ruta_matriz).stem} #{corrida}: exhaustividad {resultado['exhaustividad']:.0%}, "
                  f"precisión {resultado['precision']:.0%}, suma {resultado['suma_factores']:g}")

    carpeta = CARPETA_RESULTADOS / f"{datetime.now():%Y-%m-%d_%H%M}_extractor"
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "detalle.json").write_text(json.dumps(filas, ensure_ascii=False, indent=1), encoding="utf-8")
    (carpeta / "REPORTE_EXTRACTOR.md").write_text(_reporte(filas), encoding="utf-8")
    print(f"Reporte: {carpeta / 'REPORTE_EXTRACTOR.md'}")


if __name__ == "__main__":
    main()
