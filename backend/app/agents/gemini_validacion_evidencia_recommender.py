import json
import os

try:
    from google import genai
except ImportError:  # pragma: no cover
    genai = None


MODELO_REGLAS_VALIDACION = "langgraph_reglas_validacion_evidencia_v1"
MODELO_GEMINI_VALIDACION = "langgraph_gemini_validacion_evidencia_v1"
NIVELES_VALIDEZ = {"alto", "medio", "bajo"}
PERTINENCIAS = {"corresponde", "parcialmente_corresponde", "no_corresponde"}


def limpiar_respuesta_json(texto: str) -> str:
    texto = (texto or "").strip().replace("```json", "").replace("```", "").strip()
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


def _lista(valor) -> list:
    if isinstance(valor, list):
        return [str(item) for item in valor if item]
    if valor:
        return [str(valor)]
    return []


def _fallback_reglas(resultado_base: dict) -> dict:
    return {
        "activo": False,
        "modelo_usado": MODELO_REGLAS_VALIDACION,
        "nivel_validez": resultado_base.get("nivel_validez", "medio"),
        "pertinencia": resultado_base.get("pertinencia", "parcialmente_corresponde"),
        "resumen": resultado_base.get("resumen", "Validacion generada por reglas locales."),
        "elementos_detectados": _lista(resultado_base.get("elementos_detectados")),
        "elementos_faltantes": _lista(resultado_base.get("elementos_faltantes")),
        "observaciones": _lista(resultado_base.get("observaciones")),
        "recomendaciones": _lista(resultado_base.get("recomendaciones")),
        "accion_sugerida": resultado_base.get("accion_sugerida", "Revisar y completar sustento documental."),
    }


def _crear_prompt(evidencia: dict, texto: str, resultado_base: dict) -> str:
    contexto = {
        "evidencia": {
            "macroproceso": evidencia.get("macroproceso"),
            "codigo": evidencia.get("codigo"),
            "titulo": evidencia.get("titulo"),
            "descripcion": evidencia.get("descripcion"),
            "tipo_evidencia": evidencia.get("tipo_evidencia"),
            "responsable": evidencia.get("responsable"),
            "origen_documento": evidencia.get("origen_documento"),
        },
        "resultado_base": resultado_base,
        "texto_documento": texto[:12000],
    }
    return (
        "Eres un auditor academico de evidencias documentales para mejora continua. "
        "Evalua si el documento de sustento corresponde a la evidencia declarada y al "
        "macroproceso. Devuelve SOLO JSON valido, sin markdown.\n\n"
        "Criterios: titulo o identificacion del documento, relacion con la evidencia, "
        "fecha, responsable, actividades o acuerdos, indicadores o metas, sustento "
        "documental suficiente y consistencia con el macroproceso.\n\n"
        "Estructura obligatoria:\n"
        "{\n"
        f'  "modelo_usado": "{MODELO_GEMINI_VALIDACION}",\n'
        '  "nivel_validez": "alto|medio|bajo",\n'
        '  "pertinencia": "corresponde|parcialmente_corresponde|no_corresponde",\n'
        '  "resumen": "texto",\n'
        '  "elementos_detectados": ["fecha"],\n'
        '  "elementos_faltantes": ["firmas"],\n'
        '  "observaciones": ["texto"],\n'
        '  "recomendaciones": ["texto"],\n'
        '  "accion_sugerida": "texto"\n'
        "}\n\n"
        f"Contexto:\n{json.dumps(contexto, ensure_ascii=False)}"
    )


def enriquecer_validacion_evidencia_con_gemini(evidencia: dict, texto: str, resultado_base: dict) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    if not api_key:
        print("[Gemini Validacion Evidencia] GEMINI_API_KEY no configurada. Usando reglas.")
        return _fallback_reglas(resultado_base)
    if genai is None:
        print("[Gemini Validacion Evidencia] SDK google-genai no disponible. Usando reglas.")
        return _fallback_reglas(resultado_base)

    try:
        print("[Gemini Validacion Evidencia] Intentando validar evidencia con modelo:", model)
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=_crear_prompt(evidencia, texto, resultado_base),
        )
        data = _parsear_json(getattr(response, "text", ""))
        print("[Gemini Validacion Evidencia] Respuesta recibida correctamente.")

        nivel = str(data.get("nivel_validez") or resultado_base.get("nivel_validez", "medio")).lower()
        if nivel not in NIVELES_VALIDEZ:
            nivel = "medio"
        pertinencia = str(data.get("pertinencia") or resultado_base.get("pertinencia", "parcialmente_corresponde")).lower()
        if pertinencia not in PERTINENCIAS:
            pertinencia = "parcialmente_corresponde"

        return {
            "activo": True,
            "modelo_usado": MODELO_GEMINI_VALIDACION,
            "nivel_validez": nivel,
            "pertinencia": pertinencia,
            "resumen": str(data.get("resumen") or resultado_base.get("resumen") or ""),
            "elementos_detectados": _lista(data.get("elementos_detectados") or resultado_base.get("elementos_detectados")),
            "elementos_faltantes": _lista(data.get("elementos_faltantes") or resultado_base.get("elementos_faltantes")),
            "observaciones": _lista(data.get("observaciones") or resultado_base.get("observaciones")),
            "recomendaciones": _lista(data.get("recomendaciones") or resultado_base.get("recomendaciones")),
            "accion_sugerida": str(data.get("accion_sugerida") or resultado_base.get("accion_sugerida") or ""),
        }
    except Exception as e:
        print("[Gemini Validacion Evidencia] Error:", type(e).__name__, str(e))
        return _fallback_reglas(resultado_base)
