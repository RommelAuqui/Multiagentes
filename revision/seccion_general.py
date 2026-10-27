"""FOR-01: compara la Sección general de las Bases con la de las Bases estándar oficiales.

La Sección general «no debe ser modificada en ningún extremo, bajo sanción de nulidad». Su texto oficial se
toma de las Bases estándar de la Directiva N.° 0005-2025-EF/54.01 (modificada por la R. D. N.° 0001-2026-EF/54.01)
y se guarda en revision/plantillas/*.json. Para regenerarlo desde los Word oficiales:

    python -m revision.seccion_general
"""
import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import cache
from pathlib import Path

CARPETA = Path(__file__).parent / "plantillas"
PLANTILLAS = {
    "consultoria_obra": "Bases estándar del concurso público para consultoría de obra",
    "consultoria_general": "Bases estándar del concurso público para consultoría en general",
}
FUENTE = "Directiva N.° 0005-2025-EF/54.01, modificada por la R. D. N.° 0001-2026-EF/54.01"
MAXIMO_CAMBIOS = 8
CONTEXTO = 4  # palabras que se muestran antes y después de cada cambio
# Numeración que la plantilla genera automáticamente y en el PDF aparece como texto (1.1., a), ii)) o
# llamadas a notas al pie.
_ENUMERACION = re.compile(r"^(?:\d{1,2}|[a-z]|[ivx]{1,4})$")


@dataclass
class Cambio:
    plantilla: str  # lo que dice la plantilla (vacío si se agregó texto)
    bases: str  # lo que dicen las Bases (vacío si se eliminó texto)
    pagina: int | None


# ---------- Texto oficial ----------

def extraer_de_docx(ruta: Path) -> dict:
    """Bloques de la Sección general del Word oficial: párrafos y tablas en orden, y las notas al pie."""
    from docx import Document
    from docx.oxml.ns import qn

    documento = Document(ruta)

    def texto(elemento) -> str:
        return " ".join("".join(t.text or "" for t in elemento.iter(qn("w:t"))).split())

    bloques, referencias, dentro = [], [], False
    for elemento in documento.element.body.iterchildren():
        if elemento.tag == qn("w:p"):
            parrafo = texto(elemento)
            if parrafo.upper() == "SECCIÓN GENERAL":
                dentro = True
            elif parrafo.upper() == "SECCIÓN ESPECÍFICA":
                break
            if dentro and parrafo:
                bloques.append({"texto": parrafo})
                referencias += [r.get(qn("w:id")) for r in elemento.iter(qn("w:footnoteReference"))]
        elif elemento.tag == qn("w:tbl") and dentro:
            filas = [[texto(celda) for celda in fila.iter(qn("w:tc"))] for fila in elemento.iter(qn("w:tr"))]
            bloques.append({"tabla": filas})
    notas = {}
    for parte in documento.part.package.parts:
        if parte.partname.endswith("/footnotes.xml"):
            from docx.oxml import parse_xml
            for nota in parse_xml(parte.blob).iter(qn("w:footnote")):
                notas[nota.get(qn("w:id"))] = texto(nota)
    return {"bloques": bloques, "notas": [notas[r] for r in referencias if notas.get(r)]}


@cache
def plantilla(nombre: str) -> dict:
    return json.loads((CARPETA / f"{nombre}.json").read_text(encoding="utf-8"))


def textos(datos: dict) -> list[str]:
    """La Sección general en el orden en que se lee: cada párrafo y cada celda de las tablas."""
    salida = []
    for bloque in datos["bloques"]:
        if "texto" in bloque:
            salida.append(bloque["texto"])
        else:
            salida += [celda for fila in bloque["tabla"] for celda in fila if celda]
    return salida


def texto_oficial(nombre: str) -> str:
    """La Sección general oficial como texto, seguida del título de la Sección específica (para las pruebas)."""
    return "\n".join(textos(plantilla(nombre))) + "\nSECCIÓN ESPECÍFICA\nCONDICIONES ESPECIALES DEL PROCEDIMIENTO"


# ---------- Comparación ----------

def _sin_tildes(palabra: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", palabra.lower()) if unicodedata.category(c) != "Mn")


def _palabras(texto: str) -> list[str]:
    return re.findall(r"\w+", texto)


def _lineas_repetidas(paginas: list[dict]) -> set[str]:
    """Encabezados y pies de página: líneas que se repiten en la mayoría de las páginas."""
    conteo: dict[str, int] = {}
    for pagina in paginas:
        for linea in {re.sub(r"\d+", "#", l.strip()) for l in (pagina.get("texto") or "").splitlines()}:
            if linea:
                conteo[linea] = conteo.get(linea, 0) + 1
    minimo = max(3, len(paginas) // 2)
    return {linea for linea, veces in conteo.items() if veces >= minimo}


def _palabras_de_las_bases(paginas: list[dict]) -> tuple[list[str], list[int]]:
    repetidas = _lineas_repetidas(paginas)
    palabras, numeros = [], []
    for pagina in paginas:
        for linea in (pagina.get("texto") or "").splitlines():
            if re.sub(r"\d+", "#", linea.strip()) in repetidas:
                continue
            nuevas = _palabras(linea)
            palabras += nuevas
            numeros += [pagina["pagina"]] * len(nuevas)
    return palabras, numeros


def _buscar(claves: list[str], frase: tuple[str, ...], desde: int = 0) -> list[int]:
    n = len(frase)
    return [i for i in range(desde, len(claves) - n + 1) if tuple(claves[i:i + n]) == frase]


def ubicar(claves: list[str]) -> tuple[int, int] | None:
    """Inicio y fin de la Sección general: de «SECCIÓN GENERAL / DISPOSICIONES COMUNES» a «SECCIÓN ESPECÍFICA /
    CONDICIONES ESPECIALES». Si un índice repite los títulos, se toma el tramo más largo."""
    inicios = [i for i in _buscar(claves, ("seccion", "general")) if "disposiciones" in claves[i + 2:i + 5]]
    finales = [i for i in _buscar(claves, ("seccion", "especifica")) if "condiciones" in claves[i + 2:i + 5]]
    tramos = [(i, min(f for f in finales if f > i)) for i in inicios if any(f > i for f in finales)]
    return max(tramos, key=lambda t: t[1] - t[0]) if tramos else None


def tipo_de_bases(claves: list[str]) -> str | None:
    """Qué Bases estándar corresponden, según el título de la Sección general."""
    titulo = " ".join(claves[:20])
    if "abreviado" in titulo:
        return None
    if "consultoria de obra" in titulo:
        return "consultoria_obra"
    if "consultoria en general" in titulo:
        return "consultoria_general"
    return None


def _repetibles(datos: dict) -> list[str]:
    """Texto que el PDF puede repetir o mover sin que sea un cambio: las notas al pie (van al final de la página)
    y los encabezados de las tablas (se repiten cuando la tabla sigue en otra página)."""
    partes = list(datos["notas"]) + [" ".join(b["tabla"][0]) for b in datos["bloques"] if "tabla" in b]
    return sorted((" ".join(_sin_tildes(p) for p in _palabras(t)) for t in partes), key=len, reverse=True)


def _solo_repetibles(palabras: list[str], repetibles: list[str]) -> bool:
    """Si el texto agregado es solo notas al pie, encabezados de tabla o numeración (una nota puede quedar
    partida entre dos páginas: basta que el trozo sea parte de una nota)."""
    # Sin espacios: el PDF puede cortar una palabra larga (un enlace) en dos.
    partes = [parte.replace(" ", "") for parte in repetibles]
    texto = "".join(palabras)
    for parte in partes:
        texto = texto.replace(parte, " ")
    resto = [trozo.strip("0123456789") for trozo in texto.split()]  # quedan las llamadas a las notas
    return all(not trozo or any(trozo in parte for parte in partes) for trozo in resto)


def _es_menor(antes: list[str], despues: list[str], repetibles: list[str]) -> bool:
    """Diferencias que no son cambios de contenido: numeración, llamadas o textos de notas al pie, encabezados
    de tabla repetidos, palabras cortadas por un salto de línea y errores de lectura de una sola palabra."""
    if all(_ENUMERACION.match(p) for p in antes + despues):
        return True
    if "".join(antes) == "".join(despues):
        return True
    if not antes and _solo_repetibles(despues, repetibles):
        return True
    if len(antes) == len(despues) == 1 and min(len(antes[0]), len(despues[0])) >= 5:
        return SequenceMatcher(None, antes[0], despues[0]).ratio() >= 0.8
    return False


def _fragmento(palabras: list[str], desde: int, hasta: int) -> str:
    inicio, fin = max(0, desde - CONTEXTO), min(len(palabras), hasta + CONTEXTO)
    texto = " ".join(palabras[inicio:fin])
    if len(texto) > 220:
        texto = texto[:220].rsplit(" ", 1)[0] + " …"
    return ("… " if inicio else "") + texto + (" …" if fin < len(palabras) else "")


ANCLA = 6  # palabras seguidas que, si aparecen una sola vez en cada texto, los alinean
TRAMO_MAXIMO = 4_000_000  # tramos sin anclas más grandes que esto se toman como reemplazados enteros


def _anclas(a: list[str], b: list[str]) -> list[tuple[int, int]]:
    """Frases de ANCLA palabras que aparecen una sola vez en cada texto, en el mismo orden en ambos
    (subsecuencia creciente más larga, como el «patience diff»)."""
    def unicas(palabras):
        vistas: dict[tuple, int | None] = {}
        for i in range(len(palabras) - ANCLA + 1):
            frase = tuple(palabras[i:i + ANCLA])
            vistas[frase] = None if frase in vistas else i
        return {f: i for f, i in vistas.items() if i is not None}

    en_b = unicas(b)
    pares = sorted((i, en_b[f]) for f, i in unicas(a).items() if f in en_b)
    # Subsecuencia creciente más larga en j.
    from bisect import bisect_left
    colas, indices, previo = [], [], [-1] * len(pares)
    for k, (_, j) in enumerate(pares):
        pos = bisect_left(colas, j)
        if pos:
            previo[k] = indices[pos - 1]
        if pos == len(colas):
            colas.append(j), indices.append(k)
        else:
            colas[pos], indices[pos] = j, k
    salida, k = [], indices[-1] if indices else -1
    while k >= 0:
        salida.append(pares[k])
        k = previo[k]
    return salida[::-1]


def _diferencias(a: list[str], b: list[str]) -> list[tuple[int, int, int, int]]:
    """Tramos distintos (i1, i2, j1, j2) entre las dos listas de palabras."""
    salida, pa, pb = [], 0, 0

    def tramo(i, j):
        if i == pa and j == pb:
            return
        if (i - pa) * (j - pb) > TRAMO_MAXIMO:
            salida.append((pa, i, pb, j))
            return
        for operacion, i1, i2, j1, j2 in SequenceMatcher(None, a[pa:i], b[pb:j], autojunk=False).get_opcodes():
            if operacion != "equal":
                salida.append((pa + i1, pa + i2, pb + j1, pb + j2))

    for i, j in _anclas(a, b):
        if i < pa or j < pb:
            continue  # ya cubierta por la ancla anterior
        tramo(i, j)
        while i < len(a) and j < len(b) and a[i] == b[j]:
            i, j = i + 1, j + 1
        pa, pb = i, j
    tramo(len(a), len(b))
    return salida


def comparar(datos: dict, palabras: list[str], paginas: list[int]) -> list[Cambio]:
    """Cambios de la Sección general de las Bases (palabras ya recortadas a esa sección) frente a la plantilla."""
    oficial = [p for t in textos(datos) for p in _palabras(t)]
    claves_oficial = [_sin_tildes(p) for p in oficial]
    claves = [_sin_tildes(p) for p in palabras]
    repetibles = _repetibles(datos)

    tramos = []
    for i1, i2, j1, j2 in _diferencias(claves_oficial, claves):
        if _es_menor(claves_oficial[i1:i2], claves[j1:j2], repetibles):
            continue
        # Se unen los cambios separados por pocas palabras: son un mismo cambio de redacción.
        if tramos and i1 - tramos[-1][1] <= 3 and j1 - tramos[-1][3] <= 3:
            tramos[-1] = (tramos[-1][0], i2, tramos[-1][2], j2)
        else:
            tramos.append((i1, i2, j1, j2))
    return [Cambio(_fragmento(oficial, i1, i2) if i2 > i1 else "",
                   _fragmento(palabras, j1, j2) if j2 > j1 else "",
                   paginas[min(j1, len(paginas) - 1)] if paginas else None)
            for i1, i2, j1, j2 in tramos]


def revisar(paginas: list[dict]) -> tuple[str, str, list[Cambio], list[int]]:
    """(estado, descripción, cambios, páginas de la sección) para FOR-01."""
    palabras, numeros = _palabras_de_las_bases(paginas)
    claves = [_sin_tildes(p) for p in palabras]
    tramo = ubicar(claves)
    if not tramo:
        return ("falla", "No se encontró la Sección general de las Bases estándar («SECCIÓN GENERAL – DISPOSICIONES "
                         "COMUNES…»): las Bases no siguen la estructura obligatoria.", [], [])
    inicio, fin = tramo
    nombre = tipo_de_bases(claves[inicio:fin])
    if nombre is None:
        return ("no_verificado", "No se pudo verificar: no se cuenta con las Bases estándar oficiales del tipo de "
                                 "procedimiento de estas Bases (solo concurso público para consultoría de obra y para "
                                 "consultoría en general).", [], [])
    cambios = comparar(plantilla(nombre), palabras[inicio:fin], numeros[inicio:fin])
    referencia = f"{PLANTILLAS[nombre]} ({FUENTE})"
    if not cambios:
        return ("cumple", f"La Sección general coincide con la de las {referencia}.", [], [])
    detalle = "; ".join(_describir(c) for c in cambios[:MAXIMO_CAMBIOS])
    mas = f" y {len(cambios) - MAXIMO_CAMBIOS} más" if len(cambios) > MAXIMO_CAMBIOS else ""
    return ("falla", f"La Sección general fue modificada: difiere de las {referencia} en {len(cambios)} punto(s). "
                     f"{detalle}{mas}.", cambios, sorted({c.pagina for c in cambios if c.pagina}))


def _describir(cambio: Cambio) -> str:
    pagina = f"pág. {cambio.pagina}: " if cambio.pagina else ""
    if not cambio.bases:
        return f"{pagina}se eliminó «{cambio.plantilla}»"
    if not cambio.plantilla:
        return f"{pagina}se agregó «{cambio.bases}»"
    return f"{pagina}dice «{cambio.bases}» donde la plantilla dice «{cambio.plantilla}»"


if __name__ == "__main__":
    for nombre in PLANTILLAS:
        datos = extraer_de_docx(CARPETA / f"{nombre}.docx")
        (CARPETA / f"{nombre}.json").write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{nombre}: {len(datos['bloques'])} bloques, {len(datos['notas'])} notas al pie")
