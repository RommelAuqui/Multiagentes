from agents.evaluador import evaluar_criterio


def evaluar_criterio_tecnico(concurso_id: str, postor_id: str, criterio: dict, query_embedding: list[float]) -> dict:
    return evaluar_criterio("tecnico", "Agente Técnico", concurso_id, postor_id, criterio, query_embedding)
