# Adaptadores del sistema original — Paso 3

## Alcance y separación

La evaluación aislada ejecuta funciones analíticas originales con expedientes sintéticos. No crea agentes ni grafos, no consulta Supabase, no llama Gemini y no modifica persistencia. Las salidas son análisis descriptivos originales; no son resultados científicos ni dictámenes normativos.

| Macroproceso | Funciones originales ejecutadas | Módulo analítico aislado | Estado |
|---|---|---|---|
| Gestión de Sílabos | `curricular_analyzer.analizar_texto_silabo(texto, silabo)` | `backend/app/agents/curricular_analyzer.py` (sin cambios) | Integrado; el adaptador continúa invocando la función original. |
| Gestión Académica | `calcular_indicadores_gestion_academica(state)`, `clasificar_evidencias_academicas(state)`, `detectar_riesgos_academicos(state)` | `backend/app/agents/gestion_academica_analysis.py` | Integrado; ejecuta las tres funciones en el orden original del grafo. |
| Planificación Estratégica | `calcular_indicadores_planificacion(state)`, `detectar_riesgos_estrategicos(state)` | `backend/app/agents/planificacion_analysis.py` | Integrado; ejecuta las dos funciones en el orden original del grafo. |

## Revisión de funciones y dependencias

Las cinco funciones extraídas reciben el estado (`GestionAcademicaState` o `PlanificacionState`) y devuelven un nuevo diccionario que conserva el estado de entrada y añade los campos analíticos. Académica añade `indicadores`, `clasificacion`, `riesgos_detectados`, `observaciones_academicas`, `evidencias_criticas`, `acciones_sugeridas` y `resumen_base`; Planificación añade `dashboard`, `riesgos_detectados`, `evidencias_criticas`, `acciones_sugeridas` y `resumen_base`. Los nombres y las reglas de esos campos se conservaron.

Las funciones leen `state.get(...)` y los campos de las evidencias; no mutan las evidencias ni usan variables globales. Su única excepción observada es la entrada malformada: por ejemplo, una lista con `None` falla con `AttributeError` al invocar `.get`, como antes de la extracción. Las entradas incompletas y vacías admitidas por las funciones conservan sus valores predeterminados originales.

Auxiliares trasladados junto con la lógica que los necesita:

- Académica: `_entero`, `_avance`, `_normalizar_texto`, `_texto_evidencia`, `_codigo_titulo`, `_normalizar_nivel_riesgo`, `_riesgo_por_avance`, `_max_riesgo`, `_crear_accion`.
- Planificación: `_entero`, `_avance`, `_codigo_titulo`, `_normalizar_nivel_riesgo`, `_riesgo_por_avance`, `_max_riesgo`, `_crear_accion`.

Los módulos analíticos nuevos solo importan biblioteca estándar y `typing_extensions`. No importan `supabase_client`, Gemini, FastAPI, persistencia ni grafos. Los grafos productivos siguen importando explícitamente las funciones, los auxiliares y los tipos desde sus módulos analíticos; también conservan las exportaciones anteriores de los auxiliares. Importar los grafos por sí solos todavía carga dependencias productivas, por lo que los adaptadores experimentales no los importan.

## Caracterización previa y regresión

Antes de extraer, se ejecutaron las funciones ubicadas en los módulos originales dentro de un proceso Python aislado. `langgraph`, los recomendadores Gemini y `supabase_client` se sustituyeron únicamente para resolver importaciones; los dobles lanzaban error si se intentaba invocar un servicio. Las entradas fueron sintéticas, con estados pendientes, en proceso, completados y observados; prioridades alta/media/baja; texto clasificable; archivos faltantes/presentes; avances bajo cero, sobre 100 y no numéricos; campos faltantes y entradas vacías.

Se registraron antes del movimiento los indicadores, categorías, riesgos, acciones, evidencias críticas, resúmenes, estados vacíos y el error de entrada malformada. `evaluation/tests/test_original_adapters.py` mantiene expectativas explícitas de caracterización: Académica obtuvo 4 evidencias, avance medio 38, clasificación de A1/A2/A3 y riesgo alto; Planificación con el mismo conjunto obtuvo avance 38, 75 % sin archivo y riesgo alto. Las pruebas comparan también las salidas del adaptador con invocaciones directas a cada función analítica original y verifican la conservación del estado adicional.

El adaptador experimental de cada proceso recibe `metadata["evidencias"]` sintéticas, valida el macroproceso, prepara el estado original, ejecuta la secuencia de funciones y guarda sin transformación normativa el estado devuelto en `analysis_data`. Cada registro incluye identificadores de funciones, SHA-256 del módulo que contiene el código, duración, modo de procesamiento y procedencia. Los errores técnicos se devuelven como registros `ERROR`; no se fabrican salidas.

## Cambios en grafos y comportamiento productivo

`gestion_academica_graph.py` y `planificacion_graph.py` solo cambiaron para importar desde los módulos de análisis los tipos, auxiliares y funciones trasladados. No se alteraron nodos, nombres, transiciones, orden, estado, rutas, recomendaciones Gemini, consultas Supabase ni persistencia. Las pruebas comparan estáticamente los nodos y conexiones esperados; ningún grafo fue compilado ni ejecutado durante las pruebas.

La extracción de funciones puras no demuestra el comportamiento de servicios productivos. No se ejecutaron ni verificaron contra servicios las consultas Supabase, las llamadas Gemini, la persistencia ni las rutas. Los grafos siguen dependiendo de esas integraciones al cargarse y su funcionamiento completo requiere una validación aparte en entorno controlado.

## Adaptador y evaluación normativa

El adaptador de Sílabos se conserva y sigue llamando directamente `analizar_texto_silabo`; no se modificó `curricular_analyzer.py`.

Los tres adaptadores registran `AnalyticalKind.ORIGINAL_ANALYTICAL` y mantienen `normative_results=None`. Indicadores, categorías, recomendaciones o riesgos analíticos no se traducen a conformidad, no conformidad, criterio acreditado ni `CriterionResult`. `BenchmarkRunner` continúa orientado a resultados normativos y no admite directamente este registro descriptivo; no se crean resultados ficticios para conectarlo. La evaluación contra criterios oficiales queda pendiente de contar con el catálogo aprobado, aplicabilidad y evidencia trazable.

## Verificación de efectos externos

Las pruebas de esta fase usan exclusivamente datos en memoria. Las importaciones de módulos analíticos se verifican sin `supabase_client` ni módulos Gemini cargados; no se importan los grafos productivos para ejecutarlos. No se accedió a expedientes reales, tablas, archivos productivos ni servicios externos.
