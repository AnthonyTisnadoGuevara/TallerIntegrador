import json
import os

try:
    from google import genai
except ImportError:  # pragma: no cover - fallback when dependency is not installed
    genai = None


MODELO_REGLAS_PLANIFICACION = "langgraph_reglas_planificacion_v1"
MODELO_GEMINI_PLANIFICACION = "langgraph_gemini_planificacion_v1"
NIVELES_RIESGO_VALIDOS = {"bajo", "medio", "alto"}
PRIORIDADES_VALIDAS = {"alta", "media", "baja"}


def limpiar_respuesta_json(texto: str) -> str:
    texto = (texto or "").strip()
    texto = texto.replace("```json", "").replace("```", "").strip()
    inicio = texto.find("{")
    fin = texto.rfind("}")
    if inicio != -1 and fin != -1:
        return texto[inicio:fin + 1]
    return texto


def _parsear_json(texto: str) -> dict:
    texto_limpio = limpiar_respuesta_json(texto)
    if not texto_limpio:
        raise ValueError("Gemini no devolvio contenido.")
    return json.loads(texto_limpio)


def _normalizar_lista(valor) -> list:
    if isinstance(valor, list):
        return [str(item) for item in valor if item]
    if valor:
        return [str(valor)]
    return []


def _normalizar_acciones(valor) -> list[dict]:
    acciones = valor if isinstance(valor, list) else []
    resultado = []

    for accion in acciones:
        if not isinstance(accion, dict):
            continue
        prioridad = str(accion.get("prioridad") or "media").strip().lower()
        if prioridad not in PRIORIDADES_VALIDAS:
            prioridad = "media"
        resultado.append(
            {
                "titulo": str(accion.get("titulo") or "Accion sugerida"),
                "descripcion": str(accion.get("descripcion") or "Sin descripcion."),
                "prioridad": prioridad,
                "responsable_sugerido": str(accion.get("responsable_sugerido") or "Responsable por definir"),
                "evidencia_relacionada": str(accion.get("evidencia_relacionada") or ""),
            }
        )

    return resultado


def _fallback_reglas(
    riesgos_detectados: list,
    resumen_base: dict,
    evidencias_criticas: list | None = None,
    acciones_sugeridas: list | None = None,
) -> dict:
    nivel_riesgo = resumen_base.get("nivel_riesgo", "medio")
    if nivel_riesgo not in NIVELES_RIESGO_VALIDOS:
        nivel_riesgo = "medio"

    recomendaciones = []
    if resumen_base.get("pendientes_alta", 0) > 0:
        recomendaciones.append(
            "Priorizar las evidencias de alta prioridad pendientes y asignar responsables con fechas de cierre."
        )
    if resumen_base.get("porcentaje_sin_archivo", 0) >= 50:
        recomendaciones.append(
            "Completar el sustento documental de las evidencias para fortalecer la trazabilidad del plan."
        )
    if resumen_base.get("avance_promedio", 0) < 70:
        recomendaciones.append(
            "Actualizar el avance de cada evidencia y revisar el cronograma del Plan General de Desarrollo."
        )
    if not recomendaciones:
        recomendaciones.append(
            "Mantener el seguimiento periodico y documentar los avances alcanzados."
        )

    return {
        "activo": False,
        "modelo_usado": MODELO_REGLAS_PLANIFICACION,
        "nivel_riesgo": nivel_riesgo,
        "resumen": resumen_base.get(
            "resumen",
            "Analisis generado por reglas de seguimiento estrategico.",
        ),
        "riesgos": _normalizar_lista(riesgos_detectados),
        "evidencias_criticas": _normalizar_lista(evidencias_criticas),
        "recomendaciones": recomendaciones,
        "acciones_sugeridas": acciones_sugeridas or [],
        "observacion_general": resumen_base.get(
            "observacion_general",
            "Resultado generado con reglas locales por falta de respuesta disponible de Gemini.",
        ),
    }


def _evidencia_para_prompt(evidencia: dict) -> dict:
    return {
        "codigo": evidencia.get("codigo"),
        "titulo": evidencia.get("titulo"),
        "descripcion": evidencia.get("descripcion"),
        "tipo_evidencia": evidencia.get("tipo_evidencia"),
        "responsable": evidencia.get("responsable"),
        "mes_programado": evidencia.get("mes_programado"),
        "estado": evidencia.get("estado"),
        "prioridad": evidencia.get("prioridad"),
        "avance": evidencia.get("avance"),
        "archivo_url": bool(evidencia.get("archivo_url")),
        "observacion": evidencia.get("observacion"),
        "origen_documento": evidencia.get("origen_documento"),
    }


def _crear_prompt(
    evidencias: list,
    dashboard: dict,
    riesgos_detectados: list,
    resumen_base: dict,
) -> str:
    contexto = {
        "dashboard": dashboard,
        "resumen_base": resumen_base,
        "riesgos_detectados": riesgos_detectados,
        "evidencias": [_evidencia_para_prompt(item) for item in evidencias[:30]],
    }

    return (
        "Eres un agente especializado en planificacion estrategica, acreditacion, mejora "
        "continua y seguimiento de planes de desarrollo de programas universitarios.\n\n"
        "Analiza evidencias del macroproceso planificacion_estrategica y genera un "
        "diagnostico ejecutivo, accionable y distinto de un simple resumen de tabla.\n\n"
        "Reglas obligatorias:\n"
        "- Devuelve SOLO JSON valido, sin markdown ni texto adicional.\n"
        "- No inventes codigos de evidencia.\n"
        "- Basa las evidencias criticas en los codigos recibidos.\n"
        "- Usa nivel_riesgo bajo, medio o alto.\n"
        "- Usa prioridad alta, media o baja en acciones_sugeridas.\n"
        "- Si hay evidencias de prioridad alta pendientes, tratarlas como riesgo relevante.\n"
        "- Si faltan archivo_url, advertir falta de sustento documental.\n"
        "- Las recomendaciones deben ser concretas y verificables.\n\n"
        "Estructura obligatoria:\n"
        "{\n"
        f'  "modelo_usado": "{MODELO_GEMINI_PLANIFICACION}",\n'
        '  "nivel_riesgo": "bajo|medio|alto",\n'
        '  "resumen": "texto",\n'
        '  "riesgos": ["texto"],\n'
        '  "evidencias_criticas": ["PE-001 - motivo"],\n'
        '  "recomendaciones": ["texto"],\n'
        '  "acciones_sugeridas": [\n'
        "    {\n"
        '      "titulo": "texto",\n'
        '      "descripcion": "texto",\n'
        '      "prioridad": "alta|media|baja",\n'
        '      "responsable_sugerido": "texto",\n'
        '      "evidencia_relacionada": "PE-001"\n'
        "    }\n"
        "  ],\n"
        '  "observacion_general": "texto"\n'
        "}\n\n"
        f"Contexto:\n{json.dumps(contexto, ensure_ascii=False)}"
    )


def generar_recomendaciones_planificacion_con_gemini(
    evidencias: list,
    dashboard: dict,
    riesgos_detectados: list,
    resumen_base: dict,
) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    evidencias_criticas = resumen_base.get("evidencias_criticas", [])
    acciones_sugeridas = resumen_base.get("acciones_sugeridas", [])

    if not api_key:
        print("[Gemini Planificación] GEMINI_API_KEY no configurada. Usando reglas.")
        return _fallback_reglas(riesgos_detectados, resumen_base, evidencias_criticas, acciones_sugeridas)

    if genai is None:
        print("[Gemini Planificación] SDK google-genai no disponible. Usando reglas.")
        return _fallback_reglas(riesgos_detectados, resumen_base, evidencias_criticas, acciones_sugeridas)

    try:
        print("[Gemini Planificación] Intentando generar recomendaciones con modelo:", model)
        client = genai.Client(api_key=api_key)
        prompt = _crear_prompt(evidencias, dashboard, riesgos_detectados, resumen_base)
        response = client.models.generate_content(
            model=model,
            contents=prompt,
        )
        texto_respuesta = getattr(response, "text", "")
        print("[Gemini Planificación] Respuesta recibida correctamente")
        data = _parsear_json(texto_respuesta)

        nivel_riesgo = str(data.get("nivel_riesgo") or resumen_base.get("nivel_riesgo", "medio")).strip().lower()
        if nivel_riesgo not in NIVELES_RIESGO_VALIDOS:
            nivel_riesgo = resumen_base.get("nivel_riesgo", "medio")

        return {
            "activo": True,
            "modelo_usado": MODELO_GEMINI_PLANIFICACION,
            "nivel_riesgo": nivel_riesgo,
            "resumen": str(data.get("resumen") or resumen_base.get("resumen") or ""),
            "riesgos": _normalizar_lista(data.get("riesgos") or riesgos_detectados),
            "evidencias_criticas": _normalizar_lista(data.get("evidencias_criticas") or evidencias_criticas),
            "recomendaciones": _normalizar_lista(data.get("recomendaciones")),
            "acciones_sugeridas": _normalizar_acciones(data.get("acciones_sugeridas") or acciones_sugeridas),
            "observacion_general": str(
                data.get("observacion_general")
                or resumen_base.get("observacion_general")
                or "Analisis generado con Gemini."
            ),
        }
    except Exception as e:
        print("[Gemini Planificación] Error:", type(e).__name__, str(e))
        return _fallback_reglas(riesgos_detectados, resumen_base, evidencias_criticas, acciones_sugeridas)
