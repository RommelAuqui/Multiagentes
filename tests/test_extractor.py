import agents.extractor as extractor


def test_extraer_criterios_normaliza_y_descarta_invalidos(monkeypatch):
    monkeypatch.setattr(extractor, "generar_json", lambda _modelo, _prompt: {"criterios": [
        {"tipo": "Legal", "descripcion": " Declaración jurada ", "referencia": "", "obligatorio": "no"},
        {"tipo": "tecnico", "descripcion": "Experiencia de 5 años", "referencia": "Pág. 12"},
        {"tipo": "economico", "descripcion": "Precio"},
        {"tipo": "tecnico", "descripcion": ""},
        "texto suelto",
    ]})

    assert extractor.extraer_criterios("bases") == [
        {"tipo": "legal", "descripcion": "Declaración jurada", "referencia": None, "obligatorio": False},
        {"tipo": "tecnico", "descripcion": "Experiencia de 5 años", "referencia": "Pág. 12", "obligatorio": True},
    ]


def test_extraer_criterios_sin_lista(monkeypatch):
    monkeypatch.setattr(extractor, "generar_json", lambda _modelo, _prompt: {"otra_cosa": 1})
    assert extractor.extraer_criterios("bases") == []


def test_extraer_criterios_recorta_bases_muy_largas(monkeypatch):
    prompts = []
    monkeypatch.setattr(extractor, "generar_json", lambda _modelo, prompt: prompts.append(prompt) or {})
    extractor.extraer_criterios("§" * (extractor.MAX_CARACTERES_BASES + 500))
    assert prompts[0].count("§") == extractor.MAX_CARACTERES_BASES
