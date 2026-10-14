"""Reglas analíticas originales de Planificación Estratégica, aisladas de producción."""
from typing import Any

from typing_extensions import TypedDict


class PlanificacionState(TypedDict, total=False):
    evidencias: list
    dashboard: dict
    riesgos_detectados: list
    evidencias_criticas: list
    acciones_sugeridas: list
    resumen_base: dict
    recomendacion_gemini: dict
    resultado: dict
    error: str


def _entero(valor: Any, defecto: int = 0) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return defecto


def _avance(evidencia: dict) -> int:
    return max(0, min(100, _entero(evidencia.get("avance"), 0)))


def _codigo_titulo(evidencia: dict) -> str:
    codigo = evidencia.get("codigo") or "Sin codigo"
    titulo = evidencia.get("titulo") or "Evidencia sin titulo"
    return f"{codigo} - {titulo}"


def _normalizar_nivel_riesgo(nivel: str) -> str:
    nivel = str(nivel or "medio").strip().lower()
    return nivel if nivel in {"bajo", "medio", "alto"} else "medio"


def _riesgo_por_avance(avance_promedio: int) -> str:
    if avance_promedio < 30:
        return "alto"
    if avance_promedio <= 70:
        return "medio"
    return "bajo"


def _max_riesgo(*niveles: str) -> str:
    orden = {"bajo": 0, "medio": 1, "alto": 2}
    return max((_normalizar_nivel_riesgo(nivel) for nivel in niveles), key=lambda item: orden[item])


def _crear_accion(
    titulo: str, descripcion: str, prioridad: str, responsable: str, evidencia: dict | None = None
) -> dict:
    return {
        "titulo": titulo,
        "descripcion": descripcion,
        "prioridad": prioridad,
        "responsable_sugerido": responsable,
        "evidencia_relacionada": (evidencia or {}).get("codigo") or "",
    }


def calcular_indicadores_planificacion(state: PlanificacionState) -> PlanificacionState:
    evidencias = state.get("evidencias", [])
    total = len(evidencias)
    completadas = sum(1 for item in evidencias if item.get("estado") == "completado")
    pendientes = sum(1 for item in evidencias if item.get("estado") == "pendiente")
    en_proceso = sum(1 for item in evidencias if item.get("estado") == "en_proceso")
    observadas = sum(1 for item in evidencias if item.get("estado") == "observado")
    alta = sum(1 for item in evidencias if item.get("prioridad") == "alta")
    media = sum(1 for item in evidencias if item.get("prioridad") == "media")
    baja = sum(1 for item in evidencias if item.get("prioridad") == "baja")
    sin_archivo = sum(1 for item in evidencias if not item.get("archivo_url"))
    pendientes_alta = sum(1 for item in evidencias if item.get("estado") == "pendiente" and item.get("prioridad") == "alta")
    avance_promedio = round(sum(_avance(item) for item in evidencias) / total) if total else 0
    porcentaje_sin_archivo = round((sin_archivo / total) * 100) if total else 0
    dashboard = {
        "total": total, "pendientes": pendientes, "en_proceso": en_proceso,
        "completadas": completadas, "observadas": observadas, "avance_promedio": avance_promedio,
        "alta": alta, "media": media, "baja": baja, "sin_archivo": sin_archivo,
        "porcentaje_sin_archivo": porcentaje_sin_archivo, "pendientes_alta": pendientes_alta,
    }
    return {**state, "dashboard": dashboard}


def detectar_riesgos_estrategicos(state: PlanificacionState) -> PlanificacionState:
    evidencias = state.get("evidencias", [])
    dashboard = state.get("dashboard", {})
    riesgos = []
    evidencias_criticas = []
    acciones = []
    nivel_riesgo = _riesgo_por_avance(dashboard.get("avance_promedio", 0))

    if dashboard.get("pendientes_alta", 0) > 0:
        nivel_riesgo = _max_riesgo(nivel_riesgo, "alto")
        riesgos.append("Existen evidencias de prioridad alta en estado pendiente, lo que compromete el avance estrategico.")

    if dashboard.get("avance_promedio", 0) < 30:
        riesgos.append("El avance promedio es menor al 30%, con riesgo alto de retraso en la ejecucion.")
    elif dashboard.get("avance_promedio", 0) <= 70:
        riesgos.append("El avance promedio se encuentra entre 30% y 70%, con riesgo medio de cumplimiento.")
    else:
        riesgos.append("El avance promedio supera el 70%, con riesgo bajo si se mantiene el seguimiento.")

    inconsistencias = [item for item in evidencias if item.get("estado") == "completado" and _avance(item) < 100]
    if inconsistencias:
        nivel_riesgo = _max_riesgo(nivel_riesgo, "medio")
        riesgos.append("Hay evidencias completadas con avance menor a 100%, lo que genera inconsistencia de seguimiento.")
        evidencias_criticas.extend(f"{_codigo_titulo(item)}: completada con avance {_avance(item)}%." for item in inconsistencias)

    pendientes_alta = [item for item in evidencias if item.get("estado") == "pendiente" and item.get("prioridad") == "alta"]
    for item in pendientes_alta:
        evidencias_criticas.append(f"{_codigo_titulo(item)}: prioridad alta pendiente.")
        acciones.append(_crear_accion(
            "Atender evidencia estrategica pendiente",
            "Definir responsable, fecha de cierre y evidencia documental para resolver la actividad prioritaria.",
            "alta", item.get("responsable") or "Director del programa", item,
        ))

    if dashboard.get("porcentaje_sin_archivo", 0) >= 50:
        nivel_riesgo = _max_riesgo(nivel_riesgo, "medio")
        riesgos.append("La mayoria de evidencias no cuenta con archivo_url, por lo que falta sustento documental.")
        acciones.append(_crear_accion(
            "Completar sustento documental de evidencias",
            "Cargar o vincular documentos de respaldo para evidencias sin archivo_url.",
            "media", "Responsables del macroproceso",
        ))

    if dashboard.get("completadas", 0) == 0:
        nivel_riesgo = _max_riesgo(nivel_riesgo, "alto")
        riesgos.append("No hay evidencias completadas, lo que indica bajo nivel de ejecucion del plan.")
        acciones.append(_crear_accion(
            "Cerrar al menos una evidencia prioritaria",
            "Seleccionar una evidencia de alto impacto y formalizar su cumplimiento con archivo de respaldo.",
            "alta", "Director del programa",
        ))

    if not riesgos:
        riesgos.append("No se detectaron riesgos criticos con las reglas actuales.")
    resumen = (
        f"Se analizaron {dashboard.get('total', 0)} evidencias de planificacion estrategica. "
        f"El avance promedio es {dashboard.get('avance_promedio', 0)}%, con "
        f"{dashboard.get('pendientes', 0)} pendientes, {dashboard.get('en_proceso', 0)} en proceso "
        f"y {dashboard.get('completadas', 0)} completadas."
    )
    resumen_base = {
        **dashboard, "nivel_riesgo": nivel_riesgo, "resumen": resumen,
        "riesgos_detectados": riesgos, "evidencias_criticas": evidencias_criticas,
        "acciones_sugeridas": acciones,
        "observacion_general": "Diagnostico base calculado por reglas del agente de planificacion estrategica.",
    }
    return {
        **state, "riesgos_detectados": riesgos, "evidencias_criticas": evidencias_criticas,
        "acciones_sugeridas": acciones, "resumen_base": resumen_base,
    }
