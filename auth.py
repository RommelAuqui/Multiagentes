import streamlit as st

from config import ADMIN_PASSWORD


def acceso_autorizado() -> bool:
    if st.session_state.get("admin_autenticado"):
        return True

    if not ADMIN_PASSWORD:
        st.error("ADMIN_PASSWORD no está configurado. Defínelo en .env o en los Secrets de Streamlit antes de usar este portal.")
        return False

    st.subheader("Acceso restringido — Portal del Comité")
    clave = st.text_input("Contraseña del comité", type="password")
    if st.button("Ingresar"):
        if clave == ADMIN_PASSWORD:
            st.session_state["admin_autenticado"] = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta.")

    return False
