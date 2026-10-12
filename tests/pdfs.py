import zlib


def imagen_gris(ancho: int, alto: int) -> dict:
    return {"datos": zlib.compress(bytes(ancho * alto)), "ancho": ancho, "alto": alto,
            "filtro": "FlateDecode", "color": "DeviceGray"}


def imagen_jpeg(datos: bytes, ancho: int, alto: int) -> dict:
    return {"datos": datos, "ancho": ancho, "alto": alto, "filtro": "DCTDecode", "color": "DeviceRGB"}


def _escapar(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def construir_pdf(paginas: list[dict]) -> bytes:
    """Cada página es {"lineas": [...], "imagen": imagen_gris(...) | imagen_jpeg(...) | None}."""
    objetos: list[bytes] = [b"", b""]  # 1: catálogo y 2: árbol de páginas, se completan al final

    def agregar(objeto: bytes) -> int:
        objetos.append(objeto)
        return len(objetos)

    fuente = agregar(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    hojas = []
    for pagina in paginas:
        recursos, dibujo = f"/Font << /F1 {fuente} 0 R >>", ""
        if imagen := pagina.get("imagen"):
            numero = agregar(
                f"<< /Type /XObject /Subtype /Image /Width {imagen['ancho']} /Height {imagen['alto']} "
                f"/ColorSpace /{imagen['color']} /BitsPerComponent 8 /Filter /{imagen['filtro']} "
                f"/Length {len(imagen['datos'])} >>\nstream\n".encode() + imagen["datos"] + b"\nendstream"
            )
            recursos += f" /XObject << /Im1 {numero} 0 R >>"
            dibujo = "q 495 0 0 600 50 100 cm /Im1 Do Q "
        lineas = " ".join(f"({_escapar(linea)}) '" for linea in pagina.get("lineas", []))
        flujo = (dibujo + (f"BT /F1 10 Tf 14 TL 50 800 Td {lineas} ET" if lineas else "")).encode("cp1252")
        contenido = agregar(b"<< /Length %d >>\nstream\n" % len(flujo) + flujo + b"\nendstream")
        hojas.append(agregar(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << {recursos} >> "
            f"/Contents {contenido} 0 R >>".encode()
        ))

    objetos[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objetos[1] = f"<< /Type /Pages /Kids [{' '.join(f'{h} 0 R' for h in hojas)}] /Count {len(hojas)} >>".encode()

    salida, posiciones = bytearray(b"%PDF-1.4\n"), []
    for numero, objeto in enumerate(objetos, start=1):
        posiciones.append(len(salida))
        salida += f"{numero} 0 obj\n".encode() + objeto + b"\nendobj\n"
    inicio_xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    salida += b"".join(f"{p:010d} 00000 n \n".encode() for p in posiciones)
    salida += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{inicio_xref}\n%%EOF".encode()
    return bytes(salida)
