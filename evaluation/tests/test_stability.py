from dataclasses import replace
import unittest

from evaluation.metrics.stability import analyze_stability
from evaluation.schemas import (Classification, EffectiveMode, ExecutionStatus)
from metric_helpers import make_execution, make_result, setup_case


class FixedEmbeddingProvider:
    metadata = {"model_name": "fixed-vector-test-double", "mode": "synthetic_test"}
    def embed_pair(self, candidate, reference):
        return [1, 0], [1, 0]


class StabilityTests(unittest.TestCase):
    def setUp(self):
        self.expediente, self.catalog, self.config = setup_case()

    def _five_runs(self, labels=None):
        labels = labels or [Classification.NON_CONFORMING] * 5
        records = []
        for replica, label in enumerate(labels, 1):
            result = make_result(self.expediente, self.catalog, self.config, "x",
                                 classification=label)
            records.append(make_execution(self.expediente, self.catalog, self.config,
                                          replica=replica, results=(result,)))
        return records

    def test_five_replicas_produce_ten_pairs_and_label_agreement(self):
        runs = self._five_runs([Classification.NON_CONFORMING] * 4 + [Classification.CONFORMING])
        summary, pairs = analyze_stability(runs, self.catalog.normative_version,
                                           FixedEmbeddingProvider())
        group = summary["groups"][0]
        self.assertEqual(len(pairs), 10)
        self.assertEqual(summary["pair_slots_total"], 10)
        self.assertTrue(group["controlled_group"])
        self.assertEqual(group["execution_ids_by_replica"]["5"], [runs[4].execution_id])
        self.assertAlmostEqual(group["mean_pair_label_agreement"], .6)
        self.assertEqual(group["semantic_cosine"]["n"], 10)
        self.assertEqual(group["semantic_cosine"]["mean"], 1)

    def test_missing_or_failed_replica_remains_reported_and_group_incomplete(self):
        runs = self._five_runs()
        runs[2] = make_execution(self.expediente, self.catalog, self.config,
                                 replica=3, status=ExecutionStatus.ERROR)
        summary, pairs = analyze_stability(runs, self.catalog.normative_version)
        group = summary["groups"][0]
        self.assertFalse(group["controlled_group"])
        self.assertEqual(group["failed_runs"], 1)
        self.assertEqual(len(pairs), 10)
        failed_pairs = [row for row in pairs if 3 in (row["replica_left"], row["replica_right"])]
        self.assertEqual(len(failed_pairs), 4)
        self.assertTrue(all(row["semantic_status"] == "not_calculable_failed_run" for row in failed_pairs))

    def test_duplicate_replica_and_distinct_configurations_are_not_mixed(self):
        runs = self._five_runs()
        duplicate = make_execution(self.expediente, self.catalog, self.config,
                                   replica=1, results=runs[0].results)
        summary, pairs = analyze_stability([*runs, duplicate], self.catalog.normative_version)
        self.assertEqual(summary["groups"][0]["duplicate_replicas"], [1])
        self.assertFalse(summary["groups"][0]["controlled_group"])

        other_config = replace(self.config, temperature=0.2, seed=4, generation_null_reason=None)
        variant = make_execution(self.expediente, self.catalog, other_config,
                                 replica=2, results=runs[1].results)
        summary, pairs = analyze_stability([runs[0], variant, *runs[2:]], self.catalog.normative_version)
        self.assertEqual(summary["groups"][0]["condition_variants"], 2)
        self.assertFalse(summary["groups"][0]["controlled_group"])
        self.assertTrue(all(row["status"] == "incompatible_conditions" for row in pairs))

    def test_missing_replica_produces_ten_slots_with_missing_pair_statuses(self):
        runs = self._five_runs()[:4]
        summary, pairs = analyze_stability(runs, self.catalog.normative_version,
                                           semantic_block_reason="model_not_installed")
        self.assertEqual(summary["groups"][0]["missing_replicas"], [5])
        self.assertEqual(len(pairs), 10)
        missing = [row for row in pairs if 5 in (row["replica_left"], row["replica_right"])]
        self.assertEqual(len(missing), 4)
        self.assertTrue(all(row["status"] == "missing_or_duplicate_replica" for row in missing))
        self.assertEqual(summary["semantic_block_reason"], "model_not_installed")

    def test_modes_are_part_of_full_config_signature(self):
        runs = self._five_runs()
        simulated = replace(self.config, effective_mode=EffectiveMode.MOCK)
        variant = make_execution(self.expediente, self.catalog, simulated,
                                 replica=2, results=runs[1].results)
        summary, _ = analyze_stability([runs[0], variant, *runs[2:]], self.catalog.normative_version)
        self.assertEqual(summary["groups"][0]["condition_variants"], 2)
        self.assertFalse(summary["groups"][0]["controlled_group"])


if __name__ == "__main__":
    unittest.main()
