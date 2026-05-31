-- ==========================================================
-- BASE DE DATOS MVP - GESTIÓN DE SÍLABOS
-- Proyecto: Sistema de monitoreo de mejora continua ISIA
-- ==========================================================

create extension if not exists "uuid-ossp";

-- =========================
-- TABLA: silabos
-- =========================
create table if not exists silabos (
    id uuid primary key default uuid_generate_v4(),

    semestre_academico varchar(10) not null,
    facultad varchar(100),
    programa_estudios varchar(150),

    asignatura varchar(150) not null,
    codigo_asignatura varchar(30) not null,
    ciclo integer not null,

    modalidad varchar(50),
    creditos integer,
    total_horas_semestrales integer,
    total_horas_semanales integer,

    fecha_inicio date,
    fecha_culminacion date,
    duracion_semanas integer,

    docente_responsable varchar(250),
    correo_docente varchar(250),

    archivo_url text,

    estado varchar(30) not null default 'pendiente',
    porcentaje_cumplimiento numeric(5,2) default 0,

    observacion_general text,

    created_at timestamp with time zone default now(),
    updated_at timestamp with time zone default now(),

    constraint chk_estado_silabo check (
        estado in ('pendiente', 'completo', 'observado', 'incompleto')
    ),

    constraint chk_ciclo check (
        ciclo >= 1 and ciclo <= 10
    )
);

-- =========================
-- TABLA: validacion_silabo
-- =========================
create table if not exists validacion_silabo (
    id uuid primary key default uuid_generate_v4(),

    silabo_id uuid not null references silabos(id) on delete cascade,

    seccion varchar(150) not null,
    cumple boolean not null default false,
    observacion text,

    created_at timestamp with time zone default now()
);

-- =========================
-- TABLA: historial_silabo
-- =========================
create table if not exists historial_silabo (
    id uuid primary key default uuid_generate_v4(),

    silabo_id uuid not null references silabos(id) on delete cascade,

    estado_anterior varchar(30),
    estado_nuevo varchar(30),

    observacion text,
    usuario varchar(150),

    created_at timestamp with time zone default now()
);

-- =========================
-- TABLA: alertas_silabo
-- =========================
create table if not exists alertas_silabo (
    id uuid primary key default uuid_generate_v4(),

    silabo_id uuid not null references silabos(id) on delete cascade,

    tipo_alerta varchar(50) not null,
    mensaje text not null,
    estado_alerta varchar(30) not null default 'pendiente',

    created_at timestamp with time zone default now(),

    constraint chk_estado_alerta check (
        estado_alerta in ('pendiente', 'enviada', 'atendida')
    )
);