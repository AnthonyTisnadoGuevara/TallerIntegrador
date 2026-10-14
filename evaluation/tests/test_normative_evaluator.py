from dataclasses import replace
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import tempfile
import unittest

from evaluation.adapters import LocalNormativeGraphAdapter
from evaluation.agent_input import build_agent_input
from evaluation.catalog import approve_catalog, load_catalog
from evaluation.contracts import ApplicabilityRecord, ReviewStatus
from evaluation.schemas import ApplicabilityStatus, DocumentReference, Expediente
from evaluation.factory import synthetic_config
from evaluation.normative_evaluator import (PROMPT_SHA256, InferenceFailure,
                                           PromptedNormativeEvaluator,
                                           ProviderResponse)
from evaluation.normative_graph import run_normative_pipeline
from evaluation.schemas import (Classification, EffectiveMode, EvaluationState,
                                Evidence)
from evaluation.store import LocalExecutionStore
from evaluation.runner import BenchmarkRunner
from evaluation.metrics.telemetry import analyze_telemetry


class LocalMockProvider:
    provider_name = "mock-local"
    model_name = "synthetic-model"
    model_version = "fixture-1"
    effective_mode = EffectiveMode.MOCK
    external_calls_enabled = False
    business_writes_enabled = False

    def __init__(self, response):
        self.response = response
        self.prompt = None

    def generate(self, prompt, config):
        self.prompt = prompt
        return self.response


class NormativeEvaluatorTests(unittest.TestCase):
    """Usa exclusivamente un catálogo y documento de prueba sintéticos."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        fixture = Path(__file__).parents[1] / "fixtures" / "synthetic_catalog.json"
        self.catalog = approve_catalog(load_catalog(fixture), validated_by="mock-reviewer",
                                       approval_reference="synthetic://approval",
                                       validated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.text = "Synthetic heading\nOnly local test evidence.\n"
        (self.root / "document.txt").write_bytes(self.text.encode("utf-8"))
        self.document = DocumentReference("SYNTH-DOC", "synthetic", "txt",
            hashlib.sha256(self.text.encode()).hexdigest(), "1", "document.txt")
        self.expediente = Expediente("SYNTH-CASE", "SYNTH-CORPUS", (self.document,), "1", "b" * 64)
        self.criterion = self.catalog.criteria[0]
        applicability = ApplicabilityRecord(self.expediente.expediente_id,
            self.criterion.criterion_id, self.catalog.catalog_id, self.catalog.normative_version,
            ApplicabilityStatus.APPLICABLE, "revisado para prueba sintética", ReviewStatus.REVIEWED)
        self.request = build_agent_input(self.expediente, self.catalog,
            (self.criterion.applicability_rule,), (applicability,))

    def tearDown(self):
        self.temp.cleanup()

    def mock_config(self):
        return replace(synthetic_config(), prompt_sha256=PROMPT_SHA256,
                      catalog_sha256=self.catalog.content_sha256,
                      provider="mock-local", model="synthetic-model",
                      model_version="fixture-1")

    def evaluator(self, provider):
        config = self.mock_config()
        return PromptedNormativeEvaluator(provider, catalog_sha256=config.catalog_sha256)

    def test_versioned_prompt_excludes_ground_truth_and_runner_records_mode(self):
        config = self.mock_config()
        provider = LocalMockProvider(ProviderResponse(
            EvaluationState.EVALUATED, Classification.CONFORMING,
            "Dictamen de fixture respaldado por el mock.",
            (Evidence(self.document.document_id, "documento", locator="line:2",
                      expediente_id=self.expediente.expediente_id),)))
        evaluator = self.evaluator(provider)
        state = run_normative_pipeline(self.request, self.root, config, evaluator=evaluator)
        self.assertEqual(state["status"], "completed_not_normatively_evaluated")
        self.assertNotIn("ground_truth", provider.prompt.lower())
        self.assertNotIn("reference_verdict", provider.prompt.lower())
        self.assertIn(self.text, provider.prompt)
        self.assertEqual(state["metadata"]["criterion_evaluations"][0]["prompt_sha256"], PROMPT_SHA256)

        with tempfile.TemporaryDirectory() as temp:
            adapter = LocalNormativeGraphAdapter(self.request, str(self.root), evaluator=evaluator)
            runner = BenchmarkRunner(LocalExecutionStore(Path(temp) / "runs.jsonl"), adapter)
            record = runner.run(self.expediente, config)
        self.assertEqual(record.status.value, "completado")
        self.assertEqual(record.telemetry["criterion_evaluations"][0]["effective_mode"], "simulado")
        self.assertEqual(record.telemetry["criterion_evaluations"][0]["model"], "synthetic-model")
        summary, details = analyze_telemetry([record])
        self.assertEqual(summary["observed_inference_modes"], ["simulado"])
        self.assertEqual(details[0]["models"], ["synthetic-model"])

    def test_nonconformity_requires_a_located_evidence_reference(self):
        config = self.mock_config()
        response = ProviderResponse(
            EvaluationState.EVALUATED, Classification.NON_CONFORMING,
            "Posible incumplimiento del fixture.",
            (Evidence(self.document.document_id, "documento", locator="line:2",
                      expediente_id=self.expediente.expediente_id),))
        state = run_normative_pipeline(
            self.request, self.root, config,
            evaluator=self.evaluator(LocalMockProvider(response)))
        self.assertEqual(state["results"][0].classification, Classification.NON_CONFORMING)
        self.assertEqual(state["results"][0].evidence[0].location_status, "localizado")

        unsupported = replace(response, evidence=(replace(response.evidence[0], locator="line:99"),))
        state = run_normative_pipeline(
            self.request, self.root, config,
            evaluator=self.evaluator(LocalMockProvider(unsupported)))
        self.assertEqual(state["results"][0].evaluation_state, EvaluationState.NOT_EVALUABLE)
        self.assertEqual(state["results"][0].classification, Classification.INDETERMINATE)

    def test_missing_evidence_and_provider_error_never_become_normative_fallback(self):
        config = self.mock_config()
        no_evidence = ProviderResponse(EvaluationState.EVALUATED,
                                       Classification.NON_CONFORMING,
                                       "No hay evidencia localizada.")
        state = run_normative_pipeline(
            self.request, self.root, config,
            evaluator=self.evaluator(LocalMockProvider(no_evidence)))
        self.assertEqual(state["results"][0].evaluation_state, EvaluationState.NOT_EVALUABLE)
        self.assertEqual(state["results"][0].classification, Classification.INDETERMINATE)

        class FailingProvider(LocalMockProvider):
            def generate(self, prompt, config):
                raise TimeoutError("fixture only")

        evaluator = self.evaluator(FailingProvider(no_evidence))
        with self.assertRaises(InferenceFailure):
            run_normative_pipeline(self.request, self.root, config, evaluator=evaluator)
        with tempfile.TemporaryDirectory() as temp:
            adapter = LocalNormativeGraphAdapter(self.request, str(self.root), evaluator=evaluator)
            runner = BenchmarkRunner(LocalExecutionStore(Path(temp) / "runs.jsonl"), adapter)
            record = runner.run(self.expediente, config)
        self.assertEqual(record.error_category.value, "proveedor_llm")
        self.assertEqual(record.telemetry["provider_mode_attempted"], "simulado")
        self.assertEqual(record.telemetry["inference_status"], "failed_no_fallback")
        self.assertEqual(record.telemetry["error_codes"], ["INFERENCE_PROVIDER_FAILURE"])

    def test_injected_provider_with_external_calls_is_rejected(self):
        provider = LocalMockProvider(ProviderResponse(
            EvaluationState.NOT_EVALUABLE, Classification.INDETERMINATE, "abstención"))
        provider.external_calls_enabled = True
        with self.assertRaises(ValueError):
            PromptedNormativeEvaluator(provider, catalog_sha256=self.catalog.content_sha256)

    def test_unapproved_applicability_rule_does_not_reach_provider(self):
        config = self.mock_config()
        provider = LocalMockProvider(ProviderResponse(
            EvaluationState.EVALUATED, Classification.CONFORMING,
            "No debería ser invocado."))
        request = build_agent_input(self.expediente, self.catalog,
                                    ("regla distinta no autorizada",),
                                    self.request.applicability_records)
        state = run_normative_pipeline(request, self.root, config,
                                       evaluator=self.evaluator(provider))
        self.assertIsNone(provider.prompt)
        self.assertEqual(state["results"][0].evaluation_state, EvaluationState.NOT_EVALUABLE)


if __name__ == "__main__":
    unittest.main()
