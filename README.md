# Sistema Multiagente Autónomo con RAG para Evaluación de Concursos Públicos

Comité evaluador sintético (Legal, Técnico, Coordinador) que audita propuestas técnicas
contra las Bases/TDR de un concurso público, citando documento, página y artículo legal.

## Stack

- Streamlit (frontend, dos vistas)
- Supabase: PostgreSQL + pgvector + Storage
- Google Gemini API (razonamiento y embeddings)
- pypdf (texto de cada página) + Gemini multimodal (páginas escaneadas, imágenes y tablas)
- python-docx / openpyxl (generación de actas y matriz comparativa)

## Arquitectura

| Agente | Archivo | Rol |
| --- | --- | --- |
| Lector | `rag/lector.py` | Transcribe con Gemini las páginas escaneadas o con imágenes (tablas, sellos, firmas). |
| Extractor | `agents/extractor.py` | Arma la matriz según las bases estándar: documentos de admisión, requisitos de calificación y factores de evaluación con su puntaje y forma de asignación. No inventa criterios ni puntajes. |
| Legal | `agents/legal.py` | Evalúa los criterios legales contra la evidencia recuperada por RAG. |
| Técnico | `agents/tecnico.py` | Evalúa los criterios técnicos y asigna el puntaje de los factores según las Bases. |
| Coordinador | `agents/coordinador.py` | Concilia ambas evaluaciones y detecta tensiones o contradicciones; si las hay, el caso pasa a revisión del comité. |

### Agentes autónomos con herramientas

Los agentes Legal y Técnico no responden en un solo paso: trabajan en un bucle de *function calling*
([`agents/agente.py`](agents/agente.py)) en el que deciden qué herramienta usar, ven el resultado y
siguen investigando hasta concluir (máximo 6 pasos):

| Herramienta | Para qué |
| --- | --- |
| `buscar_evidencia` | Nueva búsqueda semántica con sus propias palabras, en toda la oferta o en un archivo (RAG agéntico). |
| `leer_pagina` | Leer una página completa, por ejemplo una tabla cortada entre fragmentos. |
| `listar_documentos` / `datos_del_postor` | Ver los archivos de la oferta; comparar el RUC registrado con el de los anexos. |
| `calcular_experiencia` | Sumar periodos en meses calendario, contando una sola vez los traslapes. |
| `sumar_montos` | Sumar montos facturados y compararlos con la cuantía o el valor referencial. |
| `emitir_evaluacion` | Entregar el veredicto (o puntaje), la justificación y las citas. |

Los cálculos son código determinista ([`agents/herramientas.py`](agents/herramientas.py)), no
aritmética del modelo. Si el Coordinador detecta una contradicción en un criterio, se lo **devuelve a
su agente** con la observación; el agente vuelve a investigar y el Coordinador revisa de nuevo. Si
la tensión persiste, el caso pasa al comité. Cada paso (búsquedas, lecturas, cálculos, devoluciones)
se guarda y el comité lo ve en la revisión y en el acta.

El resultado final no lo decide la IA: lo calcula [`agents/reglas.py`](agents/reglas.py) a partir de
los veredictos de cada criterio (No admitido → No califica → Requiere revisión → Puntaje insuficiente
→ Califica). Cuando la evidencia es dudosa, los agentes responden "Requiere revisión" en vez de
aprobar o descalificar. `agents/orchestrator.py` coordina la evaluación de un postor; `rag/` extrae,
fragmenta, vectoriza y recupera los documentos; `views/` contiene los dos portales de Streamlit.

## Configuración inicial

### 1. Base de datos

En el panel SQL de tu proyecto Supabase, ejecuta el contenido de [`db/schema.sql`](db/schema.sql).
Esto habilita `pgvector`, crea las tablas (con Row Level Security activado) y la función
`match_documentos` usada por el RAG. Supabase avisará de "operaciones destructivas": son los
`drop ... if exists` que actualizan bases creadas con versiones anteriores; en una base nueva
no borran nada.

> En `SUPABASE_KEY` usa la clave **secret** o **service_role**, nunca la anon/publishable:
> la app necesita saltarse RLS, y la clave pública no debe poder leer las propuestas.

> **¿Ya tenías la base creada con una versión anterior?** Vuelve a ejecutar `db/schema.sql`
> completo: es idempotente y aplica los cambios (índices, RUC único por concurso, la nueva
> `match_documentos`, la tabla `consultas_ia`, las columnas de etapas, puntajes y revisión del comité,
> y las de la oferta en varios archivos).
> Si ya existen postulaciones duplicadas del mismo RUC en un concurso, el índice único fallará:
> elimina primero los duplicados. Los documentos indexados antes de esta versión siguen
> funcionando, pero se recuperan mejor si se vuelven a subir.

### 2. Storage

En Supabase → Storage, crea un bucket llamado `licitaciones` (privado).

### 3. Variables de entorno (local)

```bash
cp .env.example .env
```

Completa `.env` con `SUPABASE_URL`, `SUPABASE_KEY` (service role), `GEMINI_API_KEY` y
`ADMIN_PASSWORD` (la contraseña de acceso al Portal del Comité). Este archivo nunca se sube
al repositorio — si trabajas en equipo, comparte estos valores por un canal privado (no por
GitHub, no por chat público), nunca los subas a ningún commit.

Variables opcionales:

| Variable | Por defecto | Uso |
| --- | --- | --- |
| `LLM_MODEL` | `gemini-3.5-flash-lite` | Modelo de los agentes. Se usa una versión fija (no un alias `-latest`) para que los resultados sean reproducibles. |
| `MODELO_LECTOR` | igual a `LLM_MODEL` | Modelo que transcribe las páginas escaneadas. |
| `EMBEDDING_MODEL` | `gemini-embedding-001` | Modelo de embeddings. |
| `EVAL_HILOS` | `1` | Criterios evaluados en paralelo. Súbelo a 3–4 si tu plan de Gemini tiene cuota suficiente; con el plan gratuito, déjalo en 1. |

### 3.1. PDF escaneados

No hay que instalar nada. Cada página se lee primero como texto; las páginas escaneadas (sin texto
seleccionable) y las que tienen una imagen grande pegada —por ejemplo, una constancia escaneada
dentro de un documento de Word— se envían a Gemini en lotes de 5 para que las transcriba
literalmente, con las tablas en formato Markdown. Los logos y firmas pequeñas no activan esta lectura.

### 3.2. Trazabilidad y reproducibilidad

Todas las consultas a la IA usan temperatura 0 y semilla fija, y quedan registradas en la tabla
`consultas_ia` (agente, concurso, postor, modelo, prompt, respuesta, tokens, duración y error).

### 4. Instalación

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 5. Ejecutar en local

```bash
streamlit run app.py
```

## Tests

Los tests usan una base de datos falsa en memoria y simulan Gemini, así que no necesitan
claves ni conexión:

```bash
pip install -r requirements-dev.txt
pytest
```

Incluyen pruebas de los dos portales con `streamlit.testing` (postulación, validación de RUC,
creación y eliminación de convocatorias, evaluación) y se ejecutan en GitHub Actions en cada push.

## Despliegue en Streamlit Community Cloud

1. Conecta el repositorio de GitHub en [share.streamlit.io](https://share.streamlit.io).
2. En **App settings → Secrets**, pega el contenido de `.streamlit/secrets.toml.example`
   con tus valores reales (mismo formato TOML).
3. Cada `git push` a `main` despliega automáticamente.

## Flujo de uso

1. **Nueva convocatoria**: el comité sube las Bases en PDF. El Agente Extractor arma la matriz
   (admisión, calificación y factores de evaluación con puntajes) y la convocatoria queda **en revisión**.
2. **Revisión de la matriz**: en «Concursos en Curso» el comité corrige la matriz en una tabla
   editable (puede agregar, quitar o editar criterios y fijar el puntaje mínimo) y la **publica**.
   Desde ese momento la matriz queda fija y la convocatoria aparece en el Portal del Postor.
3. **Postulación**: el participante elige una convocatoria abierta, ingresa su RUC (se valida el
   dígito verificador de SUNAT) y Razón Social, y sube su oferta técnica en uno o varios PDF (hasta
   10, como en el SEACE). Cada fragmento indexado recuerda su archivo y página, así que las citas
   dicen, por ejemplo, «Anexo 15 - Personal clave.pdf, página 3». Cada RUC puede postular una sola
   vez por concurso.
4. **Evaluación**: se evalúa cada postor (o todos los pendientes a la vez). Los Agentes Legal y
   Técnico proponen el veredicto o el puntaje de cada criterio con citas, y el Coordinador concilia.
5. **Revisión del comité**: en «Ver detalle y revisión del comité» se descargan los archivos de la
   oferta y se confirma o corrige cada criterio (Cumple, No Cumple o No aplica, o el puntaje). Resolver un caso dudoso o cambiar la propuesta de la IA exige justificación, y la
   revisión queda firmada con el nombre del miembro del comité y la fecha. Un postor ya revisado no
   se puede reevaluar con la IA.
6. **Administración**: cerrar o reabrir postulaciones, o eliminar la convocatoria con sus documentos.
7. **Salidas**: Acta de Dictamen Técnico (.docx) por postor, con la propuesta de la IA y la decisión
   del comité por etapa, y Matriz Comparativa (.xlsx) del concurso.
