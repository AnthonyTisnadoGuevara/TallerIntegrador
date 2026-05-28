import re
import unicodedata


SECCIONES_OBLIGATORIAS = {
    "Datos generales": ["datos generales", "informacion general"],
    "Sumilla": ["sumilla"],
    "Aporte al perfil de egreso": ["aporte al perfil de egreso", "perfil de egreso"],
    "Programación por unidades": ["programación por unidades", "unidades de aprendizaje"],
    "Estrategias metodológicas": ["estrategias metodológicas", "metodología"],
    "Recursos": ["recursos", "medios y materiales"],
    "Evaluación": ["evaluación", "instrumentos de evaluación"],
    "Tutoría": ["tutoría", "apoyo pedagógico"],
    "Bibliografía": ["bibliografía", "referencias bibliográficas"],
}

CONTENIDOS_CLAVE = [
    "programación",
    "algoritmo",
    "variables",
    "condicionales",
    "bucles",
    "funciones",
    "arreglos",
    "matemática",
    "matrices",
    "ecuaciones",
    "derivadas",
    "integrales",
    "base de datos",
    "sql",
    "modelo entidad relacion",
    "inteligencia artificial",
    "machine learning",
    "datos",
    "redes",
    "seguridad",
    "arquitectura",
]

VERBOS_APRENDIZAJE = [
    "al finalizar",
    "logra",
    "resuelve",
    "diseña",
    "implementa",
    "analiza",
    "evalúa",
    "desarrolla",
]


def _normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFD", texto or "")
    sin_tildes = "".join(caracter for caracter in sin_tildes if unicodedata.category(caracter) != "Mn")
    return sin_tildes.lower()


def _contiene_verbo(texto_normalizado: str, verbo: str) -> bool:
    patron = rf"\b{re.escape(_normalizar(verbo))}\b"
    return re.search(patron, texto_normalizado) is not None


def _lineas_con_resultados(texto: str) -> list[str]:
    resultados = []
    for linea in re.split(r"[\n\r]+|(?<=[.;])\s+", texto):
        linea_limpia = linea.strip()
        if not linea_limpia:
            continue
        normalizada = _normalizar(linea_limpia)
        if any(_contiene_verbo(normalizada, verbo) for verbo in VERBOS_APRENDIZAJE):
            if linea_limpia not in resultados:
                resultados.append(linea_limpia)
    return resultados[:10]


def analizar_texto_silabo(texto: str, silabo: dict) -> dict:
    """Genera un analisis curricular inicial mediante reglas deterministas."""
    texto_normalizado = _normalizar(texto)

    secciones_faltantes = [
        seccion
        for seccion, claves in SECCIONES_OBLIGATORIAS.items()
        if not any(_normalizar(clave) in texto_normalizado for clave in claves)
    ]
    contenidos_detectados = [
        contenido for contenido in CONTENIDOS_CLAVE if _normalizar(contenido) in texto_normalizado
    ]
    resultados_aprendizaje = _lineas_con_resultados(texto)
    competencias_detectadas = [
        verbo for verbo in VERBOS_APRENDIZAJE if _contiene_verbo(texto_normalizado, verbo)
    ]

    cantidad_faltantes = len(secciones_faltantes)
    if cantidad_faltantes <= 1:
        nivel_riesgo = "bajo"
    elif cantidad_faltantes <= 3:
        nivel_riesgo = "medio"
    else:
        nivel_riesgo = "alto"

    sugerencias = []
    if "Bibliografía" in secciones_faltantes:
        sugerencias.append("Incorporar bibliografía actualizada y pertinente.")
    if "Evaluación" in secciones_faltantes:
        sugerencias.append("Precisar técnicas e instrumentos de evaluación.")
    if "Programación por unidades" in secciones_faltantes:
        sugerencias.append("Detallar la programación por unidades de aprendizaje.")
    if len(contenidos_detectados) < 3:
        sugerencias.append("Precisar contenidos temáticos y su progresión.")
    if len(resultados_aprendizaje) < 2:
        sugerencias.append("Redactar resultados de aprendizaje observables y medibles.")
    if not sugerencias:
        sugerencias.append(
            "El sílabo presenta una estructura favorable; se recomienda mantener "
            "actualizada la bibliografía y evidencias de aprendizaje."
        )

    asignatura = silabo.get("asignatura") or "la asignatura registrada"
    codigo = silabo.get("codigo_asignatura") or "sin código"
    resumen = (
        f"Análisis documental del sílabo de {asignatura} ({codigo}). "
        f"Se identificaron {len(contenidos_detectados)} contenidos temáticos, "
        f"{len(resultados_aprendizaje)} resultados o desempeños formulados y "
        f"{cantidad_faltantes} secciones obligatorias faltantes."
    )
    observacion_general = (
        f"Análisis por reglas aplicado al contenido del documento. "
        f"Nivel de riesgo {nivel_riesgo} por {cantidad_faltantes} secciones faltantes."
    )

    return {
        "resumen": resumen,
        "competencias_detectadas": competencias_detectadas,
        "contenidos_detectados": contenidos_detectados,
        "resultados_aprendizaje": resultados_aprendizaje,
        "secciones_faltantes": secciones_faltantes,
        "sugerencias": sugerencias,
        "nivel_riesgo": nivel_riesgo,
        "observacion_general": observacion_general,
    }
