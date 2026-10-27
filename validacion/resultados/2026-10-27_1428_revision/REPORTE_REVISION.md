# Validación del módulo de revisión de Bases

- **Fecha:** 27/10/2026 14:48
- **Modo:** reglas fijas y agente revisor
- **Convocatorias:** 3 · rondas revisadas: 6

## Resumen

| Métrica | Valor |
|---|---|
| Fallas sembradas detectadas (exhaustividad) | — (0 de 0) |
| Hallazgos que eran fallas reales (precisión) | 0,0 % |
| Falsos positivos | 1 |
| Verificaciones no verificadas | 0 |
| Consultas a Gemini | 281 |
| Tokens | 739 663 |
| Tiempo total | 1177 s |

## Por convocatoria y ronda

| Convocatoria | Ronda | Esperadas | Detectadas | No detectadas | De más |
|---|---|---|---|---|---|
| convocatoria_1_supervision_agua_potable | A | — | — | — | — |
| convocatoria_1_supervision_agua_potable | B | — | — | — | — |
| convocatoria_2_expediente_centro_de_salud | A | — | — | — | — |
| convocatoria_2_expediente_centro_de_salud | B | — | — | — | — |
| convocatoria_3_plan_desarrollo_urbano | A | — | COH-06 | — | COH-06 |
| convocatoria_3_plan_desarrollo_urbano | B | — | — | — | — |

## Hallazgos de más (posibles falsos positivos)

- **convocatoria_3_plan_desarrollo_urbano, ronda A, COH-06** (agente): El Capítulo III de las Bases incluye requisitos de calificación y redacción detallada que no figuran de forma idéntica en el requerimiento original del área usuaria.

Un hallazgo de más no siempre es un error: puede ser una falla real que no se sembró a propósito. Cada uno se revisa a mano antes de reportarlo como falso positivo.
