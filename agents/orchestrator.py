import time

from agents.coordinador import consolidar_dictamen
from agents.legal import evaluar_criterio_legal
from agents.tecnico import evaluar_criterio_tecnico
from db.client import get_client

PAUSA_ENTRE_CRITERIOS = 2.0


def evaluar_postor(postor_id: str) -> dict:
    client = get_client()

    postor = client.table("postores").select("*").eq("id", postor_id).single().execute().data
    concurso_id = postor["concurso_id"]

    criterios = client.table("criterios").select("*").eq("concurso_id", concurso_id).execute().data
    criterios_legales = [c for c in criterios if c["tipo"] == "legal"]
    criterios_tecnicos = [c for c in criterios if c["tipo"] == "tecnico"]

    resultados_legal = []
    for c in criterios_legales:
        resultados_legal.append(evaluar_criterio_legal(concurso_id, postor_id, c))
        time.sleep(PAUSA_ENTRE_CRITERIOS)

    resultados_tecnico = []
    for c in criterios_tecnicos:
        resultados_tecnico.append(evaluar_criterio_tecnico(concurso_id, postor_id, c))
        time.sleep(PAUSA_ENTRE_CRITERIOS)

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

    client.table("dictamenes").insert(filas_dictamenes).execute()

    client.table("postores").update({"estado": "evaluado"}).eq("id", postor_id).execute()

    return {
        "postor": postor,
        "resultados_legal": resultados_legal,
        "resultados_tecnico": resultados_tecnico,
        "dictamen": dictamen,
    }
