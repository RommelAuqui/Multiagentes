import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()


def get_secret(key, default=None):
    # Primero las variables de entorno (el .env en local, o las de los tests); luego los Secrets de Streamlit.
    if os.environ.get(key):
        return os.environ[key]
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return default


def normalizar_url_supabase(url: str | None) -> str | None:
    # El panel de Supabase también muestra la URL de la API REST (.../rest/v1/); el cliente necesita la base.
    if not url:
        return url
    return url.strip().rstrip("/").removesuffix("/rest/v1")


SUPABASE_URL = normalizar_url_supabase(get_secret("SUPABASE_URL"))
SUPABASE_KEY = get_secret("SUPABASE_KEY")
GEMINI_API_KEY = get_secret("GEMINI_API_KEY")
ADMIN_PASSWORD = get_secret("ADMIN_PASSWORD")
STORAGE_BUCKET = get_secret("STORAGE_BUCKET", "licitaciones")
LLM_MODEL = get_secret("LLM_MODEL", "gemini-3.5-flash-lite")
EMBEDDING_MODEL = get_secret("EMBEDDING_MODEL", "gemini-embedding-001")
EMBEDDING_DIMENSIONS = int(get_secret("EMBEDDING_DIMENSIONS", 768))
OCR_IDIOMA = get_secret("OCR_IDIOMA", "spa")
OCR_DPI = int(get_secret("OCR_DPI", 200))
TESSERACT_CMD = get_secret("TESSERACT_CMD")
POPPLER_PATH = get_secret("POPPLER_PATH")
EVAL_HILOS = max(1, int(get_secret("EVAL_HILOS", 1)))


def configuracion_faltante() -> list[str]:
    obligatorias = {
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_KEY": SUPABASE_KEY,
        "GEMINI_API_KEY": GEMINI_API_KEY,
    }
    return [nombre for nombre, valor in obligatorias.items() if not valor]
