from __future__ import annotations
import json
from pathlib import Path
import tempfile
import unittest
from dataclasses import replace
from evaluation.factory import synthetic_config, synthetic_expediente
from evaluation.runner import BenchmarkRunner, MockAnalysisAdapter, UnsafeAdapterError
from evaluation.schemas import Classification, CriterionResult, EvaluationState, ExecutionStatus
from evaluation.store import DuplicateExecutionError, IntegrityError, LocalExecutionStore


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = LocalExecutionStore(Path(self.temp.name) / "runs.jsonl")
        self.expediente = synthetic_expediente()
        self.config = synthetic_config()
        self.runner = BenchmarkRunner(self.store)

    def tearDown(self):
        self.temp.cleanup()

    def test_synthetic_fixture_and_schema_validate(self):
        self.assertEqual(self.expediente.source, "sintetico")
        self.assertEqual(len(self.expediente.documents), 1)

    def test_five_replicas_have_unique_ids_and_are_queryable(self):
        records = self.runner.run_replicas(self.expediente, self.config, 5)
        self.assertEqual(len(records), 5)
        self.assertEqual(len({r.execution_id for r in records}), 5)
        self.assertTrue(all(r.status is ExecutionStatus.SUCCESS for r in records))
        self.assertEqual(len(self.store.query(expediente_id=self.expediente.expediente_id)), 5)
        self.assertEqual(self.store.query(replica=3)[0].replica, 3)

    def test_failure_is_saved_without_raw_exception_message(self):
        record = BenchmarkRunner(self.store, MockAnalysisAdapter(fail_for_test=True)).run(
            self.expediente, self.config)
        self.assertEqual(record.status, ExecutionStatus.ERROR)
        self.assertNotIn("sensitive", record.error_message)
        self.assertEqual(self.store.read_all()[0].error_type, "RuntimeError")

    def test_external_adapter_is_rejected(self):
        adapter = MockAnalysisAdapter()
        adapter.external_calls_enabled = True
        with self.assertRaises(UnsafeAdapterError):
            BenchmarkRunner(self.store, adapter).run(self.expediente, self.config)
        self.assertEqual(self.store.read_all(), [])

    def test_custom_adapter_is_not_implicitly_authorized(self):
        class CustomAdapter:
            mode = self.config.effective_mode
            external_calls_enabled = False
            business_writes_enabled = False
        with self.assertRaises(UnsafeAdapterError):
            BenchmarkRunner(self.store, CustomAdapter()).run(self.expediente, self.config)
        self.assertEqual(self.store.read_all(), [])

    def test_adapter_receives_and_persists_same_execution_id_and_metadata(self):
        record = self.runner.run(self.expediente, self.config)
        self.assertEqual(record.results[0].execution_id, record.execution_id)
        self.assertEqual(record.verdict.criterion_results[0].execution_id, record.execution_id)
        self.assertEqual(record.telemetry["adapter"], "MockAnalysisAdapter")
        self.assertEqual(record.telemetry["run_status"], "mock_completed")

    def test_duplicate_execution_id_is_rejected(self):
        record = self.runner.run(self.expediente, self.config)
        with self.assertRaises(DuplicateExecutionError):
            self.store.save(record)

    def test_duplicate_replica_number_in_same_experiment_is_rejected(self):
        first = self.runner.run_replicas(self.expediente, self.config, 1)[0]
        new_id = "different-execution-id"
        results = tuple(replace(result, execution_id=new_id) for result in first.results)
        duplicate_replica = replace(
            first, execution_id=new_id, results=results,
            verdict=replace(first.verdict, criterion_results=results))
        with self.assertRaises(DuplicateExecutionError):
            self.store.save(duplicate_replica)

    def test_tampered_jsonl_is_detected(self):
        self.runner.run(self.expediente, self.config)
        data = json.loads(self.store.path.read_text(encoding="utf-8"))
        data["record"]["replica"] = 9
        self.store.path.write_text(json.dumps(data) + "\n", encoding="utf-8")
        with self.assertRaises(IntegrityError):
            self.store.read_all()

    def test_non_synthetic_configuration_is_rejected(self):
        with self.assertRaises(UnsafeAdapterError):
            self.runner.run(self.expediente, replace(self.config, external_calls_enabled=True))

    def test_evaluation_and_classification_are_distinct_and_consistent(self):
        with self.assertRaises(ValueError):
            CriterionResult("C", EvaluationState.NOT_EVALUABLE, Classification.CONFORMING, "not assessed")


if __name__ == "__main__":
    unittest.main()
