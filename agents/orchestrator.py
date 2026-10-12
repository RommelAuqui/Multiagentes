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


def _evaluar_criterios(concurso_id: str, postor_id: str, criterios: list[dict]) -> list[dict]:
    if not criterios:
        return []

    agentes = {"legal": evaluar_criterio_legal, "tecnico": evaluar_criterio_tecnico}
    embeddings = embed_consultas([texto_de_busqueda(c) for c in criterios])

    def ejecutar(criterio: dict, embedding: list[float]) -> dict:
        resultado = agentes[criterio["tipo"]](concurso_id, postor_id, criterio, embedding)
        time.sleep(PAUSA_ENTRE_CRITERIOS)
        return {**resultado, "agente": criterio["tipo"]}

    with ThreadPoolExecutor(max_workers=EVAL_HILOS) as executor:
        return list(executor.map(ejecutar, criterios, embeddings))


def evaluar_postor(postor_id: str) -> dict:
    client = get_client()

    postor = client.table("postores").select("*").eq("id", postor_id).single().execute().data
    concurso_id = postor["concurso_id"]
    concurso = client.table("concursos").select("*").eq("id", concurso_id).single().execute().data

    criterios = client.table("criterios").select("*").eq("concurso_id", concurso_id).execute().data
    criterios.sort(key=lambda c: (c.get("orden") is None, c.get("orden") or 0))

    resultados = _evaluar_criterios(concurso_id, postor_id, criterios)
    dictamen = consolidar_dictamen(
        resultados, concurso.get("puntaje_minimo"), ContextoIA("coordinador", concurso_id, postor_id)
    )

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
    })

    # Se insertan los nuevos antes de borrar los anteriores: si algo falla, no se pierde la evaluación previa.
    nuevos = client.table("dictamenes").insert(filas_dictamenes).execute().data
    client.table("dictamenes").delete().eq("postor_id", postor_id).not_.in_(
        "id", [d["id"] for d in nuevos]
    ).execute()

    client.table("postores").update({"estado": "evaluado"}).eq("id", postor_id).execute()

    return {"postor": postor, "resultados": resultados, "dictamen": dictamen}
