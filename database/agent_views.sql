-- =========================================================
-- VISTAS PARA DASHBOARD DE AGENTES
-- Macroproceso: Gestión de Sílabos
-- =========================================================

create or replace view dashboard_analisis_curricular as
select
    count(*) as total_analisis,

    count(*) filter (
        where nivel_riesgo = 'bajo'
    ) as riesgo_bajo,

    count(*) filter (
        where nivel_riesgo = 'medio'
    ) as riesgo_medio,

    count(*) filter (
        where nivel_riesgo = 'alto'
    ) as riesgo_alto,

    count(*) filter (
        where estado_analisis = 'analizado'
    ) as analizados,

    count(*) filter (
        where estado_analisis = 'pendiente'
    ) as pendientes

from analisis_silabo;


create or replace view dashboard_brechas_curriculares as
select
    count(*) as total_brechas,

    count(*) filter (
        where prioridad = 'alta'
    ) as brechas_alta,

    count(*) filter (
        where prioridad = 'media'
    ) as brechas_media,

    count(*) filter (
        where prioridad = 'baja'
    ) as brechas_baja,

    count(*) filter (
        where estado = 'pendiente'
    ) as pendientes,

    count(*) filter (
        where estado = 'atendida'
    ) as atendidas

from brechas_curriculares;


create or replace view dashboard_trazabilidad_curricular as
select
    count(*) as total_relaciones,

    count(*) filter (
        where tipo_relacion = 'continuidad_tematica'
    ) as continuidad_tematica,

    count(*) filter (
        where tipo_relacion = 'progresion_adecuada'
    ) as progresion_adecuada,

    count(*) filter (
        where tipo_relacion = 'repeticion'
    ) as repeticiones,

    count(*) filter (
        where tipo_relacion = 'vacio_formativo'
    ) as vacios_formativos,

    count(*) filter (
        where nivel_coherencia = 'alto'
    ) as coherencia_alta,

    count(*) filter (
        where nivel_coherencia = 'medio'
    ) as coherencia_media,

    count(*) filter (
        where nivel_coherencia = 'bajo'
    ) as coherencia_baja

from trazabilidad_curricular;