create table if not exists validacion_ia_macroproceso_evidencias (
  id uuid primary key default gen_random_uuid(),
  evidencia_id uuid not null,
  macroproceso varchar not null,
  modelo_usado varchar,
  nivel_validez varchar,
  pertinencia varchar,
  resumen text,
  elementos_detectados jsonb default '[]'::jsonb,
  elementos_faltantes jsonb default '[]'::jsonb,
  observaciones jsonb default '[]'::jsonb,
  recomendaciones jsonb default '[]'::jsonb,
  accion_sugerida text,
  created_at timestamptz default now()
);

create index if not exists idx_validacion_ia_macro_evidencia_id
  on validacion_ia_macroproceso_evidencias (evidencia_id);

create index if not exists idx_validacion_ia_macroproceso
  on validacion_ia_macroproceso_evidencias (macroproceso);

create index if not exists idx_validacion_ia_created_at
  on validacion_ia_macroproceso_evidencias (created_at);

create index if not exists idx_validacion_ia_nivel_validez
  on validacion_ia_macroproceso_evidencias (nivel_validez);
