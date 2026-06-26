create table if not exists seguimiento_semanal_evidencias (
  id uuid primary key default gen_random_uuid(),
  evidencia_id uuid not null references macroproceso_evidencias(id) on delete cascade,
  macroproceso text not null check (macroproceso in ('planificacion_estrategica', 'gestion_academica')),
  codigo_evidencia text,
  semana_inicio date not null,
  semana_fin date not null,
  responsable text,
  accion_realizada boolean not null default false,
  nivel_avance text not null check (nivel_avance in ('Sin avance', 'Bajo', 'Medio', 'Alto', 'Completado')),
  porcentaje_avance integer default 0 check (porcentaje_avance >= 0 and porcentaje_avance <= 100),
  descripcion_accion text,
  resultado_observado text,
  dificultad_encontrada text,
  compromiso_siguiente_semana text,
  requiere_apoyo boolean default false,
  tipo_apoyo_requerido text,
  archivo_sustento_url text,
  observacion text,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  constraint seguimiento_semana_rango_valido check (semana_inicio <= semana_fin),
  constraint seguimiento_unico_por_semana unique (evidencia_id, semana_inicio)
);

create index if not exists idx_seguimiento_semanal_evidencia_id
  on seguimiento_semanal_evidencias(evidencia_id);

create index if not exists idx_seguimiento_semanal_macroproceso
  on seguimiento_semanal_evidencias(macroproceso);

create index if not exists idx_seguimiento_semanal_codigo
  on seguimiento_semanal_evidencias(codigo_evidencia);

create index if not exists idx_seguimiento_semanal_semana_inicio
  on seguimiento_semanal_evidencias(semana_inicio);
