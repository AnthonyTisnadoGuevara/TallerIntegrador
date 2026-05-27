-- =========================================================
-- ESQUEMA PARA AGENTES DE ANÁLISIS CURRICULAR
-- Macroproceso: Gestión de Sílabos
-- =========================================================

-- =========================================================
-- TABLA: analisis_silabo
-- Guarda el análisis individual de cada sílabo realizado por el agente
-- =========================================================

create table if not exists analisis_silabo (
    id uuid primary key default gen_random_uuid(),

    silabo_id uuid not null references silabos(id) on delete cascade,

    resumen text,

    competencias_detectadas jsonb default '[]'::jsonb,
    contenidos_detectados jsonb default '[]'::jsonb,
    resultados_aprendizaje jsonb default '[]'::jsonb,
    secciones_faltantes jsonb default '[]'::jsonb,
    sugerencias jsonb default '[]'::jsonb,

    nivel_riesgo varchar(20) default 'bajo',
    estado_analisis varchar(30) default 'analizado',

    modelo_usado varchar(100),
    observacion_general text,

    created_at timestamp with time zone default now(),
    updated_at timestamp with time zone default now()
);


-- =========================================================
-- TABLA: trazabilidad_curricular
-- Guarda relaciones entre sílabos de distintos ciclos
-- =========================================================

create table if not exists trazabilidad_curricular (
    id uuid primary key default gen_random_uuid(),

    silabo_origen_id uuid references silabos(id) on delete cascade,
    silabo_destino_id uuid references silabos(id) on delete cascade,

    ciclo_origen integer,
    ciclo_destino integer,

    asignatura_origen varchar(150),
    asignatura_destino varchar(150),

    tipo_relacion varchar(50) not null,
    descripcion text,
    nivel_coherencia varchar(20) default 'medio',
    observacion text,
    sugerencia text,

    created_at timestamp with time zone default now()
);


-- =========================================================
-- TABLA: brechas_curriculares
-- Guarda problemas o vacíos detectados en la progresión curricular
-- =========================================================

create table if not exists brechas_curriculares (
    id uuid primary key default gen_random_uuid(),

    silabo_id uuid references silabos(id) on delete cascade,

    ciclo integer,
    asignatura varchar(150),

    tipo_brecha varchar(50) not null,
    descripcion text not null,
    recomendacion text,

    prioridad varchar(20) default 'media',
    estado varchar(30) default 'pendiente',

    created_at timestamp with time zone default now(),
    updated_at timestamp with time zone default now()
);


-- =========================================================
-- ÍNDICES PARA CONSULTAS MÁS RÁPIDAS
-- =========================================================

create index if not exists idx_analisis_silabo_silabo_id
on analisis_silabo(silabo_id);

create index if not exists idx_trazabilidad_origen
on trazabilidad_curricular(silabo_origen_id);

create index if not exists idx_trazabilidad_destino
on trazabilidad_curricular(silabo_destino_id);

create index if not exists idx_brechas_silabo_id
on brechas_curriculares(silabo_id);

create index if not exists idx_brechas_ciclo
on brechas_curriculares(ciclo);

create index if not exists idx_brechas_estado
on brechas_curriculares(estado);