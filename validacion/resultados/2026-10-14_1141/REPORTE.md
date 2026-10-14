# Validación del sistema multiagente

- **Fecha:** 14/10/2026 11:41
- **Modelo:** `gemini-3.5-flash-lite`
- **Casos:** 1 (P03) · **Repeticiones:** 1
- **Modos comparados:** Agentes autónomos (Fase 2)

## Resumen

| Métrica | Agentes autónomos (Fase 2) |
|---|---|
| Exactitud en requisitos | 100,0 % |
| Kappa de Cohen (requisitos) | 1,00 |
| Aprobaciones indebidas | 0 |
| Rechazos indebidos | 0 |
| Derivaciones innecesarias al comité | 0 |
| Exactitud en puntajes | 100,0 % |
| Error absoluto medio del puntaje | 0,0 |
| Sobrepuntajes (más de lo que corresponde) | 0 |
| Exactitud del resultado final | 100,0 % |
| «Califica» indebido | 0 |
| Tiempo promedio por postor (s) | 58,1 |
| Consultas a la IA por postor | 13,0 |
| Tokens por postor | 30 413,0 |
| Reproducibilidad entre repeticiones | — |

## Resultado final por caso

| Caso | Dificultad | Esperado | Agentes autónomos (Fase 2) |
|---|---|---|---|
| **P03** Experiencia con traslape | Dos periodos que se superponen 8 meses: sumados a ojo dan 38 meses, pero son 30 (se exigen 36). | No califica (100 pts) | ✅ No califica (100 pts) |

## Decisiones incorrectas

No hubo errores: todas las decisiones coinciden con la respuesta correcta.

## Matriz de confusión de los requisitos

**Agentes autónomos (Fase 2)** (filas: respuesta correcta; columnas: decisión del sistema)

| Correcto \ Sistema | Cumple | No Cumple | No aplica |
|---|---|---|---|
| Cumple | 5 | 0 | 0 |
| No Cumple | 0 | 1 | 0 |
| No aplica | 0 | 0 | 1 |

## Banco de casos (respuesta correcta)

| Caso | Anexo 1 | Anexo 2 | Anexo 3 | Promesa de consorcio | Facturación del postor | Título del jefe | Experiencia del jefe | Puntaje experiencia | Puntaje metodología | Resultado |
|---|---|---|---|---|---|---|---|---|---|---|
| **P03** Experiencia con traslape | Cumple | Cumple | Cumple | No aplica | Cumple | Cumple | No Cumple | 60 | 40 | No califica |

El detalle de cada caso y su dificultad está en `validacion/casos.py`; todas las decisiones, con la
justificación de los agentes, en `decisiones.csv`.

## Definiciones

- **Exactitud en requisitos**: proporción de decisiones de admisión y calificación iguales a la
  respuesta correcta (o a una alternativa igualmente válida, como en P05).
- **Kappa de Cohen**: acuerdo con la respuesta correcta descontando el que se daría por azar
  (1 = perfecto; 0 = no mejor que el azar; > 0,8 se considera casi perfecto).
- **Aprobación indebida**: el sistema declara «Cumple» o «No aplica» un requisito que no se cumple o
  que debía revisar el comité. Es el error más grave, porque deja pasar una oferta deficiente.
- **Rechazo indebido**: el sistema declara «No Cumple» un requisito que sí se cumple.
- **Derivación innecesaria**: el sistema pide revisión del comité en un caso que tenía respuesta clara.
  No es un error grave, pero le cuesta tiempo al comité.
- **Error absoluto medio del puntaje**: diferencia promedio, en puntos, entre el puntaje asignado y el
  correcto en cada factor de evaluación.
- **Reproducibilidad**: proporción de decisiones idénticas al repetir la evaluación de los mismos casos.
