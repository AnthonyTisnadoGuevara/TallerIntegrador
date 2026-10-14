from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from evaluation.agent_input import AgentInputValidationError, build_agent_input, validate_agent_payload_shape
from evaluation.catalog import (CatalogStatus, CatalogValidationError, approve_catalog, load_catalog)
from evaluation.contracts import (ApplicabilityRecord, EvidenceReference, LocationStatus, ReviewStatus)
from evaluation.dataset import validate_dataset
from evaluation.factory import synthetic_expediente
from evaluation.ground_truth import (DisagreementResolution, GroundTruthAnnotation,
                                     GroundTruthRecord, GroundTruthStatus, has_disagreement)
from evaluation.ground_truth_store import GroundTruthStore
from evaluation.runner import BenchmarkRunner
from evaluation.schemas import (ApplicabilityStatus, Classification, CriterionResult,
                                EvaluationState, ExecutionStatus, canonical_json, sha256_json, to_primitive)
from evaluation.store import DuplicateExecutionError, LocalExecutionStore


FIXTURES = Path(__file__).parents[1] / "fixtures"
NOW = datetime(2026, 1, 2, tzinfo=timezone.utc)


class Phase2ATests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.expediente = synthetic_expediente()
        self.catalog = load_catalog(FIXTURES / "synthetic_catalog.json")

    def tearDown(self):
        self.temp.cleanup()

    def test_synthetic_catalog_loads_pending_and_hashes_raw_file(self):
        catalog = load_catalog(FIXTURES / "synthetic_catalog.json")
        self.assertEqual(catalog.status, CatalogStatus.PENDING)
        self.assertEqual(len(catalog.content_sha256), 64)
        self.assertEqual(catalog.criteria[0].official_id, "SYNTH-REF-001")

    def test_catalog_rejects_duplicate_criterion_ids(self):
        data = json.loads((FIXTURES / "synthetic_catalog.json").read_text(encoding="utf-8"))
        data["criteria"].append(dict(data["criteria"][0], official_id="SYNTH-REF-002"))
        path = Path(self.temp.name) / "duplicate.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(CatalogValidationError):
            load_catalog(path)

    def test_catalog_rejects_incompatible_version_and_self_approval(self):
        data = json.loads((FIXTURES / "synthetic_catalog.json").read_text(encoding="utf-8"))
        data["criteria"][0]["normative_version"] = "OTHER"
        path = Path(self.temp.name) / "version.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(CatalogValidationError):
            load_catalog(path)
        data["criteria"][0]["normative_version"] = data["normative_version"]
        data["validation_status"] = CatalogStatus.VALIDATED.value
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(CatalogValidationError):
            load_catalog(path)

    def test_catalog_integrity_mismatch_rejected(self):
        with self.assertRaises(CatalogValidationError):
            load_catalog(FIXTURES / "synthetic_catalog.json", expected_sha256="0" * 64)

    def test_undetermined_applicability_stays_indeterminate(self):
        record = ApplicabilityRecord(self.expediente.expediente_id, self.catalog.criteria[0].criterion_id,
                                     self.catalog.catalog_id, self.catalog.normative_version,
                                     ApplicabilityStatus.UNDETERMINED, "Insuficiente información ficticia.",
                                     ReviewStatus.PENDING)
        self.assertEqual(record.status, ApplicabilityStatus.UNDETERMINED)

    def _annotation(self, annotation_id, evaluator_id, label, *, reviewed=True):
        return GroundTruthAnnotation(
            annotation_id, self.expediente.expediente_id, self.catalog.criteria[0].criterion_id,
            self.catalog.normative_version, evaluator_id, ApplicabilityStatus.APPLICABLE,
            label, "Dictamen sintético de prueba.", (),
            ReviewStatus.REVIEWED if reviewed else ReviewStatus.INDIVIDUAL,
            NOW, "annotation-v1", NOW if reviewed else None)

    def test_reviewed_annotation_requires_reference_label_and_verdict(self):
        with self.assertRaises(ValueError):
            GroundTruthAnnotation("A", "E", "C", "V", "R", ApplicabilityStatus.APPLICABLE,
                                  None, None, (), ReviewStatus.REVIEWED, NOW, "v1", NOW)

    def test_disagreement_requires_and_accepts_documented_resolution(self):
        a1 = self._annotation("A1", "reviewer-1", Classification.CONFORMING)
        a2 = self._annotation("A2", "reviewer-2", Classification.NON_CONFORMING)
        pending = GroundTruthRecord(self.expediente.expediente_id, self.catalog.criteria[0].criterion_id,
                                    self.catalog.catalog_id, self.catalog.normative_version,
                                    (a1, a2), GroundTruthStatus.DISAGREEMENT)
        self.assertTrue(has_disagreement(pending))
        resolution = DisagreementResolution(("A1", "A2"), ApplicabilityStatus.APPLICABLE,
                                            Classification.INDETERMINATE, "Requiere revisión del especialista.",
                                            "adjudicator", NOW)
        final = GroundTruthRecord(
            pending.expediente_id, pending.criterion_id, pending.catalog_id, pending.normative_version,
            pending.annotations, GroundTruthStatus.VALIDATED, resolution,
            ApplicabilityStatus.APPLICABLE, Classification.INDETERMINATE,
            "Dictamen de adjudicación sintético.", "validator", NOW, "gt-v1")
        self.assertEqual(final.status, GroundTruthStatus.VALIDATED)
        issues = validate_dataset(expedientes=(self.expediente,), catalogs=(self.catalog,), ground_truth=(final,))
        self.assertIn("UNVALIDATED_CATALOG", {issue.code for issue in issues})

    def test_unadjudicated_disagreement_is_not_metric_ready(self):
        a1 = self._annotation("A1", "reviewer-1", Classification.CONFORMING)
        a2 = self._annotation("A2", "reviewer-2", Classification.NON_CONFORMING)
        pending = GroundTruthRecord(self.expediente.expediente_id, self.catalog.criteria[0].criterion_id,
                                    self.catalog.catalog_id, self.catalog.normative_version,
                                    (a1, a2), GroundTruthStatus.DISAGREEMENT)
        issues = validate_dataset(expedientes=(self.expediente,), catalogs=(self.catalog,), ground_truth=(pending,))
        self.assertIn("UNADJUDICATED_REFERENCE", {issue.code for issue in issues})
        self.assertIn("REFERENCE_NOT_VALIDATED", {issue.code for issue in issues})

    def test_evidence_from_foreign_document_is_rejected_by_dataset(self):
        evidence = EvidenceReference(self.expediente.expediente_id, "NOT-IN-CASE",
                                     LocationStatus.LOCATED, locator="page:1")
        applicability = ApplicabilityRecord(
            self.expediente.expediente_id, self.catalog.criteria[0].criterion_id,
            self.catalog.catalog_id, self.catalog.normative_version,
            ApplicabilityStatus.APPLICABLE, "Motivo sintético.", ReviewStatus.INDIVIDUAL,
            (evidence,))
        issues = validate_dataset(expedientes=(self.expediente,), catalogs=(self.catalog,),
                                  applicability=(applicability,))
        self.assertIn("FOREIGN_DOCUMENT", {issue.code for issue in issues})

    def test_agent_input_rejects_pending_catalog_and_ground_truth_fields(self):
        with self.assertRaises(AgentInputValidationError):
            build_agent_input(self.expediente, self.catalog, ("synthetic rule",))
        approved = approve_catalog(self.catalog, validated_by="synthetic-reviewer",
                                   approval_reference="synthetic://approval-test", validated_at=NOW)
        build_agent_input(self.expediente, approved, ("synthetic authorized rule",))
        with self.assertRaises(AgentInputValidationError):
            validate_agent_payload_shape({"expediente": {}, "catalog": {}, "authorized_rules": [],
                                          "ground_truth": {}})
        with self.assertRaises(AgentInputValidationError):
            validate_agent_payload_shape({"expediente": {"reference_label": "no_conforme"},
                                          "catalog": {}, "authorized_rules": []})

    def test_catalog_approval_requires_provenance_fields(self):
        with self.assertRaises(ValueError):
            approve_catalog(self.catalog, validated_by="", approval_reference="", validated_at=NOW)

    def test_malformed_catalog_reports_required_fields(self):
        path = Path(self.temp.name) / "malformed.json"
        path.write_text(json.dumps({"catalog_id": "x", "criteria": []}), encoding="utf-8")
        with self.assertRaises(CatalogValidationError) as caught:
            load_catalog(path)
        self.assertTrue(any("normative_version" in issue for issue in caught.exception.issues))
        self.assertTrue(any("criteria" in issue for issue in caught.exception.issues))

    def test_ground_truth_store_round_trips_separate_reference_data(self):
        annotation = self._annotation("A1", "reviewer-1", Classification.INDETERMINATE)
        record = GroundTruthRecord(
            self.expediente.expediente_id, self.catalog.criteria[0].criterion_id,
            self.catalog.catalog_id, self.catalog.normative_version, (annotation,))
        path = Path(self.temp.name) / "ground_truth.jsonl"
        store = GroundTruthStore(path)
        snapshot_id = store.save_snapshot(record)
        self.assertTrue(snapshot_id)
        self.assertEqual(store.read_all(), [record])
        with self.assertRaises(ValueError):
            store.save_snapshot(record)

    def test_old_synthetic_execution_record_without_new_optional_fields_is_readable(self):
        from evaluation.factory import synthetic_config
        from evaluation.runner import BenchmarkRunner
        from evaluation.store import LocalExecutionStore
        store = LocalExecutionStore(Path(self.temp.name) / "legacy.jsonl")
        record = BenchmarkRunner(store).run(self.expediente, synthetic_config())
        payload = to_primitive(record)
        payload.pop("experiment_id", None)
        for result in payload["results"]:
            for key in ("expediente_id", "catalog_id", "normative_version", "execution_id"):
                result.pop(key, None)
        for result in payload["verdict"]["criterion_results"]:
            for key in ("expediente_id", "catalog_id", "normative_version", "execution_id"):
                result.pop(key, None)
        envelope = {"record": payload, "integrity_sha256": sha256_json(payload)}
        store.path.write_text(canonical_json(envelope) + "\n", encoding="utf-8")
        self.assertEqual(store.read_all()[0].execution_id, record.execution_id)

    def test_invalid_label_and_duplicate_evaluator_are_rejected(self):
        with self.assertRaises(ValueError):
            self._annotation("A", "reviewer-1", "not-a-label")
        a1 = self._annotation("A1", "reviewer-1", Classification.CONFORMING)
        a2 = self._annotation("A2", "reviewer-1", Classification.CONFORMING)
        with self.assertRaises(ValueError):
            GroundTruthRecord(self.expediente.expediente_id, self.catalog.criteria[0].criterion_id,
                              self.catalog.catalog_id, self.catalog.normative_version, (a1, a2))

    def test_dataset_rejects_nonexistent_criterion_and_incompatible_version(self):
        applicability = ApplicabilityRecord(
            self.expediente.expediente_id, "DOES-NOT-EXIST", self.catalog.catalog_id, "OTHER-V",
            ApplicabilityStatus.APPLICABLE, "synthetic", ReviewStatus.PENDING)
        issues = validate_dataset(expedientes=(self.expediente,), catalogs=(self.catalog,),
                                  applicability=(applicability,))
        self.assertIn("UNKNOWN_OR_INCOMPATIBLE_CRITERION", {issue.code for issue in issues})

    def test_execution_times_and_replica_uniqueness(self):
        with self.assertRaises(ValueError):
            self.runner_record(started=NOW, finished=NOW.replace(year=2025))
        store = LocalExecutionStore(Path(self.temp.name) / "runs.jsonl")
        from evaluation.factory import synthetic_config
        runner = BenchmarkRunner(store)
        experiment_id = str(uuid4())
        first = runner.run(self.expediente, synthetic_config(), replica=1, experiment_id=experiment_id)
        new_execution_id = str(uuid4())
        new_results = tuple(replace(result, execution_id=new_execution_id) for result in first.results)
        duplicate = replace(first, execution_id=new_execution_id, results=new_results,
                            verdict=replace(first.verdict, criterion_results=new_results))
        with self.assertRaises(DuplicateExecutionError):
            store.save(duplicate)

    def runner_record(self, started, finished):
        from evaluation.factory import synthetic_config
        from evaluation.schemas import ExecutionRecord
        result = CriterionResult("C", EvaluationState.EVALUATED, Classification.INDETERMINATE, "synthetic")
        from evaluation.schemas import Verdict
        return ExecutionRecord("id", self.expediente.expediente_id, 1, synthetic_config(),
                               ExecutionStatus.SUCCESS, started, finished, 1, (result,),
                               Verdict(self.expediente.expediente_id, Classification.INDETERMINATE,
                                       "synthetic", (result,)))


if __name__ == "__main__":
    unittest.main()
