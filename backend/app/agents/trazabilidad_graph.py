import json
import unicodedata
from typing import Any

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from app.services.supabase_client import supabase


FAMILIAS_TEMATICAS = {
    "programacion": [
        "programacion",
        "algoritmo",
        "java",
        "poo",
        "objetos",
        "clases",
        "estructuras de datos",
        "patrones",
    ],
    "datos": [
        "estadistica",
        "probabilidad",
        "datos",
        "base de datos",
        "sql",
        "big data",
        "machine learning",
        "deep learning",
    ],
    "ia": [
        "inteligencia artificial",
        "machine learning",
        "deep learning",
        "redes neuronales",
        "vision",
        "percepcion",
        "nlp",
    ],
    "infraestructura": [
        "redes",
        "sistemas operativos",
        "nube",
        "infraestructura",
        "terraform",
        "ansible",
        "iot",
        "blockchain",
    ],
    "software": [
        "requisitos",
        "ingenieria de software",
        "arquitectura",
        "sistemas integrados",
        "aplicaciones moviles",
    ],
    "gestion": [
        "procesos",
        "bpmn",
        "gestion",
        "proyectos",
        "pmbok",
        "customer development",
        "agile",
    ],
    "investigacion": [
        "proyecto de investigacion",
        "tesis",
        "metodologia",
        "instrumentos",
        "resultados",
    ],
}

TERMINOS_AVANZADOS = {
    "programacion": ["patrones", "arquitectura", "estructuras de datos"],
    "datos": ["big data", "machine learning", "deep learning"],
    "ia": ["machine learning", "deep learning", "redes neuronales", "vision", "nlp"],
    "infraestructura": ["nube", "terraform", "ansible", "iot", "blockchain"],
    "software": ["arquitectura", "sistemas integrados", "aplicaciones moviles"],
    "gestion": ["pmbok", "customer development", "agile"],
    "investigacion": ["tesis", "resultados"],
}

_graph_trazabilidad = None


class TrazabilidadState(TypedDict, total=False):
    silabos: list
    analisis: list
    silabos_por_ciclo: dict
    relaciones: list
    brechas: list
    resultado_trazabilidad: list
    resultado_brechas: list
    error: str


def _normalizar_texto(valor: Any) -> str:
    texto = str(valor or "")
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(caracter for caracter in texto if unicodedata.category(caracter) != "Mn")
    return texto.lower().strip()


def _entero_o_none(valor: Any) -> int | None:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def normalizar_lista(valor):
    if valor is None:
        return []

    if isinstance(valor, list):
        return valor

    if isinstance(valor, str):
        valor_limpio = valor.strip()
        if not valor_limpio:
            return []
        try:
            resultado = json.loads(valor_limpio)
        except json.JSONDecodeError:
            return [valor_limpio]
        return resultado if isinstance(resultado, list) else []

    return []


def calcular_interseccion(lista_a, lista_b):
    valores_a = [str(item) for item in normalizar_lista(lista_a)]
    valores_b = [str(item) for item in normalizar_lista(lista_b)]
    normalizados_b = {_normalizar_texto(item): item for item in valores_b}

    comunes = []
    for item_a in valores_a:
        normalizado_a = _normalizar_texto(item_a)
        if not normalizado_a:
            continue

        for normalizado_b, item_b in normalizados_b.items():
            if (
                normalizado_a == normalizado_b
                or normalizado_a in normalizado_b
                or normalizado_b in normalizado_a
            ):
                comunes.append(item_b)
                break

    return comunes


def detectar_familias(texto_o_lista):
    if isinstance(texto_o_lista, list):
        texto = " ".join(str(item) for item in texto_o_lista)
    else:
        texto = str(texto_o_lista or "")

    texto_normalizado = _normalizar_texto(texto)
    familias = []
    for familia, palabras_clave in FAMILIAS_TEMATICAS.items():
        if any(_normalizar_texto(palabra) in texto_normalizado for palabra in palabras_clave):
            familias.append(familia)

    return familias


def _texto_curricular(item: dict) -> str:
    silabo = item.get("silabo") or {}
    analisis = item.get("analisis") or {}
    partes = [
        silabo.get("asignatura"),
        silabo.get("codigo_asignatura"),
        analisis.get("resumen"),
        " ".join(str(valor) for valor in normalizar_lista(analisis.get("contenidos_detectados"))),
        " ".join(str(valor) for valor in normalizar_lista(analisis.get("competencias_detectadas"))),
        " ".join(str(valor) for valor in normalizar_lista(analisis.get("resultados_aprendizaje"))),
    ]
    return " ".join(str(parte) for parte in partes if parte)


def _tiene_terminos_avanzados(familia: str, texto: str) -> bool:
    texto_normalizado = _normalizar_texto(texto)
    return any(
        _normalizar_texto(termino) in texto_normalizado
        for termino in TERMINOS_AVANZADOS.get(familia, [])
    )


def obtener_silabos_y_analisis(state: TrazabilidadState) -> TrazabilidadState:
    silabos_response = (
        supabase.table("silabos")
        .select("*")
        .order("ciclo")
        .execute()
    )
    analisis_response = supabase.table("analisis_silabo").select("*").execute()

    return {
        **state,
        "silabos": silabos_response.data or [],
        "analisis": analisis_response.data or [],
    }


def agrupar_por_ciclo(state: TrazabilidadState) -> TrazabilidadState:
    analisis_por_silabo = {
        item.get("silabo_id"): item
        for item in state.get("analisis", [])
        if item.get("silabo_id")
    }
    silabos_por_ciclo = {}

    for silabo in state.get("silabos", []):
        ciclo = silabo.get("ciclo")
        if ciclo is None:
            continue

        ciclo_entero = _entero_o_none(ciclo)
        if ciclo_entero is None:
            continue

        silabos_por_ciclo.setdefault(ciclo_entero, []).append(
            {
                "silabo": silabo,
                "analisis": analisis_por_silabo.get(silabo.get("id"), {}),
            }
        )

    return {
        **state,
        "silabos_por_ciclo": silabos_por_ciclo,
    }


def analizar_relaciones(state: TrazabilidadState) -> TrazabilidadState:
    silabos_por_ciclo = state.get("silabos_por_ciclo", {})
    relaciones = []
    familias_acumuladas = set()

    for ciclo in range(1, 10):
        origenes = silabos_por_ciclo.get(ciclo, [])
        destinos = silabos_por_ciclo.get(ciclo + 1, [])

        for origen in origenes:
            familias_acumuladas.update(detectar_familias(_texto_curricular(origen)))

        for origen in origenes:
            silabo_origen = origen.get("silabo", {})
            analisis_origen = origen.get("analisis", {})
            texto_origen = _texto_curricular(origen)
            familias_origen = set(detectar_familias(texto_origen))
            contenidos_origen = normalizar_lista(analisis_origen.get("contenidos_detectados"))

            for destino in destinos:
                silabo_destino = destino.get("silabo", {})
                analisis_destino = destino.get("analisis", {})
                texto_destino = _texto_curricular(destino)
                familias_destino = set(detectar_familias(texto_destino))
                contenidos_destino = normalizar_lista(analisis_destino.get("contenidos_detectados"))
                familias_comunes = sorted(familias_origen & familias_destino)
                contenidos_comunes = calcular_interseccion(contenidos_origen, contenidos_destino)

                if familias_comunes or contenidos_comunes:
                    familia_principal = familias_comunes[0] if familias_comunes else "contenidos"
                    es_progresion = _tiene_terminos_avanzados(familia_principal, texto_destino)
                    tipo_relacion = "progresion_adecuada" if es_progresion else "continuidad_tematica"
                    nivel_coherencia = "alto" if es_progresion or len(contenidos_comunes) >= 2 else "medio"
                    descripcion = (
                        f"{silabo_destino.get('asignatura')} mantiene continuidad con "
                        f"{silabo_origen.get('asignatura')} en {', '.join(familias_comunes) or 'contenidos afines'}."
                    )

                    if len(contenidos_comunes) >= 4 and not es_progresion:
                        tipo_relacion = "repeticion"
                        nivel_coherencia = "bajo"
                        descripcion = (
                            f"Se detecta repetición temática entre {silabo_origen.get('asignatura')} "
                            f"y {silabo_destino.get('asignatura')} sin evidencia clara de mayor complejidad."
                        )

                    relaciones.append(
                        {
                            "silabo_origen_id": silabo_origen.get("id"),
                            "silabo_destino_id": silabo_destino.get("id"),
                            "ciclo_origen": ciclo,
                            "ciclo_destino": ciclo + 1,
                            "asignatura_origen": silabo_origen.get("asignatura"),
                            "asignatura_destino": silabo_destino.get("asignatura"),
                            "tipo_relacion": tipo_relacion,
                            "descripcion": descripcion,
                            "nivel_coherencia": nivel_coherencia,
                            "observacion": (
                                f"Familias comunes: {', '.join(familias_comunes) or 'no identificadas'}. "
                                f"Contenidos comunes: {len(contenidos_comunes)}."
                            ),
                            "sugerencia": (
                                "Explicitar prerrequisitos y evidencias de progresión curricular."
                                if nivel_coherencia != "alto"
                                else "Mantener la articulación y documentar evidencias de continuidad."
                            ),
                        }
                    )
                    continue

                familias_avanzadas_destino = [
                    familia
                    for familia in familias_destino
                    if _tiene_terminos_avanzados(familia, texto_destino)
                ]
                if familias_avanzadas_destino and not (set(familias_avanzadas_destino) & familias_acumuladas):
                    relaciones.append(
                        {
                            "silabo_origen_id": silabo_origen.get("id"),
                            "silabo_destino_id": silabo_destino.get("id"),
                            "ciclo_origen": ciclo,
                            "ciclo_destino": ciclo + 1,
                            "asignatura_origen": silabo_origen.get("asignatura"),
                            "asignatura_destino": silabo_destino.get("asignatura"),
                            "tipo_relacion": "vacio_formativo",
                            "descripcion": (
                                f"{silabo_destino.get('asignatura')} incluye temas avanzados "
                                "sin una base temática previa claramente detectada."
                            ),
                            "nivel_coherencia": "bajo",
                            "observacion": f"Familias avanzadas sin base previa: {', '.join(familias_avanzadas_destino)}.",
                            "sugerencia": "Revisar prerrequisitos o incorporar contenidos base en ciclos previos.",
                        }
                    )

        for destino in destinos:
            familias_acumuladas.update(detectar_familias(_texto_curricular(destino)))

    return {
        **state,
        "relaciones": relaciones,
    }


def detectar_brechas(state: TrazabilidadState) -> TrazabilidadState:
    relaciones = state.get("relaciones", [])
    silabos = state.get("silabos", [])
    analisis_por_silabo = {
        item.get("silabo_id"): item
        for item in state.get("analisis", [])
        if item.get("silabo_id")
    }
    destinos_con_relacion = {
        relacion.get("silabo_destino_id")
        for relacion in relaciones
        if relacion.get("tipo_relacion") in {"continuidad_tematica", "progresion_adecuada"}
    }
    brechas = []

    for silabo in silabos:
        silabo_id = silabo.get("id")
        ciclo = _entero_o_none(silabo.get("ciclo"))
        asignatura = silabo.get("asignatura")
        analisis = analisis_por_silabo.get(silabo_id, {})
        secciones_faltantes = normalizar_lista(analisis.get("secciones_faltantes"))

        if analisis.get("nivel_riesgo") == "alto" or len(secciones_faltantes) >= 4:
            brechas.append(
                {
                    "silabo_id": silabo_id,
                    "ciclo": ciclo,
                    "asignatura": asignatura,
                    "tipo_brecha": "estructura_incompleta",
                    "descripcion": "El sílabo presenta riesgo alto o varias secciones obligatorias faltantes.",
                    "recomendacion": "Completar estructura institucional, evaluación, bibliografía y programación por unidades.",
                    "prioridad": "alta",
                    "estado": "pendiente",
                }
            )

        if ciclo and ciclo >= 5 and silabo_id not in destinos_con_relacion:
            brechas.append(
                {
                    "silabo_id": silabo_id,
                    "ciclo": ciclo,
                    "asignatura": asignatura,
                    "tipo_brecha": "falta_trazabilidad",
                    "descripcion": "Curso avanzado sin relación curricular clara con cursos previos analizados.",
                    "recomendacion": "Revisar mapa curricular y explicitar prerrequisitos o competencias de entrada.",
                    "prioridad": "media",
                    "estado": "pendiente",
                }
            )

    for relacion in relaciones:
        if relacion.get("tipo_relacion") not in {"vacio_formativo", "repeticion"}:
            continue

        brechas.append(
            {
                "silabo_id": relacion.get("silabo_destino_id"),
                "ciclo": relacion.get("ciclo_destino"),
                "asignatura": relacion.get("asignatura_destino"),
                "tipo_brecha": relacion.get("tipo_relacion"),
                "descripcion": relacion.get("descripcion"),
                "recomendacion": relacion.get("sugerencia"),
                "prioridad": "alta" if relacion.get("tipo_relacion") == "vacio_formativo" else "media",
                "estado": "pendiente",
            }
        )

    return {
        **state,
        "brechas": brechas,
    }


def guardar_trazabilidad(state: TrazabilidadState) -> TrazabilidadState:
    relaciones = state.get("relaciones", [])

    (
        supabase.table("trazabilidad_curricular")
        .delete()
        .neq("id", "00000000-0000-0000-0000-000000000000")
        .execute()
    )

    resultado = []
    if relaciones:
        insert_response = supabase.table("trazabilidad_curricular").insert(relaciones).execute()
        resultado = insert_response.data or relaciones

    return {
        **state,
        "resultado_trazabilidad": resultado,
    }


def guardar_brechas(state: TrazabilidadState) -> TrazabilidadState:
    brechas = state.get("brechas", [])

    (
        supabase.table("brechas_curriculares")
        .delete()
        .eq("estado", "pendiente")
        .execute()
    )

    resultado = []
    if brechas:
        insert_response = supabase.table("brechas_curriculares").insert(brechas).execute()
        resultado = insert_response.data or brechas

    return {
        **state,
        "resultado_brechas": resultado,
    }


def construir_grafo_trazabilidad():
    graph = StateGraph(TrazabilidadState)
    graph.add_node("obtener_silabos_y_analisis", obtener_silabos_y_analisis)
    graph.add_node("agrupar_por_ciclo", agrupar_por_ciclo)
    graph.add_node("analizar_relaciones", analizar_relaciones)
    graph.add_node("detectar_brechas", detectar_brechas)
    graph.add_node("guardar_trazabilidad", guardar_trazabilidad)
    graph.add_node("guardar_brechas", guardar_brechas)

    graph.add_edge(START, "obtener_silabos_y_analisis")
    graph.add_edge("obtener_silabos_y_analisis", "agrupar_por_ciclo")
    graph.add_edge("agrupar_por_ciclo", "analizar_relaciones")
    graph.add_edge("analizar_relaciones", "detectar_brechas")
    graph.add_edge("detectar_brechas", "guardar_trazabilidad")
    graph.add_edge("guardar_trazabilidad", "guardar_brechas")
    graph.add_edge("guardar_brechas", END)

    return graph.compile()


def get_graph_trazabilidad():
    global _graph_trazabilidad
    if _graph_trazabilidad is None:
        _graph_trazabilidad = construir_grafo_trazabilidad()
    return _graph_trazabilidad


def ejecutar_grafo_trazabilidad() -> dict:
    graph = get_graph_trazabilidad()
    return graph.invoke({})
