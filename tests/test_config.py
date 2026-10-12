import pytest

from config import normalizar_url_supabase


@pytest.mark.parametrize("url", [
    "https://abc.supabase.co",
    "https://abc.supabase.co/",
    "https://abc.supabase.co/rest/v1/",
    " https://abc.supabase.co/rest/v1 ",
])
def test_normalizar_url_supabase(url):
    assert normalizar_url_supabase(url) == "https://abc.supabase.co"


def test_normalizar_url_vacia():
    assert normalizar_url_supabase(None) is None
    assert normalizar_url_supabase("") == ""
