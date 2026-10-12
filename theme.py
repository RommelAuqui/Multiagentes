import streamlit as st

CSS_BASE = """
<style>
html, body, [class*="css"] {
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
}

html, body {
    background-color: var(--ml-bg);
}

.stApp {
    background-color: var(--ml-bg);
    color: var(--ml-text);
}

[data-testid="stSelectboxVirtualDropdown"] {
    background-color: var(--ml-card-bg) !important;
    border: 1px solid var(--ml-border);
    border-radius: 8px;
}

[data-testid="stSelectboxVirtualDropdown"] [role="option"] {
    background-color: var(--ml-card-bg) !important;
    color: var(--ml-text) !important;
}

[data-testid="stSelectboxVirtualDropdown"] [role="option"]:hover,
[data-testid="stSelectboxVirtualDropdown"] [aria-selected="true"] {
    background-color: var(--ml-bg) !important;
    color: var(--ml-text) !important;
}

header[data-testid="stHeader"] {
    background-color: var(--ml-bg);
}

div[data-testid="stToolbar"] {
    background-color: var(--ml-bg);
}

div[data-testid="stDecoration"] {
    background-image: none;
    background-color: var(--ml-accent);
}

div[data-testid="stSidebarCollapsedControl"],
div[data-testid="stSidebarCollapsedControl"] button {
    background-color: var(--ml-bg);
    color: var(--ml-text);
}

header[data-testid="stHeader"] svg,
div[data-testid="stToolbar"] svg,
div[data-testid="stSidebarCollapsedControl"] svg {
    fill: var(--ml-text);
}

section[data-testid="stSidebar"] {
    background-color: var(--ml-sidebar-bg);
    border-right: 1px solid var(--ml-border);
}

h1, h2, h3 {
    color: var(--ml-text);
    font-weight: 700;
}

h1 {
    border-bottom: 3px solid var(--ml-accent);
    padding-bottom: 0.4rem;
    margin-bottom: 1.2rem;
}

p, span, label, div {
    color: var(--ml-text);
}

.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
    background-color: var(--ml-accent);
    color: #ffffff !important;
    border: none;
    border-radius: 8px;
    padding: 0.5rem 1.1rem;
    font-weight: 600;
    transition: background-color 0.15s ease-in-out;
}

.stButton > button *, .stDownloadButton > button *, .stFormSubmitButton > button * {
    color: #ffffff !important;
}

.stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {
    background-color: var(--ml-accent-hover);
    color: #ffffff !important;
}

.stTextInput input, .stTextArea textarea, .stNumberInput input {
    background-color: var(--ml-card-bg);
    color: var(--ml-text);
    border: 1px solid var(--ml-border);
    border-radius: 6px;
}

.stTextInput > div, .stTextArea > div,
[data-testid="stTextInputRootElement"],
[data-testid="stNumberInputContainer"] {
    background-color: var(--ml-card-bg) !important;
    border-color: var(--ml-border) !important;
}

.stTextInput button, .stTextInput button svg {
    background-color: transparent;
    fill: var(--ml-text-muted);
    color: var(--ml-text-muted);
}

div[data-baseweb="select"] > div {
    background-color: var(--ml-card-bg);
    border-color: var(--ml-border);
    color: var(--ml-text);
}

[data-testid="stExpander"] {
    background-color: var(--ml-card-bg);
    border: 1px solid var(--ml-border);
    border-radius: 10px;
}

[data-testid="stFileUploaderDropzone"] {
    background-color: var(--ml-card-bg) !important;
    border: 1px dashed var(--ml-border) !important;
}

[data-testid="stFileUploaderDropzone"] button {
    background-color: var(--ml-bg) !important;
    color: var(--ml-text) !important;
    border: 1px solid var(--ml-border) !important;
}

[data-testid="stFileUploaderDropzoneInstructions"] span,
[data-testid="stFileUploaderDropzoneInstructions"] small {
    color: var(--ml-text-muted) !important;
}

[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: var(--ml-card-bg);
    border-color: var(--ml-border) !important;
    border-radius: 12px;
}

table {
    color: var(--ml-text) !important;
    border-color: var(--ml-border) !important;
}

.stTable table thead th {
    background-color: var(--ml-sidebar-bg) !important;
    color: var(--ml-text) !important;
}

.stTable table tbody td, .stTable table tbody th {
    background-color: var(--ml-card-bg) !important;
    color: var(--ml-text) !important;
    border-color: var(--ml-border) !important;
}

.ml-card {
    background-color: var(--ml-card-bg);
    border: 1px solid var(--ml-border);
    border-radius: 12px;
    padding: 1rem 1.3rem;
    margin-bottom: 0.8rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.ml-card-title {
    font-weight: 700;
    font-size: 1.05rem;
}

.ml-card-sub {
    color: var(--ml-text-muted);
    font-size: 0.85rem;
}

.ml-badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 999px;
    font-size: 0.8rem;
    font-weight: 700;
}

.ml-badge-cumple {
    background-color: var(--ml-success-bg);
    color: var(--ml-success-text);
}

.ml-badge-no-cumple {
    background-color: var(--ml-danger-bg);
    color: var(--ml-danger-text);
}

.ml-badge-pendiente {
    background-color: var(--ml-warning-bg);
    color: var(--ml-warning-text);
}
</style>
"""

CSS_CLARO = """
<style>
:root {
    --ml-bg: #f5f7fa;
    --ml-sidebar-bg: #ffffff;
    --ml-card-bg: #ffffff;
    --ml-text: #1a1d27;
    --ml-text-muted: #6b7280;
    --ml-border: #e2e5eb;
    --ml-accent: #2563eb;
    --ml-accent-hover: #1d4ed8;
    --ml-success-bg: #dcfce7;
    --ml-success-text: #15803d;
    --ml-danger-bg: #fee2e2;
    --ml-danger-text: #b91c1c;
    --ml-warning-bg: #fef3c7;
    --ml-warning-text: #92400e;
}
</style>
"""

CSS_OSCURO = """
<style>
:root {
    --ml-bg: #0f1117;
    --ml-sidebar-bg: #171a23;
    --ml-card-bg: #1b1f2a;
    --ml-text: #e5e7eb;
    --ml-text-muted: #9ca3af;
    --ml-border: #2b2f3b;
    --ml-accent: #3b82f6;
    --ml-accent-hover: #60a5fa;
    --ml-success-bg: #14321f;
    --ml-success-text: #4ade80;
    --ml-danger-bg: #3a1414;
    --ml-danger-text: #f87171;
    --ml-warning-bg: #3a2c0f;
    --ml-warning-text: #fbbf24;
}
</style>
"""


def aplicar_tema():
    if "modo_oscuro" not in st.session_state:
        st.session_state["modo_oscuro"] = False

    with st.sidebar:
        st.toggle("🌙 Modo oscuro", key="modo_oscuro")

    st.markdown(CSS_OSCURO if st.session_state["modo_oscuro"] else CSS_CLARO, unsafe_allow_html=True)
    st.markdown(CSS_BASE, unsafe_allow_html=True)


def tarjeta_postor_html(razon_social: str, ruc: str) -> str:
    return f"""
    <div class="ml-card-title">{razon_social}</div>
    <div class="ml-card-sub">RUC {ruc}</div>
    """


def badge_html(texto: str, clase: str) -> str:
    return f'<span class="ml-badge {clase}">{texto}</span>'
