import pytest

from validaciones import ruc_valido


@pytest.mark.parametrize("ruc", [
    "20131312955",  # RUC de la SUNAT
    "10123456781",  # persona natural con DNI 12345678
])
def test_ruc_valido(ruc):
    assert ruc_valido(ruc)


@pytest.mark.parametrize("ruc", [
    "20131312954",  # dígito verificador incorrecto
    "2013131295",  # 10 dígitos
    "201313129550",  # 12 dígitos
    "30131312955",  # prefijo inexistente
    "2013131295a",
    "２0131312955",  # dígito Unicode de ancho completo
    "",
])
def test_ruc_invalido(ruc):
    assert not ruc_valido(ruc)
