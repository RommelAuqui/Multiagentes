import agents.orchestrator as orquestador


def _evaluador(veredicto):
    def evaluar(_concurso_id, _postor_id, criterio, embedding):
        es_factor = criterio["etapa"] == "evaluacion"
        return {
            "criterio_id": criterio["id"],
            "criterio_descripcion": criterio["descripcion"],
            "etapa": criterio["etapa"],
            "obligatorio": criterio["obligatorio"],
            "puntaje_maximo": criterio.get("puntaje_maximo"),
            "veredicto": "Evaluado" if es_factor else veredicto,
            "puntaje": 20.0 if es_factor else None,
            "justificacion": f"embedding {embedding[0]}",
            "citas": [],
        }
    return evaluar


def test_evaluacion_completa_y_reevaluacion_sin_duplicados(db_falsa, monkeypatch):
    monkeypatch.setattr(orquestador, "PAUSA_ENTRE_CRITERIOS", 0)
    monkeypatch.setattr(orquestador, "embed_consultas", lambda textos: [[float(len(t))] for t in textos])
    monkeypatch.setattr(orquestador, "evaluar_criterio_legal", _evaluador("Cumple"))
    monkeypatch.setattr(orquestador, "evaluar_criterio_tecnico", _evaluador("Cumple"))
    monkeypatch.setattr(orquestador, "consolidar_dictamen", lambda resultados, minimo, contexto: {
        "veredicto": "Califica", "puntaje": 20.0, "puntaje_maximo": 30, "justificacion": f"mínimo {minimo}", "citas": [],
    })

    concurso = db_falsa.table("concursos").insert({"nombre": "C", "estado": "abierto", "puntaje_minimo": 15}).execute().data[0]
    postor = db_falsa.table("postores").insert({
        "concurso_id": concurso["id"], "ruc": "20131312955", "razon_social": "P", "estado": "recibido",
    }).execute().data[0]
    db_falsa.table("criterios").insert([
        {"concurso_id": concurso["id"], "etapa": "evaluacion", "tipo": "tecnico", "descripcion": "Metodología",
         "obligatorio": False, "puntaje_maximo": 30, "orden": 1},
        {"concurso_id": concurso["id"], "etapa": "admision", "tipo": "legal", "descripcion": "Anexo 2",
         "acreditacion": "DJ", "obligatorio": True, "orden": 0},
    ]).execute()

    resultado = orquestador.evaluar_postor(postor["id"])
    orquestador.evaluar_postor(postor["id"])

    # Se evalúa en el orden de la matriz, y la búsqueda usa la descripción más la forma de acreditación.
    assert [(r["agente"], r["etapa"], r["justificacion"]) for r in resultado["resultados"]] == [
        ("legal", "admision", "embedding 10.0"), ("tecnico", "evaluacion", "embedding 11.0"),
    ]
    filas = db_falsa.filas("dictamenes")
    assert sorted(f["agente"] for f in filas) == ["coordinador", "legal", "tecnico"]
    final = next(f for f in filas if f["agente"] == "coordinador")
    assert (final["veredicto"], final["puntaje_maximo"], final["justificacion"]) == ("Califica", 30, "mínimo 15")
    assert db_falsa.filas("postores")[0]["estado"] == "evaluado"
