from agents.respuestas import normalizar_citas, normalizar_veredicto

FRAGMENTOS = [
    {"origen": "propuesta", "pagina": 3},
    {"origen": "cv", "pagina": 3},
    {"origen": "cv", "pagina": 5},
]


def test_veredicto_de_requisitos():
    assert normalizar_veredicto(" cumple ", "calificacion") == "Cumple"
    assert normalizar_veredicto("NO CUMPLE", "admision") == "No Cumple"
    assert normalizar_veredicto("requiere revision", "calificacion") == "Requiere revisión"
    assert normalizar_veredicto("No aplica", "admision") == "No aplica"


def test_una_respuesta_ambigua_queda_para_el_comite():
    assert normalizar_veredicto("Cumple parcialmente", "calificacion") == "Requiere revisión"
    assert normalizar_veredicto(None, "admision") == "Requiere revisión"
    assert normalizar_veredicto("Cumple", "evaluacion") == "Requiere revisión"
    assert normalizar_veredicto("evaluado", "evaluacion") == "Evaluado"


def test_cita_con_documento_y_pagina_validos():
    citas = [{"documento": "Propuesta", "pagina": 3, "extracto": " texto "}]
    assert normalizar_citas(citas, FRAGMENTOS) == [
        {"documento": "propuesta", "pagina": 3, "extracto": "texto"}
    ]


def test_cita_sin_documento_se_resuelve_si_la_pagina_es_unica():
    assert normalizar_citas([{"pagina": "5"}], FRAGMENTOS) == [
        {"documento": "cv", "pagina": 5, "extracto": ""}
    ]


def test_se_descartan_citas_ambiguas_inventadas_o_malformadas():
    citas = [{"pagina": 3}, {"pagina": 99}, {"pagina": "x"}, "texto suelto"]
    assert normalizar_citas(citas, FRAGMENTOS) == []
    assert normalizar_citas("no es lista", FRAGMENTOS) == []
