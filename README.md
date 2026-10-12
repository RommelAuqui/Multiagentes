# Sistema Multiagente Autónomo con RAG para Evaluación de Concursos Públicos

Comité evaluador sintético (Legal, Técnico, Coordinador) que audita propuestas técnicas
contra las Bases/TDR de un concurso público, citando folio/página y artículo legal.

## Stack

- Streamlit (frontend, dos vistas)
- Supabase: PostgreSQL + pgvector + Storage
- Google Gemini API (razonamiento y embeddings)
- pypdf (extracción de texto por página)
- python-docx / openpyxl (generación de actas y matriz comparativa)

## Configuración inicial

### 1. Base de datos

En el panel SQL de tu proyecto Supabase, ejecuta el contenido de [`db/schema.sql`](db/schema.sql).
Esto habilita `pgvector`, crea las tablas y la función `match_documentos` usada por el RAG.

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

## Despliegue en Streamlit Community Cloud

1. Conecta el repositorio de GitHub en [share.streamlit.io](https://share.streamlit.io).
2. En **App settings → Secrets**, pega el contenido de `.streamlit/secrets.toml.example`
   con tus valores reales (mismo formato TOML).
3. Cada `git push` a `main` despliega automáticamente.

## Flujo de uso

1. **Portal del Comité**: crea una convocatoria subiendo las Bases/TDR en PDF. El Agente
   Extractor genera la matriz de requisitos legales y técnicos.
2. **Portal del Postor**: el participante se registra con su RUC/Razón Social y sube su
   Propuesta Técnica y CV en PDF. Los documentos se indexan automáticamente para el RAG.
3. **Evaluación**: desde el Portal del Comité, se lanza la evaluación por postor. Los
   Agentes Legal y Técnico analizan cada criterio contra los fragmentos relevantes de sus
   documentos, y el Agente Coordinador consolida el dictamen final.
4. **Salidas**: descarga del Acta de Dictamen Técnico (.docx) por postor y de la Matriz
   Comparativa (.xlsx) del concurso completo.
