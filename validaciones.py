import re

PESOS_RUC = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
PREFIJOS_RUC = ("10", "15", "16", "17", "20")


def ruc_valido(ruc: str) -> bool:
    # Formato SUNAT: 11 dígitos, prefijo de tipo de contribuyente y dígito verificador módulo 11.
    if not re.fullmatch(r"[0-9]{11}", ruc) or ruc[:2] not in PREFIJOS_RUC:
        return False
    suma = sum(int(digito) * peso for digito, peso in zip(ruc, PESOS_RUC))
    return (11 - suma % 11) % 10 == int(ruc[10])
