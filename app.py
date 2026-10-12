import streamlit as st

from auth import acceso_autorizado
from config import configuracion_faltante
from theme import aplicar_tema
from views import comite, postor

st.set_page_config(page_title="Comité Evaluador Sintético", layout="wide", page_icon="🏛️")

aplicar_tema()

faltantes = configuracion_faltante()
if faltantes:
    st.error(
        f"Faltan variables de configuración: {', '.join(faltantes)}. "
        "Defínelas en .env o en los Secrets de Streamlit."
    )
    st.stop()

st.sidebar.title("Comité Evaluador Sintético")
vista = st.sidebar.radio("Selecciona tu portal", ["Comité / Administrador", "Postor / Participante"])

if vista == "Comité / Administrador":
    if acceso_autorizado():
        comite.render()
else:
    postor.render()
