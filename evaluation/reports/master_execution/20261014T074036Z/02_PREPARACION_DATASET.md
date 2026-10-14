# Prompt 2 — Dataset y Ground Truth

**Estado: BLOQUEADO — DATASET REAL PENDIENTE.**

## Inventario

En el repositorio hay fixtures sintéticos (`evaluation/fixtures/synthetic_*`) y plantillas de corpus, catálogo normativo, Ground Truth y manifiesto de investigación (`evaluation/templates/`). No se encontró un corpus de expedientes institucionales 2025 autorizado, ni catálogo normativo oficial con versión/aplicabilidad verificadas, etiquetas reales, dictámenes de referencia o registros de revisión y adjudicación. No se inspeccionaron credenciales ni se descargaron documentos.

## Unidad y trazabilidad previstas

La unidad de procesamiento es el expediente documental. El manifiesto enlaza documentos integrantes, versiones, formatos, procedencia, autorización y SHA-256 calculado sobre los archivos; también enlaza el catálogo y su versión. La asociación expediente–criterio se registra para clasificación/cobertura. Las etiquetas y dictámenes de referencia permanecen separados de la entrada del sistema. Los macroprocesos se conservan como metadatos y no duplican automáticamente un expediente en experimentos independientes.

## Infraestructura reutilizable

- `corpus_manifest.py`: rutas locales seguras, integridad, procedencia/autorización declarada y congelación.
- `catalog.py`: carga y validación estructural/versionada; cargar un catálogo no lo vuelve oficial.
- `ground_truth.py` y `ground_truth_store.py`: anotaciones, desacuerdos, adjudicación y snapshots separados.
- `dataset.py`: referencias cruzadas y validación final.
- Plantillas vacías en `evaluation/templates/`; no constituyen datos ni contienen hashes reales de expedientes.

## Condición de preparación

No se puede congelar un corpus de tesis sin documentos autorizados. Tampoco se puede declarar aplicabilidad o Ground Truth reales sin catálogo y revisión humana documentados. No se generaron hashes, etiquetas ni dictámenes ficticios. Las pruebas sintéticas de validadores acreditan comportamiento de software únicamente.

**Resultado:** mantener el estado `DATASET REAL PENDIENTE`. El benchmark definitivo y las métricas contra referencia quedan detenidos hasta que responsables institucionales proporcionen corpus, permisos, catálogo/versionado y adjudicación de especialistas.
