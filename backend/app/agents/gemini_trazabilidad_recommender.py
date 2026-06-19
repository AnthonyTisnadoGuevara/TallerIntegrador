import json
import os

try:
    from google import genai
except ImportError:  # pragma: no cover - fallback when dependency is not installed yet
    genai = None

from app.services.vector_context_service import search_vector_context_for_prompt


MODELO_REGLAS_TRAZABILIDAD = "langgraph_reglas_trazabilidad_v1"
MODELO_GEMINI_TRAZABILIDAD = "langgraph_gemini_trazabilidad_v1"


def _fallback_reglas(relaciones: list, brechas: list) -> dict:
    return {
        "activo": False,
        "modelo_usado": MODELO_REGLAS_TRAZABILIDAD,
        "relaciones": relaciones,
        "brechas": brechas,
        "conclusion_general": "Trazabilidad generada por reglas curriculares.",
    }


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


def _relacion_para_prompt(relacion: dict) -> dict:
    return {
        "silabo_origen_id": relacion.get("silabo_origen_id"),
        "silabo_destino_id": relacion.get("silabo_destino_id"),
        "ciclo_origen": relacion.get("ciclo_origen"),
        "ciclo_destino": relacion.get("ciclo_destino"),
        "asignatura_origen": relacion.get("asignatura_origen"),
        "asignatura_destino": relacion.get("asignatura_destino"),
        "tipo_relacion": relacion.get("tipo_relacion"),
        "nivel_coherencia": relacion.get("nivel_coherencia"),
        "observacion": relacion.get("observacion"),
        "sugerencia": relacion.get("sugerencia"),
    }


def _brecha_para_prompt(brecha: dict) -> dict:
    return {
        "silabo_id": brecha.get("silabo_id"),
        "ciclo": brecha.get("ciclo"),
        "asignatura": brecha.get("asignatura"),
        "tipo_brecha": brecha.get("tipo_brecha"),
        "descripcion": brecha.get("descripcion"),
        "recomendacion": brecha.get("recomendacion"),
        "prioridad": brecha.get("prioridad"),
    }


def _crear_prompt(relaciones: list, brechas: list, resumen_contexto: dict | None) -> str:
    consulta_contexto = " ".join(
        [
            "trazabilidad curricular progresion curricular brechas formativas",
            " ".join(str(item.get("asignatura_origen", "")) for item in relaciones[:15]),
            " ".join(str(item.get("asignatura_destino", "")) for item in relaciones[:15]),
            " ".join(str(item.get("tipo_brecha", "")) for item in brechas[:15]),
        ]
    ).strip()
    contexto_vectorial = search_vector_context_for_prompt(consulta_contexto, match_count=5)
    contexto = {
        "resumen_contexto": resumen_contexto or {},
        "total_relaciones": len(relaciones),
        "total_brechas": len(brechas),
        "relaciones_muestra": [_relacion_para_prompt(item) for item in relaciones[:40]],
        "brechas_muestra": [_brecha_para_prompt(item) for item in brechas[:40]],
        "contexto_documental_vectorial": contexto_vectorial,
    }

    return (
        "Eres un especialista en trazabilidad curricular, mejora continua y gestion de "
        "programas academicos de ingenieria. Debes enriquecer la redaccion de relaciones "
        "curriculares y brechas ya detectadas por reglas.\n\n"
        "Reglas obligatorias:\n"
        "- Devuelve SOLO JSON valido, sin markdown ni texto adicional.\n"
        "- No inventes IDs.\n"
        "- No cambies ciclos ni asignaturas.\n"
        "- No elimines relaciones ni brechas de la muestra.\n"
        "- Mejora observaciones, sugerencias, descripciones y recomendaciones.\n"
        "- Usa lenguaje academico, claro y orientado a mejora continua.\n"
        "- Evita recomendaciones genericas.\n"
        "- Las brechas deben ser redactadas como problemas accionables distintos de la trazabilidad.\n"
        "- Evita repetir las mismas observaciones de las relaciones curriculares en las brechas.\n"
        "- En brechas, prioriza describir el problema, su impacto curricular y una accion de mejora concreta.\n"
        "- Relaciona las recomendaciones con progresion curricular, prerrequisitos, "
        "resultados de aprendizaje, perfil de egreso, evaluacion y mejora continua.\n"
        "- Prioriza brechas criticas con prioridad alta, media o baja.\n\n"
        "Si existe contexto documental recuperado desde la base vectorial, usalo como "
        "sustento institucional para mejorar observaciones y recomendaciones sin inventar IDs.\n\n"
        "Estructura obligatoria:\n"
        "{\n"
        '  "conclusion_general": "texto breve de la trazabilidad curricular",\n'
        '  "relaciones": [\n'
        "    {\n"
        '      "silabo_origen_id": "...",\n'
        '      "silabo_destino_id": "...",\n'
        '      "tipo_relacion": "...",\n'
        '      "nivel_coherencia": "...",\n'
        '      "observacion": "...",\n'
        '      "sugerencia": "..."\n'
        "    }\n"
        "  ],\n"
        '  "brechas": [\n'
        "    {\n"
        '      "silabo_id": "...",\n'
        '      "tipo_brecha": "...",\n'
        '      "descripcion": "...",\n'
        '      "recomendacion": "...",\n'
        '      "prioridad": "alta|media|baja"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        f"Contexto:\n{json.dumps(contexto, ensure_ascii=False)}"
    )


def enriquecer_trazabilidad_con_gemini(
    relaciones: list,
    brechas: list,
    resumen_contexto: dict | None = None,
) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    if not api_key:
        print("[Gemini Trazabilidad] GEMINI_API_KEY no configurada. Usando reglas.")
        return _fallback_reglas(relaciones, brechas)

    if genai is None:
        print("[Gemini Trazabilidad] SDK google-genai no disponible. Usando reglas.")
        return _fallback_reglas(relaciones, brechas)

    try:
        print("[Gemini Trazabilidad] Intentando enriquecer trazabilidad con modelo:", model)
        client = genai.Client(api_key=api_key)
        prompt = _crear_prompt(relaciones, brechas, resumen_contexto)
        response = client.models.generate_content(
            model=model,
            contents=prompt,
        )
        texto_respuesta = getattr(response, "text", "")
        print("[Gemini Trazabilidad] Respuesta recibida correctamente.")
        try:
            data = _parsear_json(texto_respuesta)
            print("[Gemini Trazabilidad] JSON parseado correctamente.")
        except Exception:
            print(
                "[Gemini Trazabilidad] No se pudo parsear JSON. Respuesta cruda:",
                texto_respuesta[:500],
            )
            raise

        return {
            "activo": True,
            "modelo_usado": MODELO_GEMINI_TRAZABILIDAD,
            "relaciones": data.get("relaciones", []),
            "brechas": data.get("brechas", []),
            "conclusion_general": data.get("conclusion_general"),
        }
    except Exception as e:
        print("[Gemini Trazabilidad] Error:", type(e).__name__, str(e))
        return _fallback_reglas(relaciones, brechas)
