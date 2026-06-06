create table if not exists macroproceso_evidencias (
  id uuid primary key default gen_random_uuid(),
  macroproceso varchar not null,
  codigo varchar,
  titulo varchar not null,
  descripcion text,
  tipo_evidencia varchar,
  responsable varchar,
  mes_programado varchar,
  fecha_programada date,
  fecha_cumplimiento date,
  estado varchar default 'pendiente',
  prioridad varchar default 'media',
  avance int default 0,
  observacion text,
  archivo_url text,
  origen_documento varchar,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  constraint macroproceso_evidencias_estado_check
    check (estado in ('pendiente', 'en_proceso', 'completado', 'observado')),
  constraint macroproceso_evidencias_prioridad_check
    check (prioridad in ('alta', 'media', 'baja')),
  constraint macroproceso_evidencias_avance_check
    check (avance between 0 and 100)
);

create index if not exists idx_macroproceso_evidencias_macroproceso
  on macroproceso_evidencias (macroproceso);

create index if not exists idx_macroproceso_evidencias_estado
  on macroproceso_evidencias (estado);

create index if not exists idx_macroproceso_evidencias_prioridad
  on macroproceso_evidencias (prioridad);

insert into macroproceso_evidencias (
  macroproceso,
  codigo,
  titulo,
  descripcion,
  tipo_evidencia,
  responsable,
  mes_programado,
  estado,
  prioridad,
  avance,
  origen_documento
) values
(
  'planificacion_estrategica',
  'PE-001',
  'Elaborar y ejecutar planes operativos anuales',
  'Seguimiento a la elaboracion y ejecucion de planes operativos anuales con su respectiva ejecucion presupuestal.',
  'Plan operativo',
  'Director del programa de estudio',
  'Anual',
  'pendiente',
  'alta',
  0,
  'Plan General de Desarrollo 2025-2028'
),
(
  'planificacion_estrategica',
  'PE-002',
  'Fortalecer la experiencia academica de los estudiantes',
  'Seguimiento a iniciativas orientadas al acompanamiento, permanencia y actividades extracurriculares de los estudiantes.',
  'Informe de seguimiento',
  'Director del programa / Comite academico',
  'Anual',
  'pendiente',
  'media',
  0,
  'Plan General de Desarrollo 2025-2028'
),
(
  'planificacion_estrategica',
  'PE-003',
  'Mantener actualizado el curriculo del programa',
  'Seguimiento a la revision y actualizacion curricular del programa de estudio.',
  'Matriz curricular / acta / resolucion',
  'Comite academico',
  'Anual',
  'en_proceso',
  'alta',
  40,
  'Plan General de Desarrollo 2025-2028'
),
(
  'planificacion_estrategica',
  'PE-004',
  'Gestionar el Plan Anual de Trabajo y acciones correctivas',
  'Seguimiento del PAT, cronograma de acreditacion y registro de oportunidades de mejora y acciones correctivas.',
  'PAT / ROA / informe',
  'Director del programa',
  'Anual',
  'pendiente',
  'alta',
  0,
  'Plan General de Desarrollo 2025-2028'
),
(
  'planificacion_estrategica',
  'PE-005',
  'Impulsar produccion cientifica e innovacion',
  'Seguimiento de actividades de investigacion formativa, semilleros de investigacion e innovacion.',
  'Reporte de investigacion',
  'Docentes / Comite academico',
  'Anual',
  'pendiente',
  'media',
  0,
  'Plan General de Desarrollo 2025-2028'
),
(
  'gestion_academica',
  'GA-001',
  'Registrar resolucion de actualizacion curricular',
  'Evidencia de ratificacion y aprobacion de la actualizacion curricular del programa.',
  'Resolucion',
  'Consejo Directivo / Facultad de Ingenieria',
  'Febrero',
  'completado',
  'alta',
  100,
  'RCD 57-2026 Actualizacion curricular 2022'
),
(
  'gestion_academica',
  'GA-002',
  'Registrar opinion favorable de la Oficina de Gestion Academica',
  'Evidencia de revision favorable de la actualizacion curricular por la Oficina de Gestion Academica.',
  'Oficio / informe',
  'Oficina de Gestion Academica',
  'Febrero',
  'completado',
  'alta',
  100,
  'RCD 57-2026 Actualizacion curricular 2022'
),
(
  'gestion_academica',
  'GA-003',
  'Registrar actas de socializacion con grupos de interes',
  'Seguimiento a actas de empleadores, egresados, docentes y estudiantes relacionadas con la actualizacion curricular.',
  'Acta',
  'Director PE / CIAC',
  'Anual',
  'en_proceso',
  'alta',
  50,
  'RCD 57-2026 Actualizacion curricular 2022'
),
(
  'gestion_academica',
  'GA-004',
  'Dar seguimiento a acuerdos con docentes',
  'Seguimiento a acuerdos sobre portafolio docente, silabos mal estructurados y coordinacion entre teoria y practica.',
  'Acta / informe de seguimiento',
  'Comite academico / docentes',
  'Agosto - Noviembre',
  'pendiente',
  'alta',
  0,
  'Acta de reunion docentes'
),
(
  'gestion_academica',
  'GA-005',
  'Dar seguimiento a acuerdos con estudiantes',
  'Seguimiento a aportes estudiantiles sobre transparencia, planificacion, coherencia curricular, prerrequisitos y claridad de silabos.',
  'Acta / informe de seguimiento',
  'Comite academico',
  'Julio',
  'pendiente',
  'media',
  0,
  'Acta de reunion estudiantes'
),
(
  'gestion_academica',
  'GA-006',
  'Dar seguimiento a observaciones sobre silabos y portafolios',
  'Seguimiento a observaciones relacionadas con silabos mal estructurados, avance silabico y consistencia de materiales.',
  'Informe academico',
  'Comite academico / docentes',
  'Agosto - Noviembre',
  'pendiente',
  'alta',
  0,
  'Actas de grupos de interes'
);
