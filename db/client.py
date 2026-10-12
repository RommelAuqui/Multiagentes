import streamlit as st
from supabase import Client, create_client

from config import SUPABASE_KEY, SUPABASE_URL


@st.cache_resource
def get_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)
