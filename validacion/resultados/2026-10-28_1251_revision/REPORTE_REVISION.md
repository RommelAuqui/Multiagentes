# Validación del módulo de revisión de Bases

- **Fecha:** 28/10/2026 13:57
- **Modo:** reglas fijas y agente revisor
- **Convocatorias:** 3 · rondas revisadas: 6

## Resumen

| Métrica | Valor |
|---|---|
| Fallas sembradas detectadas (exhaustividad) | 100,0 % (20 de 20) |
| Hallazgos que eran fallas reales (precisión) | 90,9 % |
| Falsos positivos | 2 |
| Verificaciones no verificadas | 0 |
| Consultas a Gemini | 304 |
| Tokens | 809 012 |
| Tiempo total | 3934 s |

## Por convocatoria y ronda

| Convocatoria | Ronda | Esperadas | Detectadas | No detectadas | De más |
|---|---|---|---|---|---|
| convocatoria_3_plan_desarrollo_urbano | A | — | — | — | — |
| convocatoria_3_plan_desarrollo_urbano | B | — | — | — | — |
| convocatoria_4_supervision_canal_de_riego | A | COH-02, COH-04, COH-06, COH-07 | COH-02, COH-04, COH-06, COH-07 | — | — |
| convocatoria_4_supervision_canal_de_riego | B | ABS-01, ABS-02, ABS-04, COH-02, COH-04, COH-06, COH-07 | ABS-01, ABS-02, ABS-03, ABS-04, COH-02, COH-04, COH-06, COH-07 | — | ABS-03 |
| convocatoria_5_expediente_puente_vehicular | A | COH-06, COH-08, COH-09, COH-10, FOR-01, PRO-06 | COH-06, COH-08, COH-09, COH-10, FOR-01, PRO-06 | — | — |
| convocatoria_5_expediente_puente_vehicular | B | ABS-03, COH-09, COH-10 | ABS-03, COH-06, COH-09, COH-10 | — | COH-06 |

## Hallazgos de más (posibles falsos positivos)

- **convocatoria_4_supervision_canal_de_riego, ronda B, ABS-03** (agente): Las Bases Integradas no incorporaron la modificación aprobada en la absolución de la observación N.° 2 del pliego, la cual disponía agregar «especialista en recursos hídricos» para el especialista en hidráulica (Capítulo III, numeral B.2).
- **convocatoria_5_expediente_puente_vehicular, ronda B, COH-06** (agente): En el Requerimiento el tercer entregable tiene como plazo 'a los ciento veinte (120) días calendario' (página 1), mientras que en el Capítulo III de las Bases Integradas (página 15) se modificó a 'a los ciento cincuenta (150) días calendario', sin que conste una absolución de consulta u observación que lo autorice.

Un hallazgo de más no siempre es un error: puede ser una falla real que no se sembró a propósito. Cada uno se revisa a mano antes de reportarlo como falso positivo.
