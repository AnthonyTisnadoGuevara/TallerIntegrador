create table if not exists historial_macroproceso_evidencias (
  id uuid primary key default gen_random_uuid(),
  evidencia_id uuid not null,
  macroproceso varchar not null,
  codigo varchar,
  titulo varchar,
  campo_modificado varchar not null,
  valor_anterior text,
  valor_nuevo text,
  observacion text,
  usuario varchar,
  created_at timestamptz default now()
);

create index if not exists idx_historial_macro_evidencia_id
  on historial_macroproceso_evidencias (evidencia_id);

create index if not exists idx_historial_macro_macroproceso
  on historial_macroproceso_evidencias (macroproceso);

create index if not exists idx_historial_macro_created_at
  on historial_macroproceso_evidencias (created_at);
