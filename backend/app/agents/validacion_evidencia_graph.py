import re
import unicodedata
from typing import Any

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from app.agents.gemini_validacion_evidencia_recommender import (
    enriquecer_validacion_evidencia_con_gemini,
)
from app.services.supabase_client import supabase
from app.utils.document_reader import extraer_texto_desde_url


class ValidacionEvidenciaState(TypedDict, total=False):
    evidencia_id: str
    evidencia: dict
    texto_documento: str
    resultado_base: dict
    resultado: dict


def _normalizar_texto(valor: Any) -> str:
    texto = str(valor or "").lower()
    texto = unicodedata.normalize("NFD", texto)
    return "".join(caracter for caracter in texto if unicodedata.category(caracter) != "Mn")


def _tokens_relevantes(*valores: Any) -> set[str]:
    texto = _normalizar_texto(" ".join(str(valor or "") for valor in valores))
    palabras = re.findall(r"[a-z0-9]{4,}", texto)
    descartes = {
        "para",
        "como",
        "este",
        "esta",
        "desde",
        "evidencia",
        "seguimiento",
        "programa",
        "estudio",
    }
    return {palabra for palabra in palabras if palabra not in descartes}


def _elementos_detectados(texto: str) -> list[str]:
    texto_norm = _normalizar_texto(texto)
    elementos = []

    patrones = {
        "fecha": r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})\b",
        "responsable": r"\b(responsable|director|coordinador|comite|oficina|docente)\b",
        "objetivo": r"\b(objetivo|proposito|finalidad|meta)\b",
        "actividades": r"\b(actividad|acciones|acuerdos|cronograma|plan operativo)\b",
        "indicadores": r"\b(indicador|avance|cumplimiento|resultado|reporte)\b",
        "firmas o aprobacion": r"\b(firma|firmado|aprobado|resolucion|acta|consejo)\b",
    }

    for nombre, patron in patrones.items():
        if re.search(patron, texto_norm):
            elementos.append(nombre)

    return elementos


def _nivel_por_puntaje(puntaje: int) -> tuple[str, str]:
    if puntaje >= 5:
        return "alto", "corresponde"
    if puntaje >= 3:
        return "medio", "parcialmente_corresponde"
    return "bajo", "no_corresponde"


def _evaluar_por_reglas(evidencia: dict, texto: str) -> dict:
    texto_norm = _normalizar_texto(texto)
    codigo = _normalizar_texto(evidencia.get("codigo"))
    macroproceso = _normalizar_texto(evidencia.get("macroproceso"))
    tokens = _tokens_relevantes(
        evidencia.get("titulo"),
        evidencia.get("descripcion"),
        evidencia.get("tipo_evidencia"),
        evidencia.get("responsable"),
        evidencia.get("origen_documento"),
    )
    coincidencias = sorted(token for token in tokens if token in texto_norm)
    elementos = _elementos_detectados(texto)
    faltantes = []

    if codigo and codigo not in texto_norm:
        faltantes.append("codigo o identificacion de la evidencia")
    if len(coincidencias) < 3:
        faltantes.append("relacion explicita con el titulo o descripcion de la evidencia")
    if "fecha" not in elementos:
        faltantes.append("fecha del documento")
    if "responsable" not in elementos:
        faltantes.append("responsable o unidad encargada")
    if "firmas o aprobacion" not in elementos:
        faltantes.append("firma, aprobacion o acto formal")

    puntaje = min(len(coincidencias), 4)
    if codigo and codigo in texto_norm:
        puntaje += 1
    if macroproceso and any(parte in texto_norm for parte in macroproceso.split("_")):
        puntaje += 1
    puntaje += min(len(elementos), 3)
    puntaje -= min(len(faltantes), 3)

    nivel_validez, pertinencia = _nivel_por_puntaje(puntaje)
    resumen = (
        "El documento presenta sustento suficiente para la evidencia."
        if nivel_validez == "alto"
        else "El documento contiene sustento parcial y requiere completar elementos de validacion."
        if nivel_validez == "medio"
        else "El documento no evidencia una correspondencia suficiente con la evidencia registrada."
    )

    recomendaciones = []
    if faltantes:
        recomendaciones.append("Completar los elementos faltantes identificados en la validacion documental.")
    if nivel_validez != "alto":
        recomendaciones.append("Adjuntar una version mas explicita del documento o una evidencia complementaria.")
    if not recomendaciones:
        recomendaciones.append("Mantener el documento como sustento y actualizar el avance segun corresponda.")

    return {
        "modelo_usado": "langgraph_reglas_validacion_evidencia_v1",
        "nivel_validez": nivel_validez,
        "pertinencia": pertinencia,
        "resumen": resumen,
        "elementos_detectados": elementos + [f"coincidencias clave: {', '.join(coincidencias[:6])}"],
        "elementos_faltantes": faltantes,
        "observaciones": [
            f"Se identificaron {len(coincidencias)} coincidencias relevantes entre la evidencia y el documento.",
            f"El documento contiene {len(texto.strip())} caracteres de texto extraible.",
        ],
        "recomendaciones": recomendaciones,
        "accion_sugerida": (
            "Registrar la validacion y continuar el seguimiento."
            if nivel_validez == "alto"
            else "Solicitar al responsable que complete o reemplace el sustento documental."
        ),
    }


def obtener_evidencia(state: ValidacionEvidenciaState) -> ValidacionEvidenciaState:
    evidencia_id = state["evidencia_id"]
    response = (
        supabase.table("macroproceso_evidencias")
        .select("*")
        .eq("id", evidencia_id)
        .execute()
    )
    if not response.data:
        raise ValueError("Evidencia no encontrada.")

    evidencia = response.data[0]
    if not evidencia.get("archivo_url"):
        raise ValueError("Primero suba un archivo de sustento para validar esta evidencia.")

    state["evidencia"] = evidencia
    return state


def extraer_texto_documento(state: ValidacionEvidenciaState) -> ValidacionEvidenciaState:
    archivo_url = state["evidencia"].get("archivo_url")
    try:
        texto = extraer_texto_desde_url(archivo_url)
    except ValueError as error:
        raise ValueError(str(error)) from error
    except Exception as error:
        raise ValueError(f"No se pudo leer el archivo de sustento: {error}") from error

    if not texto or not texto.strip():
        raise ValueError(
            "No se pudo extraer texto del documento. Use un PDF con texto seleccionable o un DOCX."
        )

    state["texto_documento"] = texto
    return state


def validar_por_reglas(state: ValidacionEvidenciaState) -> ValidacionEvidenciaState:
    state["resultado_base"] = _evaluar_por_reglas(
        state["evidencia"],
        state["texto_documento"],
    )
    return state


def generar_recomendacion_gemini(state: ValidacionEvidenciaState) -> ValidacionEvidenciaState:
    resultado = enriquecer_validacion_evidencia_con_gemini(
        state["evidencia"],
        state["texto_documento"],
        state["resultado_base"],
    )
    state["resultado"] = resultado
    return state


def guardar_validacion(state: ValidacionEvidenciaState) -> ValidacionEvidenciaState:
    evidencia = state["evidencia"]
    resultado = state["resultado"]
    payload = {
        "evidencia_id": evidencia.get("id"),
        "macroproceso": evidencia.get("macroproceso"),
        "modelo_usado": resultado.get("modelo_usado"),
        "nivel_validez": resultado.get("nivel_validez"),
        "pertinencia": resultado.get("pertinencia"),
        "resumen": resultado.get("resumen"),
        "elementos_detectados": resultado.get("elementos_detectados") or [],
        "elementos_faltantes": resultado.get("elementos_faltantes") or [],
        "observaciones": resultado.get("observaciones") or [],
        "recomendaciones": resultado.get("recomendaciones") or [],
        "accion_sugerida": resultado.get("accion_sugerida"),
    }
    response = supabase.table("validacion_ia_macroproceso_evidencias").insert(payload).execute()
    if response.data:
        resultado["id"] = response.data[0].get("id")
        resultado["created_at"] = response.data[0].get("created_at")

    state["resultado"] = resultado
    return state


def construir_grafo_validacion_evidencia():
    graph = StateGraph(ValidacionEvidenciaState)
    graph.add_node("obtener_evidencia", obtener_evidencia)
    graph.add_node("extraer_texto_documento", extraer_texto_documento)
    graph.add_node("validar_por_reglas", validar_por_reglas)
    graph.add_node("generar_recomendacion_gemini", generar_recomendacion_gemini)
    graph.add_node("guardar_validacion", guardar_validacion)

    graph.add_edge(START, "obtener_evidencia")
    graph.add_edge("obtener_evidencia", "extraer_texto_documento")
    graph.add_edge("extraer_texto_documento", "validar_por_reglas")
    graph.add_edge("validar_por_reglas", "generar_recomendacion_gemini")
    graph.add_edge("generar_recomendacion_gemini", "guardar_validacion")
    graph.add_edge("guardar_validacion", END)
    return graph.compile()


def ejecutar_grafo_validacion_evidencia(evidencia_id: str) -> dict:
    print("[Validacion IA Evidencia] Ejecutando agente de validacion documental")
    grafo = construir_grafo_validacion_evidencia()
    resultado = grafo.invoke({"evidencia_id": evidencia_id})
    modelo = (resultado.get("resultado") or {}).get("modelo_usado")
    print("[Validacion IA Evidencia] Modelo resultante:", modelo)
    return resultado.get("resultado") or {}
