create table if not exists alertas_inteligentes_macroprocesos (
  id uuid primary key default gen_random_uuid(),
  macroproceso varchar not null,
  origen_tipo varchar not null,
  origen_id uuid,
  codigo varchar,
  titulo varchar not null,
  descripcion text,
  nivel_alerta varchar not null default 'media',
  estado varchar not null default 'activa',
  recomendacion text,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  constraint alertas_inteligentes_nivel_check
    check (nivel_alerta in ('baja', 'media', 'alta', 'critica')),
  constraint alertas_inteligentes_estado_check
    check (estado in ('activa', 'atendida', 'descartada'))
);

create index if not exists idx_alertas_macroproceso
  on alertas_inteligentes_macroprocesos (macroproceso);

create index if not exists idx_alertas_nivel
  on alertas_inteligentes_macroprocesos (nivel_alerta);

create index if not exists idx_alertas_estado
  on alertas_inteligentes_macroprocesos (estado);

create index if not exists idx_alertas_created_at
  on alertas_inteligentes_macroprocesos (created_at);
