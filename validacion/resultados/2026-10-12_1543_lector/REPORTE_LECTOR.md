# Validación del lector de páginas escaneadas

- **Fecha:** 12/10/2026 15:43
- **Documento:** 6+BASES+INTEGRADAS+CPCON+02+SUPER+META+IV_20260513_093301_576.pdf
- **Páginas:** 12

Cada página digital se convirtió en imagen con aspecto de escaneo (giro de 0,8°, desenfoque, ruido y JPEG al 60 %) y se comparó la transcripción con el texto original del PDF.

- **CER**: proporción de caracteres mal leídos (inserciones, borrados y sustituciones).
- **WER**: lo mismo, contado por palabras.
- **Cobertura**: proporción de las palabras originales que aparecen en la transcripción, sin importar el orden. Si el CER es alto pero la cobertura también, la diferencia es de orden (típico en tablas), no de lectura.

El texto «original» es el que extrae pypdf del PDF digital, que también tiene pequeñas imperfecciones (espacios partidos, encabezados): las tasas son una cota superior del error real.

| Página | Caracteres | CER Gemini | WER Gemini | Cobertura Gemini |
|---|---|---|---|---|
| 19 | 2362 | 20,24 % | 26,29 % | 91,24 % |
| 20 | 1093 | 8,60 % | 11,73 % | 96,91 % |
| 21 | 3142 | 3,31 % | 5,81 % | 97,42 % |
| 22 | 3181 | 3,77 % | 9,36 % | 93,82 % |
| 23 | 2827 | 3,40 % | 5,20 % | 97,96 % |
| 24 | 4117 | 1,58 % | 4,21 % | 95,79 % |
| 25 | 2935 | 2,52 % | 7,28 % | 92,72 % |
| 54 | 3221 | 2,20 % | 5,04 % | 94,96 % |
| 55 | 3204 | 1,78 % | 3,78 % | 96,22 % |
| 56 | 2558 | 1,95 % | 3,79 % | 96,21 % |
| 57 | 3350 | 3,94 % | 5,87 % | 96,87 % |
| 58 | 1746 | 12,89 % | 17,10 % | 97,40 % |
| **Promedio ponderado** | 33736 | 4,64 % | 7,82 % | 95,57 % |

Tesseract no está instalado en este equipo, así que solo se midió Gemini. Para compararlo, instala Tesseract con el idioma español y `pip install pytesseract`, y vuelve a ejecutar este script.
