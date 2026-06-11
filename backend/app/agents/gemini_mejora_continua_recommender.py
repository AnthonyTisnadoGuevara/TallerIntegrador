import json
import os

try:
    from google import genai
except ImportError:  # pragma: no cover - fallback when dependency is not installed
    genai = None


MODELO_REGLAS_COORDINADOR = "langgraph_reglas_coordinador_mejora_continua_v1"
MODELO_GEMINI_COORDINADOR = "langgraph_gemini_coordinador_mejora_continua_v1"
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
                "titulo": str(accion.get("titulo") or "Accion prioritaria"),
                "descripcion": str(accion.get("descripcion") or "Sin descripcion."),
                "prioridad": prioridad,
                "macroproceso_relacionado": str(accion.get("macroproceso_relacionado") or "Mejora continua"),
                "responsable_sugerido": str(accion.get("responsable_sugerido") or "Comite academico"),
            }
        )

    return resultado


def _normalizar_estado_macroprocesos(valor, fallback: list) -> list:
    estado = valor if isinstance(valor, list) else fallback
    resultado = []
    for item in estado:
        if not isinstance(item, dict):
            continue
        riesgo = str(item.get("nivel_riesgo") or "medio").strip().lower()
        if riesgo not in NIVELES_RIESGO_VALIDOS:
            riesgo = "medio"
        resultado.append(
            {
                "macroproceso": str(item.get("macroproceso") or "Macroproceso"),
                "nivel_riesgo": riesgo,
                "avance_promedio": int(item.get("avance_promedio") or 0),
                "hallazgos": _normalizar_lista(item.get("hallazgos")),
            }
        )
    return resultado


def _fallback_reglas(
    datos_planificacion: dict,
    datos_gestion_academica: dict,
    datos_gestion_silabos: dict,
    indicadores_generales: dict,
    hallazgos_integrados: list,
    riesgos_detectados: dict,
    acciones_prioritarias_base: list,
) -> dict:
    estado_macroprocesos = [
        datos_planificacion,
        datos_gestion_academica,
        datos_gestion_silabos,
    ]
    macroprocesos_criticos = [
        item.get("macroproceso")
        for item in estado_macroprocesos
        if item.get("nivel_riesgo") == "alto"
    ]
    if not macroprocesos_criticos:
        macroprocesos_criticos = [
            item.get("macroproceso")
            for item in estado_macroprocesos
            if item.get("nivel_riesgo") == "medio"
        ]

    nivel = riesgos_detectados.get("nivel_riesgo_general", "medio")
    if nivel not in NIVELES_RIESGO_VALIDOS:
        nivel = "medio"

    recomendaciones = []
    if indicadores_generales.get("brechas_alta_prioridad", 0) > 0:
        recomendaciones.append("Priorizar la atencion de brechas curriculares de alta prioridad.")
    if indicadores_generales.get("acciones_pendientes", 0) > 0:
        recomendaciones.append("Cerrar acciones de mejora pendientes con responsables y fechas verificables.")
    if macroprocesos_criticos:
        recomendaciones.append("Convocar al comite academico para revisar macroprocesos criticos y aprobar acciones correctivas.")
    if not recomendaciones:
        recomendaciones.append("Mantener seguimiento periodico del Plan de Mejora Continua y actualizar evidencias.")

    return {
        "activo": False,
        "modelo_usado": MODELO_REGLAS_COORDINADOR,
        "nivel_riesgo_general": nivel,
        "resumen_general": riesgos_detectados.get(
            "resumen_general",
            "Diagnostico integral generado por reglas del coordinador de mejora continua.",
        ),
        "estado_macroprocesos": estado_macroprocesos,
        "indicadores_generales": indicadores_generales,
        "macroprocesos_criticos": [item for item in macroprocesos_criticos if item],
        "hallazgos_integrados": _normalizar_lista(hallazgos_integrados),
        "evidencias_criticas": _normalizar_lista(riesgos_detectados.get("evidencias_criticas", [])),
        "acciones_prioritarias": acciones_prioritarias_base,
        "recomendaciones_comite": recomendaciones,
        "decision_sugerida": riesgos_detectados.get(
            "decision_sugerida",
            "Priorizar seguimiento de riesgos y documentar evidencias de cierre.",
        ),
        "observacion_general": riesgos_detectados.get(
            "observacion_general",
            "Resultado generado con reglas locales por falta de respuesta disponible de Gemini.",
        ),
    }


def _crear_prompt(
    datos_planificacion: dict,
    datos_gestion_academica: dict,
    datos_gestion_silabos: dict,
    indicadores_generales: dict,
    hallazgos_integrados: list,
    riesgos_detectados: dict,
    acciones_prioritarias_base: list,
) -> str:
    contexto = {
        "datos_planificacion": datos_planificacion,
        "datos_gestion_academica": datos_gestion_academica,
        "datos_gestion_silabos": datos_gestion_silabos,
        "indicadores_generales": indicadores_generales,
        "hallazgos_integrados": hallazgos_integrados,
        "riesgos_detectados": riesgos_detectados,
        "acciones_prioritarias_base": acciones_prioritarias_base,
    }

    return (
        "Actua como un especialista en mejora continua universitaria y acreditacion de "
        "programas de estudio. Analiza la informacion integrada de los macroprocesos de "
        "Planificacion Estrategica, Gestion Academica y Gestion de Silabos. Identifica "
        "riesgos generales, macroprocesos criticos, hallazgos integrados, acciones "
        "prioritarias y recomendaciones para el comite academico. Devuelve unicamente "
        "JSON valido, sin markdown.\n\n"
        "Reglas obligatorias:\n"
        "- No inventes macroprocesos ni indicadores fuera del contexto.\n"
        "- Usa nivel_riesgo_general y nivel_riesgo con valores bajo, medio o alto.\n"
        "- Usa prioridad alta, media o baja en acciones_prioritarias.\n"
        "- Las recomendaciones deben ser concretas, verificables y orientadas a cierre del ciclo de mejora.\n\n"
        "Estructura obligatoria:\n"
        "{\n"
        f'  "modelo_usado": "{MODELO_GEMINI_COORDINADOR}",\n'
        '  "nivel_riesgo_general": "bajo|medio|alto",\n'
        '  "resumen_general": "texto",\n'
        '  "estado_macroprocesos": [\n'
        "    {\n"
        '      "macroproceso": "Planificacion Estrategica",\n'
        '      "nivel_riesgo": "bajo|medio|alto",\n'
        '      "avance_promedio": 0,\n'
        '      "hallazgos": ["texto"]\n'
        "    }\n"
        "  ],\n"
        '  "indicadores_generales": {\n'
        '    "total_macroprocesos": 3,\n'
        '    "total_evidencias_macroprocesos": 0,\n'
        '    "total_silabos": 0,\n'
        '    "total_brechas": 0,\n'
        '    "brechas_alta_prioridad": 0,\n'
        '    "total_acciones_mejora": 0,\n'
        '    "acciones_pendientes": 0,\n'
        '    "acciones_en_proceso": 0,\n'
        '    "acciones_completadas": 0\n'
        "  },\n"
        '  "macroprocesos_criticos": ["texto"],\n'
        '  "hallazgos_integrados": ["texto"],\n'
        '  "evidencias_criticas": ["texto"],\n'
        '  "acciones_prioritarias": [\n'
        "    {\n"
        '      "titulo": "texto",\n'
        '      "descripcion": "texto",\n'
        '      "prioridad": "alta|media|baja",\n'
        '      "macroproceso_relacionado": "texto",\n'
        '      "responsable_sugerido": "texto"\n'
        "    }\n"
        "  ],\n"
        '  "recomendaciones_comite": ["texto"],\n'
        '  "decision_sugerida": "texto",\n'
        '  "observacion_general": "texto"\n'
        "}\n\n"
        f"Contexto:\n{json.dumps(contexto, ensure_ascii=False)}"
    )


def generar_diagnostico_mejora_continua_con_gemini(
    datos_planificacion: dict,
    datos_gestion_academica: dict,
    datos_gestion_silabos: dict,
    indicadores_generales: dict,
    hallazgos_integrados: list,
    riesgos_detectados: dict,
    acciones_prioritarias_base: list,
) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    if not api_key:
        print("[Gemini Coordinador] GEMINI_API_KEY no configurada. Usando reglas.")
        return _fallback_reglas(
            datos_planificacion,
            datos_gestion_academica,
            datos_gestion_silabos,
            indicadores_generales,
            hallazgos_integrados,
            riesgos_detectados,
            acciones_prioritarias_base,
        )

    if genai is None:
        print("[Gemini Coordinador] SDK google-genai no disponible. Usando reglas.")
        return _fallback_reglas(
            datos_planificacion,
            datos_gestion_academica,
            datos_gestion_silabos,
            indicadores_generales,
            hallazgos_integrados,
            riesgos_detectados,
            acciones_prioritarias_base,
        )

    try:
        print("[Gemini Coordinador] Intentando generar diagnostico con modelo:", model)
        client = genai.Client(api_key=api_key)
        prompt = _crear_prompt(
            datos_planificacion,
            datos_gestion_academica,
            datos_gestion_silabos,
            indicadores_generales,
            hallazgos_integrados,
            riesgos_detectados,
            acciones_prioritarias_base,
        )
        response = client.models.generate_content(
            model=model,
            contents=prompt,
        )
        texto_respuesta = getattr(response, "text", "")
        print("[Gemini Coordinador] Respuesta recibida correctamente.")

        try:
            data = _parsear_json(texto_respuesta)
            print("[Gemini Coordinador] JSON parseado correctamente.")
        except Exception:
            print("[Gemini Coordinador] No se pudo parsear JSON. Usando reglas.")
            raise

        nivel = str(data.get("nivel_riesgo_general") or riesgos_detectados.get("nivel_riesgo_general", "medio")).strip().lower()
        if nivel not in NIVELES_RIESGO_VALIDOS:
            nivel = riesgos_detectados.get("nivel_riesgo_general", "medio")

        estado_macroprocesos_base = [
            datos_planificacion,
            datos_gestion_academica,
            datos_gestion_silabos,
        ]

        return {
            "activo": True,
            "modelo_usado": MODELO_GEMINI_COORDINADOR,
            "nivel_riesgo_general": nivel,
            "resumen_general": str(data.get("resumen_general") or riesgos_detectados.get("resumen_general") or ""),
            "estado_macroprocesos": _normalizar_estado_macroprocesos(
                data.get("estado_macroprocesos"),
                estado_macroprocesos_base,
            ),
            "indicadores_generales": data.get("indicadores_generales")
            if isinstance(data.get("indicadores_generales"), dict)
            else indicadores_generales,
            "macroprocesos_criticos": _normalizar_lista(data.get("macroprocesos_criticos")),
            "hallazgos_integrados": _normalizar_lista(data.get("hallazgos_integrados") or hallazgos_integrados),
            "evidencias_criticas": _normalizar_lista(data.get("evidencias_criticas") or riesgos_detectados.get("evidencias_criticas", [])),
            "acciones_prioritarias": _normalizar_acciones(data.get("acciones_prioritarias") or acciones_prioritarias_base),
            "recomendaciones_comite": _normalizar_lista(data.get("recomendaciones_comite")),
            "decision_sugerida": str(data.get("decision_sugerida") or riesgos_detectados.get("decision_sugerida") or ""),
            "observacion_general": str(
                data.get("observacion_general")
                or riesgos_detectados.get("observacion_general")
                or "Diagnostico integral generado con Gemini."
            ),
        }
    except Exception as e:
        print("[Gemini Coordinador] Error:", type(e).__name__, str(e))
        return _fallback_reglas(
            datos_planificacion,
            datos_gestion_academica,
            datos_gestion_silabos,
            indicadores_generales,
            hallazgos_integrados,
            riesgos_detectados,
            acciones_prioritarias_base,
        )
