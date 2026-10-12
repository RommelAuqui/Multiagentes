import streamlit as st

from auth import acceso_autorizado
from theme import aplicar_tema
from views import comite, postor

st.set_page_config(page_title="Comité Evaluador Sintético", layout="wide", page_icon="🏛️")

aplicar_tema()

st.sidebar.title("Comité Evaluador Sintético")
vista = st.sidebar.radio("Selecciona tu portal", ["Comité / Administrador", "Postor / Participante"])

if vista == "Comité / Administrador":
    if acceso_autorizado():
        comite.render()
else:
    postor.render()
