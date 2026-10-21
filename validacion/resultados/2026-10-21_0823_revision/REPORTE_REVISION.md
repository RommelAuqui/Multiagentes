# Validación del módulo de revisión de Bases

- **Fecha:** 21/10/2026 09:32
- **Modo:** reglas fijas y agente revisor
- **Convocatorias:** 2 · rondas revisadas: 4

## Resumen

| Métrica | Valor |
|---|---|
| Fallas sembradas detectadas (exhaustividad) | 88,9 % (16 de 18) |
| Hallazgos que eran fallas reales (precisión) | 84,2 % |
| Falsos positivos | 3 |
| Verificaciones no verificadas | 3 |
| Consultas a Gemini | 249 |
| Tokens | 596 717 |
| Tiempo total | 4144 s |

## Por convocatoria y ronda

| Convocatoria | Ronda | Esperadas | Detectadas | No detectadas | De más |
|---|---|---|---|---|---|
| convocatoria_4_supervision_canal_de_riego | A | COH-02, COH-04, COH-06, COH-07 | COH-02, COH-04, COH-06, COH-07 | — | — |
| convocatoria_4_supervision_canal_de_riego | B | ABS-01, ABS-02, ABS-04, COH-02, COH-04, COH-06, COH-07 | ABS-01, ABS-02, ABS-03, ABS-04, COH-02, COH-04, COH-06, COH-07 | — | ABS-03 |
| convocatoria_5_expediente_puente_vehicular | A | COH-08, COH-09, COH-10, PRO-06 | COH-06, COH-08, COH-10, PRO-06 | COH-09 | COH-06 |
| convocatoria_5_expediente_puente_vehicular | B | ABS-03, COH-09, COH-10 | ABS-03, COH-10, FOR-01 | COH-09 | FOR-01 |

## Hallazgos de más (posibles falsos positivos)

- **convocatoria_4_supervision_canal_de_riego, ronda B, ABS-03** (agente): Las Bases Integradas no incluyen la modificación anunciada en la observación N.° 2 del pliego respecto al especialista en recursos hídricos.
- **convocatoria_5_expediente_puente_vehicular, ronda A, COH-06** (agente): El Capítulo III de las Bases presenta diferencias sustanciales en su contenido respecto al requerimiento original (términos de referencia), tales como modificaciones en los plazos, actividades, forma de presentación y redacción de los requisitos de calificación del personal clave.
- **convocatoria_5_expediente_puente_vehicular, ronda B, FOR-01** (agente): La Sección general contenida en las Bases Integradas muestra una versión resumida y alterada que omite los plazos legales de consultas, elevación y apelación exigidos por la normativa de contrataciones públicas.

Un hallazgo de más no siempre es un error: puede ser una falla real que no se sembró a propósito. Cada uno se revisa a mano antes de reportarlo como falso positivo.
