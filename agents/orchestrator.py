import time
from concurrent.futures import ThreadPoolExecutor

from agents.coordinador import consolidar_dictamen
from agents.evaluador import texto_de_busqueda
from agents.gemini_client import ContextoIA
from agents.legal import evaluar_criterio_legal
from agents.tecnico import evaluar_criterio_tecnico
from config import EVAL_HILOS
from db.client import get_client
from rag.embeddings import embed_consultas

PAUSA_ENTRE_CRITERIOS = 2.0


def _evaluar_criterios(concurso_id: str, postor: dict, tareas: list[tuple]) -> list[dict]:
    """tareas: (criterio, embedding de su búsqueda, revisión pedida por el Coordinador o None)."""
    agentes = {"legal": evaluar_criterio_legal, "tecnico": evaluar_criterio_tecnico}

    def ejecutar(tarea: tuple) -> dict:
        criterio, embedding, revision = tarea
        resultado = agentes[criterio["tipo"]](concurso_id, postor, criterio, embedding, revision)
        time.sleep(PAUSA_ENTRE_CRITERIOS)
        return {**resultado, "agente": criterio["tipo"], "revisado": revision is not None}

    with ThreadPoolExecutor(max_workers=EVAL_HILOS) as executor:
        return list(executor.map(ejecutar, tareas))


def _deliberar(concurso_id: str, postor: dict, criterios: list[dict], embeddings: list, resultados: list[dict],
               tensiones: list[dict]) -> int:
    """Devuelve a su agente cada criterio observado por el Coordinador, con la observación. Retorna cuántos."""
    observados = {t["criterio"]: t["observacion"] for t in tensiones if t["criterio"] is not None}
    tareas = [
        (criterios[i], embeddings[i], {"observacion": observacion, "anterior": resultados[i]})
        for i, observacion in observados.items()
    ]
    for (indice, observacion), nuevo in zip(observados.items(), _evaluar_criterios(concurso_id, postor, tareas)):
        anterior = resultados[indice]
        devolucion = {
            "herramienta": "observacion_del_coordinador",
            "argumentos": {},
            "resumen": f"El Coordinador devolvió el criterio («{observacion}»); evaluación anterior: {anterior['veredicto']}",
        }
        resultados[indice] = {**nuevo, "pasos": [*anterior["pasos"], devolucion, *nuevo["pasos"]]}
    return len(observados)


def evaluar_postor(postor_id: str) -> dict:
    client = get_client()

    postor = client.table("postores").select("*").eq("id", postor_id).single().execute().data
    concurso_id = postor["concurso_id"]
    concurso = client.table("concursos").select("*").eq("id", concurso_id).single().execute().data

    criterios = client.table("criterios").select("*").eq("concurso_id", concurso_id).execute().data
    criterios.sort(key=lambda c: (c.get("orden") is None, c.get("orden") or 0))

    embeddings = embed_consultas([texto_de_busqueda(c) for c in criterios]) if criterios else []
    resultados = _evaluar_criterios(concurso_id, postor, [(c, e, None) for c, e in zip(criterios, embeddings)])

    coordinador = ContextoIA("coordinador", concurso_id, postor_id)
    dictamen = consolidar_dictamen(resultados, concurso.get("puntaje_minimo"), coordinador)
    pasos_coordinador = []
    # Deliberación: una ronda en la que los agentes revisan lo observado y el Coordinador vuelve a evaluar.
    if devueltos := _deliberar(concurso_id, postor, criterios, embeddings, resultados, dictamen["tensiones"]):
        dictamen = consolidar_dictamen(resultados, concurso.get("puntaje_minimo"), coordinador, segunda_ronda=True)
        pasos_coordinador.append({
            "herramienta": "deliberacion",
            "argumentos": {},
            "resumen": f"Devolvió {devueltos} criterio(s) a los agentes y volvió a revisar la evaluación",
        })

    filas_dictamenes = [{
        "postor_id": postor_id,
        "concurso_id": concurso_id,
        "criterio_id": r["criterio_id"],
        "criterio_descripcion": r["criterio_descripcion"],
        "agente": r["agente"],
        "etapa": r["etapa"],
        "obligatorio": r["obligatorio"],
        "puntaje_maximo": r["puntaje_maximo"],
        "veredicto": r["veredicto"],
        "puntaje": r["puntaje"],
        "justificacion": r["justificacion"],
        "citas": r["citas"],
        "pasos": r["pasos"],
    } for r in resultados]

    filas_dictamenes.append({
        "postor_id": postor_id,
        "concurso_id": concurso_id,
        "agente": "coordinador",
        "veredicto": dictamen["veredicto"],
        "puntaje": dictamen["puntaje"],
        "puntaje_maximo": dictamen["puntaje_maximo"],
        "justificacion": dictamen["justificacion"],
        "citas": dictamen["citas"],
        "pasos": pasos_coordinador,
    })

    # Se insertan los nuevos antes de borrar los anteriores: si algo falla, no se pierde la evaluación previa.
    nuevos = client.table("dictamenes").insert(filas_dictamenes).execute().data
    client.table("dictamenes").delete().eq("postor_id", postor_id).not_.in_(
        "id", [d["id"] for d in nuevos]
    ).execute()

    client.table("postores").update({"estado": "evaluado", "error_evaluacion": None}).eq("id", postor_id).execute()

    return {"postor": postor, "resultados": resultados, "dictamen": dictamen}
