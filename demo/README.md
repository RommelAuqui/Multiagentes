# Convocatorias de demostración

Tres concursos públicos **ficticios**, cada uno con sus Bases Integradas y tres ofertas: una que cumple
todo y dos que fallan por motivos distintos. Sirven para mostrar el sistema de punta a punta sin usar
documentos reales. Entidades, empresas, personas, RUC, DNI y montos son inventados (los RUC usan el
prefijo 2098, no asignado por SUNAT, con dígito verificador válido).

## Cómo usarlas

1. **Comité:** crea la convocatoria y sube las `Bases Integradas … .pdf` de la carpeta. Revisa la matriz
   que propone el Agente Extractor y publícala.
2. **Postor:** por cada oferta, registra la razón social y el RUC de la tabla y sube los 4 PDF de su carpeta.
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

El detalle por criterio (veredicto o puntaje esperado de cada uno) está en `datos.py`, en el campo
`esperado` de cada oferta.

## Regenerar los PDF

```bash
pip install -r requirements-dev.txt
python -m demo.generar
```
