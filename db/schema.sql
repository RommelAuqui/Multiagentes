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

-- La app usa la clave service_role/secret, que ignora RLS. Activarlo sin políticas impide que
-- las claves públicas (anon/publishable) lean o modifiquen estas tablas.
alter table concursos enable row level security;
alter table criterios enable row level security;
alter table postores enable row level security;
alter table documentos_chunks enable row level security;
alter table dictamenes enable row level security;
alter table consultas_ia enable row level security;

-- La búsqueda vectorial es exacta: siempre se filtra por concurso/postor (pocos cientos de
-- fragmentos), y un índice aproximado (ivfflat/hnsw) aplica ese filtro después de buscar,
-- con lo que puede devolver menos evidencia de la que existe.
drop index if exists documentos_chunks_embedding_idx;
create index if not exists documentos_chunks_concurso_idx on documentos_chunks (concurso_id);
create index if not exists documentos_chunks_postor_idx on documentos_chunks (postor_id);

drop function if exists match_documentos(vector, uuid, uuid, text, int);
create function match_documentos(
    query_embedding vector(768),
    match_concurso_id uuid,
    match_postor_id uuid,
    match_origen text,
    match_count int
)
returns table (
    id uuid,
    origen text,
    pagina integer,
    contenido text,
    similarity float
)
language sql stable
as $$
    select
        documentos_chunks.id,
        documentos_chunks.origen,
        documentos_chunks.pagina,
        documentos_chunks.contenido,
        1 - (documentos_chunks.embedding <=> query_embedding) as similarity
    from documentos_chunks
    where documentos_chunks.concurso_id = match_concurso_id
        and (match_postor_id is null or documentos_chunks.postor_id = match_postor_id)
        and (match_origen is null or documentos_chunks.origen = match_origen)
    order by documentos_chunks.embedding <=> query_embedding
    limit match_count;
$$;
