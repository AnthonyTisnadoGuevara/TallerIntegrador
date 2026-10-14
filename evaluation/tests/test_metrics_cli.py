import json
from pathlib import Path
import tempfile
import unittest

from evaluation.ground_truth_store import GroundTruthStore
from evaluation.schemas import EvaluationState
from evaluation.scripts import (eval_bertscore, eval_coverage, eval_precision_f1,
                                eval_stability, eval_telemetry)
from evaluation.store import LocalExecutionStore
from metric_helpers import make_execution, make_ground_truth, make_result, setup_case


class MetricsCliTests(unittest.TestCase):
    def test_all_five_clis_export_synthetic_or_explicitly_blocked_reports(self):
        expediente, catalog, config = setup_case()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runs_path = root / "runs.jsonl"
            gt_path = root / "ground_truth.jsonl"
            store = LocalExecutionStore(runs_path)
            for replica in range(1, 6):
                result = make_result(expediente, catalog, config, "pending",
                                     state=EvaluationState.EVALUATED)
                run = make_execution(expediente, catalog, config, replica=replica,
                                     results=(result,), experiment_id="SYNTH-CLI-EXP")
                store.save(run)
            GroundTruthStore(gt_path).save_snapshot(make_ground_truth(expediente, catalog))
            catalog_path = Path(__file__).parents[1] / "fixtures" / "synthetic_catalog.json"

            base = ["--results", str(runs_path), "--ground-truth", str(gt_path),
                    "--catalog", str(catalog_path), "--experiment-id", "SYNTH-CLI-EXP"]
            common_output = ["--output-dir", str(root / "reports")]
            self.assertEqual(eval_precision_f1.main(base + common_output), 0)
            self.assertEqual(eval_coverage.main(base + common_output), 0)
            self.assertEqual(eval_telemetry.main(["--results", str(runs_path),
                                                  "--experiment-id", "SYNTH-CLI-EXP",
                                                  *common_output]), 0)
            self.assertEqual(eval_bertscore.main(base + ["--response-kind", "criterion_verdict"] + common_output), 2)
            self.assertEqual(eval_stability.main(["--results", str(runs_path),
                                                  "--catalog", str(catalog_path),
                                                  "--experiment-id", "SYNTH-CLI-EXP",
                                                  *common_output]), 2)

            reports = list((root / "reports").iterdir())
            self.assertEqual(len(reports), 5)
            summaries = {path.name.split("_")[0]: json.loads(
                (path / "summary.json").read_text(encoding="utf-8")) for path in reports}
            self.assertEqual(summaries["eval"]["dataset_label"], "synthetic_test")
            blocked = [json.loads((path / "summary.json").read_text(encoding="utf-8"))
                       for path in reports if json.loads((path / "summary.json").read_text(
                           encoding="utf-8"))["status"] in ("blocked_dependency", "semantic_dependency_blocked")]
            self.assertEqual(len(blocked), 2)
            stability = next(item for item in blocked if item["instrument"] == "eval_stability")
            self.assertEqual(stability["pair_slots_total"], 10)
            semantic = next(item for item in blocked if item["instrument"] == "eval_bertscore")
            self.assertEqual(semantic["bertscore_f1"], None)
            self.assertIn("requiere --bert-model-dir", semantic["dependency_status"])


if __name__ == "__main__":
    unittest.main()
