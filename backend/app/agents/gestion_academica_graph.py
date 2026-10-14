from langgraph.graph import END, START, StateGraph

from app.agents.gestion_academica_analysis import (
    GestionAcademicaState,
    _avance,
    _crear_accion,
    _codigo_titulo,
    _entero,
    _max_riesgo,
    _normalizar_nivel_riesgo,
    _normalizar_texto,
    _riesgo_por_avance,
    _texto_evidencia,
    calcular_indicadores_gestion_academica,
    clasificar_evidencias_academicas,
    detectar_riesgos_academicos,
)
from app.agents.gemini_gestion_academica_recommender import (
    generar_recomendaciones_gestion_academica_con_gemini,
)
from app.services.supabase_client import supabase


MACROPROCESO_GESTION_ACADEMICA = "gestion_academica"
_graph_gestion_academica = None


def obtener_evidencias_gestion_academica(state: GestionAcademicaState) -> GestionAcademicaState:
    print("[Gestion Academica IA] Ejecutando agente de gestion academica")
    response = (
        supabase.table("macroproceso_evidencias")
        .select("*")
        .eq("macroproceso", MACROPROCESO_GESTION_ACADEMICA)
        .execute()
    )

    return {
        **state,
        "evidencias": response.data or [],
    }


def detectar_acuerdos_pendientes(state: GestionAcademicaState) -> GestionAcademicaState:
    clasificacion = state.get("clasificacion", {})
    acuerdos = []
    acciones = []

    candidatos = (
        clasificacion.get("actas", [])
        + clasificacion.get("acuerdos_docentes", [])
        + clasificacion.get("acuerdos_estudiantes", [])
    )
    vistos = set()
    for evidencia in candidatos:
        evidencia_id = evidencia.get("id") or evidencia.get("codigo")
        if evidencia_id in vistos:
            continue
        vistos.add(evidencia_id)

        if evidencia.get("estado") in {"pendiente", "en_proceso", "observado"}:
            acuerdos.append(f"{_codigo_titulo(evidencia)}: requiere seguimiento de acuerdos academicos.")
            acciones.append(
                _crear_accion(
                    "Dar seguimiento a acuerdos academicos",
                    "Registrar responsables, compromisos y evidencia de cierre para el acuerdo pendiente.",
                    "alta" if evidencia.get("prioridad") == "alta" else "media",
                    evidencia.get("responsable") or "Comite academico",
                    evidencia,
                )
            )

    return {
        **state,
        "acuerdos_pendientes": acuerdos,
        "acciones_sugeridas": acciones,
    }


def generar_recomendaciones_gemini(state: GestionAcademicaState) -> GestionAcademicaState:
    resultado = generar_recomendaciones_gestion_academica_con_gemini(
        evidencias=state.get("evidencias", []),
        indicadores=state.get("indicadores", {}),
        riesgos_detectados=state.get("riesgos_detectados", []),
        acuerdos_pendientes=state.get("acuerdos_pendientes", []),
        observaciones_academicas=state.get("observaciones_academicas", []),
        resumen_base=state.get("resumen_base", {}),
    )

    return {
        **state,
        "recomendacion_gemini": resultado,
    }


def preparar_resultado(state: GestionAcademicaState) -> GestionAcademicaState:
    recomendacion = state.get("recomendacion_gemini", {})
    resumen_base = state.get("resumen_base", {})

    resultado = {
        "modelo_usado": recomendacion.get("modelo_usado") or "langgraph_reglas_gestion_academica_v1",
        "nivel_riesgo": _normalizar_nivel_riesgo(
            recomendacion.get("nivel_riesgo") or resumen_base.get("nivel_riesgo")
        ),
        "resumen": recomendacion.get("resumen") or resumen_base.get("resumen") or "",
        "indicadores": recomendacion.get("indicadores") or state.get("indicadores", {}),
        "riesgos": recomendacion.get("riesgos") or state.get("riesgos_detectados", []),
        "acuerdos_pendientes": recomendacion.get("acuerdos_pendientes") or state.get("acuerdos_pendientes", []),
        "observaciones_academicas": recomendacion.get("observaciones_academicas") or state.get("observaciones_academicas", []),
        "evidencias_criticas": recomendacion.get("evidencias_criticas") or state.get("evidencias_criticas", []),
        "recomendaciones": recomendacion.get("recomendaciones") or [],
        "acciones_sugeridas": recomendacion.get("acciones_sugeridas") or state.get("acciones_sugeridas", []),
        "observacion_general": recomendacion.get("observacion_general")
        or resumen_base.get("observacion_general")
        or "",
    }

    print("[Gestion Academica IA] Modelo resultante:", resultado.get("modelo_usado"))
    return {
        **state,
        "resultado": resultado,
    }


def construir_grafo_gestion_academica():
    graph = StateGraph(GestionAcademicaState)
    graph.add_node("obtener_evidencias_gestion_academica", obtener_evidencias_gestion_academica)
    graph.add_node("calcular_indicadores_gestion_academica", calcular_indicadores_gestion_academica)
    graph.add_node("clasificar_evidencias_academicas", clasificar_evidencias_academicas)
    graph.add_node("detectar_acuerdos_pendientes", detectar_acuerdos_pendientes)
    graph.add_node("detectar_riesgos_academicos", detectar_riesgos_academicos)
    graph.add_node("generar_recomendaciones_gemini", generar_recomendaciones_gemini)
    graph.add_node("preparar_resultado", preparar_resultado)

    graph.add_edge(START, "obtener_evidencias_gestion_academica")
    graph.add_edge("obtener_evidencias_gestion_academica", "calcular_indicadores_gestion_academica")
    graph.add_edge("calcular_indicadores_gestion_academica", "clasificar_evidencias_academicas")
    graph.add_edge("clasificar_evidencias_academicas", "detectar_acuerdos_pendientes")
    graph.add_edge("detectar_acuerdos_pendientes", "detectar_riesgos_academicos")
    graph.add_edge("detectar_riesgos_academicos", "generar_recomendaciones_gemini")
    graph.add_edge("generar_recomendaciones_gemini", "preparar_resultado")
    graph.add_edge("preparar_resultado", END)

    return graph.compile()


def get_graph_gestion_academica():
    global _graph_gestion_academica
    if _graph_gestion_academica is None:
        _graph_gestion_academica = construir_grafo_gestion_academica()
    return _graph_gestion_academica


def ejecutar_grafo_gestion_academica() -> dict:
    graph = get_graph_gestion_academica()
    state = graph.invoke({})
    return state.get("resultado", {})
