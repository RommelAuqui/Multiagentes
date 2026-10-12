import time
from concurrent.futures import ThreadPoolExecutor

from agents.coordinador import consolidar_dictamen
from agents.legal import evaluar_criterio_legal
from agents.tecnico import evaluar_criterio_tecnico
from config import EVAL_HILOS
from db.client import get_client
from rag.embeddings import embed_consultas

PAUSA_ENTRE_CRITERIOS = 2.0


def _evaluar_criterios(concurso_id: str, postor_id: str, tareas: list[tuple]) -> list[dict]:
    if not tareas:
        return []

    embeddings = embed_consultas([criterio["descripcion"] for _, criterio in tareas])

    def ejecutar(tarea: tuple, embedding: list[float]) -> dict:
        evaluar, criterio = tarea
        resultado = evaluar(concurso_id, postor_id, criterio, embedding)
        time.sleep(PAUSA_ENTRE_CRITERIOS)
        return resultado

    with ThreadPoolExecutor(max_workers=EVAL_HILOS) as executor:
        return list(executor.map(ejecutar, tareas, embeddings))


def evaluar_postor(postor_id: str) -> dict:
    client = get_client()

    postor = client.table("postores").select("*").eq("id", postor_id).single().execute().data
    concurso_id = postor["concurso_id"]

    criterios = client.table("criterios").select("*").eq("concurso_id", concurso_id).execute().data
    criterios_legales = [c for c in criterios if c["tipo"] == "legal"]
    criterios_tecnicos = [c for c in criterios if c["tipo"] == "tecnico"]

    resultados = _evaluar_criterios(concurso_id, postor_id, [
        *((evaluar_criterio_legal, c) for c in criterios_legales),
        *((evaluar_criterio_tecnico, c) for c in criterios_tecnicos),
    ])
    resultados_legal = resultados[:len(criterios_legales)]
    resultados_tecnico = resultados[len(criterios_legales):]

    dictamen = consolidar_dictamen(criterios_legales, resultados_legal, resultados_tecnico)

    filas_dictamenes = []
    for agente, resultados in (("legal", resultados_legal), ("tecnico", resultados_tecnico)):
        for r in resultados:
            filas_dictamenes.append({
                "postor_id": postor_id,
                "concurso_id": concurso_id,
                "criterio_id": r["criterio_id"],
                "criterio_descripcion": r["criterio_descripcion"],
                "agente": agente,
                "veredicto": r["veredicto"],
                "justificacion": r["justificacion"],
                "citas": r.get("citas", []),
            })

    filas_dictamenes.append({
        "postor_id": postor_id,
        "concurso_id": concurso_id,
        "agente": "coordinador",
        "veredicto": dictamen["veredicto"],
        "justificacion": dictamen["justificacion"],
        "citas": dictamen["citas"],
        "puntaje": dictamen["puntaje"],
    })

    # Se insertan los nuevos antes de borrar los anteriores: si algo falla, no se pierde la evaluación previa.
    nuevos = client.table("dictamenes").insert(filas_dictamenes).execute().data
    client.table("dictamenes").delete().eq("postor_id", postor_id).not_.in_(
        "id", [d["id"] for d in nuevos]
    ).execute()

    client.table("postores").update({"estado": "evaluado"}).eq("id", postor_id).execute()

    return {
        "postor": postor,
        "resultados_legal": resultados_legal,
        "resultados_tecnico": resultados_tecnico,
        "dictamen": dictamen,
    }
