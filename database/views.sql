-- ==========================================================
-- VISTAS PARA DASHBOARD - GESTIÓN DE SÍLABOS
-- ==========================================================

create or replace view dashboard_silabos as
select
    count(*) as total_silabos,

    count(*) filter (
        where estado = 'completo'
    ) as silabos_completos,

    count(*) filter (
        where estado = 'observado'
    ) as silabos_observados,

    count(*) filter (
        where estado = 'incompleto'
    ) as silabos_incompletos,

    count(*) filter (
        where estado = 'pendiente'
    ) as silabos_pendientes,

    round(avg(porcentaje_cumplimiento), 2) as cumplimiento_promedio
from silabos;


create or replace view dashboard_silabos_por_ciclo as
select
    ciclo,
    count(*) as total_silabos,

    count(*) filter (
        where estado = 'completo'
    ) as completos,

    count(*) filter (
        where estado = 'observado'
    ) as observados,

    count(*) filter (
        where estado = 'incompleto'
    ) as incompletos,

    count(*) filter (
        where estado = 'pendiente'
    ) as pendientes,

    round(avg(porcentaje_cumplimiento), 2) as cumplimiento_promedio
from silabos
group by ciclo
order by ciclo;