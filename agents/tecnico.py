from agents.evaluador import evaluar_criterio


def evaluar_criterio_tecnico(concurso_id: str, postor_id: str, criterio: dict) -> dict:
    return evaluar_criterio("Agente Técnico", concurso_id, postor_id, criterio)
