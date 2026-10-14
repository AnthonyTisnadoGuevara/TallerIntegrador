import csv
import json
from pathlib import Path
import tempfile
import unittest

from evaluation.metrics.common import summarize_numbers, write_report
from evaluation.metrics.telemetry import analyze_telemetry
from evaluation.schemas import ExecutionStatus
from metric_helpers import make_execution, setup_case


class TelemetryTests(unittest.TestCase):
    def setUp(self):
        self.expediente, self.catalog, self.config = setup_case()

    def test_percentiles_and_sample_statistics_use_documented_linear_method(self):
        summary = summarize_numbers([1, 2, 3, 4, 5])
        self.assertEqual(summary["mean"], 3)
        self.assertEqual(summary["median"], 3)
        self.assertAlmostEqual(summary["sample_stdev"], 1.5811388300841898)
        self.assertAlmostEqual(summary["p90_linear"], 4.6)
        self.assertAlmostEqual(summary["p95_linear"], 4.8)
        self.assertIsNone(summarize_numbers([])["p90_linear"])
        self.assertIsNone(summarize_numbers([4])["sample_stdev"])

    def test_nanoseconds_convert_to_seconds_and_failures_are_retained(self):
        ok = make_execution(self.expediente, self.catalog, self.config, duration_ns=2_500_000_000)
        failed = make_execution(self.expediente, self.catalog, self.config, replica=2,
                                status=ExecutionStatus.ERROR, duration_ns=500_000_000)
        summary, rows = analyze_telemetry((ok, failed))
        self.assertEqual(rows[0]["duration_seconds"], "2.500000000")
        self.assertEqual(rows[1]["duration_seconds"], "0.500000000")
        self.assertEqual(summary["loaded_executions"], 2)
        self.assertEqual(summary["completed_executions"], 1)
        self.assertEqual(summary["error_executions"], 1)
        self.assertEqual(summary["latency_seconds_successful"]["mean"], 2.5)
        self.assertEqual(summary["latency_seconds_failed"]["mean"], .5)
        self.assertIn("error", rows[1]["status"])

    def test_uninstrumented_telemetry_is_absent_not_zero(self):
        run = make_execution(self.expediente, self.catalog, self.config)
        summary, rows = analyze_telemetry((run,))
        self.assertEqual(summary["telemetry_availability"]["memory_bytes"]["absent"], 1)
        self.assertEqual(rows[0]["telemetry_fields"]["memory_bytes"], None)
        self.assertEqual(rows[0]["telemetry_field_status"]["memory_bytes"], "not_available")
        self.assertIn("JSONL persistence excluded", summary["duration_scope"])

    def test_telemetry_report_exports_json_and_csv(self):
        run = make_execution(self.expediente, self.catalog, self.config)
        summary, rows = analyze_telemetry((run,))
        columns = ("execution_id", "duration_ns", "duration_seconds")
        with tempfile.TemporaryDirectory() as root:
            directory = write_report(root, "telemetry_test", summary, rows, columns)
            metadata = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
            with (directory / "details.csv").open(encoding="utf-8-sig", newline="") as stream:
                exported = list(csv.DictReader(stream))
            self.assertEqual(metadata["loaded_executions"], 1)
            self.assertEqual(exported[0]["execution_id"], run.execution_id)
            self.assertEqual(exported[0]["duration_ns"], str(run.duration_ns))


if __name__ == "__main__":
    unittest.main()
