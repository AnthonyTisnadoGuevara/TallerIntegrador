# Integración experimental de los tres macroprocesos — Paso 1

## Objetivo y alcance

Este paso unifica la identificación experimental de Planificación Estratégica, Gestión Académica y Gestión de Sílabos dentro de `evaluation/`. No integra todavía los grafos productivos ni constituye una evaluación normativa real. No se añadieron criterios oficiales ni se usaron documentos institucionales.

## Componentes reutilizados

Se mantienen `Expediente`, `DocumentReference`, `CriterionResult`, `ExecutionRecord`, los contratos de aplicabilidad, Ground Truth, el runner JSONL y los cinco instrumentos existentes. Se añade `Macroprocess` con los identificadores que ya usa el backend: `planificacion_estrategica`, `gestion_academica` y `gestion_silabos`.

## Expediente y documentos

La definición técnica provisional es: expediente identificado y versionado, formado por uno o más documentos autorizados y asociado explícitamente a uno o más macroprocesos. El expediente no es el documento ni se equipara automáticamente con `silabo_id`.

`Expediente` conserva `expediente_id`, `corpus_id`, `document_version`, referencias de documentos, hashes, fuente y referencia opcional al sistema de origen. `macroprocesos` es una relación explícita; un mismo expediente puede asociarse a varios procesos sin duplicar sus documentos. La definición institucional sigue pendiente de validación.

El fixture `fixtures/synthetic_macroprocess_cases.json` contiene tres casos ficticios y criterios `SYNTH-*`; no son criterios ICACIT ni datos de investigación.

## Claves y relaciones

La clave lógica nueva es `EvaluationKey(expediente_id, macroproceso, criterion_id, normative_version)`. Los resultados, ejecuciones, aplicabilidades y referencias admiten `macroproceso`. La duplicidad de resultados se controla por ejecución, macroproceso y criterio; la de Ground Truth, por expediente, macroproceso, criterio y versión normativa. Las réplicas se distinguen por experimento, expediente, macroproceso y número de réplica. La configuración ofrece una política de agregación separada por proceso por defecto; cualquier agregación transversal exige una referencia de aprobación metodológica documentada. Los instrumentos no suman procesos automáticamente.

Ground Truth permanece separado de `AgentInput`. Las anotaciones que carecen de macroproceso deben mantenerse como heredadas; no se infiere el proceso a partir del nombre del expediente y no se incluyen al calcular métricas estratificadas.

## Instrumentos OE1–OE5

- **OE1:** Precision/Recall/F1 mantiene sus fórmulas y selecciona ejecuciones y referencias del mismo macroproceso.
- **OE2:** BERTScore y coseno emparejan expediente, proceso, criterio y versión normativa; no se habilitó inferencia semántica externa.
- **OE3:** la cobertura usa aplicabilidad y salida del proceso seleccionado.
- **OE4:** la telemetría informa macroproceso y latencia por expediente/proceso; no mezcla procesos en las filas estratificadas.
- **OE5:** la estabilidad agrupa réplicas por expediente, proceso y experimento.

No se alteraron las fórmulas matemáticas ni se generaron resultados de tesis. Para datos de un solo proceso, la selección puede inferir ese proceso desde el campo explícito de las ejecuciones; ante más de uno exige selección. Los registros heredados permanecen sin atribución.

## Compatibilidad y limitaciones

Los campos añadidos son opcionales para que los JSONL anteriores se puedan leer sin reescribirlos. Un registro sin macroproceso queda sin estratificar y no debe usarse para un resultado por proceso. No se sobrescribe Ground Truth histórico.

Este paso verifica contratos, persistencia sintética y agrupación; no prueba conexión ni integración con Supabase, Gemini ni con los seis grafos productivos. No se ejecutaron consultas, migraciones ni cambios de producción.

## Pruebas y decisiones pendientes

Verificación ejecutada: `python -m unittest discover -s evaluation/tests -v` — **94 pruebas aprobadas** (83 previas y 11 nuevas de contratos/compatibilidad), usando datos sintéticos y almacenes temporales. Las comprobaciones BERTScore/embeddings quedan bloqueadas si requieren artefactos locales no instalados; esto no produce métricas de tesis.

Pendiente: definición institucional de expediente; autorización y selección del corpus; catálogo y aplicabilidad normativa aprobados; política metodológica para criterios compartidos entre procesos; nivel de localización de evidencia exigido.

## Próxima adaptación productiva mínima

La primera función a adaptar posteriormente debería ser la lectura pura del contenido del sílabo (`analizar_texto_silabo`), envolviéndola con un adaptador experimental de solo lectura que reciba una copia local del documento y devuelva salidas trazables. Es la lógica de análisis más aislable; no se debe llamar al nodo que persiste resultados ni equiparar sus secciones faltantes con no conformidades. La elección y autorización del catálogo preceden a cualquier dictamen normativo.
