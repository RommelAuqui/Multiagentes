import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()


def get_secret(key, default=None):
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, default)


SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_KEY")
GEMINI_API_KEY = get_secret("GEMINI_API_KEY")
ADMIN_PASSWORD = get_secret("ADMIN_PASSWORD")
STORAGE_BUCKET = get_secret("STORAGE_BUCKET", "licitaciones")
LLM_MODEL = get_secret("LLM_MODEL", "gemini-flash-lite-latest")
EMBEDDING_MODEL = get_secret("EMBEDDING_MODEL", "gemini-embedding-001")
EMBEDDING_DIMENSIONS = int(get_secret("EMBEDDING_DIMENSIONS", 768))
OCR_IDIOMA = get_secret("OCR_IDIOMA", "spa")
OCR_DPI = int(get_secret("OCR_DPI", 200))
TESSERACT_CMD = get_secret("TESSERACT_CMD")
POPPLER_PATH = get_secret("POPPLER_PATH")
