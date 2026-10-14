# Integración de los datos existentes de la aplicación con la evaluación de tesis

**Tipo de revisión:** inspección estática del código y SQL del repositorio.
**Fecha:** 2026-10-14.
**Acciones deliberadamente no realizadas:** no se consultó Supabase ni Storage; no se llamó a Gemini; no se ejecutaron endpoints ni grafos; no se inspeccionaron variables `.env`; no se modificaron datos o código productivo.

## Conclusión ejecutiva

Sí es posible reutilizar documentos que ya estén almacenados en la aplicación sin volver a subirlos a ella: se requiere una exportación/descarga **de solo lectura y autorizada** de los metadatos y de los objetos existentes de Storage, seguida de una copia controlada en el entorno local de investigación. Sin acceso autorizado al entorno desplegado no se puede confirmar que los registros existan, que los documentos sigan disponibles ni que correspondan a 2025.

El esquema permite guardar evidencias, archivos, fechas, avances, validaciones y resultados/historiales de análisis. Sin embargo, la aplicación no implementa en el código revisado una vinculación sistemática de cada ejecución a un expediente congelado, a criterios normativos versionados, a una salida `CriterionResult` por criterio, ni a configuración, latencia medida y réplica experimental. Por tanto, los datos actuales pueden ser una **fuente documental y de análisis exploratorio**, pero no se convierten automáticamente en Ground Truth o resultados OE1–OE5.

No ejecutar los endpoints de análisis para extraer lo que ya existe: algunos invocan Gemini, descargan documentos o persisten, borran y reemplazan resultados. Para esta fase deben usarse únicamente rutas GET o una exportación read-only, nunca POST/PUT/DELETE de agentes.

## A. Qué información admite actualmente la aplicación según el código

El frontend consume la API FastAPI y el backend usa el cliente Supabase. Los modelos de entrada visibles son modelos Pydantic en los archivos de rutas; no se encontró una capa ORM que pruebe el estado de la base desplegada.

`macroproceso_evidencias` admite `macroproceso`, `codigo`, `titulo`, `descripcion`, `tipo_evidencia`, `responsable`, `mes_programado`, `fecha_programada`, `fecha_cumplimiento`, `estado`, `prioridad`, `avance`, `observacion`, `archivo_url`, `origen_documento`, `created_at` y `updated_at`. Los estados definidos son `pendiente`, `en_proceso`, `completado` y `observado`. Su esquema SQL no contiene un campo explícito de año o periodo documental.

`seguimiento_semanal_evidencias` admite fechas de semana, responsable, porcentaje/nivel de avance, acción realizada, descripción, resultado observado, dificultad, compromiso siguiente, apoyo requerido y URL del sustento. Vincula la fila con `evidencia_id`.

Las estructuras SQL adicionales registran:

- `historial_macroproceso_evidencias`: cambios de campo, valor anterior/nuevo, observación, usuario y fecha.
- `validacion_ia_macroproceso_evidencias`: nivel de validez, pertinencia, resumen, elementos detectados/faltantes, observaciones, recomendaciones, acción sugerida, modelo y fecha.
- `analisis_ia_macroprocesos`: macroproceso, tipo, riesgo, resumen, JSON del resultado, modelo, usuario y `created_at`.
- `silabos`: semestre académico, asignatura, ciclo, fechas, docente/correo, `archivo_url`, estado y porcentaje de cumplimiento.
- `validacion_silabo`: sección, booleano `cumple`, observación y fecha.
- `historial_silabo`: cambios de estado, observación, usuario y fecha.
- `analisis_silabo`: resúmenes, competencias, contenidos, resultados de aprendizaje, secciones faltantes, sugerencias, riesgo y modelo.
- `trazabilidad_curricular` y `brechas_curriculares`: relaciones entre sílabos y brechas descriptivas, con prioridad/estado/fechas.

Las rutas también consultan `acciones_mejora`, pero no se encontró una declaración `CREATE TABLE acciones_mejora` en los SQL inspeccionados; su esquema desplegado no puede inferirse de este repositorio.

El archivo `database/macroprocesos_evidencias.sql` contiene sentencias de inserción de ejemplo, incluso referencias documentales a 2025 y a la RCD 57-2026. Eso acredita que existen semillas en el archivo fuente, **no** que se hayan aplicado, que las filas sigan allí o que sean los registros institucionales existentes en el servidor. No se verificó ningún registro vivo.

## B. Dónde se almacenan y qué historial se conserva

Los registros estructurados se consultan mediante `supabase.table(...)`. Los documentos se representan por URLs en `archivo_url` (evidencias y sílabos) y `archivo_sustento_url` (seguimiento semanal), con subida a Supabase Storage desde las rutas de la aplicación. La ruta de evidencias usa el bucket configurable `SUPABASE_STORAGE_BUCKET` (por defecto `evidencias`); el flujo de sílabos usa Storage de sílabos.

La retención del historial depende del proceso:

| Área | Persistencia según código | Límite relevante para tesis |
|---|---|---|
| Evidencias y avances | Tabla principal más historial de cambios y seguimiento semanal | Las fechas actuales no bastan para probar que una fila/valor existía así en 2025; hay que reconstruirlo con documentos e historial. |
| Análisis de planificación, gestión académica e integral | Inserta una fila append-only en `analisis_ia_macroprocesos` después del análisis | Registra hora de creación y modelo, pero no duración, hash/configuración, réplica ni snapshot de filas de entrada. |
| Validación IA de evidencia | Inserta filas en `validacion_ia_macroproceso_evidencias` | Es historial de validaciones por evidencia, no dictamen normativo por criterio; no registra duración ni configuración de modelo completa. |
| Análisis de sílabo | El grafo borra el análisis previo del mismo sílabo y luego inserta el nuevo | No conserva necesariamente todas las ejecuciones anteriores; no usar el endpoint de análisis durante una inspección read-only. |
| Trazabilidad y brechas curriculares | El grafo elimina filas de trazabilidad y brechas pendientes antes de insertar el resultado actual | No constituye historial de ejecuciones y el endpoint puede reemplazar datos existentes. No ejecutar para extraer. |

Los registros `created_at` de tablas de historial indican fechas de creación de fila/análisis; no equivalen automáticamente al periodo del expediente, al momento de inicio de inferencia o a la duración de una ejecución.

## C. Cómo se accede a documentos y avances

El frontend usa, entre otros, estos endpoints de lectura:

- `GET /api/macroprocesos/evidencias` — permite filtrar por macroproceso, estado, prioridad y responsable; el código no ofrece filtro directo por año.
- `GET /api/macroprocesos/evidencias/{id}/historial`.
- `GET /api/macroprocesos/evidencias/{id}/seguimiento-semanal` y rutas de última semana.
- `GET /api/macroprocesos/evidencias/{id}/validacion-ia` y `/historial`.
- `GET /api/macroprocesos/analisis-ia/historial` y `GET /api/macroprocesos/analisis-ia/historial/{id}`.
- `GET /api/silabos/`, `/api/silabos/{id}/historial`, `/api/agentes/analisis-silabo/{id}`, `/api/agentes/brechas-curriculares` y `/api/agentes/trazabilidad-curricular`.

Los archivos están referenciados por URL de Storage. Los endpoints `POST .../archivo` son para subir y no son necesarios si el objeto ya existe. En la fase autorizada se descargaría/copiaria el objeto existente mediante un mecanismo read-only del propietario (por ejemplo, exportación desde Storage con acceso de lectura), conservando internamente el identificador del objeto y calculando SHA-256 sobre los bytes descargados. No se deben copiar URLs firmadas ni credenciales al manifiesto o a este repositorio.

La aplicación tiene lectores para PDF/DOCX y la validación de evidencia extrae texto por URL. Eso no autoriza a llamarlos aquí: el lector productivo usa solicitudes remotas. El lector aislado `evaluation/document_reader.py` es más restrictivo: solo acepta `.txt` UTF-8 local bajo una raíz autorizada, verifica hash, impide URLs/traversal y limita tamaño. La reutilización directa de PDF/DOCX exige una extracción local/offline controlada o un lector local aprobado; el original binario debe conservar su hash y la transformación de texto debe documentarse.

## D. Cómo se ejecutan los análisis LangGraph

Los grafos se compilan con `StateGraph` y se invocan mediante `graph.invoke(...)`. El código productivo no expone una ruta genérica de ejecución read-only:

| Flujo | Secuencia/entrada visible | Efectos observados en código |
|---|---|---|
| Planificación | Lee todas las filas `macroproceso_evidencias` del macroproceso, calcula indicadores/riesgos, llama Gemini, construye resultado | El grafo no guarda el resultado en sí; la ruta POST `/api/macroprocesos/planificacion/analizar` después inserta el JSON en historial. |
| Gestión Académica | Lee las evidencias del macroproceso; indicadores, clasificación académica, acuerdos, riesgos, Gemini | La ruta POST `/gestion-academica/analizar` registra historial. No es evaluación normativa por criterio. |
| Coordinador de mejora continua | Lee evidencias, acciones, brechas y sílabos; agrega hallazgos, riesgo y Gemini | La ruta POST `/mejora-continua/analizar` inserta historial. No es equivalente a ejecutar tres grafos independientes sobre el mismo expediente; deriva un resumen sobre tablas persistidas. |
| Validación de evidencia | Recibe ID; lee fila y archivo, extrae texto, aplica reglas y Gemini | El nodo final inserta en `validacion_ia_macroproceso_evidencias`; la ruta POST `/evidencias/{id}/validar-ia` escribe. |
| Análisis de sílabo | Recibe `silabo_id`; lee fila, descarga URL, extrae texto, analiza y llama Gemini | El nodo final hace `DELETE` del análisis anterior del sílabo e `INSERT` del nuevo. Endpoint POST `/api/agentes/analizar-silabo/{id}` es destructivo respecto del resultado anterior. |
| Trazabilidad curricular | Lee sílabos y análisis, deriva relaciones y brechas, puede enriquecer con contexto/Gemini | Guarda relaciones y brechas mediante borrados e inserciones. Endpoint POST `/api/agentes/analizar-trazabilidad-curricular` no es read-only. |

Los resultados contienen indicadores, niveles de riesgo, hallazgos, elementos detectados/faltantes, observaciones, recomendaciones, brechas, relaciones o resúmenes, según el flujo. En el código no se observa un formato uniforme de resultado normativo `criterio_id + versión + aplicabilidad + clasificación + evidencia localizada` para los tres macroprocesos.

## E. Qué salidas existentes pueden alimentar OE1–OE5

| Objetivo | Datos web que podrían servir como fuente | Brecha que impide usarlos directamente como medición válida |
|---|---|---|
| OE1 — identificar no conformidades | Riesgos, observaciones, `nivel_validez`, `pertinencia`, secciones faltantes, brechas y `validacion_silabo.cumple` | Son señales descriptivas/listas de verificación del sistema. No son clasificación de conformidad contra criterio normativo oficial y no hay Ground Truth adjudicado. No mapearlas a `no_conforme`. |
| OE2 — comparar dictámenes textuales | `resultado_json`/`resumen`, `validacion...resumen`, salida de análisis curricular y recomendaciones | Hay texto de salida potencialmente recuperable, pero no se confirma que sea dictamen por criterio ni queda emparejado con `reference_verdict` de especialistas. Sirve como salida candidata exploratoria, no como puntuación OE2 definitiva. |
| OE3 — cobertura de criterios | Filas de evidencias/validaciones y checklist de sílabo | No se observa catálogo versionado ni IDs normativos evaluados enlazados a expediente y resultado. El total de evidencias o secciones no equivale a cobertura normativa. |
| OE4 — latencia | `created_at` de historial y validaciones | Solo un timestamp de persistencia. No contiene inicio/fin monotónico ni `duration_ns`; diferencias entre timestamps incluyen tiempos no aislados y no son latencia fiable del agente. |
| OE5 — estabilidad | Varias filas históricas pueden revelar análisis realizados en diferentes fechas; algunas validaciones tienen historial | No hay `experiment_id`, número de réplica, corpus/configuración congelados, hashes de entrada/prompt/código ni garantía de cinco ejecuciones comparables. Análisis de sílabo y trazabilidad además pueden sobrescribir datos anteriores. |

Los cinco scripts de `evaluation/` consumen contratos experimentales (`ExecutionRecord`, resultados por criterio y, para OE1/OE2, Ground Truth validado). No hay un importador que transforme de forma segura los esquemas web actuales a esos contratos. Aunque se escribiera un conversor, no podría inventar los campos ausentes ni convertir análisis descriptivo en dictamen normativo.

## F. Funcionalidades o datos que faltan

1. Exportación read-only autorizada y reproducible de metadatos, historiales y objetos de Storage, con filtros temporales y mapeo de relaciones.
2. Confirmación del periodo histórico por documento/registro. `macroproceso_evidencias` carece de campo `periodo`; `created_at`/`updated_at` no prueban el año de la evidencia.
3. Catálogo oficial aplicable a la documentación 2025: identificador, versión, fuente, vigencia, texto y regla de aplicabilidad validados por responsable institucional.
4. Ground Truth separado, elaborado por especialistas: aplicabilidad, etiqueta, dictamen, evidencia localizable, revisión, desacuerdo y adjudicación.
5. Salida normativa con criterio/versiones/evidencia, distinta de riesgo, pertinencia, observación o recomendación.
6. Captura por ejecución de entrada congelada/hash, versión de código, modelo/prompt/parámetros, modo real/fallback, inicio/fin/duración, error y réplica.
7. Ruta experimental que ejecute el artefacto bajo evaluación sin acceder a datos productivos ni borrar/escribir resultados existentes. Hoy no está disponible como endpoint/adaptador de evaluación integral.
8. Verificación de autorización y privacidad de documentos, nombres, correos, responsables y actas; seudonimización y ubicación de trabajo restringida.

## G. Cómo aprovechar los datos existentes sin volver a cargarlos

1. **Autorizar y seleccionar**: el propietario define cuenta/proyecto, conjunto de tablas/objetos, alcance temporal y quién puede exportar. No usar claves `service_role` en frontend ni compartir secretos.
2. **Extraer en modo lectura**: usar las rutas GET existentes o exportación de solo lectura. Seleccionar solo campos necesarios. Para 2025, obtener evidencia, historial, seguimiento, validaciones, acciones y análisis relacionados; no inferir el periodo por el macroproceso.
3. **Resolver temporalidad**: reconstruir qué valor/archivo estaba vigente en la fecha relevante a partir de historial y documentos fechados. Si no puede probarse, marcar `periodo no confirmado` y excluirlo del corpus definitivo, no completar por suposición.
4. **Copiar objetos existentes**: descargar desde Storage con autorización de lectura a una ubicación local de investigación restringida. No volver a subirlos a la web. Mantener vínculo interno a la fila/objeto original, versión, fecha de exportación y SHA-256. No poner datos personales ni URLs firmadas en reportes/Git.
5. **Construir expediente**: unidad = expediente documental; agregar los documentos que pertenecen al mismo caso con referencias a IDs de origen. Conservar macroproceso como metadato; no replicar automáticamente un caso en tres expedientes.
6. **Preparar conversión experimental**: completar un borrador del manifiesto y validar hashes/rutas. `corpus_manifest.py` permite registrar procedencia, autorización, periodo, documentos, versiones, privacidad y congelación. No congelar hasta resolver permisos, temporalidad, completitud y protocolo.
7. **Conservar las salidas históricas aparte**: exportarlas como observaciones originales del sistema, con su `created_at` y claves de relación; no tratarlas como réplicas experimentales ni Ground Truth.

Los contratos pueden recibir datos auténticos así:

| Contrato | Completable desde aplicación, si se exporta y verifica | Pendiente/externo |
|---|---|---|
| `DocumentReference` / `Expediente` | IDs pseudonimizados, nombre seguro, formato, SHA-256 real, versión/fecha documentada, localizador relativo, referencia de origen y macroprocesos | Autorización formal, periodo confirmado, completitud del expediente y contenido local bajo almacenamiento restringido. |
| `NormativeCatalog` | Nada se debe inferir de las evidencias; puede cargarse el documento oficial una vez proporcionado | Fuente/versión/texto/IDs/reglas oficiales, hash y validación humana autorizada. La RCD o un plan institucional no se vuelve automáticamente catálogo normativo. |
| `GroundTruthRecord` | Relaciones a expediente/criterio y localizadores de evidencia pueden prepararse | Etiqueta/dictamen de referencia, anotaciones independientes, evaluadores, revisión y adjudicación. No poblar desde salidas IA. |
| `Dataset` / `ExecutionRecord` | IDs, corpus hash y vínculo de macroproceso pueden referenciarse | Resultado por criterio, configuración congelada, duración instrumentada, status/réplica y validación integral. El sistema actual no conserva estos datos completos. |

Las entradas incompletas deben mantenerse como borrador/pendiente; `validate_final_dataset` está diseñado para rechazarlas hasta autorización, hashes válidos, catálogo revisado y Ground Truth completo. No añadir datos reales a `evaluation/fixtures/`.

## H. Cómo realizar la primera prueba de forma segura

Separar claramente tres niveles:

### 1. Prueba técnica de lectura y extracción

Después de autorización, escoger un solo documento cuyo periodo y pertenencia al caso estén confirmados. Copiar localmente el objeto ya existente en modo read-only; calcular hash del original; extraer texto sin red; verificar páginas/secciones y guardar un registro de procedencia sin contenido personal. No invocar ningún agente ni llamar al backend productivo. Si es PDF/DOCX, la conversión debe ejecutarse offline y documentar herramienta/versión; el lector actual de `evaluation/` solo acepta `.txt` UTF-8.

### 2. Prueba funcional del razonamiento del artefacto

No ejecutar hoy los endpoints POST de análisis. Los grafos actuales leen Supabase, llaman Gemini y algunos persisten o borran resultados; el código no ofrece un modo completo `dry-run`/solo lectura. La alternativa exige primero autorizar y preparar un snapshot local mínimo y aislado, inyectar dependencias para leer el snapshot y descartar escrituras; el comportamiento de escritura debe interceptarse. Si se elimina Gemini o se sustituye por doble, la prueba ya no acredita el comportamiento LLM real y debe rotularse como ejecución parcial/determinista. Para una ejecución con Gemini real se requiere autorización explícita para enviar ese documento al proveedor, más controles de privacidad y un canal que evite efectos de Supabase; no se hace en esta etapa.

Las funciones analíticas puras ya desacopladas de Gestión Académica y Planificación, y el analizador curricular original, pueden probarse con estado local autorizado a través de adaptadores experimentales, pero eso mide únicamente esas funciones (no los seis grafos completos ni Gemini). Debe conservarse esa distinción.

### 3. Evaluación científica OE1–OE5

Solo después de aprobación de protocolo/corpus/norma/Ground Truth y de un adaptador seguro que ejecute el artefacto objetivo real, convertir cada salida al contrato correspondiente con criterio y evidencia; congelar las entradas; capturar `duration_ns`; ejecutar réplicas independientes con igual configuración y conservar cada salida sin sobreescritura. Luego usar los scripts existentes. OE1–OE3 no son válidos sin norma/aplicabilidad/Ground Truth; OE2 no es válido contra referencia inexistente; OE4 requiere duración de runner instrumentada; OE5 requiere cinco réplicas comparables. No iniciar benchmark definitivo en la primera prueba técnica.

## I. Qué se debe autorizar o proporcionar para continuar

1. Autorización institucional de uso de los registros y documentos 2025, alcance de privacidad, retención y quién puede acceder.
2. Una vía segura de solo lectura para exportar tablas/filas y descargar objetos ya guardados; no compartir credenciales en el chat o repositorio.
3. Confirmación de qué evidencias/registros constituyen el primer expediente y cómo verificar la fecha/versión 2025 con originales e historial.
4. Catálogo normativo auténtico aplicable y responsable que confirme versión, vigencia y aplicabilidad; no basta con el SQL semilla, RCD, ROM o PAC.
5. Protocolo de Ground Truth: especialistas, etiquetas, doble revisión, adjudicador y forma de registrar evidencia/dictamen.
6. Decisión metodológica sobre evaluar el artefacto completo con Gemini o delimitar explícitamente evaluación de las funciones deterministas; si se requiere Gemini real, autorización de tratamiento por el proveedor.
7. Aprobación para diseñar después un adaptador de evaluación con snapshot y escrituras aisladas. Esta etapa no implementa ese adaptador.

## Diagnóstico final

**Reutilización de archivos existentes: viable en principio sin volver a subirlos a la aplicación**, mediante copia local de solo lectura autorizada desde el almacenamiento existente. **Disponibilidad real y periodo 2025: no verificados**, porque no se consultó el servicio ni se recibieron exportaciones locales. **Uso científico directo de los resultados web: insuficiente para OE1–OE5**, aunque algunos resúmenes/historiales puedan conservarse como salidas candidatas exploratorias. El siguiente paso es autorizar y preparar una exportación local mínima, no ejecutar los agentes.
