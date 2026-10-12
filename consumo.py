"""Consumo de la IA, a partir del registro de consultas (tabla consultas_ia)."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from config import LIMITE_DIARIO_CONSULTAS
from db.client import get_client

ZONA_HORARIA = ZoneInfo("America/Lima")
# Con agentes autónomos, un criterio toma en promedio entre 4 y 5 consultas (búsquedas, cálculos y
# conclusión), más las del Coordinador. Se estima por lo alto para no pasarse del límite a mitad de un postor.
CONSULTAS_POR_CRITERIO = 5
CONSULTAS_DEL_COORDINADOR = 4


def inicio_del_dia(ahora: datetime | None = None) -> datetime:
    local = (ahora or datetime.now(timezone.utc)).astimezone(ZONA_HORARIA)
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


def consultas_de_hoy(ahora: datetime | None = None) -> int:
    respuesta = (
        get_client().table("consultas_ia")
        .select("id", count="exact")
        .gte("created_at", inicio_del_dia(ahora).isoformat())
        .limit(1)
        .execute()
    )
    return respuesta.count or 0


def estimar_consultas(criterios: int) -> int:
    return criterios * CONSULTAS_POR_CRITERIO + CONSULTAS_DEL_COORDINADOR


def hay_cupo(criterios: int, ahora: datetime | None = None) -> bool:
    return consultas_de_hoy(ahora) + estimar_consultas(criterios) <= LIMITE_DIARIO_CONSULTAS


def consumo_por_postor(concurso_id: str) -> dict[str, dict]:
    filas = (
        get_client().table("consultas_ia")
        .select("postor_id,tokens_entrada,tokens_salida")
        .eq("concurso_id", concurso_id)
        .execute()
        .data
    )
    consumo: dict[str, dict] = {}
    for fila in filas:
        if fila.get("postor_id"):
            actual = consumo.setdefault(fila["postor_id"], {"consultas": 0, "tokens": 0})
            actual["consultas"] += 1
            actual["tokens"] += (fila.get("tokens_entrada") or 0) + (fila.get("tokens_salida") or 0)
    return consumo
