create table if not exists analisis_ia_macroprocesos (
  id uuid primary key default gen_random_uuid(),
  macroproceso varchar not null,
  tipo_analisis varchar not null,
  nivel_riesgo varchar,
  resumen text,
  resultado_json jsonb not null,
  modelo_usado varchar,
  usuario varchar,
  created_at timestamptz default now()
);

create index if not exists idx_analisis_ia_macroproceso
  on analisis_ia_macroprocesos (macroproceso);

create index if not exists idx_analisis_ia_tipo_analisis
  on analisis_ia_macroprocesos (tipo_analisis);

create index if not exists idx_analisis_ia_created_at
  on analisis_ia_macroprocesos (created_at);

create index if not exists idx_analisis_ia_nivel_riesgo
  on analisis_ia_macroprocesos (nivel_riesgo);
