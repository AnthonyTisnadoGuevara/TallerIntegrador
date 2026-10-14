# Preparación del dataset y Ground Truth

## Inventario de este repositorio

Al 14-10-2026, la inspección del workspace no encontró expedientes 2025 ni
documentos PDF/DOCX/XLSX/CSV/JSONL de origen institucional. Tampoco encontró un
catálogo normativo oficial, una versión de criterios aprobada, etiquetas reales,
dictámenes de referencia ni actas de revisión/adjudicación. No se inspeccionaron
credenciales ni se contactaron servicios.

Lo disponible es infraestructura y datos de prueba: `fixtures/synthetic_*`,
`catalog.py`, `ground_truth.py`, `ground_truth_store.py` y `dataset.py`. El catálogo
de fixture declara expresamente que es ficticio y su estado es pendiente; no se
debe adaptar como si fuera un catálogo real. Los archivos en `templates/` son
plantillas incompletas, no registros ni ejemplos con datos ficticios. Por tanto,
el estado de los datos institucionales es **DATASET REAL PENDIENTE**.

## Unidad, referencias y separación

La unidad de procesamiento es el **expediente documental**. Cada expediente
lista uno o más documentos con versión, formato, procedencia y SHA-256 calculado
desde sus bytes. Para evaluación normativa, el manifiesto vincula cada
expediente explícitamente a un `catalog_id` y `normative_version`; se requiere un
registro de Ground Truth por cada par expediente/criterio del catálogo enlazado,
incluyendo aplicabilidad no aplicable o indeterminada.

`macroprocesos` se preserva como metadato informativo. El manifiesto no replica
un expediente automáticamente en tres experimentos. Si el protocolo necesita
resultados separados por macroproceso, la selección debe aprobarse y registrarse
explícitamente en las anotaciones/configuración, sin cambiar la unidad de
procesamiento.

Ground Truth debe elaborarse por especialistas de forma independiente, sin
usar las salidas del sistema evaluado como fuente de las etiquetas y sin incluir
etiquetas o dictámenes de referencia en sus prompts. Las discrepancias deben
resolverse y documentarse antes de marcar una referencia final validada.

## Archivos y validación

- `templates/corpus_manifest_template.json`: IDs, catálogo/versiones,
  documentos, procedencia, permisos, restricciones de privacidad y congelación.
- `templates/normative_catalog_template.json`: estructura compatible con
  `evaluation/catalog.py`. Está vacía y no pasa `load_catalog` hasta completar
  los datos auténticos. `load_catalog` deja todo catálogo cargado pendiente;
  la aprobación se registra mediante revisión humana documentada, no mediante
  un campo autoaprobado en el JSON.
- `templates/ground_truth_record_template.json`: estructura orientativa vacía;
  no se carga directamente. `GroundTruthRecord` y `GroundTruthStore` son los
  contratos/almacén de anotaciones.
- `templates/research_manifest_template.json`: inventario de hashes y versiones
  de protocolo, manifiesto del corpus, catálogo(s) y snapshot JSONL de Ground
  Truth para reproducir la congelación del estudio.
- `corpus_manifest.py`: valida rutas seguras bajo una raíz local, archivos
  presentes, IDs/rutas duplicados, permisos, restricciones, hashes documentales
  y hash del manifiesto. `freeze_corpus_manifest` devuelve una copia congelada;
  no guarda archivos ni copia documentos.
- `dataset.validate_final_dataset`: exige manifiesto congelado/autorizado,
  metadatos documentales coherentes, catálogos revisados y Ground Truth completo
  para los criterios del catálogo enlazado a cada expediente.

Los validadores emiten códigos/rutas de campo, no texto de documentos. No
registrar contenido documental en manifiestos, logs o reportes. Guardar los
originales y Ground Truth en almacenamiento de acceso restringido y respaldado
por el procedimiento institucional; no añadirlos al repositorio.

## Procedimiento reproducible para datos autorizados

1. Obtener autorización institucional para corpus, uso de documentos y
   tratamiento de información personal; registrar restricciones concretas.
2. Copiar los documentos autorizados a un directorio de investigación con acceso
   restringido. No colocar originales en `evaluation/` ni en Git.
3. Completar el manifiesto con un ID estable por expediente y documento,
   referencias de procedencia, versiones, formatos, catálogo/versión aplicable
   y metadatos de macroproceso disponibles. No rellenar hashes manualmente.
4. Cargar el catálogo auténtico con `load_catalog`; verificar fuente oficial,
   edición/vigencia, IDs y reglas de aplicabilidad con el responsable
   institucional. No usar `approve_catalog` sin autorización registrada.
5. Cada especialista anota expediente + criterio: aplicabilidad, etiqueta,
   dictamen de referencia y evidencia localizable; firma la revisión con fecha e
   identificador institucional seudonimizado. Mantener anotaciones independientes.
6. Resolver desacuerdos mediante `DisagreementResolution`; validar solo registros
   completos, con al menos dos anotaciones revisadas, dictamen final, revisor,
   fecha y versión. Ground Truth permanece separado de la entrada del agente.
7. Construir contratos `Expediente` desde los documentos ya autorizados y
   verificar `validate_final_dataset` contra el manifiesto, catálogos, referencias
   y archivos. Resolver todos los issues; no omitir casos faltantes.
8. Congelar con `freeze_corpus_manifest(manifest, document_root, frozen_at=...)`.
   Guardar el resultado y el hash del manifiesto en almacenamiento de
   investigación aprobado. Guardar snapshots versionados de catálogo y Ground
   Truth, verificar el hash del catálogo al cargar (`load_catalog` acepta
   `expected_sha256`) y los hashes de integridad de los registros JSONL al leer
   (`GroundTruthStore`). Completar el manifiesto de investigación con SHA-256
   calculado de cada artefacto, versiones y conteo final; no reutilizar hashes
   de fixtures ni escribir valores manualmente.
   El `manifest_sha256` interno representa el JSON canónico sin ese campo; el
   SHA-256 anotado en el manifiesto de investigación debe calcularse sobre los
   bytes exactos del archivo serializado que se archivó.
9. Para las cinco ejecuciones de cada expediente, reutilizar exactamente el
   corpus congelado y los mismos hashes. Cualquier corrección crea una versión
   nueva del corpus y exige documentar el cambio; no reemplazar silenciosamente
   archivos bajo una misma versión.

El SHA-256 detecta modificaciones respecto del manifiesto congelado, pero no
autentica el origen, la autorización, la firma del aprobador ni la autoridad de
una norma. Esos aspectos dependen de controles institucionales externos al
repositorio.

## Alcance que aún no puede verificarse

No hay documentos reales autorizados con los que probar el flujo end-to-end ni
criterios oficiales que permitan confirmar qué catálogo corresponde al periodo
2025. La prueba de validadores con archivos temporales/ficticios verifica
comportamiento del software, no autorización ni resultados científicos. No
ejecutar evaluación definitiva mientras falte cualquier expediente, documento,
catálogo, referencia adjudicada o hash válido.
