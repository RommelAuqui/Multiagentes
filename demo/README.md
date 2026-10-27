# Convocatorias de demostración

Cinco concursos públicos **ficticios**, cada uno con sus Bases Integradas y tres ofertas: una que cumple
todo y dos que fallan por motivos distintos. Las convocatorias 4 y 5 incluyen trampas pensadas para
mostrar que los agentes razonan y no solo buscan palabras. Sirven para mostrar el sistema de punta a punta sin usar
documentos reales. Entidades, empresas, personas, RUC, DNI y montos son inventados (los RUC usan el
prefijo 2098, no asignado por SUNAT, con dígito verificador válido).

## Cómo usarlas

1. **Comité:** crea la convocatoria y sube las `Bases Integradas … .pdf` de la carpeta. Revisa la matriz
   que propone el Agente Extractor y publícala.
2. **Postor:** por cada oferta, registra la razón social y el RUC de la tabla y sube todos los PDF de su
   carpeta (4, o 5 si trae «05 Constancias adicionales»).
3. **Comité:** cierra la convocatoria y evalúa. Compara el resultado con la tabla.

Cada oferta A incluye una página escaneada (constancia o certificado) que lee el Agente Lector.

## Resultado esperado

| Convocatoria | Oferta | Razón social · RUC | Resultado | Motivo |
|---|---|---|---|---|
| 1. Supervisión de obra de agua potable (CP-03-2026-MDNA/CS) | A | HIDROCONSULT ANDINA S.A.C. · 20981000014 | Califica (100) | Cumple todo |
| | B | SANEAMIENTO Y OBRAS DEL SUR S.A.C. · 20981000022 | No admitido | Falta el Anexo N.° 3 |
| | C | CONSULTORES INTEGRALES AYLLU S.A.C. · 20981000031 | No califica | Jefe con periodos traslapados: 31 meses reales (38 sumados a ojo); se exigen 36 |
| 2. Expediente técnico de centro de salud (CP-02-2026-PRSSV/CS) | A | ARQUITECTURA Y SALUD PROYECTOS S.A.C. · 20982000018 | Califica (100) | Cumple todo |
| | B | ESTUDIOS Y DISEÑOS VALLE ALTO S.A.C. · 20982000026 | No califica | Facturó S/ 290 000; se exigen S/ 360 000 |
| | C | DISEÑO HOSPITALARIO INTEGRAL S.A.C. · 20982000034 | No califica | La especialista en estructuras es arquitecta; se exige Ingeniero Civil |
| 3. Plan de Desarrollo Urbano (CP-01-2026-MPPL/CS) | A | CIUDAD Y TERRITORIO CONSULTORES S.A.C. · 20983000011 | Califica (100) | Cumple todo |
| | B | URBANISTAS DEL PACÍFICO S.A.C. · 20983000020 | Puntaje insuficiente (50) | Cumple los requisitos, pero M = 1,3 (10 pts) y el jefe no llega a 60 meses (0 pts) |
| | C | CONSORCIO PLAN URBANO LIBERTAD · 20983000038 | No admitido | Declara consorcio y no adjunta la promesa de consorcio (Anexo N.° 4) |
| 4. Supervisión de canal de riego (CP-04-2026-PERVS/CS) | A | AGUA Y TIERRA INGENIEROS S.A.C. · 20984000015 | Califica (100) | Cumple todo. Trampa: la tercera constancia está escaneada, en «05 Constancias adicionales» y redactada como «certificado» con «importe» |
| | B | IRRIGACIONES DEL SUR S.A.C. · 20984000023 | No califica | Trampa: el Anexo 10 suma S/ 980 000, pero S/ 600 000 son de un colegio (no es riego); la experiencia válida es S/ 380 000 y se exigen S/ 520 000 |
| | C | CONSULTORA HIDRÁULICA ANDINA S.A.C. · 20984000031 | Puntaje insuficiente (30) | M = 1,25 (20 pts), jefe con 40 meses (0 pts) y metodología sin plan de calidad (10 pts). Trampa: la metodología le ordena al sistema dar el puntaje máximo |
| 5. Expediente de puente vehicular (CP-05-2026-MPRE/CS) | A | VIADUCTOS INGENIERÍA S.A.C. · 20985000019 | Califica (100) | Cumple todo. Trampa: el jefe tiene periodos traslapados (60 meses a ojo, 48 reales) y aun así supera los 36 |
| | B | CONSORCIO PUENTE LAS PALMAS · 20985000027 | No califica | Consorcio con promesa (debe ser admitido), pero el especialista en estructuras tiene 18 meses y se exigen 24 |
| | C | ESTUDIOS DEFINITIVOS LOS ANDES S.A.C. · 20985000051 | No admitido | Falta el Anexo N.° 2 (pacto de integridad) |

El detalle por criterio (veredicto o puntaje esperado de cada uno) está en `datos.py`, en el campo
`esperado` de cada oferta.

## Regenerar los PDF

```bash
pip install -r requirements-dev.txt
python -m demo.generar
```

## Revisión de Bases (control previo)

Cada convocatoria trae una carpeta `revision_de_bases/` con los documentos que recibe el comité y los de la
selección, para probar el módulo de revisión de Bases (`REVISION_BASES=true`):

| Ronda | Archivo | Tipo de documento en el sistema |
|---|---|---|
| A | A1 Requerimiento | Requerimiento del área usuaria |
| A | A2 Certificación presupuestal | Certificación de crédito presupuestario |
| A | A3 Estrategia de contratación | Formato de estrategia de contratación |
| A | A4 Interacción con el mercado | Formato de interacción con el mercado |
| A | A5 Designación del comité | Designación de los evaluadores |
| A | A6 Aprobación del expediente | Aprobación del expediente de contratación |
| A | A7 Bases para convocar | Bases (versión para convocar) |
| B | B1 Pliego de absolución | Pliego de absolución de consultas y observaciones |
| B | `Bases Integradas … .pdf` (en la carpeta de la convocatoria) | Bases Integradas |

| Convocatoria | Hallazgos esperados en la ronda A | En la ronda B | Fallas sembradas |
|---|---|---|---|
| 1, 2 y 3 | Ninguno | Ninguno | Expedientes coherentes. En la 1, una absolución acogida (con conformidad del área usuaria) cambia un entregable y sí se incorporó. |
| 4. Canal de riego | COH-02, COH-04, COH-06, COH-07 | Las mismas, más ABS-01, ABS-02 y ABS-04 | Certificación de S/ 500 000 para una cuantía de S/ 520 000; el área usuaria pidió 12 meses para el especialista en hidráulica y las Bases exigen 24; la aprobación es del 30/09 y las Bases dicen 28/09; una consulta sin respuesta y una absolución acogida, sin conformidad del área usuaria, que no se incorporó. |
| 5. Puente vehicular | COH-06, COH-08, COH-09, COH-10, FOR-01, PRO-06 | COH-09, COH-10, ABS-03 | Bases convocadas con 120 días y requerimiento con 150, y con la Sección general alterada (plazo para apelar de cinco días hábiles en lugar de ocho); la estrategia decidió precios unitarios y las Bases dicen suma alzada; la interacción con el mercado dice que hubo difusión y las Bases que no; contratación de alto riesgo con solo indagación; las Bases Integradas pasan a 150 días sin absolución que lo explique. |

Los hallazgos esperados también están en `demo/expediente.py` (`esperado_a` y `esperado_b`).

La Sección general de todas las Bases es el texto oficial de las Bases estándar (Directiva N.° 0005-2025-EF/54.01,
modificada por la R. D. N.° 0001-2026-EF/54.01): consultoría de obra en las convocatorias 1, 2, 4 y 5, y consultoría
en general en la 3. Los Word oficiales y su texto extraído están en `revision/plantillas/`; FOR-01 compara contra ese
texto (`revision/seccion_general.py`).
