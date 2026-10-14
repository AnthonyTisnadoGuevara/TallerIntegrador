# Fase 4 — instrumentos computacionales OE1–OE5

Este módulo implementa cálculo/exportación reproducibles, no una evaluación
normativa real ni resultados de tesis. Los cinco instrumentos consumen los
contratos existentes `ExecutionRecord`, catálogo y, cuando corresponda,
Ground Truth final validado. No leen documentos fuente ni invocan agentes
productivos, Supabase o proveedores LLM.

## Política común y reproducción

- El modo por defecto es `synthetic_test`. Solo acepta ejecuciones/configuración
  sintéticas y catálogos/IDs sintéticos. `authorized` exige `--authorization-ref`
  y metadatos declarados de aprobación del catálogo. Esas referencias son
  afirmaciones del operador, no autenticación ni autorización del sistema
  operativo; proteja los archivos y el host fuera de estos scripts.
- OE1, OE2 y OE3 escogen una única ejecución primaria `replica=1` por expediente
  dentro de un experimento único o indicado con `--experiment-id`. OE4 preserva
  cada ejecución seleccionada (también errores); OE5 compara todas las réplicas
  1–5 en un experimento.
- Los enlaces por expediente, criterio y versión normativa se validan. Las
  entradas inválidas/ambiguas fallan explícitamente; los casos excluidos,
  fallidos, no aplicables, indeterminados y abstenciones quedan contabilizados.
- Cada ejecución exporta `summary.json` y `details.csv` en una carpeta nueva,
  bajo `evaluation/outputs/metrics` por defecto. No se sobrescriben carpetas.
  El resumen registra hashes de entradas, configuración y procedencia (código,
  prompt, catálogo/corpus, proveedor/modelo/versión, temperatura/semilla).
  No exporta textos de expedientes. El hash es huella de integridad, no firma.
- `--config` acepta opcionalmente un JSON de `ExperimentConfig` esperado; si se
  aporta, debe coincidir exactamente con todas las ejecuciones del archivo.

## Definiciones

| Instrumento | Definición implementada | Límites/condición |
|---|---|---|
| OE1 (`eval_precision_f1`) | Clase positiva `no_conforme`, negativa `conforme`; TP/FP/TN/FN, precision, recall y F1. Denominador cero produce `null`. | Solo Ground Truth validado, aplicable y binario. Predicción ausente, ejecución fallida o resultado no evaluado es abstención; métricas condicionales a casos evaluados acompañadas de tasa de abstención. |
| OE2 (`eval_bertscore`) | Empareja rationale del `CriterionResult` evaluado con `reference_verdict` de Ground Truth por expediente+criterio+versión. Reporta P/R/F1 de BERTScore y similitud coseno de embeddings. | Requiere `--response-kind criterion_verdict`, modelos locales con revisión declarada y paquetes Python disponibles. No compara dictamen global ni usa similitud como corrección normativa. |
| OE3 (`eval_coverage`) | `criterios aplicables explícitamente evaluados / criterios aplicables validados × 100`. | Aplicabilidad proviene solo del Ground Truth final validado. Omisiones, no evaluables, indeterminados, errores técnicos y no aplicables se desglosan; denominador cero da `null`. Cobertura no es cumplimiento/acreditación. |
| OE4 (`eval_telemetry`) | Duración en segundos a partir de `duration_ns`; media, mediana, mínimo, máximo, desviación estándar muestral, P90/P95 lineales (tipo 7); separa éxitos/errores. | Conserva estados y categorías de error. Telemetría no reportada queda explícitamente ausente; no se infieren tokens, tiempo por nodo, CPU o memoria. La duración cubre invocación del adaptador y validación de salida; excluye escritura JSONL. |
| OE5 (`eval_stability`) | En cada grupo de cinco réplicas produce los 10 pares; informa réplicas faltantes/duplicadas/errores, condiciones incompatibles, acuerdo y transiciones de etiquetas, cambios de cobertura y modo. | Coseno entre rationale globales solo se calcula con encoder local. La variación estructural puede informarse aun si falta modelo, y el estado indica que la parte semántica está bloqueada. |

La selección primaria fija réplica 1 para OE1–OE3 para evitar pseudorreplicación
en métricas contra Ground Truth. OE5 usa explícitamente las cinco réplicas.
Estas son decisiones técnicas iniciales y deben ser ratificadas por el
protocolo de tesis antes de usarse en resultados publicables.

## Modelos del instrumento OE2

Configuración codificada: `bert-base-multilingual-cased`, español, 9 capas,
CPU, sin IDF ni reescalado por baseline, junto con tokenizer lento; las entradas
que exceden 510 tokens de contenido se señalan por truncamiento. La
implementación oficial de BERTScore permite seleccionar modelo/capas y advierte
el límite práctico de longitud del encoder ([documentación oficial de
BERTScore](https://github.com/Tiiiger/bert_score/blob/master/README.md)). Para
coseno se usa `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`, un
encoder multilingüe anunciado para 50 idiomas ([ficha oficial del modelo en
Hugging Face](https://huggingface.co/sentence-transformers/paraphrase-multilingual-mpnet-base-v2)).
La elección es una configuración implementada, no validación empírica de que
sea óptima para dictámenes regulatorios en español.

Ambos proveedores requieren directorios locales, no descargan pesos durante
la ejecución y registran revisión declarada por el operador (no verificada
criptográficamente). En este entorno no están instalados BERTScore, PyTorch,
Transformers ni Sentence-Transformers y no existen pesos locales confirmados;
por ello OE2/OE5 semánticos quedan bloqueados, sin estimaciones ni métricas
inventadas.

## Comandos

Desde la raíz del repositorio y el entorno `.venv-evaluation`, usando rutas
reales solo después de autorización institucional. Estos ejemplos usan modo
sintético por defecto; un archivo de datos real no pasa esa política.

```powershell
$py = ".\.venv-evaluation\Scripts\python.exe"
$common = @("--results", "evaluation\outputs\runs.jsonl",
  "--ground-truth", "evaluation\outputs\ground_truth.jsonl",
  "--catalog", "evaluation\fixtures\synthetic_catalog.json",
  "--experiment-id", "SYNTH-EXPERIMENT")
& $py -m evaluation.scripts.eval_precision_f1 @common
& $py -m evaluation.scripts.eval_coverage @common
& $py -m evaluation.scripts.eval_bertscore @common `
  --response-kind criterion_verdict `
  --bert-model-dir "RUTA_LOCAL_BERT" --bert-revision "REVISION" `
  --embedding-model-dir "RUTA_LOCAL_ENCODER" --embedding-revision "REVISION"
& $py -m evaluation.scripts.eval_telemetry `
  --results evaluation\outputs\runs.jsonl --experiment-id SYNTH-EXPERIMENT
& $py -m evaluation.scripts.eval_stability `
  --results evaluation\outputs\runs.jsonl `
  --catalog evaluation\fixtures\synthetic_catalog.json `
  --experiment-id SYNTH-EXPERIMENT `
  --embedding-model-dir "RUTA_LOCAL_ENCODER" --embedding-revision "REVISION"
```

Para medir datos autorizados, cada CLI permite `--mode authorized
--authorization-ref REF`. Los que usan catálogo admiten además
`--catalog-validated-by`, `--catalog-approval-ref` y
`--catalog-validated-at` ISO-8601 con zona horaria. No utilice datos de tesis
hasta contar con permisos, protocolo y Ground Truth real aprobado.

## Estado verificado en Fase 4

La suite unitaria completa valida fórmulas, exclusiones, linking, reportes,
política sintética y casos de dependencia ausente. Las pruebas sintéticas no
son datos ni cifras experimentales de la tesis. La ejecución de modelos
semánticos reales sigue pendiente de dependencias y pesos locales aprobados.
