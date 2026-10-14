"""Ejecución aislada de los grafos productivos originales con dobles cerrados."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib
from pathlib import Path
import socket
import sys
import types
import unittest
from unittest.mock import patch

from evaluation.schemas import Macroprocess


BACKEND = Path(__file__).resolve().parents[2] / "backend"
SYNTHETIC_SYLLABUS_TEXT = """
Datos generales. Sumilla. Aporte al perfil de egreso. Programación por unidades.
Estrategias metodológicas. Recursos. Evaluación. Tutoría. Bibliografía.
Programación, algoritmo, variables, SQL, datos. Al finalizar el estudiante analiza
datos. El estudiante desarrolla algoritmos. Responsable: comité. Fecha 2026-01-10.
Objetivo: meta académica. Actividades y cronograma. Indicadores de avance. Acta aprobada.
"""


class FakeQuery:
    def __init__(self, client, table):
        self.client = client
        self.table_name = table
        self.mode = "select"
        self.filters = []
        self.payload = None

    def select(self, *_args, **_kwargs):
        self.mode = "select"
        return self

    def eq(self, key, value):
        self.filters.append((key, "eq", value))
        return self

    def neq(self, key, value):
        self.filters.append((key, "neq", value))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def delete(self):
        self.mode = "delete"
        return self

    def insert(self, payload):
        self.mode = "insert"
        self.payload = deepcopy(payload)
        return self

    def update(self, payload):
        self.mode = "update"
        self.payload = deepcopy(payload)
        return self

    def upsert(self, payload):
        self.mode = "upsert"
        self.payload = deepcopy(payload)
        return self

    def execute(self):
        event = {"table": self.table_name, "operation": self.mode,
                 "filters": list(self.filters), "payload": deepcopy(self.payload)}
        self.client.operations.append(event)
        if self.mode != "select":
            if self.table_name not in self.client.allowed_write_tables:
                raise AssertionError(f"Escritura no autorizada en doble: {self.table_name}")
            return types.SimpleNamespace(data=[])
        rows = deepcopy(self.client.rows.get(self.table_name, []))
        for key, operator, value in self.filters:
            if operator == "eq":
                rows = [item for item in rows if item.get(key) == value]
            else:
                rows = [item for item in rows if item.get(key) != value]
        return types.SimpleNamespace(data=rows)


class FakeSupabase:
    allowed_write_tables = {
        "analisis_silabo", "validacion_ia_macroproceso_evidencias",
        "trazabilidad_curricular", "brechas_curriculares",
    }

    def __init__(self):
        self.rows = {}
        self.operations = []

    def table(self, name):
        return FakeQuery(self, name)

    def reset(self, rows):
        self.rows = deepcopy(rows)
        self.operations = []


class FakeHTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class OriginalGraphExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._original_path = list(sys.path)
        cls._saved_modules = {name: module for name, module in sys.modules.items()
                              if name == "app" or name.startswith("app.") or name == "fastapi"}
        for name in list(sys.modules):
            if name == "app" or name.startswith("app.") or name == "fastapi":
                del sys.modules[name]
        sys.path.insert(0, str(BACKEND))

        cls.supabase = FakeSupabase()
        fake_services = types.ModuleType("app.services")
        fake_services.__path__ = []
        fake_supabase_module = types.ModuleType("app.services.supabase_client")
        fake_supabase_module.supabase = cls.supabase
        sys.modules["app.services"] = fake_services
        sys.modules["app.services.supabase_client"] = fake_supabase_module

        fake_utils = types.ModuleType("app.utils")
        fake_utils.__path__ = []
        fake_document_reader = types.ModuleType("app.utils.document_reader")
        cls.document_reads = []

        def read_synthetic_document(url):
            if not str(url).startswith("https://synthetic.invalid/"):
                raise AssertionError("El lector recibió un origen no sintético")
            cls.document_reads.append(url)
            return SYNTHETIC_SYLLABUS_TEXT

        fake_document_reader.extraer_texto_desde_url = read_synthetic_document
        sys.modules["app.utils"] = fake_utils
        sys.modules["app.utils.document_reader"] = fake_document_reader

        fake_fastapi = types.ModuleType("fastapi")
        fake_fastapi.HTTPException = FakeHTTPException
        sys.modules["fastapi"] = fake_fastapi

        cls.gemini_calls = []

        def syllabus_gemini(text, syllabus, analysis):
            cls.gemini_calls.append(("syllabus", {"test_double": True}))
            return {"modelo_usado": "TEST_DOUBLE_GEMINI_SYLLABUS", "sugerencias": ["mock syllabus"],
                    "observacion_general": analysis.get("observacion_general"),
                    "recomendaciones_mejora": ["mock recommendation"]}

        def academic_gemini(**kwargs):
            cls.gemini_calls.append(("academic", {"test_double": True}))
            return {"modelo_usado": "TEST_DOUBLE_GEMINI_ACADEMIC", "recomendaciones": ["mock recommendation"]}

        def planning_gemini(**kwargs):
            cls.gemini_calls.append(("planning", {"test_double": True}))
            return {"modelo_usado": "TEST_DOUBLE_GEMINI_PLANNING", "recomendaciones": ["mock recommendation"]}

        def validation_gemini(evidence, text, base):
            cls.gemini_calls.append(("validation", {"test_double": True}))
            return {**base, "modelo_usado": "TEST_DOUBLE_GEMINI_VALIDATION",
                    "recomendaciones": ["mock validation recommendation"]}

        def trace_gemini(relations, gaps, context):
            cls.gemini_calls.append(("traceability", {"test_double": True}))
            return {"activo": False, "modelo_usado": "TEST_DOUBLE_GEMINI_TRACEABILITY",
                    "relaciones": relations, "brechas": gaps,
                    "conclusion_general": "Resultado de doble sintético; no se llamó un modelo."}

        def coordinator_gemini(**kwargs):
            cls.gemini_calls.append(("coordinator", {"test_double": True}))
            return {"modelo_usado": "TEST_DOUBLE_GEMINI_COORDINATOR",
                    "recomendaciones_comite": ["mock coordinator recommendation"]}

        gemini_functions = {
            "gemini_recommender": {"generar_recomendaciones_con_gemini": syllabus_gemini},
            "gemini_gestion_academica_recommender": {
                "generar_recomendaciones_gestion_academica_con_gemini": academic_gemini},
            "gemini_planificacion_recommender": {
                "generar_recomendaciones_planificacion_con_gemini": planning_gemini},
            "gemini_validacion_evidencia_recommender": {
                "enriquecer_validacion_evidencia_con_gemini": validation_gemini},
            "gemini_trazabilidad_recommender": {"enriquecer_trazabilidad_con_gemini": trace_gemini},
            "gemini_mejora_continua_recommender": {
                "generar_diagnostico_mejora_continua_con_gemini": coordinator_gemini},
        }
        for suffix, functions in gemini_functions.items():
            module = types.ModuleType(f"app.agents.{suffix}")
            for name, function in functions.items():
                setattr(module, name, function)
            sys.modules[module.__name__] = module

        with patch.object(socket.socket, "connect", side_effect=AssertionError("network disabled")), \
                patch("socket.create_connection", side_effect=AssertionError("network disabled")), \
                patch("socket.getaddrinfo", side_effect=AssertionError("network disabled")), \
                patch("urllib.request.urlopen", side_effect=AssertionError("network disabled")):
            cls.modules = {
                "syllabus": importlib.import_module("app.agents.syllabus_graph"),
                "academic": importlib.import_module("app.agents.gestion_academica_graph"),
                "planning": importlib.import_module("app.agents.planificacion_graph"),
                "validation": importlib.import_module("app.agents.validacion_evidencia_graph"),
                "traceability": importlib.import_module("app.agents.trazabilidad_graph"),
                "coordinator": importlib.import_module("app.agents.mejora_continua_coordinator"),
            }

    @classmethod
    def tearDownClass(cls):
        for name in list(sys.modules):
            if name == "app" or name.startswith("app.") or name == "fastapi":
                del sys.modules[name]
        sys.modules.update(cls._saved_modules)
        sys.path[:] = cls._original_path

    def setUp(self):
        self.gemini_calls.clear()
        self.document_reads.clear()

    def _run_and_trace(self, module, constructor, initial_state):
        self.assertNotIn("ground_truth", initial_state)
        self.assertNotIn("ground_truth", repr(initial_state).lower())
        nodes = []
        final_state = dict(initial_state)
        operation_offset = len(self.supabase.operations)
        gemini_offset = len(self.gemini_calls)
        original_functions = {
            "construir_grafo_analisis": ["curricular_analyzer.analizar_texto_silabo"],
            "construir_grafo_gestion_academica": [
                "gestion_academica_analysis.calcular_indicadores_gestion_academica",
                "gestion_academica_analysis.clasificar_evidencias_academicas",
                "gestion_academica_analysis.detectar_riesgos_academicos",
                "gestion_academica_graph.detectar_acuerdos_pendientes"],
            "construir_grafo_planificacion": [
                "planificacion_analysis.calcular_indicadores_planificacion",
                "planificacion_analysis.detectar_riesgos_estrategicos"],
            "construir_grafo_validacion_evidencia": ["validacion_evidencia_graph._evaluar_por_reglas"],
            "construir_grafo_trazabilidad": ["trazabilidad_graph.analizar_relaciones",
                                              "trazabilidad_graph.detectar_brechas"],
            "construir_grafo_coordinador_mejora_continua": [
                "mejora_continua_coordinator.analizar_planificacion",
                "mejora_continua_coordinator.analizar_gestion_academica",
                "mejora_continua_coordinator.analizar_gestion_silabos",
                "mejora_continua_coordinator.integrar_hallazgos",
                "mejora_continua_coordinator.calcular_riesgo_general"],
        }

        def blocked_network(*_args, **_kwargs):
            raise AssertionError("La prueba intentó abrir una conexión de red")

        with patch.object(socket.socket, "connect", blocked_network), \
                patch("socket.create_connection", blocked_network), \
                patch("socket.getaddrinfo", blocked_network), \
                patch("urllib.request.urlopen", blocked_network):
            graph = getattr(module, constructor)()
            for update in graph.stream(initial_state, stream_mode="updates"):
                for node_name, node_state in update.items():
                    nodes.append(node_name)
                    if isinstance(node_state, dict):
                        final_state.update(node_state)
        return {"graph": f"{module.__name__}.{constructor}", "initial_state": deepcopy(initial_state),
                "final_state": final_state, "nodes": nodes, "errors": [],
                "dependencies_substituted": ["Supabase in-memory query double", "Gemini identified test doubles",
                                              "synthetic document reader", "HTTPException import stub"],
                "original_functions": original_functions[constructor],
                "external_operations_intercepted": deepcopy(self.supabase.operations[operation_offset:]),
                "gemini_doubles_called": deepcopy(self.gemini_calls[gemini_offset:]),
                "technical_result": "completed"}

    def _assert_analytical_contract_accepts(self, trace, module, macroprocess, document_id):
        from evaluation.analytical_contracts import (
            AnalyticalExecutionRecord, AnalyticalKind, AnalyticalStatus,
        )
        from evaluation.schemas import DocumentReference, Expediente, Macroprocess

        expediente = Expediente(
            expediente_id="synthetic-graph-verification",
            corpus_id="synthetic-graph-corpus",
            documents=(DocumentReference(
                document_id=document_id, name="synthetic-graph-input.txt", format="txt",
                sha256="a" * 64, version="synthetic-v1", locator="synthetic://graph-input"),),
            document_version="synthetic-v1", content_sha256="b" * 64,
            macroprocesos=(macroprocess,),
        )
        source_hash = hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
        now = datetime.now(timezone.utc)
        record = AnalyticalExecutionRecord(
            execution_id="synthetic-graph-execution", expediente_id=expediente.expediente_id,
            macroproceso=macroprocess, document_ids=(document_id,),
            kind=AnalyticalKind.ORIGINAL_ANALYTICAL, function_name=trace["graph"],
            code_sha256=source_hash, status=AnalyticalStatus.COMPLETED,
            analysis_data=trace["final_state"], normative_results=None,
            started_at=now, finished_at=now, duration_ns=0,
            processing_mode="verificacion_grafo_aislada",
            provenance={"source": "synthetic_local", "nodes": trace["nodes"],
                        "dependencies_substituted": trace["dependencies_substituted"],
                        "external_operations_intercepted": trace["external_operations_intercepted"],
                        "normative_assessment_performed": False},
        )
        self.assertEqual(record.analysis_data, trace["final_state"])
        self.assertIsNone(record.normative_results)
        return record

    @staticmethod
    def _base_rows():
        return {
            "macroproceso_evidencias": [
                {"id": "SYN-PLAN-1", "codigo": "SYN-PLAN-1", "macroproceso": "planificacion_estrategica",
                 "titulo": "Plan de mejora sintético", "descripcion": "Meta institucional", "estado": "pendiente",
                 "prioridad": "alta", "avance": 20, "archivo_url": None},
                {"id": "SYN-ACAD-1", "codigo": "SYN-ACAD-1", "macroproceso": "gestion_academica",
                 "titulo": "Acta sintética de docentes", "descripcion": "seguimiento académico",
                 "estado": "pendiente", "prioridad": "alta", "avance": 10, "archivo_url": None},
            ],
            "silabos": [{"id": "SYN-SIL-1", "archivo_url": "https://synthetic.invalid/syllabus.txt",
                         "asignatura": "Curso sintético de programación", "codigo_asignatura": "SYN-101",
                         "ciclo": 1, "estado": "completo"}],
            "analisis_silabo": [{"silabo_id": "SYN-SIL-1", "resumen": "Análisis sintético",
                                 "contenidos_detectados": ["programación", "algoritmo"],
                                 "competencias_detectadas": ["analiza"], "resultados_aprendizaje": [],
                                 "secciones_faltantes": [], "nivel_riesgo": "medio"}],
            "acciones_mejora": [{"id": "SYN-ACT-1", "estado": "pendiente", "prioridad": "alta"}],
            "brechas_curriculares": [{"id": "SYN-GAP-1", "silabo_id": "SYN-SIL-1", "ciclo": 1,
                                      "tipo_brecha": "Articulación sintética", "prioridad": "alta",
                                      "estado": "pendiente"}],
        }

    def test_original_syllabus_graph_runs_with_real_rules_and_intercepted_write(self):
        self.supabase.reset(self._base_rows())
        trace = self._run_and_trace(self.modules["syllabus"], "construir_grafo_analisis",
                                    {"silabo_id": "SYN-SIL-1"})
        self.assertEqual(trace["nodes"], ["obtener_silabo", "validar_archivo", "extraer_texto",
                                           "analizar_contenido", "generar_recomendaciones_gemini",
                                           "guardar_analisis"])
        analysis = trace["final_state"]["analisis"]
        self.assertIn("contenidos_detectados", analysis)
        self.assertEqual(analysis["modelo_usado"], "TEST_DOUBLE_GEMINI_SYLLABUS")
        self.assertEqual(trace["final_state"]["resultado_guardado"][0]["silabo_id"], "SYN-SIL-1")
        self._assert_analytical_contract_accepts(
            trace, self.modules["syllabus"], Macroprocess.SYLLABUS, "SYN-SIL-1")
        writes = [event for event in self.supabase.operations if event["operation"] in {"delete", "insert"}]
        self.assertEqual([event["operation"] for event in writes], ["delete", "insert"])
        self.assertEqual(len(trace["external_operations_intercepted"]), 3)
        self.assertTrue(all(event["table"] == "analisis_silabo" for event in writes))
        self.assertEqual(self.document_reads, ["https://synthetic.invalid/syllabus.txt"])
        self.assertIn(("syllabus", {"test_double": True}), self.gemini_calls)

    def test_academic_graph_runs_original_analytics_and_identified_gemini_double(self):
        self.supabase.reset(self._base_rows())
        trace = self._run_and_trace(self.modules["academic"], "construir_grafo_gestion_academica", {})
        self.assertEqual(trace["nodes"], ["obtener_evidencias_gestion_academica",
                                           "calcular_indicadores_gestion_academica",
                                           "clasificar_evidencias_academicas", "detectar_acuerdos_pendientes",
                                           "detectar_riesgos_academicos", "generar_recomendaciones_gemini",
                                           "preparar_resultado"])
        self.assertEqual(trace["final_state"]["indicadores"]["total_evidencias"], 1)
        self.assertEqual(trace["final_state"]["clasificacion"]["acuerdos_docentes"][0]["id"], "SYN-ACAD-1")
        self.assertTrue(trace["final_state"]["riesgos_detectados"])
        self.assertEqual(trace["final_state"]["resultado"]["modelo_usado"], "TEST_DOUBLE_GEMINI_ACADEMIC")
        self._assert_analytical_contract_accepts(
            trace, self.modules["academic"], Macroprocess.ACADEMIC, "SYN-ACAD-1")
        self.assertFalse(any(event["operation"] != "select" for event in self.supabase.operations))

    def test_planning_graph_runs_original_analytics_and_identified_gemini_double(self):
        self.supabase.reset(self._base_rows())
        trace = self._run_and_trace(self.modules["planning"], "construir_grafo_planificacion", {})
        self.assertEqual(trace["nodes"], ["obtener_evidencias_planificacion",
                                           "calcular_indicadores_planificacion",
                                           "detectar_riesgos_estrategicos", "generar_recomendaciones_gemini",
                                           "preparar_resultado", "guardar_o_devolver_analisis"])
        self.assertEqual(trace["final_state"]["dashboard"]["total"], 1)
        self.assertEqual(trace["final_state"]["dashboard"]["pendientes_alta"], 1)
        self.assertTrue(trace["final_state"]["riesgos_detectados"])
        self.assertEqual(trace["final_state"]["resultado"]["modelo_usado"], "TEST_DOUBLE_GEMINI_PLANNING")
        self.assertEqual(trace["final_state"]["resultado"]["dashboard"], trace["final_state"]["dashboard"])
        self._assert_analytical_contract_accepts(
            trace, self.modules["planning"], Macroprocess.PLANNING, "SYN-PLAN-1")

    def test_evidence_validation_graph_runs_rule_evaluator_and_intercepts_insert(self):
        evidence = {"id": "SYN-EV-1", "codigo": "SYN-EV-1", "macroproceso": "gestion_academica",
                    "titulo": "Acta de seguimiento académico", "descripcion": "objetivo de mejora docente",
                    "tipo_evidencia": "acta", "responsable": "Comité académico",
                    "archivo_url": "https://synthetic.invalid/evidence.txt", "prioridad": "alta"}
        rows = self._base_rows()
        rows["macroproceso_evidencias"].append(evidence)
        self.supabase.reset(rows)
        trace = self._run_and_trace(self.modules["validation"], "construir_grafo_validacion_evidencia",
                                    {"evidencia_id": "SYN-EV-1"})
        self.assertEqual(trace["nodes"], ["obtener_evidencia", "extraer_texto_documento", "validar_por_reglas",
                                           "generar_recomendacion_gemini", "guardar_validacion"])
        self.assertIn("nivel_validez", trace["final_state"]["resultado_base"])
        self.assertEqual(trace["final_state"]["resultado"]["modelo_usado"], "TEST_DOUBLE_GEMINI_VALIDATION")
        writes = [event for event in self.supabase.operations if event["operation"] == "insert"]
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0]["table"], "validacion_ia_macroproceso_evidencias")
        self.assertEqual(writes[0]["payload"]["evidencia_id"], "SYN-EV-1")

    def test_curriculum_trace_graph_runs_rules_and_intercepts_delete_and_inserts(self):
        rows = self._base_rows()
        rows["silabos"] = [{"id": "SYN-SIL-5", "asignatura": "Taller sintético de gestión", "ciclo": 5,
                            "codigo_asignatura": "SYN-501"}]
        rows["analisis_silabo"] = [{"silabo_id": "SYN-SIL-5", "resumen": "Resumen sintético",
                                    "contenidos_detectados": ["gestión de proyectos"],
                                    "competencias_detectadas": [], "resultados_aprendizaje": [],
                                    "secciones_faltantes": [], "nivel_riesgo": "medio"}]
        self.supabase.reset(rows)
        trace = self._run_and_trace(self.modules["traceability"], "construir_grafo_trazabilidad", {})
        self.assertEqual(trace["nodes"], ["obtener_silabos_y_analisis", "agrupar_por_ciclo", "analizar_relaciones",
                                           "detectar_brechas", "enriquecer_con_gemini", "guardar_trazabilidad",
                                           "guardar_brechas"])
        self.assertTrue(trace["final_state"]["brechas"])
        self.assertTrue(any("trazabilidad" in item["tipo_brecha"].lower()
                            for item in trace["final_state"]["brechas"]))
        self.assertEqual(trace["final_state"]["modelo_trazabilidad"], "TEST_DOUBLE_GEMINI_TRACEABILITY")
        self.assertNotIn("CriterionResult", repr(trace["final_state"]))
        writes = [event for event in self.supabase.operations if event["operation"] != "select"]
        self.assertEqual([event["operation"] for event in writes], ["delete", "delete", "insert"])
        self.assertEqual({event["table"] for event in writes}, {"trazabilidad_curricular", "brechas_curriculares"})

    def test_syllabus_missing_file_stops_before_gemini_or_write(self):
        rows = self._base_rows()
        rows["silabos"][0]["archivo_url"] = None
        self.supabase.reset(rows)
        operation_offset = len(self.supabase.operations)
        with patch.object(socket.socket, "connect", side_effect=AssertionError("network disabled")), \
                patch("socket.create_connection", side_effect=AssertionError("network disabled")), \
                patch("socket.getaddrinfo", side_effect=AssertionError("network disabled")), \
                patch("urllib.request.urlopen", side_effect=AssertionError("network disabled")):
            graph = self.modules["syllabus"].construir_grafo_analisis()
            with self.assertRaises(FakeHTTPException) as caught:
                graph.invoke({"silabo_id": "SYN-SIL-1"})
        self.assertEqual(caught.exception.status_code, 400)
        self.assertFalse(self.gemini_calls)
        self.assertFalse(any(event["operation"] != "select" for event in self.supabase.operations))
        error_trace = {
            "graph": "app.agents.syllabus_graph.construir_grafo_analisis",
            "initial_state": {"silabo_id": "SYN-SIL-1"},
            "nodes": ["obtener_silabo", "validar_archivo"],
            "errors": [{"type": type(caught.exception).__name__, "status_code": caught.exception.status_code}],
            "external_operations_intercepted": self.supabase.operations[operation_offset:],
            "technical_result": "expected_error_before_gemini_and_writes",
        }
        self.assertEqual(error_trace["technical_result"], "expected_error_before_gemini_and_writes")

    def test_coordinator_consumes_persisted_snapshots_not_other_graphs(self):
        self.supabase.reset(self._base_rows())
        coordinator = self.modules["coordinator"]
        trace = self._run_and_trace(coordinator, "construir_grafo_coordinador_mejora_continua", {})
        self.assertEqual(trace["nodes"], ["obtener_datos_generales", "analizar_planificacion",
                                           "analizar_gestion_academica", "analizar_gestion_silabos",
                                           "integrar_hallazgos", "calcular_riesgo_general",
                                           "generar_recomendaciones_gemini", "preparar_resultado"])
        result = trace["final_state"]["resultado"]
        self.assertEqual(len(result["estado_macroprocesos"]), 3)
        self.assertEqual(result["modelo_usado"], "TEST_DOUBLE_GEMINI_COORDINATOR")
        reads = [event["table"] for event in self.supabase.operations if event["operation"] == "select"]
        self.assertEqual(reads, ["macroproceso_evidencias", "acciones_mejora", "brechas_curriculares", "silabos"])
        self.assertNotIn("gestion_academica_graph", coordinator.__dict__)
        source = Path(coordinator.__file__).read_text(encoding="utf-8")
        self.assertNotIn("from app.agents.gestion_academica_graph", source)
        self.assertNotIn("from app.agents.planificacion_graph", source)

    def test_original_graph_imports_resolve_to_real_langgraph_with_external_clients_stubbed(self):
        from langgraph.graph import StateGraph
        self.assertTrue(all(callable(getattr(module, constructor, None)) for module, constructor in (
            (self.modules["syllabus"], "construir_grafo_analisis"),
            (self.modules["academic"], "construir_grafo_gestion_academica"),
            (self.modules["planning"], "construir_grafo_planificacion"),
            (self.modules["validation"], "construir_grafo_validacion_evidencia"),
            (self.modules["traceability"], "construir_grafo_trazabilidad"),
            (self.modules["coordinator"], "construir_grafo_coordinador_mejora_continua"),
        )))
        self.assertTrue(StateGraph.__module__.startswith("langgraph"))
        client_module = sys.modules["app.services.supabase_client"]
        self.assertIs(client_module.supabase, self.supabase)


if __name__ == "__main__":
    unittest.main()
