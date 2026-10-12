"""Flujo automático: cierra las convocatorias vencidas y evalúa a sus postores pendientes.

Se ejecuta cada hora desde GitHub Actions (.github/workflows/evaluacion-automatica.yml), o a mano con
`python automatizacion.py`. Controles de gasto:
- Solo se evalúan las convocatorias cerradas con la evaluación automática activada.
- Cada postor se evalúa una sola vez: si falla, queda con error y no se reintenta solo.
- Se respeta un límite diario de consultas a la IA; al alcanzarlo, la ejecución se pausa hasta el día
  siguiente.
"""
import logging
from datetime import datetime, timedelta, timezone

import consumo
from agents.orchestrator import evaluar_postor
from db.client import get_client

# Una evaluación que lleva más que esto en curso se considera interrumpida (p. ej., se cortó el proceso).
MINUTOS_MAXIMOS_EVALUACION = 60
MAX_CARACTERES_ERROR = 500

registro = logging.getLogger("automatizacion")


def _fecha(valor: str) -> datetime:
    return datetime.fromisoformat(valor)


def evaluar_registrando(postor: dict, evaluar=evaluar_postor) -> None:
    """Evalúa a un postor dejando constancia del estado; si falla, queda con error y no se reintenta."""
    client = get_client()
    client.table("postores").update({
        "estado": "evaluando", "evaluacion_iniciada_en": datetime.now(timezone.utc).isoformat(), "error_evaluacion": None,
    }).eq("id", postor["id"]).execute()
    try:
        evaluar(postor["id"])
    except Exception as e:
        client.table("postores").update({
            "estado": "error", "error_evaluacion": f"{type(e).__name__}: {e}"[:MAX_CARACTERES_ERROR],
        }).eq("id", postor["id"]).execute()
        raise


def cerrar_vencidas(ahora: datetime) -> list[dict]:
    client = get_client()
    abiertas = client.table("concursos").select("*").eq("estado", "abierto").execute().data
    vencidas = [c for c in abiertas if c.get("fecha_cierre") and _fecha(c["fecha_cierre"]) <= ahora]
    for concurso in vencidas:
        client.table("concursos").update({"estado": "cerrado"}).eq("id", concurso["id"]).execute()
    return vencidas


def marcar_interrumpidas(ahora: datetime) -> list[dict]:
    client = get_client()
    en_curso = client.table("postores").select("*").eq("estado", "evaluando").execute().data
    limite = ahora - timedelta(minutes=MINUTOS_MAXIMOS_EVALUACION)
    interrumpidas = [
        p for p in en_curso if not p.get("evaluacion_iniciada_en") or _fecha(p["evaluacion_iniciada_en"]) < limite
    ]
    for postor in interrumpidas:
        client.table("postores").update({
            "estado": "error", "error_evaluacion": "La evaluación se interrumpió antes de terminar.",
        }).eq("id", postor["id"]).eq("estado", "evaluando").execute()
    return interrumpidas


def _evaluar_pendientes(resumen: dict, detalle: list[str], evaluar) -> None:
    client = get_client()
    concursos = (
        client.table("concursos").select("*").eq("estado", "cerrado").eq("evaluacion_automatica", True).execute().data
    )
    for concurso in concursos:
        criterios = len(client.table("criterios").select("id").eq("concurso_id", concurso["id"]).execute().data)
        pendientes = (
            client.table("postores").select("*").eq("concurso_id", concurso["id"]).eq("estado", "recibido").execute().data
        )
        for postor in pendientes:
            if not consumo.hay_cupo(criterios):
                resumen["pausada_por_limite"] = True
                detalle.append(
                    f"Pausada: evaluar a {postor['razon_social']} superaría el límite diario de "
                    f"{consumo.LIMITE_DIARIO_CONSULTAS} consultas. Continuará mañana."
                )
                return
            try:
                evaluar_registrando(postor, evaluar)
            except Exception as e:
                resumen["postores_con_error"] += 1
                detalle.append(f"Error al evaluar a {postor['razon_social']} ({concurso['nombre']}): {e}")
                registro.exception("Falló la evaluación de %s", postor["id"])
            else:
                resumen["postores_evaluados"] += 1
                detalle.append(f"Evaluado: {postor['razon_social']} ({concurso['nombre']}).")


def ejecutar(evaluar=evaluar_postor) -> dict:
    client = get_client()
    ahora = datetime.now(timezone.utc)
    ejecucion = client.table("ejecuciones_automaticas").insert({"inicio": ahora.isoformat()}).execute().data[0]
    resumen = {"convocatorias_cerradas": 0, "postores_evaluados": 0, "postores_con_error": 0, "pausada_por_limite": False}
    detalle: list[str] = []
    try:
        for concurso in cerrar_vencidas(ahora):
            resumen["convocatorias_cerradas"] += 1
            detalle.append(f"Se cerró «{concurso['nombre']}» por fecha límite.")
        for postor in marcar_interrumpidas(ahora):
            resumen["postores_con_error"] += 1
            detalle.append(f"Evaluación interrumpida: {postor['razon_social']}.")
        _evaluar_pendientes(resumen, detalle, evaluar)
    finally:
        client.table("ejecuciones_automaticas").update({
            **resumen,
            "fin": datetime.now(timezone.utc).isoformat(),
            "detalle": "\n".join(detalle) or "Sin tareas pendientes.",
        }).eq("id", ejecucion["id"]).execute()
    return {**resumen, "detalle": detalle}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    resultado = ejecutar()
    for linea in resultado.pop("detalle") or ["Sin tareas pendientes."]:
        print(linea)
    print(resultado)
