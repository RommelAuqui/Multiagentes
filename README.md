# Sistema Multiagente Autónomo con RAG para Evaluación de Concursos Públicos

Comité evaluador sintético (Legal, Técnico, Coordinador) que audita propuestas técnicas
contra las Bases/TDR de un concurso público, citando documento, página y artículo legal.

## Stack

- Streamlit (frontend, dos vistas)
- Supabase: PostgreSQL + pgvector + Storage
- Google Gemini API (razonamiento y embeddings)
- pypdf + Tesseract OCR (extracción de texto por página)
- python-docx / openpyxl (generación de actas y matriz comparativa)

## Arquitectura

| Agente | Archivo | Rol |
| --- | --- | --- |
| Extractor | `agents/extractor.py` | Lee las Bases y genera la matriz de criterios legales y técnicos. |
| Legal | `agents/legal.py` | Evalúa cada criterio legal contra la evidencia recuperada por RAG. |
| Técnico | `agents/tecnico.py` | Evalúa cada criterio técnico contra la evidencia recuperada por RAG. |
| Coordinador | `agents/coordinador.py` | Descalifica ante incumplimientos legales obligatorios o delibera entre ambos agentes. |

`agents/orchestrator.py` coordina la evaluación de un postor; `rag/` extrae, fragmenta, vectoriza
y recupera los documentos; `views/` contiene los dos portales de Streamlit.

## Configuración inicial

### 1. Base de datos

En el panel SQL de tu proyecto Supabase, ejecuta el contenido de [`db/schema.sql`](db/schema.sql).
Esto habilita `pgvector`, crea las tablas y la función `match_documentos` usada por el RAG.

> **¿Ya tenías la base creada con una versión anterior?** Vuelve a ejecutar `db/schema.sql`
> completo: es idempotente y aplica los cambios (quita el índice `ivfflat`, agrega índices por
> concurso/postor, el índice único de RUC por concurso y la nueva `match_documentos`).
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
| `LLM_MODEL` | `gemini-flash-lite-latest` | Modelo de los agentes. |
| `EMBEDDING_MODEL` | `gemini-embedding-001` | Modelo de embeddings. |
| `EVAL_HILOS` | `1` | Criterios evaluados en paralelo. Súbelo a 3–4 si tu plan de Gemini tiene cuota suficiente; con el plan gratuito, déjalo en 1. |
| `OCR_IDIOMA` / `OCR_DPI` | `spa` / `200` | Configuración de Tesseract. |

### 3.1. OCR para PDFs escaneados (opcional en local)

Las páginas sin texto seleccionable (imágenes escaneadas) se leen con OCR (Tesseract). Un PDF
con texto normal no lo necesita. Para usarlo en local en Windows:

1. Instala [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) y marca el idioma
   **Spanish** durante la instalación.
2. Instala [Poppler para Windows](https://github.com/oschwartz10612/poppler-windows/releases)
   y descomprímelo en una carpeta.
3. En `.env` define `TESSERACT_CMD` (ruta a `tesseract.exe`) y `POPPLER_PATH` (carpeta `bin`
   de Poppler) si no están en el PATH.

En Streamlit Community Cloud no hace falta configurar nada: el archivo `packages.txt` instala
Tesseract (con español) y Poppler automáticamente.

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

1. **Portal del Comité**: crea una convocatoria subiendo las Bases/TDR en PDF. El Agente
   Extractor genera la matriz de requisitos legales y técnicos; si no logra extraer criterios,
   la convocatoria no se crea.
2. **Portal del Postor**: el participante elige una convocatoria abierta, ingresa su RUC
   (se valida el dígito verificador de SUNAT) y Razón Social, y sube su Propuesta Técnica y
   CV en PDF. Cada RUC puede postular una sola vez por concurso. Los documentos se indexan
   para el RAG antes de registrar la postulación.
3. **Evaluación**: desde el Portal del Comité se evalúa cada postor (o todos los pendientes a
   la vez). Los Agentes Legal y Técnico analizan cada criterio contra los fragmentos relevantes
   de sus documentos y el Agente Coordinador consolida el dictamen final. Un postor ya evaluado
   puede reevaluarse; el nuevo dictamen reemplaza al anterior.
4. **Administración**: el comité puede cerrar o reabrir las postulaciones de una convocatoria,
   o eliminarla junto con sus documentos.
5. **Salidas**: descarga del Acta de Dictamen Técnico (.docx) por postor y de la Matriz
   Comparativa (.xlsx) del concurso completo.
