import os

# Valores ficticios antes de importar config: los tests nunca usan las claves reales del .env.
for _variable, _valor in {
    "SUPABASE_URL": "https://supabase.test",
    "SUPABASE_KEY": "clave-de-prueba",
    "GEMINI_API_KEY": "clave-de-prueba",
    "ADMIN_PASSWORD": "clave-comite",
    "EVAL_HILOS": "1",
}.items():
    os.environ[_variable] = _valor

import pytest

import db.client
from tests.fakes import SupabaseFalso


# Automática: ningún test puede tocar el Supabase real (por ejemplo, al registrar consultas a la IA).
@pytest.fixture(autouse=True)
def db_falsa(monkeypatch):
    falsa = SupabaseFalso()
    monkeypatch.setattr(db.client, "create_client", lambda *_: falsa)
    db.client.get_client.cache_clear()
    yield falsa
    db.client.get_client.cache_clear()
