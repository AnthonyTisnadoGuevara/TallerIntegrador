from fastapi import HTTPException
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from app.agents.curricular_analyzer import analizar_texto_silabo
from app.agents.gemini_recommender import generar_recomendaciones_con_gemini
from app.services.supabase_client import supabase
from app.utils.document_reader import extraer_texto_desde_url


MODELO_LANGGRAPH_REGLAS = "langgraph_reglas_curriculares_v1"
_graph = None


class SyllabusAnalysisState(TypedDict, total=False):
    silabo_id: str
    silabo: dict
    archivo_url: str
    texto: str
    analisis: dict
    resultado_guardado: dict
    error: str


def obtener_silabo(state: SyllabusAnalysisState) -> SyllabusAnalysisState:
    silabo_id = state.get("silabo_id")
    if not silabo_id:
        raise HTTPException(status_code=400, detail="Debe indicar el id del sílabo.")

    response = (
        supabase.table("silabos")
        .select("*")
        .eq("id", silabo_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=404, detail="Sílabo no encontrado")

    silabo = response.data[0]
    return {
        **state,
        "silabo": silabo,
        "archivo_url": silabo.get("archivo_url"),
    }


def validar_archivo(state: SyllabusAnalysisState) -> SyllabusAnalysisState:
    if not state.get("archivo_url"):
        raise HTTPException(
            status_code=400,
            detail="El sílabo no tiene archivo_url para analizar.",
        )

    return state


def extraer_texto(state: SyllabusAnalysisState) -> SyllabusAnalysisState:
    try:
        texto = extraer_texto_desde_url(state["archivo_url"])
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"No se pudo descargar o leer el documento del sílabo: {error}",
        ) from error

    return {
        **state,
        "texto": texto,
    }


def analizar_contenido(state: SyllabusAnalysisState) -> SyllabusAnalysisState:
    analisis = analizar_texto_silabo(state["texto"], state["silabo"])
    analisis["modelo_usado"] = MODELO_LANGGRAPH_REGLAS

    return {
        **state,
        "analisis": analisis,
    }


def generar_recomendaciones_gemini(state: SyllabusAnalysisState) -> SyllabusAnalysisState:
    print("[LangGraph] Ejecutando nodo generar_recomendaciones_gemini")
    texto = state.get("texto", "")
    silabo = state.get("silabo", {})
    analisis = state.get("analisis", {})
    resultado_gemini = generar_recomendaciones_con_gemini(texto, silabo, analisis)

    if resultado_gemini:
        analisis["sugerencias"] = resultado_gemini.get(
            "sugerencias",
            analisis.get("sugerencias", []),
        )
        analisis["observacion_general"] = resultado_gemini.get(
            "observacion_general",
            analisis.get("observacion_general"),
        )
        analisis["recomendaciones_mejora"] = resultado_gemini.get(
            "recomendaciones_mejora",
            [],
        )
        analisis["modelo_usado"] = resultado_gemini.get(
            "modelo_usado",
            MODELO_LANGGRAPH_REGLAS,
        )

    print("[LangGraph] Modelo resultante:", analisis.get("modelo_usado"))

    return {
        **state,
        "analisis": analisis,
    }


def guardar_analisis(state: SyllabusAnalysisState) -> SyllabusAnalysisState:
    silabo_id = state["silabo_id"]
    analisis = state["analisis"]

    (
        supabase.table("analisis_silabo")
        .delete()
        .eq("silabo_id", silabo_id)
        .execute()
    )

    analisis_data = {
        "silabo_id": silabo_id,
        "resumen": analisis.get("resumen"),
        "competencias_detectadas": analisis.get("competencias_detectadas", []),
        "contenidos_detectados": analisis.get("contenidos_detectados", []),
        "resultados_aprendizaje": analisis.get("resultados_aprendizaje", []),
        "secciones_faltantes": analisis.get("secciones_faltantes", []),
        "sugerencias": analisis.get("sugerencias", []),
        "nivel_riesgo": analisis.get("nivel_riesgo", "medio"),
        "estado_analisis": "analizado",
        "modelo_usado": analisis.get("modelo_usado", MODELO_LANGGRAPH_REGLAS),
        "observacion_general": analisis.get(
            "observacion_general",
            "Análisis generado mediante LangGraph.",
        ),
    }

    insert_response = (
        supabase.table("analisis_silabo")
        .insert(analisis_data)
        .execute()
    )

    resultado_guardado = insert_response.data if insert_response.data else [analisis_data]

    return {
        **state,
        "resultado_guardado": resultado_guardado,
    }


def construir_grafo_analisis():
    graph = StateGraph(SyllabusAnalysisState)
    graph.add_node("obtener_silabo", obtener_silabo)
    graph.add_node("validar_archivo", validar_archivo)
    graph.add_node("extraer_texto", extraer_texto)
    graph.add_node("analizar_contenido", analizar_contenido)
    graph.add_node("generar_recomendaciones_gemini", generar_recomendaciones_gemini)
    graph.add_node("guardar_analisis", guardar_analisis)

    graph.add_edge(START, "obtener_silabo")
    graph.add_edge("obtener_silabo", "validar_archivo")
    graph.add_edge("validar_archivo", "extraer_texto")
    graph.add_edge("extraer_texto", "analizar_contenido")
    graph.add_edge("analizar_contenido", "generar_recomendaciones_gemini")
    graph.add_edge("generar_recomendaciones_gemini", "guardar_analisis")
    graph.add_edge("guardar_analisis", END)

    return graph.compile()


def get_graph():
    global _graph
    if _graph is None:
        _graph = construir_grafo_analisis()
    return _graph


def ejecutar_grafo_analisis_silabo(silabo_id: str) -> dict:
    graph = get_graph()
    return graph.invoke({"silabo_id": silabo_id})
