import agents.orchestrator as orquestador


def _agente(veredicto):
    def evaluar(_concurso_id, postor, criterio, embedding, revision):
        es_factor = criterio["etapa"] == "evaluacion"
        return {
            "criterio_id": criterio["id"],
            "criterio_descripcion": criterio["descripcion"],
            "etapa": criterio["etapa"],
            "obligatorio": criterio["obligatorio"],
            "puntaje_maximo": criterio.get("puntaje_maximo"),
            "veredicto": "Evaluado" if es_factor else ("Requiere revisión" if revision else veredicto),
            "puntaje": 20.0 if es_factor else None,
            "justificacion": f"embedding {embedding[0]} | postor {postor['ruc']}"
                             + (f" | observación: {revision['observacion']}" if revision else ""),
            "citas": [],
            "pasos": [{"herramienta": "buscar_evidencia", "argumentos": {}, "resumen": "segunda" if revision else "primera"}],
        }
    return evaluar


def _preparar(db_falsa, monkeypatch, tensiones_por_ronda):
    monkeypatch.setattr(orquestador, "PAUSA_ENTRE_CRITERIOS", 0)
    monkeypatch.setattr(orquestador, "embed_consultas", lambda textos: [[float(len(t))] for t in textos])
    monkeypatch.setattr(orquestador, "evaluar_criterio_legal", _agente("Cumple"))
    monkeypatch.setattr(orquestador, "evaluar_criterio_tecnico", _agente("Cumple"))
    rondas = []

    def consolidar(resultados, minimo, contexto, segunda_ronda=False):
        rondas.append([r["veredicto"] for r in resultados])
        return {"veredicto": "Califica", "puntaje": 20.0, "puntaje_maximo": 30, "justificacion": f"mínimo {minimo}",
                "citas": [], "tensiones": tensiones_por_ronda[len(rondas) - 1]}
    monkeypatch.setattr(orquestador, "consolidar_dictamen", consolidar)

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
    return postor, rondas


def test_evaluacion_completa_y_reevaluacion_sin_duplicados(db_falsa, monkeypatch):
    postor, rondas = _preparar(db_falsa, monkeypatch, [[], []])

    resultado = orquestador.evaluar_postor(postor["id"])
    orquestador.evaluar_postor(postor["id"])

    # Se evalúa en el orden de la matriz; la búsqueda usa la descripción más la forma de acreditación.
    assert [(r["agente"], r["etapa"], r["justificacion"]) for r in resultado["resultados"]] == [
        ("legal", "admision", "embedding 10.0 | postor 20131312955"),
        ("tecnico", "evaluacion", "embedding 11.0 | postor 20131312955"),
    ]
    filas = db_falsa.filas("dictamenes")
    assert sorted(f["agente"] for f in filas) == ["coordinador", "legal", "tecnico"]
    final = next(f for f in filas if f["agente"] == "coordinador")
    assert (final["veredicto"], final["puntaje_maximo"], final["justificacion"], final["pasos"]) == ("Califica", 30, "mínimo 15", [])
    assert next(f for f in filas if f["agente"] == "legal")["pasos"][0]["resumen"] == "primera"
    assert len(rondas) == 2  # una por cada evaluación, sin deliberación
    assert db_falsa.filas("postores")[0]["estado"] == "evaluado"


def test_el_coordinador_devuelve_un_criterio_a_su_agente(db_falsa, monkeypatch):
    postor, rondas = _preparar(db_falsa, monkeypatch, [
        [{"criterio": 0, "observacion": "El Anexo 2 no está firmado"}, {"criterio": None, "observacion": "general"}],
        [],
    ])

    resultado = orquestador.evaluar_postor(postor["id"])

    assert rondas == [["Cumple", "Evaluado"], ["Requiere revisión", "Evaluado"]]
    legal = resultado["resultados"][0]
    assert legal["revisado"] and legal["justificacion"].endswith("observación: El Anexo 2 no está firmado")
    assert [p["resumen"] for p in legal["pasos"]][0] == "primera"
    assert "El Coordinador devolvió el criterio («El Anexo 2 no está firmado»)" in legal["pasos"][1]["resumen"]
    assert legal["pasos"][2]["resumen"] == "segunda"
    final = next(f for f in db_falsa.filas("dictamenes") if f["agente"] == "coordinador")
    assert final["pasos"][0]["herramienta"] == "deliberacion"
