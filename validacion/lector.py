"""Validación del lector: fidelidad de la transcripción de páginas escaneadas.

Toma páginas digitales de unas Bases reales (su texto es la respuesta correcta), las convierte en
imágenes con aspecto de escaneo (giro, desenfoque, ruido y compresión JPEG) y compara la
transcripción de Gemini con el texto original mediante CER y WER. Si Tesseract está instalado
(pytesseract y el programa tesseract), también lo mide sobre las mismas imágenes.

Uso:
    python -m validacion.lector RUTA_BASES.pdf --paginas 19-25,54-58
Requiere pypdfium2 (requirements-dev.txt) para convertir las páginas en imágenes.
"""
import argparse
import random
import re
import unicodedata
from datetime import datetime
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from agents.gemini_client import ContextoIA
from rag.pdf_extract import extraer_paginas
from validacion.pdfs import construir_pdf, imagen_jpeg

CARPETA_RESULTADOS = Path(__file__).parent / "resultados"


def distancia_edicion(a, b) -> int:
    """Levenshtein: mínimo de inserciones, borrados y sustituciones para pasar de a a b."""
    if len(a) < len(b):
        a, b = b, a
    anterior = list(range(len(b) + 1))
    for i, elemento_a in enumerate(a, start=1):
        actual = [i]
        for j, elemento_b in enumerate(b, start=1):
            actual.append(min(anterior[j] + 1, actual[j - 1] + 1, anterior[j - 1] + (elemento_a != elemento_b)))
        anterior = actual
    return anterior[-1]


def normalizar(texto: str) -> str:
    # Se descarta el formato que agrega el lector (tablas Markdown, negritas) y los saltos de línea.
    texto = unicodedata.normalize("NFC", texto)
    texto = re.sub(r"^\s*\|?\s*:?-{3,}.*$", " ", texto, flags=re.MULTILINE)
    texto = re.sub(r"[|*#_`]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def tasas_de_error(correcto: str, obtenido: str) -> dict:
    correcto, obtenido = normalizar(correcto), normalizar(obtenido)
    palabras_correctas, palabras_obtenidas = correcto.split(), obtenido.split()
    return {
        "cer": round(distancia_edicion(correcto, obtenido) / max(len(correcto), 1), 4),
        "wer": round(distancia_edicion(palabras_correctas, palabras_obtenidas) / max(len(palabras_correctas), 1), 4),
        "caracteres": len(correcto),
    }


def escanear(imagen, semilla: int):
    """Simula un escaneo: leve giro, desenfoque, ruido y compresión JPEG."""
    from PIL import ImageFilter

    imagen = imagen.convert("RGB").rotate(0.8, fillcolor="white").filter(ImageFilter.GaussianBlur(0.6))
    pixeles, (ancho, alto), azar = imagen.load(), imagen.size, random.Random(semilla)
    for _ in range(ancho * alto // 60):
        pixeles[azar.randrange(ancho), azar.randrange(alto)] = (azar.randint(120, 200),) * 3
    buffer = BytesIO()
    imagen.save(buffer, "JPEG", quality=60)
    return buffer.getvalue(), imagen


def paginas_escaneadas(contenido: bytes, numeros: list[int]) -> list[tuple[int, bytes, object]]:
    import pypdfium2

    documento = pypdfium2.PdfDocument(contenido)
    escaneos = []
    for numero in numeros:
        imagen = documento[numero - 1].render(scale=2).to_pil()  # ~144 ppp, como un escaneo de oficina
        jpeg, degradada = escanear(imagen, semilla=numero)
        escaneos.append((numero, jpeg, degradada))
    return escaneos


def _tesseract():
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return pytesseract
    except Exception:
        return None


def _rangos(texto: str) -> list[int]:
    numeros = []
    for parte in texto.split(","):
        inicio, _, fin = parte.partition("-")
        numeros += list(range(int(inicio), int(fin or inicio) + 1))
    return numeros


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf")
    parser.add_argument("--paginas", default="19-25,54-58")
    args = parser.parse_args()

    contenido = Path(args.pdf).read_bytes()
    reader = PdfReader(BytesIO(contenido))
    numeros = [n for n in _rangos(args.paginas) if len((reader.pages[n - 1].extract_text() or "").strip()) > 200]
    escaneos = paginas_escaneadas(contenido, numeros)
    pdf = construir_pdf([{"imagen": imagen_jpeg(jpeg, img.width, img.height)} for _, jpeg, img in escaneos])
    leidas = {p["pagina"]: p["texto"] for p in extraer_paginas(pdf, ContextoIA("validacion")).paginas}
    tesseract = _tesseract()

    filas = []
    for posicion, (numero, _, imagen) in enumerate(escaneos, start=1):
        correcto = reader.pages[numero - 1].extract_text() or ""
        fila = {"pagina": numero, "gemini": tasas_de_error(correcto, leidas.get(posicion, ""))}
        if tesseract:
            fila["tesseract"] = tasas_de_error(correcto, tesseract.image_to_string(imagen, lang="spa"))
        filas.append(fila)
        print(f"Página {numero}: CER Gemini {fila['gemini']['cer']:.2%}"
              + (f" · Tesseract {fila['tesseract']['cer']:.2%}" if tesseract else ""))

    motores = ["gemini", *(["tesseract"] if tesseract else [])]

    def porcentaje(valor):
        return f"{valor * 100:.2f} %".replace(".", ",")

    def promedio(motor, metrica):
        # Ponderado por caracteres: una página corta no pesa lo mismo que una llena.
        total = sum(f[motor]["caracteres"] for f in filas)
        return sum(f[motor][metrica] * f[motor]["caracteres"] for f in filas) / total

    encabezados = ["Página", "Caracteres", *(f"CER {m.capitalize()}" for m in motores), *(f"WER {m.capitalize()}" for m in motores)]
    lineas = ["| " + " | ".join(encabezados) + " |", "|" + "---|" * len(encabezados)]
    for f in filas:
        lineas.append("| " + " | ".join([str(f["pagina"]), str(f["gemini"]["caracteres"]),
                                         *(porcentaje(f[m]["cer"]) for m in motores),
                                         *(porcentaje(f[m]["wer"]) for m in motores)]) + " |")
    lineas.append("| **Promedio ponderado** | " + str(sum(f["gemini"]["caracteres"] for f in filas)) + " | "
                  + " | ".join([*(porcentaje(promedio(m, "cer")) for m in motores),
                                *(porcentaje(promedio(m, "wer")) for m in motores)]) + " |")
    nota_tesseract = "" if tesseract else (
        "\n\nTesseract no está instalado en este equipo, así que solo se midió Gemini. Para compararlo, instala "
        "Tesseract con el idioma español y `pip install pytesseract`, y vuelve a ejecutar este script.")
    reporte = (f"# Validación del lector de páginas escaneadas\n\n- **Fecha:** {datetime.now():%d/%m/%Y %H:%M}\n"
               f"- **Documento:** {Path(args.pdf).name}\n- **Páginas:** {len(filas)}\n\n"
               "Cada página digital se convirtió en imagen con aspecto de escaneo (giro de 0,8°, desenfoque, ruido "
               "y JPEG al 60 %) y se comparó la transcripción con el texto original del PDF.\n\n"
               "- **CER**: proporción de caracteres mal leídos (inserciones, borrados y sustituciones).\n"
               "- **WER**: lo mismo, contado por palabras.\n\n"
               "El texto «original» es el que extrae pypdf del PDF digital, que también tiene pequeñas "
               "imperfecciones (espacios partidos, encabezados): las tasas son una cota superior del error real.\n\n"
               + "\n".join(lineas) + nota_tesseract + "\n")
    carpeta = CARPETA_RESULTADOS / f"{datetime.now():%Y-%m-%d_%H%M}_lector"
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "REPORTE_LECTOR.md").write_text(reporte, encoding="utf-8")
    print(f"Reporte: {carpeta / 'REPORTE_LECTOR.md'}")


if __name__ == "__main__":
    main()
