"""Adaptadores locales explícitamente permitidos por el benchmark."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .agent_input import AgentInput
from .normative_graph import GRAPH_VERSION, build_normative_graph
from .normative_evaluator import NormativeCriterionEvaluator
from .schemas import (Classification, CriterionResult, EffectiveMode,
                      EvaluationState, ExperimentConfig, Expediente, RunType,
                      Verdict)


@dataclass(frozen=True)
class AdapterOutput:
    results: tuple[CriterionResult, ...]
    verdict: Verdict
    warnings: tuple[dict[str, str], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


class AnalysisAdapter(Protocol):
    mode: EffectiveMode
    external_calls_enabled: bool
    business_writes_enabled: bool

    def analyze(self, expediente: Expediente, config: ExperimentConfig, *,
                execution_id: str) -> AdapterOutput: ...


class MockAnalysisAdapter:
    """Salida ficticia determinista; no es evaluación ni usa servicios."""
    mode = EffectiveMode.SYNTHETIC
    external_calls_enabled = False
    business_writes_enabled = False

    def __init__(self, fail_for_test: bool = False):
        self._fail_for_test = fail_for_test

    def analyze(self, expediente: Expediente, config: ExperimentConfig, *,
                execution_id: str) -> AdapterOutput:
        if self._fail_for_test:
            raise RuntimeError("synthetic adapter test failure")
        result = CriterionResult(
            criterion_id="SMOKE-TEST-001", evaluation_state=EvaluationState.EVALUATED,
            classification=Classification.INDETERMINATE,
            rationale="Resultado sintético de prueba técnica; no representa evaluación académica.",
            expediente_id=expediente.expediente_id, execution_id=execution_id)
        verdict = Verdict(expediente.expediente_id, Classification.INDETERMINATE,
                          "Dictamen ficticio para validar el registro técnico.", (result,))
        return AdapterOutput((result,), verdict,
                             metadata={"graph_version": None, "run_status": "mock_completed"})


class LocalNormativeGraphAdapter:
    """Puente local a LangGraph; requiere que la dependencia ya esté instalada."""
    mode = EffectiveMode.SYNTHETIC
    external_calls_enabled = False
    business_writes_enabled = False

    def __init__(self, request: AgentInput, document_root: str,
                 evaluator: NormativeCriterionEvaluator | None = None):
        if not isinstance(request, AgentInput):
            raise TypeError("request debe ser AgentInput validado")
        self._request = request
        self.macroproceso = request.macroproceso
        self._document_root = document_root
        if evaluator is not None and (
                getattr(evaluator, "external_calls_enabled", True) is not False
                or getattr(evaluator, "business_writes_enabled", True) is not False):
            raise ValueError("el evaluador inyectado debe ser local y sin escrituras")
        self._evaluator = evaluator
        self._graph = build_normative_graph(evaluator=evaluator)

    def analyze(self, expediente: Expediente, config: ExperimentConfig, *,
                execution_id: str) -> AdapterOutput:
        if expediente.expediente_id != self._request.expediente.expediente_id:
            raise ValueError("el AgentInput corresponde a otro expediente")
        if (config.run_type is not RunType.SYNTHETIC
                or config.effective_mode is not EffectiveMode.SYNTHETIC
                or config.external_calls_enabled or config.business_writes_enabled):
            raise ValueError("configuración no sintética")
        state = self._graph.invoke({
            "request": self._request, "document_root": self._document_root,
            "config": config, "execution_id": execution_id,
        })
        if state.get("status") != "completed_not_normatively_evaluated":
            codes = tuple(error.get("code", "UNKNOWN") for error in state.get("errors", ()))
            raise NormativeGraphRunError(codes or ("GRAPH_FAILED",))
        results = tuple(state.get("results", ()))
        verdict = state.get("verdict")
        if not results or verdict is None:
            raise NormativeGraphRunError(("INCOMPLETE_OUTPUT",))
        return AdapterOutput(results, verdict, metadata={
            "graph_version": GRAPH_VERSION, "run_status": state["status"],
            "catalog_id": state.get("catalog_id"),
            "normative_version": state.get("normative_version"),
            "document_sha256": state.get("metadata", {}).get("document_sha256", {}),
            "evaluator_mode": state.get("metadata", {}).get("evaluator_mode"),
            "criterion_evaluations": state.get("metadata", {}).get("criterion_evaluations", []),
            "evidence_warnings": state.get("metadata", {}).get("evidence_warnings", []),
        })


class NormativeGraphRunError(RuntimeError):
    def __init__(self, error_codes: tuple[str, ...]):
        self.error_codes = error_codes
        super().__init__("normative graph failed")


AUTHORIZED_ADAPTER_TYPES = (MockAnalysisAdapter, LocalNormativeGraphAdapter)
