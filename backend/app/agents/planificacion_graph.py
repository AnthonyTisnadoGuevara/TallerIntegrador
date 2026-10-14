from langgraph.graph import END, START, StateGraph

from app.agents.planificacion_analysis import (
    PlanificacionState,
    _avance,
    _crear_accion,
    _entero,
    _max_riesgo,
    _normalizar_nivel_riesgo,
    _riesgo_por_avance,
    _codigo_titulo,
    calcular_indicadores_planificacion,
    detectar_riesgos_estrategicos,
)
from app.agents.gemini_planificacion_recommender import (
    generar_recomendaciones_planificacion_con_gemini,
)
from app.services.supabase_client import supabase


MACROPROCESO_PLANIFICACION = "planificacion_estrategica"
_graph_planificacion = None


def obtener_evidencias_planificacion(state: PlanificacionState) -> PlanificacionState:
    print("[Planificación IA] Ejecutando agente de planificación estratégica")
    response = (
        supabase.table("macroproceso_evidencias")
        .select("*")
        .eq("macroproceso", MACROPROCESO_PLANIFICACION)
        .execute()
    )

    evidencias = response.data or []
    return {
        **state,
        "evidencias": evidencias,
    }


def generar_recomendaciones_gemini(state: PlanificacionState) -> PlanificacionState:
    resultado = generar_recomendaciones_planificacion_con_gemini(
        evidencias=state.get("evidencias", []),
        dashboard=state.get("dashboard", {}),
        riesgos_detectados=state.get("riesgos_detectados", []),
        resumen_base=state.get("resumen_base", {}),
    )

    return {
        **state,
        "recomendacion_gemini": resultado,
    }


def preparar_resultado(state: PlanificacionState) -> PlanificacionState:
    recomendacion = state.get("recomendacion_gemini", {})
    resumen_base = state.get("resumen_base", {})

    resultado = {
        "modelo_usado": recomendacion.get("modelo_usado") or "langgraph_reglas_planificacion_v1",
        "nivel_riesgo": _normalizar_nivel_riesgo(
            recomendacion.get("nivel_riesgo") or resumen_base.get("nivel_riesgo")
        ),
        "resumen": recomendacion.get("resumen") or resumen_base.get("resumen") or "",
        "riesgos": recomendacion.get("riesgos") or state.get("riesgos_detectados", []),
        "evidencias_criticas": recomendacion.get("evidencias_criticas") or state.get("evidencias_criticas", []),
        "recomendaciones": recomendacion.get("recomendaciones") or [],
        "acciones_sugeridas": recomendacion.get("acciones_sugeridas") or state.get("acciones_sugeridas", []),
        "observacion_general": recomendacion.get("observacion_general")
        or resumen_base.get("observacion_general")
        or "",
        "dashboard": state.get("dashboard", {}),
    }

    return {
        **state,
        "resultado": resultado,
    }


def guardar_o_devolver_analisis(state: PlanificacionState) -> PlanificacionState:
    resultado = state.get("resultado", {})
    print("[Planificación IA] Modelo resultante:", resultado.get("modelo_usado"))
    return state


def construir_grafo_planificacion():
    graph = StateGraph(PlanificacionState)
    graph.add_node("obtener_evidencias_planificacion", obtener_evidencias_planificacion)
    graph.add_node("calcular_indicadores_planificacion", calcular_indicadores_planificacion)
    graph.add_node("detectar_riesgos_estrategicos", detectar_riesgos_estrategicos)
    graph.add_node("generar_recomendaciones_gemini", generar_recomendaciones_gemini)
    graph.add_node("preparar_resultado", preparar_resultado)
    graph.add_node("guardar_o_devolver_analisis", guardar_o_devolver_analisis)

    graph.add_edge(START, "obtener_evidencias_planificacion")
    graph.add_edge("obtener_evidencias_planificacion", "calcular_indicadores_planificacion")
    graph.add_edge("calcular_indicadores_planificacion", "detectar_riesgos_estrategicos")
    graph.add_edge("detectar_riesgos_estrategicos", "generar_recomendaciones_gemini")
    graph.add_edge("generar_recomendaciones_gemini", "preparar_resultado")
    graph.add_edge("preparar_resultado", "guardar_o_devolver_analisis")
    graph.add_edge("guardar_o_devolver_analisis", END)

    return graph.compile()


def get_graph_planificacion():
    global _graph_planificacion
    if _graph_planificacion is None:
        _graph_planificacion = construir_grafo_planificacion()
    return _graph_planificacion


def ejecutar_grafo_planificacion() -> dict:
    graph = get_graph_planificacion()
    state = graph.invoke({})
    return state.get("resultado", {})
