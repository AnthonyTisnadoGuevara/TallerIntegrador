import json
import os

try:
    from google import genai
except ImportError:  # pragma: no cover - fallback when dependency is not installed yet
    genai = None


MODELO_REGLAS = "langgraph_reglas_curriculares_v1"
MODELO_GEMINI = "langgraph_gemini_curricular_v1"


def _fallback_reglas(analisis: dict) -> dict:
    return {
        "activo": False,
        "modelo_usado": MODELO_REGLAS,
        "sugerencias": analisis.get("sugerencias", []),
        "observacion_general": analisis.get(
            "observacion_general",
            "Analisis generado por reglas curriculares.",
        ),
        "recomendaciones_mejora": [],
    }


def limpiar_respuesta_json(texto: str) -> str:
    texto = (texto or "").strip()
    texto = texto.replace("```json", "").replace("```", "").strip()
    inicio = texto.find("{")
    fin = texto.rfind("}")
    if inicio != -1 and fin != -1:
        return texto[inicio:fin + 1]
    return texto


def _extraer_json(texto: str) -> dict:
    texto_limpio = limpiar_respuesta_json(texto)
    if not texto_limpio:
        raise ValueError("Gemini no devolvio contenido.")

    return json.loads(texto_limpio)


def _normalizar_respuesta_gemini(data: dict, analisis: dict) -> dict:
    sugerencias = data.get("sugerencias")
    recomendaciones = data.get("recomendaciones_mejora")
    observacion = data.get("observacion_general")

    if not isinstance(sugerencias, list) or not sugerencias:
        sugerencias = analisis.get("sugerencias", [])

    if not isinstance(recomendaciones, list):
        recomendaciones = []

    if not isinstance(observacion, str) or not observacion.strip():
        observacion = analisis.get(
            "observacion_general",
            "Analisis generado por reglas curriculares.",
        )

    return {
        "activo": True,
        "modelo_usado": MODELO_GEMINI,
        "sugerencias": [str(item) for item in sugerencias],
        "observacion_general": observacion.strip(),
        "recomendaciones_mejora": recomendaciones,
    }


def _crear_prompt(texto_silabo: str, silabo: dict, analisis: dict) -> str:
    fragmento = (texto_silabo or "")[:8000]
    contexto = {
        "silabo": {
            "asignatura": silabo.get("asignatura"),
            "codigo_asignatura": silabo.get("codigo_asignatura"),
            "ciclo": silabo.get("ciclo"),
            "programa_estudios": silabo.get("programa_estudios"),
        },
        "analisis_reglas": {
            "resumen": analisis.get("resumen"),
            "competencias_detectadas": analisis.get("competencias_detectadas", []),
            "contenidos_detectados": analisis.get("contenidos_detectados", []),
            "resultados_aprendizaje": analisis.get("resultados_aprendizaje", []),
            "secciones_faltantes": analisis.get("secciones_faltantes", []),
            "nivel_riesgo": analisis.get("nivel_riesgo"),
            "sugerencias": analisis.get("sugerencias", []),
        },
        "fragmento_silabo": fragmento,
    }

    return (
        "Eres un especialista en gestion curricular universitaria para programas de "
        "ingenieria de sistemas e inteligencia artificial. Analiza el contexto y genera "
        "recomendaciones curriculares concretas, accionables y no genericas.\n\n"
        "Debes considerar: coherencia entre sumilla, resultados y unidades; prerequisitos "
        "conceptuales; progresion de contenidos; evidencias e instrumentos de evaluacion; "
        "actualizacion de bibliografia; vinculacion con el perfil de egreso; y acciones de "
        "mejora continua.\n\n"
        "Devuelve SOLO JSON valido, sin markdown, sin texto adicional, con esta estructura:\n"
        "{\n"
        '  "sugerencias": ["sugerencia 1", "sugerencia 2", "sugerencia 3"],\n'
        '  "observacion_general": "texto breve",\n'
        '  "recomendaciones_mejora": [\n'
        '    {"aspecto": "coherencia curricular", "recomendacion": "..."},\n'
        '    {"aspecto": "resultados de aprendizaje", "recomendacion": "..."}\n'
        "  ]\n"
        "}\n\n"
        f"Contexto:\n{json.dumps(contexto, ensure_ascii=False)}"
    )


def generar_recomendaciones_con_gemini(texto_silabo: str, silabo: dict, analisis: dict) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    if not api_key:
        print("[Gemini] GEMINI_API_KEY no configurada. Usando reglas.")
        return _fallback_reglas(analisis)

    if genai is None:
        print("[Gemini] SDK google-genai no disponible. Usando reglas.")
        return _fallback_reglas(analisis)

    try:
        print("[Gemini] Intentando generar recomendaciones con modelo:", model)
        client = genai.Client(api_key=api_key)
        prompt = _crear_prompt(texto_silabo, silabo, analisis)
        response = client.models.generate_content(
            model=model,
            contents=prompt,
        )
        texto_respuesta = getattr(response, "text", "")
        print("[Gemini] Respuesta recibida correctamente.")
        try:
            data = _extraer_json(texto_respuesta)
            print("[Gemini] JSON parseado correctamente.")
        except Exception:
            print("[Gemini] No se pudo parsear JSON. Respuesta cruda:", texto_respuesta[:500])
            raise
        return _normalizar_respuesta_gemini(data, analisis)
    except Exception as e:
        print("[Gemini] Error:", type(e).__name__, str(e))
        return _fallback_reglas(analisis)
