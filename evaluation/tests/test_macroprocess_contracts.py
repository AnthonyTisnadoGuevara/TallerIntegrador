from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from evaluation.ground_truth import (GroundTruthAnnotation, GroundTruthRecord,
                                     GroundTruthStatus)
from evaluation.ground_truth_store import GroundTruthStore
from evaluation.contracts import ReviewStatus
from evaluation.agent_input import AgentInputValidationError, build_agent_input
from evaluation.catalog import approve_catalog, load_catalog
from evaluation.metrics.common import MetricInputError, index_final_ground_truth, select_primary_runs
from evaluation.runner import BenchmarkRunner
from evaluation.schemas import (ApplicabilityStatus, EvaluationKey, Macroprocess,
                                MacroprocessAggregationPolicy, canonical_json,
                                sha256_json, to_primitive)
from evaluation.factory import synthetic_config, synthetic_expediente
from evaluation.store import LocalExecutionStore


class MacroprocessContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = LocalExecutionStore(Path(self.temp.name) / "runs.jsonl")

    def tearDown(self):
        self.temp.cleanup()

    def test_three_synthetic_fixtures_use_known_process_ids(self):
        fixture = Path(__file__).parents[1] / "fixtures" / "synthetic_macroprocess_cases.json"
        cases = json.loads(fixture.read_text(encoding="utf-8"))["cases"]
        self.assertEqual({case["macroproceso"] for case in cases},
                         {item.value for item in Macroprocess})
        self.assertTrue(all(case["criterion_id"].startswith("SYNTH-") for case in cases))

    def test_unknown_process_and_duplicate_process_are_rejected(self):
        with self.assertRaises(ValueError):
            Macroprocess("unknown")
        with self.assertRaisesRegex(ValueError, "duplicado"):
            replace(synthetic_expediente(), macroprocesos=(Macroprocess.PLANNING,
                                                            Macroprocess.PLANNING))

    def test_evaluation_key_separates_same_case_and_criterion_by_process(self):
        planning = EvaluationKey("E-1", Macroprocess.PLANNING, "SYNTH-C1", "N1")
        academic = EvaluationKey("E-1", Macroprocess.ACADEMIC, "SYNTH-C1", "N1")
        self.assertNotEqual(planning, academic)

    def test_cross_process_aggregation_requires_documented_methodology_approval(self):
        with self.assertRaisesRegex(ValueError, "documentada"):
            replace(synthetic_config(),
                    macroprocess_aggregation_policy=MacroprocessAggregationPolicy.APPROVED_AGGREGATION)
        approved = replace(synthetic_config(),
                           macroprocess_aggregation_policy=MacroprocessAggregationPolicy.APPROVED_AGGREGATION,
                           aggregation_approval_reference="synthetic-approval-reference")
        self.assertEqual(approved.aggregation_approval_reference, "synthetic-approval-reference")

    def test_runner_requires_process_for_multi_process_expediente_and_round_trips(self):
        exp = replace(synthetic_expediente(), macroprocesos=(Macroprocess.PLANNING,
                                                              Macroprocess.ACADEMIC))
        runner = BenchmarkRunner(self.store)
        with self.assertRaisesRegex(ValueError, "debe indicar macroproceso"):
            runner.run(exp, synthetic_config())
        record = runner.run(exp, synthetic_config(), macroproceso=Macroprocess.ACADEMIC)
        self.assertEqual(record.macroproceso, Macroprocess.ACADEMIC)
        self.assertEqual(record.results[0].macroproceso, Macroprocess.ACADEMIC)
        loaded = self.store.read_all()[0]
        self.assertEqual(loaded.macroproceso, Macroprocess.ACADEMIC)
        self.assertEqual(loaded.results[0].macroproceso, Macroprocess.ACADEMIC)

    def test_agent_input_requires_same_explicit_process_for_multi_process_case(self):
        exp = replace(synthetic_expediente(), macroprocesos=(Macroprocess.PLANNING,
                                                              Macroprocess.ACADEMIC))
        catalog_path = Path(__file__).parents[1] / "fixtures" / "synthetic_catalog.json"
        catalog = approve_catalog(load_catalog(catalog_path), validated_by="synthetic-reviewer",
                                  approval_reference="synthetic-test", validated_at=datetime.now(timezone.utc))
        with self.assertRaises(AgentInputValidationError):
            build_agent_input(exp, catalog, ("synthetic rule",))
        request = build_agent_input(exp, catalog, ("synthetic rule",),
                                    macroproceso=Macroprocess.ACADEMIC)
        self.assertIs(request.macroproceso, Macroprocess.ACADEMIC)

    def test_metrics_refuse_mixed_processes_and_can_select_one(self):
        exp = replace(synthetic_expediente(), macroprocesos=(Macroprocess.PLANNING,
                                                              Macroprocess.ACADEMIC))
        runner = BenchmarkRunner(self.store)
        first = runner.run(exp, synthetic_config(), experiment_id="EXP",
                           macroproceso=Macroprocess.PLANNING)
        second = runner.run(exp, synthetic_config(), experiment_id="EXP",
                            macroproceso=Macroprocess.ACADEMIC)
        with self.assertRaises(MetricInputError):
            select_primary_runs((first, second))
        selected = select_primary_runs((first, second), macroproceso=Macroprocess.ACADEMIC)
        self.assertEqual(selected.macroproceso, Macroprocess.ACADEMIC)
        self.assertEqual(next(iter(selected.selected_by_expediente.values())), second)

    def test_reference_index_excludes_other_and_legacy_processes(self):
        from evaluation.ground_truth import GroundTruthStatus
        now = datetime.now(timezone.utc)
        def ref(annotation_id, process):
            annotation = GroundTruthAnnotation(
                annotation_id, "E1", "SYNTH-C1", "N1", "reviewer",
                ApplicabilityStatus.UNDETERMINED, None, None, (), ReviewStatus.PENDING,
                now, "v1", macroproceso=process)
            return GroundTruthRecord("E1", "SYNTH-C1", "SYNTH-CAT", "N1", (annotation,),
                                     status=GroundTruthStatus.DRAFT, macroproceso=process)
        indexed, excluded = index_final_ground_truth(
            (ref("p", Macroprocess.PLANNING), ref("a", Macroprocess.ACADEMIC), ref("legacy", None)),
            Macroprocess.ACADEMIC)
        self.assertEqual(indexed, {})
        self.assertEqual(sum(item["reason"] == "different_or_missing_macroprocess"
                             for item in excluded), 2)

    def test_ground_truth_cannot_mix_macroprocesses(self):
        now = datetime.now(timezone.utc)
        annotation = GroundTruthAnnotation(
            "A1", "E1", "SYNTH-C1", "N1", "reviewer1",
            ApplicabilityStatus.UNDETERMINED, None, None, (),
            ReviewStatus.PENDING,
            now, "v1", macroproceso=Macroprocess.ACADEMIC)
        with self.assertRaisesRegex(ValueError, "mezclan"):
            GroundTruthRecord("E1", "SYNTH-C1", "SYNTH-CAT", "N1", (annotation,),
                              macroproceso=Macroprocess.PLANNING)

    def test_legacy_execution_without_macroprocess_remains_readable(self):
        record = BenchmarkRunner(self.store).run(synthetic_expediente(), synthetic_config())
        envelope = json.loads(self.store.path.read_text(encoding="utf-8"))
        payload = envelope["record"]
        payload.pop("macroproceso", None)
        for result in payload["results"]:
            result.pop("macroproceso", None)
        for result in payload["verdict"]["criterion_results"]:
            result.pop("macroproceso", None)
        envelope["integrity_sha256"] = sha256_json(payload)
        self.store.path.write_text(canonical_json(envelope) + "\n", encoding="utf-8")
        legacy = self.store.read_all()[0]
        self.assertEqual(legacy.expediente_id, record.expediente_id)
        self.assertIsNone(legacy.macroproceso)
        self.assertIsNone(legacy.results[0].macroproceso)

    def test_legacy_ground_truth_snapshot_without_process_remains_unassigned(self):
        now = datetime.now(timezone.utc)
        annotation = GroundTruthAnnotation(
            "A-legacy", "SYNTH-E1", "SYNTH-C1", "SYNTH-N1", "reviewer",
            ApplicabilityStatus.UNDETERMINED, None, None, (), ReviewStatus.PENDING,
            now, "v1")
        record = GroundTruthRecord("SYNTH-E1", "SYNTH-C1", "SYNTH-CAT", "SYNTH-N1",
                                   (annotation,), status=GroundTruthStatus.DRAFT)
        payload = to_primitive(record)
        payload.pop("macroproceso", None)
        payload["annotations"][0].pop("macroproceso", None)
        envelope = {"snapshot_id": "legacy-snapshot", "record": payload,
                    "integrity_sha256": sha256_json(payload)}
        path = Path(self.temp.name) / "ground_truth.jsonl"
        path.write_text(canonical_json(envelope) + "\n", encoding="utf-8")
        loaded = GroundTruthStore(path).read_all()[0]
        self.assertIsNone(loaded.macroproceso)
        self.assertIsNone(loaded.annotations[0].macroproceso)


if __name__ == "__main__":
    unittest.main()
