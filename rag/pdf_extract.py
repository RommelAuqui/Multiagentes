from dataclasses import dataclass, field
from io import BytesIO

from pypdf import PdfReader

from agents.gemini_client import ContextoIA
from rag.lector import leer_paginas_con_ia

MIN_CARACTERES_TEXTO = 50
# Desde ~700×700 px se trata de un escaneo pegado en la página; los logos y firmas suelen ser menores.
MIN_PIXELES_IMAGEN = 500_000


@dataclass
class ResultadoExtraccion:
    total_paginas: int = 0
    paginas: list[dict] = field(default_factory=list)
    paginas_ia: list[int] = field(default_factory=list)
    paginas_imagen_sin_leer: list[int] = field(default_factory=list)
    paginas_sin_texto: list[int] = field(default_factory=list)
    error_lectura: str | None = None


def _tiene_imagen_grande(recursos, profundidad: int = 0) -> bool:
    if recursos is None or profundidad > 3:
        return False
    xobjects = recursos.get_object().get("/XObject")
    if xobjects is None:
        return False
    for referencia in xobjects.get_object().values():
        objeto = referencia.get_object()
        subtipo = objeto.get("/Subtype")
        if subtipo == "/Image":
            if int(objeto.get("/Width", 0)) * int(objeto.get("/Height", 0)) >= MIN_PIXELES_IMAGEN:
                return True
        elif subtipo == "/Form" and _tiene_imagen_grande(objeto.get("/Resources"), profundidad + 1):
            return True
    return False


def _necesita_lectura_con_ia(pagina, texto: str) -> bool:
    if len(texto) < MIN_CARACTERES_TEXTO:
        return True
    try:
        return _tiene_imagen_grande(pagina.get("/Resources"))
    except Exception:
        return False


def extraer_paginas(contenido: bytes, contexto: ContextoIA) -> ResultadoExtraccion:
    reader = PdfReader(BytesIO(contenido))
    textos = [(pagina.extract_text() or "").strip() for pagina in reader.pages]
    por_leer = [
        numero for numero, (pagina, texto) in enumerate(zip(reader.pages, textos), start=1)
        if _necesita_lectura_con_ia(pagina, texto)
    ]

    resultado = ResultadoExtraccion(total_paginas=len(reader.pages))
    leidas = {}
    if por_leer:
        leidas, resultado.error_lectura = leer_paginas_con_ia(reader, por_leer, contexto)

    for numero, texto in enumerate(textos, start=1):
        texto_ia = leidas.get(numero)
        if texto_ia:
            # La transcripción incluye el texto de la página; si salió más corta, se conservan ambas.
            texto = texto_ia if len(texto_ia) >= len(texto) else f"{texto}\n\n{texto_ia}"
            resultado.paginas_ia.append(numero)
        elif numero in por_leer and texto:
            resultado.paginas_imagen_sin_leer.append(numero)

        if texto:
            resultado.paginas.append({"pagina": numero, "texto": texto, "ia": bool(texto_ia)})
        else:
            resultado.paginas_sin_texto.append(numero)

    return resultado


def dividir_en_fragmentos(paginas: list[dict], max_caracteres: int = 1500) -> list[dict]:
    fragmentos = []
    for pagina in paginas:
        texto = pagina["texto"]
        for inicio in range(0, len(texto), max_caracteres):
            fragmentos.append({
                "pagina": pagina["pagina"],
                "contenido": texto[inicio:inicio + max_caracteres],
            })
    return fragmentos


def texto_completo(paginas: list[dict]) -> str:
    return "\n\n".join(f"[Página {p['pagina']}]\n{p['texto']}" for p in paginas)
