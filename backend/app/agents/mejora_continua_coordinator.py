from typing import Any

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from app.agents.gemini_mejora_continua_recommender import (
    generar_diagnostico_mejora_continua_con_gemini,
)
from app.services.supabase_client import supabase


_graph_coordinador = None


class CoordinadorState(TypedDict, total=False):
    evidencias: list
    acciones: list
    brechas: list
    silabos: list
    datos_planificacion: dict
    datos_gestion_academica: dict
    datos_gestion_silabos: dict
    indicadores_generales: dict
    hallazgos_integrados: list
    evidencias_criticas: list
    acciones_prioritarias: list
    riesgos_detectados: dict
    recomendacion_gemini: dict
    resultado: dict


def _entero(valor: Any, defecto: int = 0) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return defecto


def _avance(evidencia: dict) -> int:
    return max(0, min(100, _entero(evidencia.get("avance"), 0)))


def _promedio_avance(evidencias: list[dict]) -> int:
    if not evidencias:
        return 0
    return round(sum(_avance(item) for item in evidencias) / len(evidencias))


def _normalizar_nivel_riesgo(nivel: str) -> str:
    nivel = str(nivel or "medio").strip().lower()
    return nivel if nivel in {"bajo", "medio", "alto"} else "medio"


def _riesgo_por_avance(avance: int, umbral_alto: int = 30, umbral_medio: int = 70) -> str:
    if avance < umbral_alto:
        return "alto"
    if avance < umbral_medio:
        return "medio"
    return "bajo"


def _codigo_titulo(evidencia: dict) -> str:
    codigo = evidencia.get("codigo") or "Sin codigo"
    titulo = evidencia.get("titulo") or "Evidencia sin titulo"
    return f"{codigo} - {titulo}"


def _safe_select(tabla: str) -> list:
    try:
        response = supabase.table(tabla).select("*").execute()
        return response.data or []
    except Exception as e:
        print(f"[Coordinador IA] No se pudo leer {tabla}: {type(e).__name__}")
        return []


def _crear_accion(
    titulo: str,
    descripcion: str,
    prioridad: str,
    macroproceso: str,
    responsable: str = "Comite academico",
) -> dict:
    return {
        "titulo": titulo,
        "descripcion": descripcion,
        "prioridad": prioridad,
        "macroproceso_relacionado": macroproceso,
        "responsable_sugerido": responsable,
    }


def _contar_por_estado(items: list[dict], estado: str) -> int:
    return sum(1 for item in items if item.get("estado") == estado)


def obtener_datos_generales(state: CoordinadorState) -> CoordinadorState:
    print("[Coordinador IA] Ejecutando agente coordinador de mejora continua")
    return {
        **state,
        "evidencias": _safe_select("macroproceso_evidencias"),
        "acciones": _safe_select("acciones_mejora"),
        "brechas": _safe_select("brechas_curriculares"),
        "silabos": _safe_select("silabos"),
    }


def analizar_planificacion(state: CoordinadorState) -> CoordinadorState:
    evidencias = [
        item
        for item in state.get("evidencias", [])
        if item.get("macroproceso") == "planificacion_estrategica"
    ]
    avance = _promedio_avance(evidencias)
    pendientes_alta = [
        item for item in evidencias if item.get("prioridad") == "alta" and item.get("estado") == "pendiente"
    ]
    completadas_sin_archivo = [
        item for item in evidencias if item.get("estado") == "completado" and not item.get("archivo_url")
    ]
    hallazgos = []
    evidencias_criticas = []
    acciones = []
    riesgo = _riesgo_por_avance(avance, 30, 70)

    if avance < 30:
        hallazgos.append("Avance estrategico menor al 30%.")
    if pendientes_alta:
        riesgo = "alto"
        hallazgos.append("Evidencias estrategicas de prioridad alta pendientes.")
        evidencias_criticas.extend(f"{_codigo_titulo(item)}: prioridad alta pendiente." for item in pendientes_alta)
        acciones.append(
            _crear_accion(
                "Atender evidencias estrategicas de alta prioridad",
                "Definir responsables y fechas para cerrar evidencias estrategicas pendientes.",
                "alta",
                "Planificacion Estrategica",
                "Director del programa",
            )
        )
    if completadas_sin_archivo:
        hallazgos.append("Evidencias estrategicas completadas sin sustento documental.")
        evidencias_criticas.extend(f"{_codigo_titulo(item)}: completada sin archivo_url." for item in completadas_sin_archivo)
    if not hallazgos:
        hallazgos.append("Seguimiento estrategico sin hallazgos criticos por reglas.")

    datos = {
        "macroproceso": "Planificacion Estrategica",
        "nivel_riesgo": riesgo,
        "avance_promedio": avance,
        "total": len(evidencias),
        "pendientes": _contar_por_estado(evidencias, "pendiente"),
        "en_proceso": _contar_por_estado(evidencias, "en_proceso"),
        "completadas": _contar_por_estado(evidencias, "completado"),
        "observadas": _contar_por_estado(evidencias, "observado"),
        "hallazgos": hallazgos,
    }

    return {
        **state,
        "datos_planificacion": datos,
        "evidencias_criticas": state.get("evidencias_criticas", []) + evidencias_criticas,
        "acciones_prioritarias": state.get("acciones_prioritarias", []) + acciones,
    }


def analizar_gestion_academica(state: CoordinadorState) -> CoordinadorState:
    evidencias = [
        item
        for item in state.get("evidencias", [])
        if item.get("macroproceso") == "gestion_academica"
    ]
    avance = _promedio_avance(evidencias)
    pendientes_alta = [
        item for item in evidencias if item.get("prioridad") == "alta" and item.get("estado") == "pendiente"
    ]
    completadas_sin_archivo = [
        item for item in evidencias if item.get("estado") == "completado" and not item.get("archivo_url")
    ]
    acuerdos_pendientes = [
        item
        for item in evidencias
        if item.get("estado") in {"pendiente", "en_proceso", "observado"}
        and any(
            palabra in str(
                f"{item.get('titulo', '')} {item.get('descripcion', '')} {item.get('tipo_evidencia', '')}"
            ).lower()
            for palabra in ["acta", "acuerdo", "docente", "estudiante"]
        )
    ]
    hallazgos = []
    evidencias_criticas = []
    acciones = []
    riesgo = _riesgo_por_avance(avance, 50, 70)

    if avance < 50:
        hallazgos.append("Avance academico menor al 50%.")
    if pendientes_alta:
        riesgo = "alto"
        hallazgos.append("Evidencias academicas de prioridad alta pendientes.")
        evidencias_criticas.extend(f"{_codigo_titulo(item)}: prioridad alta pendiente." for item in pendientes_alta)
    if acuerdos_pendientes:
        riesgo = "alto" if riesgo == "medio" else riesgo
        hallazgos.append("Acuerdos academicos pendientes de seguimiento.")
        acciones.append(
            _crear_accion(
                "Cerrar acuerdos academicos pendientes",
                "Registrar responsables, compromisos y evidencia de cierre de acuerdos con docentes o estudiantes.",
                "alta",
                "Gestion Academica",
                "Comite academico",
            )
        )
    if completadas_sin_archivo:
        hallazgos.append("Evidencias academicas completadas sin sustento documental.")
        evidencias_criticas.extend(f"{_codigo_titulo(item)}: completada sin archivo_url." for item in completadas_sin_archivo)
    if not hallazgos:
        hallazgos.append("Gestion academica sin hallazgos criticos por reglas.")

    datos = {
        "macroproceso": "Gestion Academica",
        "nivel_riesgo": riesgo,
        "avance_promedio": avance,
        "total": len(evidencias),
        "pendientes": _contar_por_estado(evidencias, "pendiente"),
        "en_proceso": _contar_por_estado(evidencias, "en_proceso"),
        "completadas": _contar_por_estado(evidencias, "completado"),
        "observadas": _contar_por_estado(evidencias, "observado"),
        "hallazgos": hallazgos,
    }

    return {
        **state,
        "datos_gestion_academica": datos,
        "evidencias_criticas": state.get("evidencias_criticas", []) + evidencias_criticas,
        "acciones_prioritarias": state.get("acciones_prioritarias", []) + acciones,
    }


def analizar_gestion_silabos(state: CoordinadorState) -> CoordinadorState:
    silabos = state.get("silabos", [])
    brechas = state.get("brechas", [])
    acciones_mejora = state.get("acciones", [])
    total_silabos = len(silabos)
    silabos_completos = sum(1 for item in silabos if item.get("estado") == "completo")
    avance = round((silabos_completos / total_silabos) * 100) if total_silabos else 0
    brechas_alta = [item for item in brechas if item.get("prioridad") == "alta"]
    acciones_pendientes = [item for item in acciones_mejora if item.get("estado") == "pendiente"]
    acciones_alta = [item for item in acciones_mejora if item.get("prioridad") == "alta" and item.get("estado") != "atendida"]
    hallazgos = []
    acciones = []
    riesgo = _riesgo_por_avance(avance, 50, 80)

    if brechas_alta:
        riesgo = "alto"
        hallazgos.append("Existen brechas curriculares de prioridad alta.")
        acciones.append(
            _crear_accion(
                "Priorizar cierre de brechas curriculares altas",
                "Revisar brechas de alta prioridad y asociarlas a acciones de mejora verificables.",
                "alta",
                "Gestion de Silabos",
                "Coordinacion academica",
            )
        )
    if acciones_pendientes or acciones_alta:
        riesgo = "alto" if acciones_alta else _normalizar_nivel_riesgo(riesgo)
        hallazgos.append("Existen acciones de mejora pendientes o de alta prioridad sin cierre.")
    if brechas and not acciones_mejora:
        riesgo = "alto"
        hallazgos.append("Hay brechas curriculares sin acciones de mejora asociadas.")
    if total_silabos == 0:
        riesgo = "medio"
        hallazgos.append("No hay silabos disponibles para diagnostico integral.")
    if not hallazgos:
        hallazgos.append("Gestion de silabos sin hallazgos criticos por reglas.")

    datos = {
        "macroproceso": "Gestion de Silabos",
        "nivel_riesgo": riesgo,
        "avance_promedio": avance,
        "total_silabos": total_silabos,
        "total_brechas": len(brechas),
        "brechas_alta_prioridad": len(brechas_alta),
        "acciones_pendientes": len(acciones_pendientes),
        "hallazgos": hallazgos,
    }

    return {
        **state,
        "datos_gestion_silabos": datos,
        "acciones_prioritarias": state.get("acciones_prioritarias", []) + acciones,
    }


def integrar_hallazgos(state: CoordinadorState) -> CoordinadorState:
    datos = [
        state.get("datos_planificacion", {}),
        state.get("datos_gestion_academica", {}),
        state.get("datos_gestion_silabos", {}),
    ]
    hallazgos = []
    evidencias = state.get("evidencias", [])
    acciones = state.get("acciones", [])
    brechas = state.get("brechas", [])

    for item in datos:
        hallazgos.extend(item.get("hallazgos", []))

    if sum(1 for item in datos if item.get("avance_promedio", 0) < 50) >= 2:
        hallazgos.append("Bajo avance repetido en dos o mas macroprocesos.")
    if any(item.get("estado") == "completado" and not item.get("archivo_url") for item in evidencias):
        hallazgos.append("Falta de sustento documental en evidencias completadas.")
    if any(item.get("estado") == "pendiente" for item in acciones):
        hallazgos.append("Acciones de mejora pendientes de cierre.")
    if any(item.get("prioridad") == "alta" for item in brechas):
        hallazgos.append("Brechas curriculares de alta prioridad sin atencion integral.")
    if any(item.get("prioridad") == "alta" and item.get("estado") == "pendiente" for item in evidencias):
        hallazgos.append("Evidencias de prioridad alta pendientes en macroprocesos.")

    # Preserve order while removing duplicates.
    hallazgos_unicos = list(dict.fromkeys(hallazgos))
    return {
        **state,
        "hallazgos_integrados": hallazgos_unicos,
    }


def calcular_riesgo_general(state: CoordinadorState) -> CoordinadorState:
    datos_planificacion = state.get("datos_planificacion", {})
    datos_gestion_academica = state.get("datos_gestion_academica", {})
    datos_gestion_silabos = state.get("datos_gestion_silabos", {})
    evidencias = state.get("evidencias", [])
    silabos = state.get("silabos", [])
    brechas = state.get("brechas", [])
    acciones = state.get("acciones", [])
    brechas_alta = sum(1 for item in brechas if item.get("prioridad") == "alta")
    acciones_pendientes = sum(1 for item in acciones if item.get("estado") == "pendiente")
    acciones_en_proceso = sum(1 for item in acciones if item.get("estado") == "en_proceso")
    acciones_completadas = sum(
        1 for item in acciones if item.get("estado") in {"atendida", "completada", "completo"}
    )
    acciones_alta_pendientes = sum(
        1 for item in acciones if item.get("prioridad") == "alta" and item.get("estado") != "atendida"
    )
    estado_macroprocesos = [
        datos_planificacion,
        datos_gestion_academica,
        datos_gestion_silabos,
    ]
    riesgos_altos = sum(1 for item in estado_macroprocesos if item.get("nivel_riesgo") == "alto")
    riesgos_medios = sum(1 for item in estado_macroprocesos if item.get("nivel_riesgo") == "medio")

    if not evidencias and not silabos and not brechas and not acciones:
        nivel = "medio"
        advertencia = "No hay datos suficientes para generar el diagnostico integral."
    elif riesgos_altos >= 2 or brechas_alta >= 3 or acciones_alta_pendientes >= 3:
        nivel = "alto"
        advertencia = ""
    elif riesgos_altos >= 1 or riesgos_medios >= 1 or state.get("evidencias_criticas"):
        nivel = "medio"
        advertencia = ""
    else:
        nivel = "bajo"
        advertencia = ""

    indicadores = {
        "total_macroprocesos": 3,
        "total_evidencias_macroprocesos": len(evidencias),
        "total_silabos": len(silabos),
        "total_brechas": len(brechas),
        "brechas_alta_prioridad": brechas_alta,
        "total_acciones_mejora": len(acciones),
        "acciones_pendientes": acciones_pendientes,
        "acciones_en_proceso": acciones_en_proceso,
        "acciones_completadas": acciones_completadas,
    }
    resumen = (
        f"Diagnostico integrado de {indicadores['total_macroprocesos']} macroprocesos: "
        f"{indicadores['total_evidencias_macroprocesos']} evidencias, "
        f"{indicadores['total_silabos']} silabos, {indicadores['total_brechas']} brechas y "
        f"{indicadores['total_acciones_mejora']} acciones de mejora."
    )
    if advertencia:
        resumen = advertencia

    decision = (
        "Convocar sesion del comite academico y priorizar acciones correctivas de alto impacto."
        if nivel == "alto"
        else "Mantener seguimiento con responsables y fechas de cierre para hallazgos moderados."
        if nivel == "medio"
        else "Continuar monitoreo periodico y consolidar evidencias de cumplimiento."
    )
    riesgos_detectados = {
        "nivel_riesgo_general": nivel,
        "resumen_general": resumen,
        "evidencias_criticas": state.get("evidencias_criticas", []),
        "decision_sugerida": decision,
        "observacion_general": advertencia or "Diagnostico integrado calculado por reglas del coordinador.",
    }

    return {
        **state,
        "indicadores_generales": indicadores,
        "riesgos_detectados": riesgos_detectados,
    }


def generar_recomendaciones_gemini(state: CoordinadorState) -> CoordinadorState:
    resultado = generar_diagnostico_mejora_continua_con_gemini(
        datos_planificacion=state.get("datos_planificacion", {}),
        datos_gestion_academica=state.get("datos_gestion_academica", {}),
        datos_gestion_silabos=state.get("datos_gestion_silabos", {}),
        indicadores_generales=state.get("indicadores_generales", {}),
        hallazgos_integrados=state.get("hallazgos_integrados", []),
        riesgos_detectados=state.get("riesgos_detectados", {}),
        acciones_prioritarias_base=state.get("acciones_prioritarias", []),
    )
    return {
        **state,
        "recomendacion_gemini": resultado,
    }


def preparar_resultado(state: CoordinadorState) -> CoordinadorState:
    recomendacion = state.get("recomendacion_gemini", {})
    fallback_estado = [
        state.get("datos_planificacion", {}),
        state.get("datos_gestion_academica", {}),
        state.get("datos_gestion_silabos", {}),
    ]
    resultado = {
        "modelo_usado": recomendacion.get("modelo_usado") or "langgraph_reglas_coordinador_mejora_continua_v1",
        "nivel_riesgo_general": _normalizar_nivel_riesgo(
            recomendacion.get("nivel_riesgo_general")
            or state.get("riesgos_detectados", {}).get("nivel_riesgo_general")
        ),
        "resumen_general": recomendacion.get("resumen_general")
        or state.get("riesgos_detectados", {}).get("resumen_general")
        or "",
        "estado_macroprocesos": recomendacion.get("estado_macroprocesos") or fallback_estado,
        "indicadores_generales": recomendacion.get("indicadores_generales") or state.get("indicadores_generales", {}),
        "macroprocesos_criticos": recomendacion.get("macroprocesos_criticos") or [
            item.get("macroproceso")
            for item in fallback_estado
            if item.get("nivel_riesgo") == "alto"
        ],
        "hallazgos_integrados": recomendacion.get("hallazgos_integrados") or state.get("hallazgos_integrados", []),
        "evidencias_criticas": recomendacion.get("evidencias_criticas") or state.get("evidencias_criticas", []),
        "acciones_prioritarias": recomendacion.get("acciones_prioritarias") or state.get("acciones_prioritarias", []),
        "recomendaciones_comite": recomendacion.get("recomendaciones_comite") or [],
        "decision_sugerida": recomendacion.get("decision_sugerida")
        or state.get("riesgos_detectados", {}).get("decision_sugerida")
        or "",
        "observacion_general": recomendacion.get("observacion_general")
        or state.get("riesgos_detectados", {}).get("observacion_general")
        or "",
    }
    print("[Coordinador IA] Modelo resultante:", resultado.get("modelo_usado"))
    return {
        **state,
        "resultado": resultado,
    }


def construir_grafo_coordinador_mejora_continua():
    graph = StateGraph(CoordinadorState)
    graph.add_node("obtener_datos_generales", obtener_datos_generales)
    graph.add_node("analizar_planificacion", analizar_planificacion)
    graph.add_node("analizar_gestion_academica", analizar_gestion_academica)
    graph.add_node("analizar_gestion_silabos", analizar_gestion_silabos)
    graph.add_node("integrar_hallazgos", integrar_hallazgos)
    graph.add_node("calcular_riesgo_general", calcular_riesgo_general)
    graph.add_node("generar_recomendaciones_gemini", generar_recomendaciones_gemini)
    graph.add_node("preparar_resultado", preparar_resultado)

    graph.add_edge(START, "obtener_datos_generales")
    graph.add_edge("obtener_datos_generales", "analizar_planificacion")
    graph.add_edge("analizar_planificacion", "analizar_gestion_academica")
    graph.add_edge("analizar_gestion_academica", "analizar_gestion_silabos")
    graph.add_edge("analizar_gestion_silabos", "integrar_hallazgos")
    graph.add_edge("integrar_hallazgos", "calcular_riesgo_general")
    graph.add_edge("calcular_riesgo_general", "generar_recomendaciones_gemini")
    graph.add_edge("generar_recomendaciones_gemini", "preparar_resultado")
    graph.add_edge("preparar_resultado", END)

    return graph.compile()


def get_graph_coordinador_mejora_continua():
    global _graph_coordinador
    if _graph_coordinador is None:
        _graph_coordinador = construir_grafo_coordinador_mejora_continua()
    return _graph_coordinador


def ejecutar_grafo_coordinador_mejora_continua() -> dict:
    graph = get_graph_coordinador_mejora_continua()
    state = graph.invoke({})
    return state.get("resultado", {})
