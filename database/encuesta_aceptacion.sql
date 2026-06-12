create table if not exists encuesta_aceptacion (
  id uuid primary key default gen_random_uuid(),
  nombre_usuario varchar,
  rol_usuario varchar,
  claridad_interfaz int not null,
  facilidad_uso int not null,
  utilidad_evidencias int not null,
  utilidad_ia int not null,
  utilidad_alertas int not null,
  utilidad_semaforo int not null,
  satisfaccion_general int not null,
  comentario text,
  created_at timestamptz default now(),
  constraint encuesta_aceptacion_claridad_check
    check (claridad_interfaz between 1 and 5),
  constraint encuesta_aceptacion_facilidad_check
    check (facilidad_uso between 1 and 5),
  constraint encuesta_aceptacion_evidencias_check
    check (utilidad_evidencias between 1 and 5),
  constraint encuesta_aceptacion_ia_check
    check (utilidad_ia between 1 and 5),
  constraint encuesta_aceptacion_alertas_check
    check (utilidad_alertas between 1 and 5),
  constraint encuesta_aceptacion_semaforo_check
    check (utilidad_semaforo between 1 and 5),
  constraint encuesta_aceptacion_satisfaccion_check
    check (satisfaccion_general between 1 and 5)
);

create index if not exists idx_encuesta_aceptacion_created_at
  on encuesta_aceptacion (created_at);

create index if not exists idx_encuesta_aceptacion_rol_usuario
  on encuesta_aceptacion (rol_usuario);
