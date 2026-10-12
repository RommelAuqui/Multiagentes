from agents.evaluador import evaluar_criterio


def evaluar_criterio_legal(
    concurso_id: str, postor: dict, criterio: dict, query_embedding: list[float], revision: dict | None = None
) -> dict:
    return evaluar_criterio("legal", "Agente Legal", concurso_id, postor, criterio, query_embedding, revision)
