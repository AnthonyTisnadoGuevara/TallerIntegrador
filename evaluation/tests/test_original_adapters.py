from __future__ import annotations

from dataclasses import fields, replace
import hashlib
import inspect
from pathlib import Path
import sys
import unittest

from backend.app.agents.curricular_analyzer import analizar_texto_silabo
from evaluation.analytical_contracts import AnalyticalInput, AnalyticalKind, AnalyticalStatus
from evaluation.factory import synthetic_expediente
from evaluation.original_adapters import (ACADEMIC_ADAPTER, PLANNING_ADAPTER,
                                          SyllabusAnalyzerAdapter)
from evaluation.schemas import Macroprocess


def synthetic_evidence_set():
    """Conjunto sintético usado para fijar la salida observada antes de extraer."""
    return [
        {"id": "A1", "codigo": "AC-1", "titulo": "Acta de docentes y estudiantes",
         "descripcion": "Acta para seguimiento de docentes y estudiantes", "estado": "pendiente",
         "prioridad": "alta", "avance": -10},
        {"id": "A2", "codigo": "AC-2", "titulo": "Resolucion de plan de estudios",
         "descripcion": "resolucion institucional", "estado": "completado", "prioridad": "media",
         "avance": 120, "archivo_url": None},
        {"id": "A3", "codigo": "AC-3", "titulo": "Portafolio de silabo",
         "descripcion": "silabo y portafolio", "estado": "observado", "prioridad": "baja",
         "avance": "dato-invalido", "archivo_url": "/synthetic/a3.pdf"},
        {"id": "A4", "titulo": "Evidencia sin clasificacion", "estado": "en_proceso", "avance": 50},
    ]


def make_macroprocess_input(macroproceso, evidencias):
    expediente = replace(synthetic_expediente(), macroprocesos=(macroproceso,))
    return AnalyticalInput(
        expediente, macroproceso, (expediente.documents[0].document_id,), "Synthetic analytical input",
        {"evidencias": evidencias},
    )


class OriginalAdapterTests(unittest.TestCase):
    def setUp(self):
        self.expediente = replace(synthetic_expediente(),
                                  macroprocesos=(Macroprocess.SYLLABUS,))
        self.doc_ids = (self.expediente.documents[0].document_id,)
        self.text = ("Sumilla: programación y algoritmos. Evaluación de resultados. "
                     "Al finalizar, el estudiante analiza datos y desarrolla software.")
        self.metadata = {"asignatura": "Curso ficticio", "codigo_asignatura": "SYNTH-01"}
        self.data = AnalyticalInput(self.expediente, Macroprocess.SYLLABUS,
                                    self.doc_ids, self.text, self.metadata)

    def test_adapter_invokes_original_function_and_preserves_full_output(self):
        expected = analizar_texto_silabo(self.text, dict(self.metadata))
        record = SyllabusAnalyzerAdapter().run(self.data)
        self.assertEqual(analizar_texto_silabo.__module__, "backend.app.agents.curricular_analyzer")
        self.assertEqual(record.analysis_data, expected)
        self.assertEqual(record.kind, AnalyticalKind.ORIGINAL_ANALYTICAL)
        self.assertEqual(record.macroproceso, Macroprocess.SYLLABUS)
        self.assertEqual(record.document_ids, self.doc_ids)
        self.assertIsNone(record.normative_results)
        self.assertFalse(record.provenance["normative_assessment_performed"])
        source = Path(inspect.getsourcefile(analizar_texto_silabo)).read_bytes()
        self.assertEqual(record.code_sha256, hashlib.sha256(source).hexdigest())

    def test_original_import_did_not_load_productive_clients_or_graph(self):
        self.assertNotIn("app.services.supabase_client", sys.modules)
        self.assertNotIn("backend.app.agents.syllabus_graph", sys.modules)
        self.assertFalse(any("gemini" in name for name in sys.modules))

    def test_original_function_error_is_recorded_without_fake_analysis(self):
        class BrokenMetadata(dict):
            def get(self, *_args, **_kwargs):
                raise RuntimeError("synthetic original-function failure")

        data = AnalyticalInput(self.expediente, Macroprocess.SYLLABUS,
                               self.doc_ids, self.text, BrokenMetadata(self.metadata))
        record = SyllabusAnalyzerAdapter().run(data)
        self.assertEqual(record.status, AnalyticalStatus.ERROR)
        self.assertEqual(record.error_type, "RuntimeError")
        self.assertIn("synthetic original-function failure", record.error_message)
        self.assertIsNone(record.analysis_data)

    def test_academic_adapter_executes_original_functions_and_preserves_analytic_state(self):
        from backend.app.agents.gestion_academica_analysis import (
            calcular_indicadores_gestion_academica, clasificar_evidencias_academicas,
            detectar_riesgos_academicos,
        )
        evidencias = synthetic_evidence_set()
        expected = detectar_riesgos_academicos(clasificar_evidencias_academicas(
            calcular_indicadores_gestion_academica({"evidencias": evidencias})))
        data = make_macroprocess_input(Macroprocess.ACADEMIC, evidencias)
        record = ACADEMIC_ADAPTER.run(data)
        self.assertEqual(record.status, AnalyticalStatus.COMPLETED)
        self.assertEqual(record.analysis_data, expected)
        self.assertEqual(record.analysis_data["indicadores"]["avance_promedio"], 38)
        self.assertEqual(record.analysis_data["resumen_base"]["nivel_riesgo"], "alto")
        self.assertIsNone(record.normative_results)
        self.assertFalse(record.provenance["normative_assessment_performed"])
        self.assertEqual(len(record.provenance["functions"]), 3)
        self.assertEqual(len(record.code_sha256), 64)

    def test_planning_adapter_executes_original_functions_and_preserves_analytic_state(self):
        from backend.app.agents.planificacion_analysis import (
            calcular_indicadores_planificacion, detectar_riesgos_estrategicos,
        )
        evidencias = synthetic_evidence_set()
        expected = detectar_riesgos_estrategicos(
            calcular_indicadores_planificacion({"evidencias": evidencias}))
        record = PLANNING_ADAPTER.run(make_macroprocess_input(Macroprocess.PLANNING, evidencias))
        self.assertEqual(record.status, AnalyticalStatus.COMPLETED)
        self.assertEqual(record.analysis_data, expected)
        self.assertEqual(record.analysis_data["dashboard"]["avance_promedio"], 38)
        self.assertEqual(record.analysis_data["resumen_base"]["nivel_riesgo"], "alto")
        self.assertIsNone(record.normative_results)
        self.assertFalse(record.provenance["normative_assessment_performed"])
        self.assertEqual(len(record.provenance["functions"]), 2)
        self.assertEqual(len(record.code_sha256), 64)

    def test_adapters_record_technical_errors_and_reject_wrong_process(self):
        for adapter, process in ((ACADEMIC_ADAPTER, Macroprocess.ACADEMIC),
                                 (PLANNING_ADAPTER, Macroprocess.PLANNING)):
            data = make_macroprocess_input(process, [])
            bad_data = replace(data, metadata={})
            record = adapter.run(bad_data)
            self.assertEqual(record.status, AnalyticalStatus.ERROR)
            self.assertEqual(record.error_type, "ValueError")
            self.assertIsNone(record.analysis_data)
            with self.assertRaises(ValueError):
                adapter.run(make_macroprocess_input(
                    Macroprocess.SYLLABUS, synthetic_evidence_set()))

    def test_analytic_modules_load_without_productive_clients(self):
        import backend.app.agents.gestion_academica_analysis
        import backend.app.agents.planificacion_analysis
        self.assertNotIn("app.services.supabase_client", sys.modules)
        self.assertFalse(any("gemini" in name.lower() for name in sys.modules))

    def test_pre_extraction_characterization_outputs_are_preserved(self):
        from backend.app.agents.gestion_academica_analysis import (
            calcular_indicadores_gestion_academica, clasificar_evidencias_academicas,
            detectar_riesgos_academicos,
        )
        from backend.app.agents.planificacion_analysis import (
            calcular_indicadores_planificacion, detectar_riesgos_estrategicos,
        )
        evidencias = synthetic_evidence_set()
        original_academic = detectar_riesgos_academicos(clasificar_evidencias_academicas(
            calcular_indicadores_gestion_academica({"evidencias": evidencias})))
        self.assertEqual(original_academic["indicadores"], {
            "total_evidencias": 4, "pendientes": 1, "en_proceso": 1, "completadas": 1,
            "observadas": 1, "avance_promedio": 38, "prioridad_alta": 1,
            "sin_sustento_documental": 3, "completadas_sin_sustento_documental": 1,
        })
        self.assertEqual([item["id"] for item in original_academic["clasificacion"]["actas"]], ["A1"])
        self.assertEqual([item["id"] for item in original_academic["clasificacion"]["resoluciones"]], ["A2"])
        self.assertEqual([item["id"] for item in original_academic["clasificacion"]["silabos_portafolios"]], ["A3"])
        self.assertEqual(original_academic["resumen_base"]["nivel_riesgo"], "alto")
        self.assertEqual(original_academic["evidencias_criticas"], [
            "AC-1 - Acta de docentes y estudiantes: prioridad alta pendiente.",
            "AC-2 - Resolucion de plan de estudios: completada sin sustento documental.",
        ])
        empty_academic = detectar_riesgos_academicos(clasificar_evidencias_academicas(
            calcular_indicadores_gestion_academica({})))
        self.assertEqual(empty_academic["indicadores"]["total_evidencias"], 0)
        self.assertEqual(empty_academic["riesgos_detectados"], [
            "No se encontraron evidencias suficientes para analizar la gestion academica."])

        original_planning = detectar_riesgos_estrategicos(
            calcular_indicadores_planificacion({"evidencias": evidencias, "sentinel": "kept"}))
        self.assertEqual(original_planning["dashboard"], {
            "total": 4, "pendientes": 1, "en_proceso": 1, "completadas": 1, "observadas": 1,
            "avance_promedio": 38, "alta": 1, "media": 1, "baja": 1, "sin_archivo": 3,
            "porcentaje_sin_archivo": 75, "pendientes_alta": 1,
        })
        self.assertEqual(original_planning["sentinel"], "kept")
        self.assertEqual(original_planning["resumen_base"]["nivel_riesgo"], "alto")
        self.assertEqual(original_planning["evidencias_criticas"], [
            "AC-1 - Acta de docentes y estudiantes: prioridad alta pendiente."])
        empty_planning = detectar_riesgos_estrategicos(calcular_indicadores_planificacion({}))
        self.assertEqual(empty_planning["dashboard"]["total"], 0)
        self.assertEqual(empty_planning["resumen_base"]["nivel_riesgo"], "alto")

        with self.assertRaises(AttributeError):
            calcular_indicadores_gestion_academica({"evidencias": [None]})

    def test_original_adapters_do_not_import_graphs_or_touch_persistent_files(self):
        self.assertNotIn("backend.app.agents.gestion_academica_graph", sys.modules)
        self.assertNotIn("backend.app.agents.planificacion_graph", sys.modules)
        # The adapters' inputs and outputs are in-memory synthetic values only.

    def test_graph_node_names_and_edges_remain_unchanged(self):
        root = Path(__file__).resolve().parents[2]
        academic = (root / "backend/app/agents/gestion_academica_graph.py").read_text(encoding="utf-8")
        planning = (root / "backend/app/agents/planificacion_graph.py").read_text(encoding="utf-8")
        for source, nodes, edges in (
            (academic, ("obtener_evidencias_gestion_academica", "calcular_indicadores_gestion_academica",
                        "clasificar_evidencias_academicas", "detectar_acuerdos_pendientes",
                        "detectar_riesgos_academicos", "generar_recomendaciones_gemini", "preparar_resultado"),
             ('graph.add_edge(START, "obtener_evidencias_gestion_academica")',
              'graph.add_edge("obtener_evidencias_gestion_academica", "calcular_indicadores_gestion_academica")',
              'graph.add_edge("calcular_indicadores_gestion_academica", "clasificar_evidencias_academicas")',
              'graph.add_edge("clasificar_evidencias_academicas", "detectar_acuerdos_pendientes")',
              'graph.add_edge("detectar_acuerdos_pendientes", "detectar_riesgos_academicos")',
              'graph.add_edge("detectar_riesgos_academicos", "generar_recomendaciones_gemini")',
              'graph.add_edge("generar_recomendaciones_gemini", "preparar_resultado")',
              'graph.add_edge("preparar_resultado", END)')),
            (planning, ("obtener_evidencias_planificacion", "calcular_indicadores_planificacion",
                        "detectar_riesgos_estrategicos", "generar_recomendaciones_gemini",
                        "preparar_resultado", "guardar_o_devolver_analisis"),
             ('graph.add_edge(START, "obtener_evidencias_planificacion")',
              'graph.add_edge("obtener_evidencias_planificacion", "calcular_indicadores_planificacion")',
              'graph.add_edge("calcular_indicadores_planificacion", "detectar_riesgos_estrategicos")',
              'graph.add_edge("detectar_riesgos_estrategicos", "generar_recomendaciones_gemini")',
              'graph.add_edge("generar_recomendaciones_gemini", "preparar_resultado")',
              'graph.add_edge("preparar_resultado", "guardar_o_devolver_analisis")',
              'graph.add_edge("guardar_o_devolver_analisis", END)')),
        ):
            for node in nodes:
                self.assertIn(f'add_node("{node}"', source)
            for edge in edges:
                self.assertIn(edge, source)
            self.assertIn("graph.compile()", source)

    def test_analytical_input_has_no_ground_truth_fields(self):
        self.assertNotIn("ground_truth", {item.name for item in fields(AnalyticalInput)})

    def test_adapter_input_rejects_non_synthetic_expediente(self):
        real = replace(self.expediente, source="autorizado")
        with self.assertRaisesRegex(ValueError, "sintéticos"):
            AnalyticalInput(real, Macroprocess.SYLLABUS, self.doc_ids,
                            self.text, self.metadata)


if __name__ == "__main__":
    unittest.main()
