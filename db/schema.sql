create extension if not exists vector;
create extension if not exists pgcrypto;

create table if not exists concursos (
    id uuid primary key default gen_random_uuid(),
    nombre text not null,
    descripcion text,
    bases_pdf_path text,
    estado text not null default 'abierto',
    created_at timestamptz not null default now()
);

create table if not exists criterios (
    id uuid primary key default gen_random_uuid(),
    concurso_id uuid not null references concursos(id) on delete cascade,
    tipo text not null check (tipo in ('legal', 'tecnico')),
    descripcion text not null,
    referencia text,
    obligatorio boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists postores (
    id uuid primary key default gen_random_uuid(),
    concurso_id uuid not null references concursos(id) on delete cascade,
    ruc text not null,
    razon_social text not null,
    propuesta_pdf_path text,
    cv_pdf_path text,
    estado text not null default 'recibido',
    created_at timestamptz not null default now()
);

-- Un RUC solo puede postular una vez a cada concurso.
create unique index if not exists postores_concurso_ruc_idx on postores (concurso_id, ruc);

create table if not exists documentos_chunks (
    id uuid primary key default gen_random_uuid(),
    concurso_id uuid not null references concursos(id) on delete cascade,
    postor_id uuid references postores(id) on delete cascade,
    origen text not null check (origen in ('bases', 'propuesta', 'cv')),
    pagina integer not null,
    contenido text not null,
    embedding vector(768),
    created_at timestamptz not null default now()
);

create table if not exists dictamenes (
    id uuid primary key default gen_random_uuid(),
    postor_id uuid not null references postores(id) on delete cascade,
    concurso_id uuid not null references concursos(id) on delete cascade,
    criterio_id uuid references criterios(id) on delete set null,
    criterio_descripcion text,
    agente text not null check (agente in ('legal', 'tecnico', 'coordinador')),
    veredicto text not null,
    justificacion text,
    citas jsonb,
    puntaje numeric,
    created_at timestamptz not null default now()
);

-- Trazabilidad: cada consulta a la IA (prompt, respuesta, modelo, tokens y tiempo).
create table if not exists consultas_ia (
    id uuid primary key default gen_random_uuid(),
    concurso_id uuid references concursos(id) on delete cascade,
    postor_id uuid references postores(id) on delete cascade,
    agente text not null,
    modelo text not null,
    prompt text not null,
    adjuntos integer not null default 0,
    respuesta text,
    tokens_entrada integer,
    tokens_salida integer,
    duracion_ms integer,
    error text,
    created_at timestamptz not null default now()
);
create index if not exists consultas_ia_concurso_idx on consultas_ia (concurso_id);

-- Matriz según la estructura de las bases estándar (admisión, calificación y factores de
-- evaluación con puntaje) y revisión del comité sobre lo que propone la IA.
alter table concursos add column if not exists puntaje_minimo numeric;
alter table criterios add column if not exists etapa text not null default 'calificacion';
alter table criterios add column if not exists acreditacion text;
alter table criterios add column if not exists puntaje_maximo numeric;
alter table criterios add column if not exists asignacion_puntaje text;
alter table criterios add column if not exists orden integer;
alter table dictamenes add column if not exists etapa text;
alter table dictamenes add column if not exists obligatorio boolean;
alter table dictamenes add column if not exists puntaje_maximo numeric;
alter table dictamenes add column if not exists veredicto_comite text;
alter table dictamenes add column if not exists puntaje_comite numeric;
alter table dictamenes add column if not exists justificacion_comite text;
alter table dictamenes add column if not exists revisado_por text;
alter table dictamenes add column if not exists revisado_en timestamptz;

-- Oferta en varios archivos (hasta 10, como en el SEACE): cada fragmento recuerda su archivo.
alter table postores add column if not exists archivos jsonb not null default '[]';
alter table documentos_chunks add column if not exists documento text;
alter table documentos_chunks drop constraint if exists documentos_chunks_origen_check;
alter table documentos_chunks add constraint documentos_chunks_origen_check
    check (origen in ('bases', 'oferta', 'propuesta', 'cv'));

-- Agentes con herramientas: posición de cada fragmento en su archivo (para leer una página completa)
-- y los pasos que siguió el agente en cada criterio (búsquedas, lecturas, cálculos, deliberación).
alter table documentos_chunks add column if not exists orden integer;
alter table dictamenes add column if not exists pasos jsonb;

-- Flujo automático: cierre por fecha, evaluación automática al cerrar y bitácora de cada ejecución.
alter table concursos add column if not exists fecha_cierre timestamptz;
alter table concursos add column if not exists evaluacion_automatica boolean not null default false;
alter table postores add column if not exists error_evaluacion text;
alter table postores add column if not exists evaluacion_iniciada_en timestamptz;
create index if not exists consultas_ia_fecha_idx on consultas_ia (created_at);

create table if not exists ejecuciones_automaticas (
    id uuid primary key default gen_random_uuid(),
    inicio timestamptz not null default now(),
    fin timestamptz,
    convocatorias_cerradas integer not null default 0,
    postores_evaluados integer not null default 0,
    postores_con_error integer not null default 0,
    pausada_por_limite boolean not null default false,
    detalle text
);

do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'criterios_etapa_check') then
        alter table criterios add constraint criterios_etapa_check
            check (etapa in ('admision', 'calificacion', 'evaluacion'));
    end if;
end $$;

-- La app usa la clave service_role/secret, que ignora RLS. Activarlo sin políticas impide que
-- las claves públicas (anon/publishable) lean o modifiquen estas tablas.
alter table concursos enable row level security;
alter table criterios enable row level security;
alter table postores enable row level security;
alter table documentos_chunks enable row level security;
alter table dictamenes enable row level security;
alter table consultas_ia enable row level security;
alter table ejecuciones_automaticas enable row level security;

-- La búsqueda vectorial es exacta: siempre se filtra por concurso/postor (pocos cientos de
-- fragmentos), y un índice aproximado (ivfflat/hnsw) aplica ese filtro después de buscar,
-- con lo que puede devolver menos evidencia de la que existe.
drop index if exists documentos_chunks_embedding_idx;
create index if not exists documentos_chunks_concurso_idx on documentos_chunks (concurso_id);
create index if not exists documentos_chunks_postor_idx on documentos_chunks (postor_id);

drop function if exists match_documentos(vector, uuid, uuid, text, int);
drop function if exists match_documentos(vector, uuid, uuid, text, int, text);
create function match_documentos(
    query_embedding vector(768),
    match_concurso_id uuid,
    match_postor_id uuid,
    match_origen text,
    match_count int,
    match_documento text default null
)
returns table (
    id uuid,
    origen text,
    documento text,
    pagina integer,
    contenido text,
    similarity float
)
language sql stable
as $$
    select
        documentos_chunks.id,
        documentos_chunks.origen,
        documentos_chunks.documento,
        documentos_chunks.pagina,
        documentos_chunks.contenido,
        1 - (documentos_chunks.embedding <=> query_embedding) as similarity
    from documentos_chunks
    where documentos_chunks.concurso_id = match_concurso_id
        and (match_postor_id is null or documentos_chunks.postor_id = match_postor_id)
        and (match_origen is null or documentos_chunks.origen = match_origen)
        and (match_documento is null
             or coalesce(documentos_chunks.documento, documentos_chunks.origen) = match_documento)
    order by documentos_chunks.embedding <=> query_embedding
    limit match_count;
$$;

-- Revisión de Bases (control previo): documentos del expediente y de la selección por versión, cada
-- corrida de la revisión y los hallazgos con la respuesta del comité.
alter table concursos add column if not exists ronda_revision text;

create table if not exists documentos_expediente (
    id uuid primary key default gen_random_uuid(),
    concurso_id uuid not null references concursos(id) on delete cascade,
    tipo text not null,
    version integer not null default 1,
    nombre text not null,
    path text,
    paginas jsonb not null default '[]',
    datos jsonb not null default '{}',
    error_lectura text,
    created_at timestamptz not null default now()
);
create index if not exists documentos_expediente_concurso_idx on documentos_expediente (concurso_id, tipo);

create table if not exists revisiones_bases (
    id uuid primary key default gen_random_uuid(),
    concurso_id uuid not null references concursos(id) on delete cascade,
    ronda text not null check (ronda in ('A', 'B')),
    documentos jsonb not null default '{}',
    resultados jsonb not null default '[]',
    created_at timestamptz not null default now()
);

create table if not exists hallazgos (
    id uuid primary key default gen_random_uuid(),
    concurso_id uuid not null references concursos(id) on delete cascade,
    ronda text not null check (ronda in ('A', 'B')),
    codigo text not null,
    clave text not null default '',
    gravedad text not null,
    resultado text not null check (resultado in ('falla', 'no_verificado', 'cumple')),
    estado text not null default 'pendiente' check (estado in ('pendiente', 'se_mantiene', 'corregido')),
    descripcion text not null,
    citas jsonb not null default '[]',
    detectado_en uuid references revisiones_bases(id) on delete set null,
    ultima_revision uuid references revisiones_bases(id) on delete set null,
    resuelto_en uuid references revisiones_bases(id) on delete set null,
    justificacion_comite text,
    revisado_por text,
    revisado_en timestamptz,
    created_at timestamptz not null default now(),
    unique (concurso_id, ronda, codigo, clave)
);

alter table documentos_expediente enable row level security;
alter table revisiones_bases enable row level security;
alter table hallazgos enable row level security;
