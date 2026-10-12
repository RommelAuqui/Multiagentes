import agents.extractor as extractor
from agents.gemini_client import ContextoIA

CONTEXTO = ContextoIA("extractor", "C1")


def test_matriz_con_las_tres_etapas_de_las_bases(monkeypatch):
    monkeypatch.setattr(extractor, "generar_json", lambda _modelo, _prompt, _contexto: {
        "puntaje_minimo": "80",
        "criterios": [
            {"etapa": "Admisión", "tipo": "Legal", "descripcion": " Declaración jurada (Anexo 2) ",
             "acreditacion": "Anexo 2", "referencia": "", "obligatorio": "si"},
            {"etapa": "calificacion", "tipo": "tecnico", "descripcion": "Jefe de supervisión con 5 años",
             "acreditacion": "Copia de contratos y constancias", "obligatorio": False, "puntaje_maximo": 30},
            {"etapa": "Factor de evaluación", "tipo": "", "descripcion": "Experiencia del postor",
             "puntaje_maximo": "60", "asignacion_puntaje": "M >= 3 veces el valor: 60 puntos", "obligatorio": True},
            {"etapa": "economica", "tipo": "tecnico", "descripcion": "Precio"},
            {"etapa": "evaluacion", "descripcion": ""},
            "texto suelto",
        ],
    })

    matriz = extractor.extraer_criterios("bases", CONTEXTO)

    assert matriz.puntaje_minimo == 80
    assert matriz.criterios == [
        {"etapa": "admision", "tipo": "legal", "descripcion": "Declaración jurada (Anexo 2)", "acreditacion": "Anexo 2",
         "referencia": None, "obligatorio": True, "puntaje_maximo": None, "asignacion_puntaje": None},
        # Un requisito de calificación no tiene puntaje, aunque el modelo invente uno.
        {"etapa": "calificacion", "tipo": "tecnico", "descripcion": "Jefe de supervisión con 5 años",
         "acreditacion": "Copia de contratos y constancias", "referencia": None, "obligatorio": False,
         "puntaje_maximo": None, "asignacion_puntaje": None},
        {"etapa": "evaluacion", "tipo": "tecnico", "descripcion": "Experiencia del postor", "acreditacion": None,
         "referencia": None, "obligatorio": False, "puntaje_maximo": 60.0,
         "asignacion_puntaje": "M >= 3 veces el valor: 60 puntos"},
    ]


def test_extraer_criterios_sin_lista(monkeypatch):
    monkeypatch.setattr(extractor, "generar_json", lambda _modelo, _prompt, _contexto: {"otra_cosa": 1})
    matriz = extractor.extraer_criterios("bases", CONTEXTO)
    assert matriz.criterios == [] and matriz.puntaje_minimo is None


def test_extraer_criterios_recorta_bases_muy_largas(monkeypatch):
    prompts = []
    monkeypatch.setattr(extractor, "generar_json", lambda _modelo, prompt, _contexto: prompts.append(prompt) or {})
    extractor.extraer_criterios("§" * (extractor.MAX_CARACTERES_BASES + 500), CONTEXTO)
    assert prompts[0].count("§") == extractor.MAX_CARACTERES_BASES


def _factor(nombre, puntos):
    return {"etapa": "evaluacion", "tipo": "tecnico", "descripcion": nombre, "puntaje_maximo": puntos}


def test_si_los_factores_no_suman_el_total_el_extractor_se_corrige(monkeypatch):
    respuestas = iter([
        {"puntaje_total": 100, "criterios": [_factor("A", 55), _factor("B", 45), _factor("B duplicado", 45)]},
        {"puntaje_total": 100, "criterios": [_factor("A", 55), _factor("B", 45)]},
    ])
    prompts = []
    monkeypatch.setattr(extractor, "generar_json", lambda _m, prompt, _c: prompts.append(prompt) or next(respuestas))

    matriz = extractor.extraer_criterios("bases", CONTEXTO)

    assert matriz.cuadra and matriz.suma_factores == 100 and len(prompts) == 2
    assert "suma de los puntajes máximos de los factores de evaluación fue 145" in prompts[1]
    assert "- B duplicado (45 puntos)" in prompts[1]


def test_si_la_correccion_empeora_se_conserva_el_primer_intento(monkeypatch):
    respuestas = iter([
        {"puntaje_total": 100, "criterios": [_factor("A", 55), _factor("B", 40)]},
        {"criterios": [_factor("A", 55)]},
    ])
    monkeypatch.setattr(extractor, "generar_json", lambda *_: next(respuestas))

    matriz = extractor.extraer_criterios("bases", CONTEXTO)

    assert matriz.suma_factores == 95 and not matriz.cuadra


def test_sin_total_declarado_no_se_corrige(monkeypatch):
    llamadas = []
    monkeypatch.setattr(extractor, "generar_json", lambda *_: llamadas.append(1) or {"criterios": [_factor("A", 30)]})
    assert extractor.extraer_criterios("bases", CONTEXTO).cuadra and len(llamadas) == 1
