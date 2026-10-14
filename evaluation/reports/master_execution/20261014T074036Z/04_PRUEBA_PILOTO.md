# Prompt 4 — Prueba piloto

**Estado: BLOQUEADO para el piloto del artefacto objetivo.**

## Comprobación de condiciones

El repositorio identifica el sistema productivo como grafos que pueden leer/escribir Supabase, invocar Gemini y, según el proceso, descargar documentos. Las ejecuciones aisladas documentadas compilaron/recorrieron los seis grafos con dependencias sustituidas, efectos interceptados y entradas sintéticas. No se habilitó una ejecución autorizada, aislada y no persistente del artefacto completo contra expedientes reales.

Faltan también corpus autorizado, catálogo oficial aplicable y Ground Truth validado. El grafo local con `TransportOnlyEvaluator` solo transporta contratos y declara resultados no evaluables; no se usó ni se presenta como reemplazo del sistema objeto de tesis.

## Trabajo técnico que sí existe

Se conserva como evidencia técnica separada: suite de 123 pruebas sintéticas; prueba previa de inferencia BERTScore/MPNet en texto artificial; comprobaciones previas de estructura de grafos con dobles. Ninguno de estos ejercicios es un piloto experimental de expedientes ni genera cobertura o dictámenes válidos.

## Instrumentos

| Indicador | Estado para piloto del artefacto objetivo |
|---|---|
| OE1 Precision/Recall/F1 | Pendiente: no hay Ground Truth ni salidas normativas. |
| OE2 BERTScore/coseno | Código verificado sintéticamente; sin pares reales de referencia. |
| OE3 Cobertura | Pendiente: no hay catálogo/aplicabilidad oficial ni evaluaciones por criterio. |
| OE4 Latencia | Script funcional; no hay medición representativa del artefacto objetivo bajo protocolo. |
| OE5 Estabilidad | Comparador funcional; no existen cinco réplicas reales comparables por expediente. |

## Condiciones mínimas para reabrir

Obtener autorizaciones y congelar el dataset; validar el catálogo y Ground Truth; definir una ruta de ejecución aislada del artefacto efectivamente evaluado, con servicios y persistencia controlados; fijar la configuración; y demostrar conservación de salidas por criterio, evidencia, versión y telemetría. Hasta entonces, no declarar `PILOTO TÉCNICO VERIFICADO` del sistema multiagente ni `PILOTO EXPERIMENTAL VERIFICADO`.
