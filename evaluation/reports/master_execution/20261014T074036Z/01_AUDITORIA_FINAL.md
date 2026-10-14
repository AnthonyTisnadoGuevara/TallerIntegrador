# Prompt 1 — Auditoría final de infraestructura

**Estado: COMPLETADO CON LIMITACIONES.** Se auditó la infraestructura existente sin crear otro evaluador ni iniciar llamadas productivas.

## Artefacto, objetivos e instrumentos

La infraestructura de `evaluation/` incluye contratos de ejecución, manifiesto y congelación de corpus, carga versionada de catálogos, contratos de Ground Truth con revisión/adjudicación, validadores, almacenamiento local JSONL, adaptadores analíticos originales, un grafo normativo local y los cinco instrumentos OE1–OE5. Los instrumentos están implementados como código; que puedan calcular entradas no demuestra que haya resultados experimentales válidos.

| Objetivo | Instrumento | Estado actual |
|---|---|---|
| OE1 | Precision, Recall y F1 (`eval_precision_f1`) | Implementado y cubierto técnicamente; requiere resultados normativos y Ground Truth final validado. |
| OE2 | BERTScore P/R/F1 y coseno (`eval_bertscore`) | Inferencia real local comprobada solo con pares sintéticos; no hay pares de tesis. |
| OE3 | Cobertura (`eval_coverage`) | Implementado; requiere catálogo/aplicabilidad validados y ejecuciones del artefacto objetivo. |
| OE4 | Latencia y telemetría (`eval_telemetry`) | Instrumento implementado; no hay latencia de producción medida para el estudio. |
| OE5 | Estabilidad (`eval_stability`) | Comparador de cinco réplicas implementado; la métrica semántica se probó con cinco registros sintéticos, no con réplicas reales del artefacto. |

## Sistema objetivo frente a entorno experimental

Los informes previos documentan compilación y recorrido sintético de los seis grafos originales mediante dobles, interceptación de lecturas/escrituras y bloqueo de red. Eso comprueba estructura y rutas de código bajo condiciones de prueba, no llamadas reales a Gemini/Supabase, ni seguridad operacional integral, ni un dictamen normativo válido. Los adaptadores de análisis aislado de Sílabos, Gestión Académica y Planificación conservan salidas analíticas con `normative_results=None`.

El grafo normativo local disponible usa `TransportOnlyEvaluator`, que no decide conformidad y devuelve `no_evaluable`/`indeterminado`. No es una implementación normativa del sistema original ni debe presentarse como tal. No se deben interpretar riesgos, clasificaciones académicas o recomendaciones descriptivas como conformidad, no conformidad o acreditación.

## Riesgos y límites

- Faltan expedientes autorizados, catálogo auténtico y Ground Truth adjudicado para el periodo de estudio.
- No hay evaluación normativa efectiva por criterio enlazada a evidencia y a una fuente oficial validada.
- Las pruebas de grafos emplean dobles; no verifican servicios reales.
- La capa experimental local no sustituye sin más el artefacto multiagente objeto de tesis.
- Los hashes de integridad no autentican origen, autorización ni identidad de quien aprueba.
- `evaluation/METRICAS_TESIS.md` contiene una descripción previa que aún dice que faltan paquetes/modelos semánticos; la verificación más reciente está en `evaluation/SEMANTIC_RUNTIME_VERIFICATION.md` y confirma disponibilidad local. Este reporte toma como vigente la comprobación más reciente.

## Conclusión de auditoría

La infraestructura técnica de preparación, validación y cálculo de instrumentos está disponible. La evaluación computacional definitiva no está lista para ejecutarse; depende de entradas institucionales autorizadas, Ground Truth, reglas normativas aprobadas y un flujo seguro que ejecute el artefacto realmente estudiado.
