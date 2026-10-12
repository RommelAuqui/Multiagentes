import agents.orchestrator as orquestador


def _evaluador(veredicto):
    def evaluar(_concurso_id, _postor_id, criterio, embedding):
        return {
            "criterio_id": criterio["id"],
            "criterio_descripcion": criterio["descripcion"],
            "veredicto": veredicto,
            "justificacion": f"embedding {embedding[0]}",
            "citas": [],
        }
    return evaluar


def test_reevaluar_reemplaza_los_dictamenes(db_falsa, monkeypatch):
    monkeypatch.setattr(orquestador, "PAUSA_ENTRE_CRITERIOS", 0)
    monkeypatch.setattr(orquestador, "embed_consultas", lambda textos: [[float(len(t))] for t in textos])
    monkeypatch.setattr(orquestador, "evaluar_criterio_legal", _evaluador("Cumple"))
    monkeypatch.setattr(orquestador, "evaluar_criterio_tecnico", _evaluador("No Cumple"))
    monkeypatch.setattr(orquestador, "consolidar_dictamen", lambda *_: {
        "veredicto": "Cumple", "puntaje": 0.0, "justificacion": "x", "citas": [],
    })

    concurso = db_falsa.table("concursos").insert({"nombre": "C", "estado": "abierto"}).execute().data[0]
    postor = db_falsa.table("postores").insert({
        "concurso_id": concurso["id"], "ruc": "20131312955", "razon_social": "P", "estado": "recibido",
    }).execute().data[0]
    db_falsa.table("criterios").insert([
        {"concurso_id": concurso["id"], "tipo": "tecnico", "descripcion": "tec", "obligatorio": True},
        {"concurso_id": concurso["id"], "tipo": "legal", "descripcion": "legal1", "obligatorio": True},
    ]).execute()

    resultado = orquestador.evaluar_postor(postor["id"])
    orquestador.evaluar_postor(postor["id"])

    # Cada criterio recibe el embedding de su propia descripción, aunque legal y técnico se mezclen.
    assert [r["justificacion"] for r in resultado["resultados_legal"]] == ["embedding 6.0"]
    assert [r["justificacion"] for r in resultado["resultados_tecnico"]] == ["embedding 3.0"]
    assert sorted(d["agente"] for d in db_falsa.filas("dictamenes")) == ["coordinador", "legal", "tecnico"]
    assert db_falsa.filas("postores")[0]["estado"] == "evaluado"
