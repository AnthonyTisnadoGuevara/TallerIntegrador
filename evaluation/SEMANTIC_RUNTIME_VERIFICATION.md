# Verificación técnica local de métricas semánticas

Fecha de la prueba: 2026-10-14 (UTC). Esta verificación utiliza solamente
frases sintéticas en español. No es benchmarking, no usa expedientes reales y
no produce resultados de investigación.

## Entorno reproducible

- Python 3.12.10; Windows 11 x86-64; Intel64 Family 6 Model 186; 16 CPU lógicos.
- PyTorch CPU `2.8.0+cpu`; `torch.cuda.is_available()` devolvió `False` y no se
  encontró `nvidia-smi`.
- Dependencias directas fijadas en `requirements-semantic.txt`; lock completo
  del entorno en `requirements-semantic-lock.txt`.
- Versiones instaladas: `bert-score 0.3.13`, `transformers 4.57.3`,
  `sentence-transformers 5.1.2`, `torch 2.8.0+cpu`, `numpy 2.2.6`.
- `pip check`: sin dependencias rotas.
- Los artefactos están bajo `evaluation/models/`, ignorado por Git. Los
  scripts requieren directorios locales y sus cargadores usan
  `local_files_only=True`; durante la evaluación semántica no se descargan
  pesos.

## Modelos fijados

| Uso | Repositorio | Commit descargado | Parámetros relevantes |
|---|---|---|---|
| BERTScore | `google-bert/bert-base-multilingual-cased` | `4e0bfe511dc35db10f88a6a9a9d34428de950536` | Tokenizer lento; español (`lang=es`); capa 9; CPU; `idf=False`; sin baseline rescaling; máximo práctico 510 tokens de contenido (el exceso se trunca y se marca). |
| Coseno | `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` | `54591597ec6b010533f416d3aba6347e70666397` | Embeddings de 768 dimensiones; máximo 128 tokens; ambos vectores L2-normalizados antes del coseno. |

El commit completo se pasó como `revision` a `snapshot_download`; la
descarga se completó desde esos commits. El adaptador ahora exige que la
revisión recibida sea un SHA hexadecimal completo de 40 caracteres. El
cargador registra ese SHA, pero no re-hashea automáticamente cada archivo ni
demuestra por sí solo que un directorio arbitrario corresponda a esa revisión.

SHA-256 de pesos/configuración descargados:

- BERT `pytorch_model.bin`: `3496a508a9a3511c8a55e4d0e6f471c70c68c2a8c4784b3b2b5dc16ffb87d238`
- BERT `config.json`: `8b94b5c10efd3c3ca667e5ccd501314eb670cefbf7a465f0a3fc0928a1a0ab87`
- MPNet `model.safetensors`: `b5722100700c48b74c9c199c5f39ff9493c94d1497f719e791d4bc3861d7714a`
- MPNet `config.json`: `4d10c2021c6b5fbe8b70698abc6ccc6691dc28d1bae9732f7fa1087782feba7e`

## Ejecución sintética directa

Par de prueba (no institucional):

- Candidato: “El equipo docente revisó el plan de mejora y registró evidencias verificables para cada actividad.”
- Referencia: “Los docentes analizaron el plan de mejora y conservaron pruebas comprobables de las actividades realizadas.”

Inferencia CPU real:

- BERTScore Precision: `0.8781245351`
- BERTScore Recall: `0.8758855462`
- BERTScore F1: `0.8770036101`
- Coseno MPNet: `0.9303452308`
- Longitud: ninguno de los dos textos superó el límite BERTScore de 510 tokens.
- Tiempos observados en esta máquina: carga BERT `5.132 s`, BERTScore `0.877 s`,
  carga Sentence-Transformers `0.737 s`, embeddings+coseno `0.096 s`. Son tiempos
  de una prueba técnica, no una caracterización de rendimiento científico.

## Verificación de los instrumentos

Se invocaron `eval_bertscore.py` y `eval_stability.py` con JSONL temporal y
frases sintéticas en español. Ambos terminaron con código 0:

- OE2: un par vinculado por expediente/criterio/versión; Precision `0.9061467648`,
  Recall `0.8732984662`, F1 `0.8894194961`, coseno `0.9035077613`.
- OE5: cinco registros de prueba con configuración sintética igual; se
  generaron las 10 parejas y se calcularon las 10 similitudes; coseno medio
  `0.8492397932`.

Estas cifras solo acreditan que los CLI cargan los modelos, emparejan y ejecutan
las operaciones en datos artificiales. No son estimaciones de desempeño ni de
estabilidad del sistema multiagente.

## Corrección técnica y validación

`bert_score.score(..., return_hash=True)` entrega `(scores, hash)`, donde
`scores=(precision, recall, f1)`. El adaptador experimental esperaba cuatro
elementos planos y falló en la primera inferencia real. Se corrigió el
desempaquetado en `metrics/semantic.py` y se añadió una prueba unitaria para el
formato real de retorno. Los metadatos de MPNet ahora incluyen dimensión 768.
También se ajustó una expectativa de prueba CLI que asumía dependencias
ausentes, para que verifique el bloqueo correcto cuando no se proporcionan
rutas locales de modelos aunque las bibliotecas sí estén instaladas.

Suite final:

```text
python -m unittest discover -s evaluation/tests -v
Ran 123 tests ... OK
```

La suite y la prueba CLI no invocaron Supabase, Gemini ni los grafos
productivos. No se modificaron agentes originales, endpoints ni frontend.

## Estado

Las implementaciones semánticas de OE2 y OE5 están **técnicamente operativas en
este entorno CPU**. Para utilizarlas en el estudio siguen siendo necesarios
expedientes autorizados, catálogo normativo auténtico y Ground Truth validado;
OE5 requiere además las cinco ejecuciones reales comparables del artefacto que
la tesis evalúa. La prueba sintética no sustituye ninguna de esas condiciones.
