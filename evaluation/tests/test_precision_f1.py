from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from evaluation.metrics.classification import calculate_precision_f1
from evaluation.metrics.common import (MetricInputError, enforce_mode,
                                       select_primary_runs, validate_catalog_links,
                                       write_report)
from evaluation.ground_truth import GroundTruthStatus
from evaluation.schemas import (ApplicabilityStatus, Classification, EvaluationState,
                                ExecutionStatus)
from metric_helpers import (make_execution, make_ground_truth, make_result, setup_case)


class PrecisionF1Tests(unittest.TestCase):
    def setUp(self):
        self.expediente, self.catalog, self.config = setup_case()

    def test_known_confusion_matrix_precision_recall_f1(self):
        refs = [make_ground_truth(self.expediente, self.catalog, f"C{i}", label)
                for i, label in enumerate((Classification.NON_CONFORMING,
                                           Classification.NON_CONFORMING,
                                           Classification.CONFORMING,
                                           Classification.CONFORMING), 1)]
        results = [make_result(self.expediente, self.catalog, self.config, "x", f"C{i}", pred)
                   for i, pred in enumerate((Classification.NON_CONFORMING,
                                             Classification.CONFORMING,
                                             Classification.NON_CONFORMING,
                                             Classification.CONFORMING), 1)]
        execution = make_execution(self.expediente, self.catalog, self.config, results=results)
        summary, rows = calculate_precision_f1(refs, select_primary_runs([execution]))
        self.assertEqual(summary["confusion_matrix"], {
            "positive": "no_conforme", "negative": "conforme", "tp": 1, "fp": 1, "tn": 1, "fn": 1})
        self.assertEqual(summary["precision"], .5)
        self.assertEqual(summary["recall"], .5)
        self.assertEqual(summary["f1"], .5)
        self.assertEqual(len(rows), 4)

    def test_missing_and_non_evaluable_predictions_are_counted_as_abstentions(self):
        refs = [make_ground_truth(self.expediente, self.catalog, f"C{i}") for i in range(1, 3)]
        result = make_result(self.expediente, self.catalog, self.config, "x", "C1",
                             state=EvaluationState.NOT_EVALUABLE)
        execution = make_execution(self.expediente, self.catalog, self.config, results=(result,))
        summary, _ = calculate_precision_f1(refs, select_primary_runs([execution]))
        self.assertEqual(summary["abstentions"], 2)
        self.assertEqual(summary["abstention_rate"], 1.0)
        self.assertEqual(summary["evaluated_cases"], 0)
        self.assertIsNone(summary["precision"])

    def test_zero_denominators_are_null_not_zero(self):
        refs = [make_ground_truth(self.expediente, self.catalog, "C1", Classification.CONFORMING)]
        result = make_result(self.expediente, self.catalog, self.config, "x", "C1",
                             Classification.CONFORMING)
        execution = make_execution(self.expediente, self.catalog, self.config, results=(result,))
        summary, _ = calculate_precision_f1(refs, select_primary_runs([execution]))
        self.assertIsNone(summary["precision"])
        self.assertIsNone(summary["recall"])
        self.assertIsNone(summary["f1"])
        self.assertEqual(summary["confusion_matrix"]["tn"], 1)

    def test_unvalidated_and_nonapplicable_references_are_excluded_explicitly(self):
        unvalidated = make_ground_truth(self.expediente, self.catalog, "C1",
                                        status=GroundTruthStatus.DRAFT)
        not_applicable = make_ground_truth(self.expediente, self.catalog, "C2",
                                          applicability=ApplicabilityStatus.NOT_APPLICABLE)
        execution = make_execution(self.expediente, self.catalog, self.config)
        summary, rows = calculate_precision_f1((unvalidated, not_applicable), select_primary_runs([execution]))
        self.assertEqual(summary["eligible_reference_cases"], 0)
        self.assertIn("reference_not_applicable", {entry["reason"] for entry in summary["excluded_cases"]})
        self.assertIn("reference_status:borrador", {entry["reason"] for entry in summary["excluded_cases"]})
        self.assertEqual(len(rows), 1)

    def test_duplicate_ground_truth_and_incompatible_version_rejected(self):
        gt = make_ground_truth(self.expediente, self.catalog)
        with self.assertRaises(MetricInputError):
            calculate_precision_f1((gt, gt), select_primary_runs([
                make_execution(self.expediente, self.catalog, self.config)]))
        changed_annotations = tuple(replace(a, normative_version="OTHER") for a in gt.annotations)
        incompatible = replace(gt, normative_version="OTHER", annotations=changed_annotations)
        with self.assertRaises(MetricInputError):
            validate_catalog_links(self.catalog, (incompatible,), ())

    def test_failed_execution_is_retained_as_abstention(self):
        gt = make_ground_truth(self.expediente, self.catalog)
        failed = make_execution(self.expediente, self.catalog, self.config,
                                status=ExecutionStatus.ERROR)
        summary, _ = calculate_precision_f1((gt,), select_primary_runs([failed]))
        self.assertEqual(summary["abstentions"], 1)
        self.assertEqual(summary["selected_execution_failures"], 1)
        self.assertIn("execution_failed", summary["excluded_cases"][0]["reason"])

    def test_selection_requires_one_experiment_or_explicit_choice(self):
        first = make_execution(self.expediente, self.catalog, self.config, experiment_id="E1")
        second = make_execution(self.expediente, self.catalog, self.config, experiment_id="E2")
        with self.assertRaises(MetricInputError):
            select_primary_runs((first, second))
        selection = select_primary_runs((first, second), "E1")
        self.assertEqual(selection.selected_by_expediente[self.expediente.expediente_id], first)
        self.assertEqual(len(selection.exclusions), 1)

    def test_authorized_mode_requires_explicit_reference(self):
        with self.assertRaises(MetricInputError):
            enforce_mode("authorized", ())
        enforce_mode("authorized", (), authorization_ref="synthetic approval ref")

    def test_export_never_overwrites_previous_report(self):
        with tempfile.TemporaryDirectory() as root:
            first = write_report(root, "test_metric", {"mode": "synthetic_test"},
                                 [{"id": "SYNTH-1", "score": .75}], ("id", "score"))
            second = write_report(root, "test_metric", {"mode": "synthetic_test"},
                                  [{"id": "SYNTH-2", "score": .5}], ("id", "score"))
            self.assertNotEqual(first, second)
            self.assertTrue((first / "summary.json").is_file())
            self.assertTrue((second / "details.csv").is_file())


if __name__ == "__main__":
    unittest.main()
