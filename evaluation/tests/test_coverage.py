from dataclasses import replace
import unittest

from evaluation.metrics.coverage import calculate_coverage
from evaluation.metrics.common import select_primary_runs
from evaluation.schemas import (ApplicabilityStatus, Classification, EvaluationState,
                                ExecutionStatus)
from metric_helpers import make_execution, make_ground_truth, make_result, setup_case


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.expediente, self.catalog, self.config = setup_case()

    def test_explicit_evaluated_result_counts_as_coverage(self):
        gt = make_ground_truth(self.expediente, self.catalog)
        result = make_result(self.expediente, self.catalog, self.config, "x",
                             state=EvaluationState.EVALUATED)
        run = make_execution(self.expediente, self.catalog, self.config, results=(result,))
        summary, rows = calculate_coverage(self.catalog, (gt,), select_primary_runs((run,)))
        self.assertEqual(summary["total_applicable"], 1)
        self.assertEqual(summary["explicitly_evaluated"], 1)
        self.assertEqual(summary["coverage_percent"], 100.0)
        self.assertTrue(rows[0]["coverage_counted"])

    def test_not_evaluable_and_skipped_do_not_count(self):
        gt = make_ground_truth(self.expediente, self.catalog)
        for state, key in ((EvaluationState.NOT_EVALUABLE, "not_evaluable"),
                           (EvaluationState.SKIPPED, "omitted")):
            result = make_result(self.expediente, self.catalog, self.config, "x", state=state)
            run = make_execution(self.expediente, self.catalog, self.config, results=(result,))
            summary, _ = calculate_coverage(self.catalog, (gt,), select_primary_runs((run,)))
            self.assertEqual(summary[key], 1)
            self.assertEqual(summary["explicitly_evaluated"], 0)
            self.assertEqual(summary["coverage_percent"], 0)

    def test_nonapplicable_and_undetermined_are_separate_and_not_denominator(self):
        second = replace(self.expediente, expediente_id="SYNTH-CASE-2")
        third = replace(self.expediente, expediente_id="SYNTH-CASE-3")
        refs = (
            make_ground_truth(self.expediente, self.catalog,
                              applicability=ApplicabilityStatus.NOT_APPLICABLE),
            make_ground_truth(second, self.catalog,
                              applicability=ApplicabilityStatus.UNDETERMINED,
                              label=Classification.INDETERMINATE),
        )
        runs = (make_execution(self.expediente, self.catalog, self.config),
                make_execution(second, self.catalog, self.config),
                make_execution(third, self.catalog, self.config))
        summary, rows = calculate_coverage(self.catalog, refs, select_primary_runs(runs))
        self.assertEqual(summary["documented_not_applicable"], 1)
        self.assertEqual(summary["applicability_undetermined"], 1)
        self.assertEqual(summary["insufficient_or_unvalidated_records"], 1)
        self.assertEqual(summary["total_applicable"], 0)
        self.assertIsNone(summary["coverage_percent"])
        self.assertEqual(len(rows), 3)

    def test_no_denominator_is_null_and_explained(self):
        gt = make_ground_truth(self.expediente, self.catalog,
                               applicability=ApplicabilityStatus.NOT_APPLICABLE)
        run = make_execution(self.expediente, self.catalog, self.config)
        summary, _ = calculate_coverage(self.catalog, (gt,), select_primary_runs((run,)))
        self.assertIsNone(summary["coverage_percent"])
        self.assertIn("no validated applicable", summary["undefined_reason"])

    def test_failure_and_omitted_output_are_reported(self):
        gt = make_ground_truth(self.expediente, self.catalog)
        failed = make_execution(self.expediente, self.catalog, self.config,
                                status=ExecutionStatus.ERROR)
        summary, rows = calculate_coverage(self.catalog, (gt,), select_primary_runs((failed,)))
        self.assertEqual(summary["technical_errors"], 1)
        self.assertEqual(rows[0]["reason"], "execution_error:inesperado")
        other_result = make_result(self.expediente, self.catalog, self.config, "x", "OTHER")
        run = make_execution(self.expediente, self.catalog, self.config, results=(other_result,))
        summary, rows = calculate_coverage(self.catalog, (gt,), select_primary_runs((run,)))
        self.assertEqual(summary["omitted"], 1)
        self.assertEqual(rows[0]["reason"], "criterion_omitted_from_output")

    def test_analysis_record_without_required_links_is_not_counted(self):
        gt = make_ground_truth(self.expediente, self.catalog)
        linked = make_result(self.expediente, self.catalog, self.config, "x")
        unlinked = replace(linked, expediente_id=None, execution_id=None)
        run = make_execution(self.expediente, self.catalog, self.config, results=(unlinked,),
                             bind_result_links=False)
        summary, rows = calculate_coverage(self.catalog, (gt,), select_primary_runs((run,)))
        self.assertEqual(summary["insufficient_or_unvalidated_records"], 1)
        self.assertFalse(rows[0]["coverage_counted"])


if __name__ == "__main__":
    unittest.main()
