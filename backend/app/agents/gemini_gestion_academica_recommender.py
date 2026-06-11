import json
import os

try:
    from google import genai
except ImportError:  # pragma: no cover - fallback when dependency is not installed
    genai = None


MODELO_REGLAS_GESTION_ACADEMICA = "langgraph_reglas_gestion_academica_v1"
MODELO_GEMINI_GESTION_ACADEMICA = "langgraph_gemini_gestion_academica_v1"
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
    indicadores: dict,
    riesgos_detectados: list,
    acuerdos_pendientes: list,
    observaciones_academicas: list,
    resumen_base: dict,
) -> dict:
    nivel_riesgo = resumen_base.get("nivel_riesgo", "medio")
    if nivel_riesgo not in NIVELES_RIESGO_VALIDOS:
        nivel_riesgo = "medio"

    recomendaciones = []
    if indicadores.get("pendientes", 0) > 0:
        recomendaciones.append(
            "Priorizar el cierre de evidencias academicas pendientes, especialmente las de prioridad alta."
        )
    if indicadores.get("sin_sustento_documental", 0) > 0:
        recomendaciones.append(
            "Completar el sustento documental de evidencias academicas completadas y en proceso."
        )
    if acuerdos_pendientes:
        recomendaciones.append(
            "Formalizar seguimiento de acuerdos con docentes, estudiantes y grupos de interes."
        )
    if observaciones_academicas:
        recomendaciones.append(
            "Revisar coherencia de silabos, portafolios y evidencias academicas observadas."
        )
    if not recomendaciones:
        recomendaciones.append(
            "Mantener el seguimiento academico y registrar evidencias verificables de mejora continua."
        )

    return {
        "activo": False,
        "modelo_usado": MODELO_REGLAS_GESTION_ACADEMICA,
        "nivel_riesgo": nivel_riesgo,
        "resumen": resumen_base.get("resumen", "Analisis generado por reglas de gestion academica."),
        "indicadores": indicadores,
        "riesgos": _normalizar_lista(riesgos_detectados),
        "acuerdos_pendientes": _normalizar_lista(acuerdos_pendientes),
        "observaciones_academicas": _normalizar_lista(observaciones_academicas),
        "evidencias_criticas": _normalizar_lista(resumen_base.get("evidencias_criticas", [])),
        "recomendaciones": recomendaciones,
        "acciones_sugeridas": resumen_base.get("acciones_sugeridas", []),
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
    indicadores: dict,
    riesgos_detectados: list,
    acuerdos_pendientes: list,
    observaciones_academicas: list,
    resumen_base: dict,
) -> str:
    contexto = {
        "indicadores": indicadores,
        "riesgos_detectados": riesgos_detectados,
        "acuerdos_pendientes": acuerdos_pendientes,
        "observaciones_academicas": observaciones_academicas,
        "resumen_base": resumen_base,
        "evidencias": [_evidencia_para_prompt(item) for item in evidencias[:30]],
    }

    return (
        "Eres un agente especializado en gestion academica universitaria, mejora continua, "
        "actualizacion curricular, seguimiento de acuerdos y aseguramiento de calidad.\n\n"
        "Analiza las evidencias del macroproceso de Gestion Academica del Programa de Estudio. "
        "Redacta un diagnostico academico claro, identificando riesgos, acuerdos pendientes, "
        "observaciones recurrentes, evidencias criticas y acciones sugeridas. No repitas textos "
        "genericos. Las recomendaciones deben estar orientadas a mejora continua, actualizacion "
        "curricular, seguimiento de acuerdos, coherencia de silabos, portafolios docentes y "
        "evidencias academicas.\n\n"
        "Reglas obligatorias:\n"
        "- Devuelve SOLO JSON valido, sin markdown ni texto adicional.\n"
        "- No inventes codigos de evidencia.\n"
        "- Usa nivel_riesgo bajo, medio o alto.\n"
        "- Usa prioridad alta, media o baja en acciones_sugeridas.\n"
        "- Relaciona evidencias criticas con codigos GA si existen.\n"
        "- Las acciones deben ser concretas, verificables y asignables.\n\n"
        "Estructura obligatoria:\n"
        "{\n"
        f'  "modelo_usado": "{MODELO_GEMINI_GESTION_ACADEMICA}",\n'
        '  "nivel_riesgo": "bajo|medio|alto",\n'
        '  "resumen": "texto",\n'
        '  "indicadores": {\n'
        '    "total_evidencias": 0,\n'
        '    "pendientes": 0,\n'
        '    "en_proceso": 0,\n'
        '    "completadas": 0,\n'
        '    "observadas": 0,\n'
        '    "avance_promedio": 0,\n'
        '    "prioridad_alta": 0,\n'
        '    "sin_sustento_documental": 0\n'
        "  },\n"
        '  "riesgos": ["texto"],\n'
        '  "acuerdos_pendientes": ["texto"],\n'
        '  "observaciones_academicas": ["texto"],\n'
        '  "evidencias_criticas": ["GA-004 - motivo"],\n'
        '  "recomendaciones": ["texto"],\n'
        '  "acciones_sugeridas": [\n'
        "    {\n"
        '      "titulo": "texto",\n'
        '      "descripcion": "texto",\n'
        '      "prioridad": "alta|media|baja",\n'
        '      "responsable_sugerido": "texto",\n'
        '      "evidencia_relacionada": "GA-004"\n'
        "    }\n"
        "  ],\n"
        '  "observacion_general": "texto"\n'
        "}\n\n"
        f"Contexto:\n{json.dumps(contexto, ensure_ascii=False)}"
    )


def generar_recomendaciones_gestion_academica_con_gemini(
    evidencias: list,
    indicadores: dict,
    riesgos_detectados: list,
    acuerdos_pendientes: list,
    observaciones_academicas: list,
    resumen_base: dict,
) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    if not api_key:
        print("[Gemini Gestion Academica] GEMINI_API_KEY no configurada. Usando reglas.")
        return _fallback_reglas(indicadores, riesgos_detectados, acuerdos_pendientes, observaciones_academicas, resumen_base)

    if genai is None:
        print("[Gemini Gestion Academica] SDK google-genai no disponible. Usando reglas.")
        return _fallback_reglas(indicadores, riesgos_detectados, acuerdos_pendientes, observaciones_academicas, resumen_base)

    try:
        print("[Gemini Gestion Academica] Intentando generar recomendaciones con modelo:", model)
        client = genai.Client(api_key=api_key)
        prompt = _crear_prompt(
            evidencias,
            indicadores,
            riesgos_detectados,
            acuerdos_pendientes,
            observaciones_academicas,
            resumen_base,
        )
        response = client.models.generate_content(
            model=model,
            contents=prompt,
        )
        texto_respuesta = getattr(response, "text", "")
        print("[Gemini Gestion Academica] Respuesta recibida correctamente.")

        try:
            data = _parsear_json(texto_respuesta)
            print("[Gemini Gestion Academica] JSON parseado correctamente.")
        except Exception:
            print("[Gemini Gestion Academica] No se pudo parsear JSON. Usando reglas.")
            raise

        nivel_riesgo = str(data.get("nivel_riesgo") or resumen_base.get("nivel_riesgo", "medio")).strip().lower()
        if nivel_riesgo not in NIVELES_RIESGO_VALIDOS:
            nivel_riesgo = resumen_base.get("nivel_riesgo", "medio")

        return {
            "activo": True,
            "modelo_usado": MODELO_GEMINI_GESTION_ACADEMICA,
            "nivel_riesgo": nivel_riesgo,
            "resumen": str(data.get("resumen") or resumen_base.get("resumen") or ""),
            "indicadores": data.get("indicadores") if isinstance(data.get("indicadores"), dict) else indicadores,
            "riesgos": _normalizar_lista(data.get("riesgos") or riesgos_detectados),
            "acuerdos_pendientes": _normalizar_lista(data.get("acuerdos_pendientes") or acuerdos_pendientes),
            "observaciones_academicas": _normalizar_lista(data.get("observaciones_academicas") or observaciones_academicas),
            "evidencias_criticas": _normalizar_lista(data.get("evidencias_criticas") or resumen_base.get("evidencias_criticas", [])),
            "recomendaciones": _normalizar_lista(data.get("recomendaciones")),
            "acciones_sugeridas": _normalizar_acciones(data.get("acciones_sugeridas") or resumen_base.get("acciones_sugeridas", [])),
            "observacion_general": str(
                data.get("observacion_general")
                or resumen_base.get("observacion_general")
                or "Analisis generado con Gemini."
            ),
        }
    except Exception as e:
        print("[Gemini Gestion Academica] Error:", type(e).__name__, str(e))
        return _fallback_reglas(indicadores, riesgos_detectados, acuerdos_pendientes, observaciones_academicas, resumen_base)
