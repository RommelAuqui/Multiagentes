from datetime import datetime, timedelta, timezone

import pytest

import automatizacion
import consumo

AHORA = datetime.now(timezone.utc)


def _concurso(db_falsa, nombre, estado="cerrado", automatica=True, cierre=None):
    return db_falsa.table("concursos").insert({
        "nombre": nombre, "estado": estado, "evaluacion_automatica": automatica,
        "fecha_cierre": cierre.isoformat() if cierre else None,
    }).execute().data[0]


def _postor(db_falsa, concurso, razon_social, estado="recibido", **extra):
    return db_falsa.table("postores").insert({
        "concurso_id": concurso["id"], "ruc": f"20{abs(hash(razon_social)) % 10**9:09d}",
        "razon_social": razon_social, "estado": estado, **extra,
    }).execute().data[0]


@pytest.fixture
def evaluador(db_falsa):
    """Simula evaluar_postor: comprueba que el postor quedó «evaluando» y lo marca evaluado."""
    evaluados = []

    def evaluar(postor_id):
        [postor] = [p for p in db_falsa.filas("postores") if p["id"] == postor_id]
        assert postor["estado"] == "evaluando" and postor["evaluacion_iniciada_en"]
        evaluados.append(postor["razon_social"])
        if postor["razon_social"].startswith("Falla"):
            raise RuntimeError("503 alta demanda")
        db_falsa.table("postores").update({"estado": "evaluado"}).eq("id", postor_id).execute()
    evaluar.evaluados = evaluados
    return evaluar


def test_cierra_las_convocatorias_vencidas(db_falsa, evaluador):
    vencida = _concurso(db_falsa, "Vencida", estado="abierto", cierre=AHORA - timedelta(minutes=5))
    vigente = _concurso(db_falsa, "Vigente", estado="abierto", cierre=AHORA + timedelta(days=1))
    sin_fecha = _concurso(db_falsa, "Sin fecha", estado="abierto")

    resumen = automatizacion.ejecutar(evaluador)

    estados = {c["id"]: c["estado"] for c in db_falsa.filas("concursos")}
    assert (estados[vencida["id"]], estados[vigente["id"]], estados[sin_fecha["id"]]) == ("cerrado", "abierto", "abierto")
    assert resumen["convocatorias_cerradas"] == 1 and "Se cerró «Vencida» por fecha límite." in resumen["detalle"]


def test_evalua_una_sola_vez_y_no_reintenta_los_errores(db_falsa, evaluador):
    automatica = _concurso(db_falsa, "Automática")
    manual = _concurso(db_falsa, "Manual", automatica=False)
    abierta = _concurso(db_falsa, "Abierta", estado="abierto")
    _postor(db_falsa, automatica, "Consultora A")
    _postor(db_falsa, automatica, "Falla SAC")
    _postor(db_falsa, automatica, "Ya evaluada", estado="evaluado")
    _postor(db_falsa, manual, "Consultora Manual")
    _postor(db_falsa, abierta, "Consultora Abierta")

    primera = automatizacion.ejecutar(evaluador)
    segunda = automatizacion.ejecutar(evaluador)

    assert evaluador.evaluados == ["Consultora A", "Falla SAC"]
    assert (primera["postores_evaluados"], primera["postores_con_error"]) == (1, 1)
    assert (segunda["postores_evaluados"], segunda["postores_con_error"]) == (0, 0)
    falla = next(p for p in db_falsa.filas("postores") if p["razon_social"] == "Falla SAC")
    assert falla["estado"] == "error" and "503 alta demanda" in falla["error_evaluacion"]
    ejecuciones = db_falsa.filas("ejecuciones_automaticas")
    assert len(ejecuciones) == 2 and ejecuciones[0]["fin"] and "Evaluado: Consultora A (Automática)." in ejecuciones[0]["detalle"]
    assert ejecuciones[1]["detalle"] == "Sin tareas pendientes."


def test_se_pausa_al_llegar_al_limite_diario(db_falsa, evaluador, monkeypatch):
    monkeypatch.setattr(consumo, "LIMITE_DIARIO_CONSULTAS", 30)
    concurso = _concurso(db_falsa, "Automática")
    db_falsa.table("criterios").insert([{"concurso_id": concurso["id"], "descripcion": f"c{n}"} for n in range(4)]).execute()
    _postor(db_falsa, concurso, "Consultora A")
    # 5 consultas hechas hoy + 24 estimadas para 4 criterios = 29: cabe uno; con 10 ya no.
    db_falsa.table("consultas_ia").insert([{"agente": "legal", "modelo": "m", "prompt": "p"}] * 5).execute()

    assert automatizacion.ejecutar(evaluador)["postores_evaluados"] == 1

    _postor(db_falsa, concurso, "Consultora B")
    db_falsa.table("consultas_ia").insert([{"agente": "legal", "modelo": "m", "prompt": "p"}] * 5).execute()
    resumen = automatizacion.ejecutar(evaluador)

    assert resumen["pausada_por_limite"] and resumen["postores_evaluados"] == 0
    assert evaluador.evaluados == ["Consultora A"]
    assert "superaría el límite diario de 30 consultas" in resumen["detalle"][0]
    assert next(p for p in db_falsa.filas("postores") if p["razon_social"] == "Consultora B")["estado"] == "recibido"


def test_una_evaluacion_interrumpida_queda_con_error(db_falsa, evaluador):
    concurso = _concurso(db_falsa, "Automática")
    _postor(db_falsa, concurso, "Colgada", estado="evaluando",
            evaluacion_iniciada_en=(AHORA - timedelta(hours=2)).isoformat())
    _postor(db_falsa, concurso, "En curso", estado="evaluando",
            evaluacion_iniciada_en=(AHORA - timedelta(minutes=10)).isoformat())

    resumen = automatizacion.ejecutar(evaluador)

    estados = {p["razon_social"]: p["estado"] for p in db_falsa.filas("postores")}
    assert estados == {"Colgada": "error", "En curso": "evaluando"}
    assert resumen["postores_con_error"] == 1 and evaluador.evaluados == []


def test_consumo_de_hoy_en_hora_de_lima(db_falsa):
    # 03:00 UTC del 12 de octubre son las 22:00 del 11 en Lima: el día empieza a las 05:00 UTC del 11.
    ahora = datetime(2026, 10, 12, 3, 0, tzinfo=timezone.utc)
    assert consumo.inicio_del_dia(ahora) == datetime(2026, 10, 11, 5, 0, tzinfo=timezone.utc)

    db_falsa.table("consultas_ia").insert([
        {"agente": "legal", "concurso_id": "C1", "postor_id": "P1", "tokens_entrada": 1000, "tokens_salida": 50},
        {"agente": "tecnico", "concurso_id": "C1", "postor_id": "P1", "tokens_entrada": 2000, "tokens_salida": 100},
        {"agente": "lector", "concurso_id": "C1", "postor_id": None, "tokens_entrada": 500, "tokens_salida": 500},
    ]).execute()
    db_falsa.filas("consultas_ia")[0]["created_at"] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()

    assert consumo.consultas_de_hoy() == 2
    assert consumo.consumo_por_postor("C1") == {"P1": {"consultas": 2, "tokens": 3150}}
