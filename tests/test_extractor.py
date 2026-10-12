import agents.extractor as extractor
from agents.gemini_client import ContextoIA

CONTEXTO = ContextoIA("extractor")


def test_extraer_criterios_normaliza_y_descarta_invalidos(monkeypatch):
    monkeypatch.setattr(extractor, "generar_json", lambda _modelo, _prompt, _contexto: {"criterios": [
        {"tipo": "Legal", "descripcion": " Declaración jurada ", "referencia": "", "obligatorio": "no"},
        {"tipo": "tecnico", "descripcion": "Experiencia de 5 años", "referencia": "Pág. 12"},
        {"tipo": "economico", "descripcion": "Precio"},
        {"tipo": "tecnico", "descripcion": ""},
        "texto suelto",
    ]})

    assert extractor.extraer_criterios("bases", CONTEXTO) == [
        {"tipo": "legal", "descripcion": "Declaración jurada", "referencia": None, "obligatorio": False},
        {"tipo": "tecnico", "descripcion": "Experiencia de 5 años", "referencia": "Pág. 12", "obligatorio": True},
    ]


def test_extraer_criterios_sin_lista(monkeypatch):
    monkeypatch.setattr(extractor, "generar_json", lambda _modelo, _prompt, _contexto: {"otra_cosa": 1})
    assert extractor.extraer_criterios("bases", CONTEXTO) == []


def test_extraer_criterios_recorta_bases_muy_largas(monkeypatch):
    prompts = []
    monkeypatch.setattr(extractor, "generar_json", lambda _modelo, prompt, _contexto: prompts.append(prompt) or {})
    extractor.extraer_criterios("§" * (extractor.MAX_CARACTERES_BASES + 500), CONTEXTO)
    assert prompts[0].count("§") == extractor.MAX_CARACTERES_BASES
