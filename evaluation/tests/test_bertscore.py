from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from evaluation.metrics.semantic import (BertScoreLocal, SemanticDependencyError,
                                         build_semantic_pairs, cosine_similarity,
                                         score_semantic_pairs)
from evaluation.metrics.common import select_primary_runs
from evaluation.schemas import EvaluationState
from metric_helpers import make_execution, make_ground_truth, make_result, setup_case


class FakeBertScore:
    metadata = {"metric": "test-double-not-real-bertscore", "mode": "synthetic_test"}
    def score_pair(self, candidate, reference):
        return {"precision": .8, "recall": .6, "f1": .6857142857,
                "candidate_truncated": False, "reference_truncated": False}


class FakeEmbedder:
    metadata = {"model_name": "fixed-vector-test-double", "mode": "synthetic_test"}
    def embed_pair(self, candidate, reference):
        return [1.0, 0.0], [0.0, 1.0]


class _ScoreScalar:
    def __init__(self, value):
        self.value = value

    def item(self):
        return self.value


class BertScoreInstrumentTests(unittest.TestCase):
    def setUp(self):
        self.expediente, self.catalog, self.config = setup_case()

    def test_cosine_formula_known_vectors_and_invalid_inputs(self):
        self.assertEqual(cosine_similarity([1, 0], [1, 0]), 1)
        self.assertEqual(cosine_similarity([1, 0], [0, 1]), 0)
        with self.assertRaises(ValueError):
            cosine_similarity([1], [1, 2])
        with self.assertRaises(ValueError):
            cosine_similarity([0, 0], [1, 2])

    def test_bertscore_nested_return_shape_is_unpacked(self):
        provider = BertScoreLocal.__new__(BertScoreLocal)
        provider.model_dir = "synthetic-local-model-path"
        provider._tokenizer = type("Tokenizer", (), {
            "encode": lambda self, text, add_special_tokens=False: ["token"]
        })()
        provider._score = lambda *args, **kwargs: (
            ([_ScoreScalar(.91)], [_ScoreScalar(.82)], [_ScoreScalar(.86)]), "setting-hash")

        values = provider.score_pair("texto candidato", "texto referencia")

        self.assertEqual(values["precision"], .91)
        self.assertEqual(values["recall"], .82)
        self.assertEqual(values["f1"], .86)
        self.assertFalse(values["candidate_truncated"])
        self.assertFalse(values["reference_truncated"])

    def test_only_validated_applicable_matching_criterion_pairs_are_built(self):
        gt = make_ground_truth(self.expediente, self.catalog)
        result = make_result(self.expediente, self.catalog, self.config, "x",
                             state=EvaluationState.EVALUATED)
        run = make_execution(self.expediente, self.catalog, self.config, results=(result,))
        pairs, exclusions = build_semantic_pairs((gt,), select_primary_runs((run,)))
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].criterion_id, gt.criterion_id)
        self.assertEqual(pairs[0].reference, gt.reference_verdict)
        self.assertEqual(exclusions, [])

    def test_version_mismatch_and_non_evaluable_output_are_excluded(self):
        gt = make_ground_truth(self.expediente, self.catalog)
        result = make_result(self.expediente, self.catalog, self.config, "x",
                             state=EvaluationState.NOT_EVALUABLE)
        run = make_execution(self.expediente, self.catalog, self.config, results=(result,))
        pairs, exclusions = build_semantic_pairs((gt,), select_primary_runs((run,)))
        self.assertEqual(pairs, [])
        self.assertIn("prediction_not_evaluated:no_evaluable", exclusions[0]["reason"])
        wrong_id = str(uuid4())
        wrong_version = replace(result, normative_version="OTHER", execution_id=wrong_id)
        run = make_execution(self.expediente, self.catalog, self.config, results=(wrong_version,),
                             execution_id=wrong_id, bind_result_links=False)
        pairs, exclusions = build_semantic_pairs((gt,), select_primary_runs((run,)))
        self.assertEqual(pairs, [])
        self.assertEqual(exclusions[0]["reason"], "criterion_or_version_not_matched")

    def test_provider_interfaces_and_statistics_are_test_doubles_only(self):
        gt = make_ground_truth(self.expediente, self.catalog)
        result = make_result(self.expediente, self.catalog, self.config, "x",
                             state=EvaluationState.EVALUATED)
        run = make_execution(self.expediente, self.catalog, self.config, results=(result,))
        pairs, _ = build_semantic_pairs((gt,), select_primary_runs((run,)))
        rows, summary = score_semantic_pairs(pairs, FakeBertScore(), FakeEmbedder())
        self.assertEqual(rows[0]["bertscore_f1"], .6857142857)
        self.assertEqual(rows[0]["cosine_similarity"], 0)
        self.assertEqual(summary["bertscore_f1"]["n"], 1)
        self.assertEqual(summary["cosine_similarity"]["n"], 1)
        self.assertEqual(FakeBertScore.metadata["mode"], "synthetic_test")

    def test_metric_failures_are_reported_independently(self):
        class BrokenBert(FakeBertScore):
            def score_pair(self, candidate, reference):
                raise RuntimeError("synthetic failure")
        gt = make_ground_truth(self.expediente, self.catalog)
        result = make_result(self.expediente, self.catalog, self.config, "x",
                             state=EvaluationState.EVALUATED)
        run = make_execution(self.expediente, self.catalog, self.config, results=(result,))
        pairs, _ = build_semantic_pairs((gt,), select_primary_runs((run,)))
        rows, summary = score_semantic_pairs(pairs, BrokenBert(), FakeEmbedder())
        self.assertIsNone(rows[0]["bertscore_f1"])
        self.assertEqual(rows[0]["cosine_similarity"], 0)
        self.assertEqual(rows[0]["status"], "partially_calculable")
        self.assertEqual(summary["not_calculable_pairs"], 0)

    def test_real_inference_fails_closed_without_local_dependencies_or_weights(self):
        with self.assertRaises(SemanticDependencyError):
            BertScoreLocal("Z:\\not-a-real-model", "declared-test-revision")
        with tempfile.TemporaryDirectory() as model_dir:
            with patch("evaluation.metrics.semantic.importlib.util.find_spec", return_value=None):
                with self.assertRaisesRegex(SemanticDependencyError, "faltan dependencias"):
                    BertScoreLocal(model_dir, "1" * 40)


if __name__ == "__main__":
    unittest.main()
