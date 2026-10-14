# Prompt 3 — Modelos y métricas semánticas

**Estado: COMPLETADO CON LIMITACIONES — verificación técnica sintética satisfactoria.**

## Entorno instalado y reproducible

Entorno `.venv-evaluation`: Python 3.12.10, Windows x86-64. PyTorch `2.8.0+cpu`; CUDA no disponible, por lo que se usa CPU. Transformers `4.57.3`, distribución `bert-score==0.3.13`, Sentence-Transformers `5.1.2` y NumPy `2.2.6`. `pip check` informa que no hay requisitos rotos. Versiones directas y lock completo: `evaluation/requirements-semantic.txt` y `evaluation/requirements-semantic-lock.txt`.

El atributo Python `bert_score.__version__` devuelve `0.3.12`, aunque los metadatos de distribución (`importlib.metadata`/`pip show`) y ambos archivos de dependencias fijan `0.3.13`. La implementación registra la versión desde metadatos de distribución. Se documenta la discrepancia del atributo del módulo para no confundirla con la versión instalada.

## Modelos y parámetros

| Métrica | Artefacto/revisión local | Parámetros y límite |
|---|---|---|
| BERTScore | `google-bert/bert-base-multilingual-cased`, commit `4e0bfe511dc35db10f88a6a9a9d34428de950536` | Español, capa 9, CPU, tokenizer lento, sin IDF ni baseline rescaling; contenido >510 tokens señalado/truncado. |
| Coseno | `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`, commit `54591597ec6b010533f416d3aba6347e70666397` | Embeddings 768D, máximo 128 tokens, normalización L2 antes del coseno. |

Los modelos están guardados bajo `evaluation/models/`. Los cargadores requieren directorios locales y `local_files_only=True`; las ejecuciones no activan descarga implícita. Las revisiones se pasan como SHA completos, aunque el adaptador no verifica criptográficamente que cualquier directorio local corresponda a ese SHA.

## Evidencia de inferencia sintética

La prueba directa previa con frases sintéticas españolas calculó BERTScore P/R/F1 `0.8781245351 / 0.8758855462 / 0.8770036101` y coseno `0.9303452308`. En la prueba CLI OE2, P/R/F1 `0.9061467648 / 0.8732984662 / 0.8894194961`, coseno `0.9035077613`. En OE5, cinco registros sintéticos produjeron las 10 parejas; se calcularon 10 cosenos, media `0.8492397932`. Estos valores son verificaciones técnicas, no resultados científicos.

La suite actual de 123 pruebas comprueba contratos/errores/offline, no vuelve a descargar ni reejecuta inferencia de modelos. La inferencia real en texto sintético queda acreditada por `evaluation/SEMANTIC_RUNTIME_VERIFICATION.md` y sus pruebas CLI registradas.

## Estado OE2/OE5

Las métricas semánticas están técnicamente operativas en este host para entradas que cumplan el contrato; OE2 necesita pares normativos autorizados y referencia validada. La parte semántica de OE5 necesita cinco ejecuciones reales comparables del artefacto objetivo. Los modelos no convierten similitud en corrección normativa. Sin datos reales autorizados no se emiten resultados de OE2/OE5 de la tesis.
