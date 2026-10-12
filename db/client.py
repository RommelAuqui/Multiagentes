from functools import cache

from supabase import Client, create_client

from config import SUPABASE_KEY, SUPABASE_URL


# Un único cliente por proceso; a diferencia de st.cache_resource, se puede usar desde hilos.
@cache
def get_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)
