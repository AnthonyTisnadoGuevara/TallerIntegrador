from __future__ import annotations
import hashlib
import inspect
from pathlib import Path
import tempfile
import unittest

from evaluation.agent_input import AgentInputValidationError, build_agent_input
from evaluation.catalog import CatalogStatus, approve_catalog, load_catalog
from evaluation.contracts import ApplicabilityRecord, LocationStatus, ReviewStatus
from evaluation.document_reader import DocumentReadError, read_local_document
from evaluation.factory import synthetic_config, synthetic_expediente
from evaluation.normative_graph import (GraphDependencyUnavailable, TransportOnlyEvaluator,
                                        build_normative_graph, run_normative_pipeline, validate_input_node,
                                        validate_result_evidence)
from evaluation.schemas import (ApplicabilityStatus, Classification, CriterionResult,
                                DocumentReference, ErrorCategory, EvaluationState)


FIXTURE_CATALOG = Path(__file__).parents[1] / "fixtures" / "synthetic_catalog.json"


class NormativeGraphTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.catalog = approve_catalog(
            load_catalog(FIXTURE_CATALOG), validated_by="synthetic-reviewer",
            approval_reference="synthetic://fixture-approval", validated_at=synthetic_expediente_time())
        self.text = "Synthetic heading\nOnly technical fixture content, not institutional evidence.\n"
        (self.root / "document.txt").write_bytes(self.text.encode("utf-8"))
        self.document = DocumentReference(
            "SYNTH-LOCAL-DOC", "synthetic local document", "txt",
            hashlib.sha256(self.text.encode("utf-8")).hexdigest(), "1", "document.txt")
        base = synthetic_expediente()
        from evaluation.schemas import Expediente
        self.expediente = Expediente("SYNTH-LOCAL-CASE", base.corpus_id, (self.document,), "1", "b" * 64)
        self.criterion = self.catalog.criteria[0]
        self.applicable = ApplicabilityRecord(
            self.expediente.expediente_id, self.criterion.criterion_id,
            self.catalog.catalog_id, self.catalog.normative_version,
            ApplicabilityStatus.APPLICABLE, "Registro sintético revisado para probar el flujo.",
            ReviewStatus.REVIEWED)
        self.request = build_agent_input(self.expediente, self.catalog,
                                         ("Regla sintética de transporte; no es normativa.",),
                                         (self.applicable,))

    def tearDown(self):
        self.temp.cleanup()

    def test_synthetic_pipeline_reads_txt_and_never_claims_conformity(self):
        state = run_normative_pipeline(self.request, self.root, synthetic_config())
        self.assertEqual(state["status"], "completed_not_normatively_evaluated")
        self.assertEqual(state["documents"][0].text, self.text)
        self.assertEqual(len(state["results"]), 1)
        self.assertEqual(state["results"][0].evaluation_state, EvaluationState.NOT_EVALUABLE)
        self.assertEqual(state["results"][0].classification, Classification.INDETERMINATE)
        self.assertEqual(state["verdict"].overall_classification, Classification.INDETERMINATE)
        self.assertEqual(state["results"][0].execution_id, state["execution_id"])

    def test_input_node_preserves_runner_execution_id(self):
        from evaluation.normative_graph import validate_input_node
        expected_id = "synthetic-runner-execution-001"
        state = validate_input_node({"request": self.request, "document_root": str(self.root),
                                     "config": synthetic_config(), "execution_id": expected_id})
        self.assertEqual(state["execution_id"], expected_id)

    def test_missing_applicability_remains_undetermined(self):
        request = build_agent_input(self.expediente, self.catalog, ("synthetic rule",))
        state = run_normative_pipeline(request, self.root, synthetic_config())
        self.assertEqual(state["applicability"][0].status, ApplicabilityStatus.UNDETERMINED)
        self.assertEqual(state["results"][0].classification, Classification.INDETERMINATE)
        self.assertEqual(state["results"][0].evaluation_state, EvaluationState.NOT_EVALUABLE)

    def test_unreviewed_applicability_is_not_used_as_a_decision(self):
        pending = ApplicabilityRecord(
            self.expediente.expediente_id, self.criterion.criterion_id,
            self.catalog.catalog_id, self.catalog.normative_version,
            ApplicabilityStatus.APPLICABLE, "not reviewed", ReviewStatus.PENDING)
        request = build_agent_input(self.expediente, self.catalog, ("synthetic rule",), (pending,))
        state = run_normative_pipeline(request, self.root, synthetic_config())
        self.assertEqual(state["applicability"][0].status, ApplicabilityStatus.UNDETERMINED)

    def test_not_applicable_is_separate_from_evaluation_classification(self):
        record = ApplicabilityRecord(
            self.expediente.expediente_id, self.criterion.criterion_id,
            self.catalog.catalog_id, self.catalog.normative_version,
            ApplicabilityStatus.NOT_APPLICABLE, "synthetic scope exclusion", ReviewStatus.REVIEWED)
        request = build_agent_input(self.expediente, self.catalog, ("synthetic rule",), (record,))
        state = run_normative_pipeline(request, self.root, synthetic_config())
        self.assertEqual(state["results"][0].evaluation_state, EvaluationState.NOT_APPLICABLE)
        self.assertEqual(state["results"][0].classification, Classification.NOT_APPLICABLE)

    def test_catalog_pending_is_rejected_before_graph_entry(self):
        with self.assertRaises(AgentInputValidationError):
            build_agent_input(self.expediente, load_catalog(FIXTURE_CATALOG), ("synthetic rule",))

    def test_document_missing_hash_and_format_errors_are_explicit(self):
        missing = DocumentReference("M", "missing", "txt", "a" * 64, "1", "missing.txt")
        with self.assertRaises(DocumentReadError) as caught:
            read_local_document(missing, self.root)
        self.assertEqual(caught.exception.code, "document_not_found")
        bad_hash = DocumentReference("H", "hash", "txt", "0" * 64, "1", "document.txt")
        with self.assertRaises(DocumentReadError) as caught:
            read_local_document(bad_hash, self.root)
        self.assertEqual(caught.exception.code, "hash_mismatch")
        unsupported = DocumentReference("P", "pdf", "pdf", "a" * 64, "1", "doc.pdf")
        with self.assertRaises(DocumentReadError) as caught:
            read_local_document(unsupported, self.root)
        self.assertEqual(caught.exception.code, "unsupported_format")

    def test_document_failure_stops_run_and_never_becomes_nonconformity(self):
        missing_doc = DocumentReference("M", "missing", "txt", "a" * 64, "1", "missing.txt")
        from evaluation.schemas import Expediente
        case = Expediente(self.expediente.expediente_id, self.expediente.corpus_id,
                          (missing_doc,), "1", "b" * 64)
        request = build_agent_input(case, self.catalog, ("synthetic rule",), (self.applicable,))
        state = run_normative_pipeline(request, self.root, synthetic_config())
        self.assertEqual(state["status"], "failed")
        self.assertIsNone(state.get("verdict"))
        self.assertEqual(state["errors"][0]["code"], "DOCUMENT_NOT_FOUND")

    def test_extra_ground_truth_state_input_is_rejected(self):
        state = validate_input_node({"request": self.request, "document_root": str(self.root),
                                     "config": synthetic_config(), "ground_truth": {}})
        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["errors"][0]["code"], "INPUT_FIELDS_NOT_ALLOWED")
        self.assertNotIn("ground_truth", state)

    def test_url_and_path_traversal_are_rejected(self):
        for locator in ("https://example.invalid/doc.txt", "../outside.txt", "..\\outside.txt"):
            document = DocumentReference("X", "x", "txt", "a" * 64, "1", locator)
            with self.assertRaises(DocumentReadError) as caught:
                read_local_document(document, self.root)
            self.assertEqual(caught.exception.code, "invalid_reference")

    def test_empty_and_invalid_utf8_documents_are_distinct(self):
        (self.root / "empty.txt").write_bytes(b" \n")
        empty = DocumentReference("E", "empty", "txt", hashlib.sha256(b" \n").hexdigest(), "1", "empty.txt")
        with self.assertRaises(DocumentReadError) as caught:
            read_local_document(empty, self.root)
        self.assertEqual(caught.exception.code, "empty_document")
        raw = b"\xff\xfe"
        (self.root / "invalid.txt").write_bytes(raw)
        invalid = DocumentReference("U", "invalid", "txt", hashlib.sha256(raw).hexdigest(), "1", "invalid.txt")
        with self.assertRaises(DocumentReadError) as caught:
            read_local_document(invalid, self.root)
        self.assertEqual(caught.exception.code, "invalid_encoding")

    def test_evidence_document_and_line_locator_are_checked(self):
        result = CriterionResult(
            self.criterion.criterion_id, EvaluationState.EVALUATED, Classification.INDETERMINATE,
            "synthetic only", (self._evidence(self.document.document_id, "line:1"),),
            self.expediente.expediente_id, self.catalog.catalog_id, self.catalog.normative_version)
        check = validate_result_evidence((result,), self.expediente.documents,
                                         (read_local_document(self.document, self.root),))
        self.assertFalse(check.errors)
        self.assertEqual(check.results[0].evidence[0].location_status, "localizado")
        foreign = CriterionResult(
            self.criterion.criterion_id, EvaluationState.EVALUATED, Classification.INDETERMINATE,
            "synthetic only", (self._evidence("FOREIGN-DOC", "line:1"),),
            self.expediente.expediente_id, self.catalog.catalog_id, self.catalog.normative_version)
        check = validate_result_evidence((foreign,), self.expediente.documents,
                                         (read_local_document(self.document, self.root),))
        self.assertIn("FOREIGN_EVIDENCE_DOCUMENT", {item["code"] for item in check.errors})

    def test_page_evidence_is_not_claimed_verified_by_txt_reader(self):
        result = CriterionResult(
            self.criterion.criterion_id, EvaluationState.EVALUATED, Classification.INDETERMINATE,
            "synthetic only", (self._evidence(self.document.document_id, "page:1"),),
            self.expediente.expediente_id, self.catalog.catalog_id, self.catalog.normative_version)
        checked = validate_result_evidence((result,), self.expediente.documents,
                                           (read_local_document(self.document, self.root),))
        self.assertEqual(checked.results[0].evidence[0].location_status, "no_verificable")

    def test_state_has_no_ground_truth_fields_or_imports(self):
        from evaluation import normative_graph
        names = set(normative_graph.NormativeGraphState.__annotations__)
        self.assertFalse(names.intersection({"ground_truth", "reference_label", "reference_verdict", "adjudication"}))
        source = inspect.getsource(normative_graph)
        self.assertNotIn("ground_truth", source.lower())
        self.assertNotIn("supabase", source.lower())
        self.assertNotIn("gemini", source.lower())

    def test_transport_evaluator_is_explicitly_not_an_ai_or_normative_evaluator(self):
        self.assertEqual(TransportOnlyEvaluator.mode, "synthetic_transport_only")

    def test_langgraph_compiles_or_reports_missing_dependency(self):
        try:
            import langgraph  # noqa: F401
        except ImportError:
            with self.assertRaises(GraphDependencyUnavailable):
                build_normative_graph()
        else:
            from langgraph.graph.state import CompiledStateGraph
            self.assertIsInstance(build_normative_graph(), CompiledStateGraph)

    def test_compiled_langgraph_invokes_all_nodes_and_preserves_contracts(self):
        from langgraph.graph.state import CompiledStateGraph
        graph = build_normative_graph()
        self.assertIsInstance(graph, CompiledStateGraph)
        invocation = {"request": self.request, "document_root": str(self.root),
                      "config": synthetic_config(), "execution_id": "synthetic-graph-run"}
        expected_nodes = [
            "validate_input", "prepare_expedient", "verify_catalog", "resolve_applicability",
            "process_documents", "prepare_evaluation_units", "evaluate_criteria",
            "verify_evidence", "consolidate_results", "generate_verdict", "validate_output",
        ]
        updates = list(graph.stream(invocation, stream_mode="updates"))
        self.assertEqual([next(iter(update)) for update in updates], expected_nodes)
        state = graph.invoke(invocation)
        self.assertEqual(state["status"], "completed_not_normatively_evaluated")
        self.assertEqual(state["execution_id"], invocation["execution_id"])
        self.assertEqual(state["expediente_id"], self.expediente.expediente_id)
        self.assertEqual(state["results"][0].criterion_id, self.criterion.criterion_id)
        self.assertEqual(state["results"][0].evaluation_state, EvaluationState.NOT_EVALUABLE)
        self.assertEqual(state["results"][0].classification, Classification.INDETERMINATE)
        self.assertEqual(state["verdict"].criterion_results, state["results"])
        self.assertIn(self.document.document_id, state["metadata"]["document_sha256"])

    def test_langgraph_runner_adapter_persists_five_synthetic_replicas(self):
        import json
        import socket
        from unittest.mock import patch
        from evaluation.adapters import LocalNormativeGraphAdapter
        from evaluation.runner import BenchmarkRunner
        from evaluation.store import LocalExecutionStore

        store = LocalExecutionStore(self.root / "benchmark-runs.jsonl")
        adapter = LocalNormativeGraphAdapter(self.request, str(self.root))
        runner = BenchmarkRunner(store, adapter)
        with patch.object(socket, "socket", side_effect=AssertionError("network is disabled in test")):
            records = runner.run_replicas(self.expediente, synthetic_config(), 5)
        self.assertEqual(len(records), 5)
        self.assertTrue(all(record.status.value == "completado" for record in records))
        self.assertEqual([record.replica for record in records], [1, 2, 3, 4, 5])
        self.assertEqual(len({record.execution_id for record in records}), 5)
        self.assertTrue(all(record.results[0].execution_id == record.execution_id for record in records))
        experiment_id = records[0].experiment_id
        self.assertTrue(all(record.experiment_id == experiment_id for record in records))
        recovered = store.query(experiment_id=experiment_id)
        self.assertEqual(len(recovered), 5)
        self.assertEqual([record.replica for record in recovered], [1, 2, 3, 4, 5])
        self.assertEqual(len(store.read_all()), 5)
        line = json.loads(store.path.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(line["record"]["execution_id"], records[0].execution_id)
        self.assertEqual(recovered[0].results[0].classification, Classification.INDETERMINATE)
        self.assertEqual(recovered[0].telemetry["adapter"], "LocalNormativeGraphAdapter")
        self.assertEqual(recovered[0].telemetry["graph_version"], "normative-evaluation-2b.1")

    def test_adapter_records_graph_document_error_code(self):
        from evaluation.adapters import LocalNormativeGraphAdapter
        from evaluation.runner import BenchmarkRunner
        from evaluation.schemas import Expediente
        from evaluation.store import LocalExecutionStore

        missing_doc = DocumentReference("MISSING", "missing synthetic file", "txt",
                                        "a" * 64, "1", "missing.txt")
        case = Expediente(self.expediente.expediente_id, self.expediente.corpus_id,
                          (missing_doc,), "1", "c" * 64)
        request = build_agent_input(case, self.catalog, ("synthetic rule",), (self.applicable,))
        store = LocalExecutionStore(self.root / "failed-run.jsonl")
        record = BenchmarkRunner(store, LocalNormativeGraphAdapter(request, str(self.root))).run(
            case, synthetic_config())
        self.assertEqual(record.status.value, "error")
        self.assertEqual(record.error_category, ErrorCategory.DOCUMENT_READ)
        self.assertIn("DOCUMENT_NOT_FOUND", record.telemetry["error_codes"])
        self.assertEqual(store.read_all()[0].execution_id, record.execution_id)

    @staticmethod
    def _evidence(document_id, locator):
        from evaluation.schemas import Evidence
        return Evidence(document_id, "synthetic-test-reference", locator=locator)


def synthetic_expediente_time():
    from datetime import datetime, timezone
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


if __name__ == "__main__":
    unittest.main()
