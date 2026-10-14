"""Reglas analíticas originales de Gestión Académica, sin dependencias productivas."""
import unicodedata
from typing import Any

from typing_extensions import TypedDict


class GestionAcademicaState(TypedDict, total=False):
    evidencias: list
    indicadores: dict
    clasificacion: dict
    acuerdos_pendientes: list
    riesgos_detectados: list
    observaciones_academicas: list
    evidencias_criticas: list
    acciones_sugeridas: list
    resumen_base: dict
    recomendacion_gemini: dict
    resultado: dict
    error: str


def _entero(valor: Any, defecto: int = 0) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return defecto


def _avance(evidencia: dict) -> int:
    return max(0, min(100, _entero(evidencia.get("avance"), 0)))


def _normalizar_texto(valor: Any) -> str:
    texto = str(valor or "")
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(caracter for caracter in texto if unicodedata.category(caracter) != "Mn")
    return texto.lower().strip()


def _texto_evidencia(evidencia: dict) -> str:
    partes = [
        evidencia.get("codigo"), evidencia.get("titulo"), evidencia.get("descripcion"),
        evidencia.get("tipo_evidencia"), evidencia.get("responsable"),
        evidencia.get("observacion"), evidencia.get("origen_documento"),
    ]
    return _normalizar_texto(" ".join(str(parte) for parte in partes if parte))


def _codigo_titulo(evidencia: dict) -> str:
    codigo = evidencia.get("codigo") or "Sin codigo"
    titulo = evidencia.get("titulo") or "Evidencia sin titulo"
    return f"{codigo} - {titulo}"


def _normalizar_nivel_riesgo(nivel: str) -> str:
    nivel = str(nivel or "medio").strip().lower()
    return nivel if nivel in {"bajo", "medio", "alto"} else "medio"


def _riesgo_por_avance(avance_promedio: int) -> str:
    if avance_promedio < 30:
        return "alto"
    if avance_promedio < 70:
        return "medio"
    return "bajo"


def _max_riesgo(*niveles: str) -> str:
    orden = {"bajo": 0, "medio": 1, "alto": 2}
    return max((_normalizar_nivel_riesgo(nivel) for nivel in niveles), key=lambda item: orden[item])


def _crear_accion(
    titulo: str, descripcion: str, prioridad: str, responsable: str, evidencia: dict | None = None
) -> dict:
    return {
        "titulo": titulo,
        "descripcion": descripcion,
        "prioridad": prioridad,
        "responsable_sugerido": responsable,
        "evidencia_relacionada": (evidencia or {}).get("codigo") or "",
    }


def calcular_indicadores_gestion_academica(state: GestionAcademicaState) -> GestionAcademicaState:
    evidencias = state.get("evidencias", [])
    total = len(evidencias)
    completadas = sum(1 for item in evidencias if item.get("estado") == "completado")
    pendientes = sum(1 for item in evidencias if item.get("estado") == "pendiente")
    en_proceso = sum(1 for item in evidencias if item.get("estado") == "en_proceso")
    observadas = sum(1 for item in evidencias if item.get("estado") == "observado")
    prioridad_alta = sum(1 for item in evidencias if item.get("prioridad") == "alta")
    sin_archivo = sum(1 for item in evidencias if not item.get("archivo_url"))
    completadas_sin_archivo = sum(
        1 for item in evidencias if item.get("estado") == "completado" and not item.get("archivo_url")
    )
    avance_promedio = round(sum(_avance(item) for item in evidencias) / total) if total else 0
    indicadores = {
        "total_evidencias": total, "pendientes": pendientes, "en_proceso": en_proceso,
        "completadas": completadas, "observadas": observadas, "avance_promedio": avance_promedio,
        "prioridad_alta": prioridad_alta, "sin_sustento_documental": sin_archivo,
        "completadas_sin_sustento_documental": completadas_sin_archivo,
    }
    return {**state, "indicadores": indicadores}


def clasificar_evidencias_academicas(state: GestionAcademicaState) -> GestionAcademicaState:
    clasificacion = {
        "actas": [], "resoluciones": [], "oficios": [], "acuerdos_docentes": [],
        "acuerdos_estudiantes": [], "silabos_portafolios": [],
    }
    for evidencia in state.get("evidencias", []):
        texto = _texto_evidencia(evidencia)
        if "acta" in texto:
            clasificacion["actas"].append(evidencia)
        if "resolucion" in texto:
            clasificacion["resoluciones"].append(evidencia)
        if "oficio" in texto:
            clasificacion["oficios"].append(evidencia)
        if "docente" in texto or "docentes" in texto:
            clasificacion["acuerdos_docentes"].append(evidencia)
        if "estudiante" in texto or "estudiantes" in texto:
            clasificacion["acuerdos_estudiantes"].append(evidencia)
        if "silabo" in texto or "silabos" in texto or "portafolio" in texto or "portafolios" in texto:
            clasificacion["silabos_portafolios"].append(evidencia)
    return {**state, "clasificacion": clasificacion}


def detectar_riesgos_academicos(state: GestionAcademicaState) -> GestionAcademicaState:
    evidencias = state.get("evidencias", [])
    indicadores = state.get("indicadores", {})
    clasificacion = state.get("clasificacion", {})
    riesgos = []
    observaciones = []
    evidencias_criticas = []
    acciones = list(state.get("acciones_sugeridas", []))
    nivel_riesgo = _riesgo_por_avance(indicadores.get("avance_promedio", 0))

    if indicadores.get("avance_promedio", 0) < 30:
        riesgos.append("El avance promedio academico es menor al 30%, con alto riesgo de retraso.")
    elif indicadores.get("avance_promedio", 0) < 70:
        riesgos.append("El avance promedio academico se encuentra entre 30% y 70%, con riesgo medio.")
    else:
        riesgos.append("El avance promedio academico es mayor o igual a 70%, con riesgo bajo si se sostiene el seguimiento.")

    pendientes_alta = [item for item in evidencias if item.get("estado") == "pendiente" and item.get("prioridad") == "alta"]
    if pendientes_alta:
        nivel_riesgo = _max_riesgo(nivel_riesgo, "alto")
        riesgos.append("Existen evidencias academicas de prioridad alta en estado pendiente.")
        for evidencia in pendientes_alta:
            evidencias_criticas.append(f"{_codigo_titulo(evidencia)}: prioridad alta pendiente.")
            acciones.append(_crear_accion(
                "Cerrar evidencia academica prioritaria",
                "Definir fecha de cierre, responsable y sustento documental para la evidencia prioritaria.",
                "alta", evidencia.get("responsable") or "Coordinacion academica", evidencia,
            ))

    docentes_pendientes = [item for item in clasificacion.get("acuerdos_docentes", []) if item.get("estado") == "pendiente"]
    if docentes_pendientes:
        nivel_riesgo = _max_riesgo(nivel_riesgo, "medio")
        riesgos.append("Hay evidencias pendientes relacionadas con docentes, con riesgo de seguimiento docente.")
        observaciones.extend(f"{_codigo_titulo(item)}: acuerdo docente pendiente de seguimiento." for item in docentes_pendientes)

    silabos_portafolios_pendientes = [item for item in clasificacion.get("silabos_portafolios", []) if item.get("estado") in {"pendiente", "observado"}]
    if silabos_portafolios_pendientes:
        nivel_riesgo = _max_riesgo(nivel_riesgo, "alto")
        riesgos.append("Hay evidencias pendientes u observadas sobre silabos o portafolios, con riesgo de coherencia academica.")
        observaciones.extend(f"{_codigo_titulo(item)}: requiere revision de coherencia academica." for item in silabos_portafolios_pendientes)

    completadas_sin_archivo = [item for item in evidencias if item.get("estado") == "completado" and not item.get("archivo_url")]
    if completadas_sin_archivo:
        nivel_riesgo = _max_riesgo(nivel_riesgo, "medio")
        riesgos.append("Existen evidencias completadas sin archivo_url, lo que debilita el sustento documental.")
        evidencias_criticas.extend(f"{_codigo_titulo(item)}: completada sin sustento documental." for item in completadas_sin_archivo)

    actas_en_proceso = [item for item in clasificacion.get("actas", []) if item.get("estado") == "en_proceso"]
    if actas_en_proceso:
        riesgos.append("Existen actas o acuerdos en proceso que requieren seguimiento de cierre.")

    observadas = [item for item in evidencias if item.get("estado") == "observado"]
    if observadas:
        nivel_riesgo = _max_riesgo(nivel_riesgo, "alto")
        riesgos.append("Hay evidencias observadas, con riesgo de incumplimiento academico.")
        observaciones.extend(f"{_codigo_titulo(item)}: evidencia observada pendiente de subsanacion." for item in observadas)

    inconsistencias = [item for item in evidencias if item.get("estado") == "completado" and _avance(item) < 100]
    if inconsistencias:
        nivel_riesgo = _max_riesgo(nivel_riesgo, "medio")
        riesgos.append("Hay evidencias completadas con avance menor a 100%, lo que genera inconsistencia.")
        evidencias_criticas.extend(f"{_codigo_titulo(item)}: completada con avance {_avance(item)}%." for item in inconsistencias)

    if indicadores.get("total_evidencias", 0) == 0:
        nivel_riesgo = "alto"
        riesgos = ["No se encontraron evidencias suficientes para analizar la gestion academica."]

    resumen = (
        f"Se analizaron {indicadores.get('total_evidencias', 0)} evidencias de gestion academica. "
        f"El avance promedio es {indicadores.get('avance_promedio', 0)}%, con "
        f"{indicadores.get('pendientes', 0)} pendientes, {indicadores.get('en_proceso', 0)} en proceso, "
        f"{indicadores.get('completadas', 0)} completadas y {indicadores.get('observadas', 0)} observadas."
    )
    resumen_base = {
        "nivel_riesgo": nivel_riesgo, "resumen": resumen, "indicadores": indicadores,
        "evidencias_criticas": evidencias_criticas, "acciones_sugeridas": acciones,
        "observacion_general": "Diagnostico base calculado por reglas del agente de gestion academica.",
    }
    return {
        **state, "riesgos_detectados": riesgos, "observaciones_academicas": observaciones,
        "evidencias_criticas": evidencias_criticas, "acciones_sugeridas": acciones,
        "resumen_base": resumen_base,
    }
