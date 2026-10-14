"""Runner de ejecuciones experimentales locales y sintéticas."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import platform
import time
from uuid import uuid4

from .adapters import (AUTHORIZED_ADAPTER_TYPES, AdapterOutput, AnalysisAdapter,
                       LocalNormativeGraphAdapter, MockAnalysisAdapter)
from .schemas import (EffectiveMode, ErrorCategory, ExecutionRecord,
                      ExecutionStatus, Expediente, ExperimentConfig, Macroprocess, RunType)
from .store import LocalExecutionStore


class UnsafeAdapterError(RuntimeError):
    pass


class BenchmarkRunner:
    def __init__(self, store: LocalExecutionStore, adapter: AnalysisAdapter | None = None):
        self.store = store
        self.adapter = adapter if adapter is not None else MockAnalysisAdapter()

    def _check_safety(self, config: ExperimentConfig) -> None:
        if (config.external_calls_enabled or config.business_writes_enabled
                or config.run_type is not RunType.SYNTHETIC
                or config.effective_mode is not EffectiveMode.SYNTHETIC):
            raise UnsafeAdapterError("solo se admite configuración sintética/local sin escrituras")
        if type(self.adapter) not in AUTHORIZED_ADAPTER_TYPES:
            raise UnsafeAdapterError("adaptador no incluido en la allowlist local explícita")
        if (getattr(self.adapter, "mode", None) is not EffectiveMode.SYNTHETIC
                or getattr(self.adapter, "external_calls_enabled", True) is not False
                or getattr(self.adapter, "business_writes_enabled", True) is not False):
            raise UnsafeAdapterError("adaptador no declara capacidades sintéticas seguras")

    def run(self, expediente: Expediente, config: ExperimentConfig, replica: int = 1,
            experiment_id: str | None = None,
            macroproceso: Macroprocess | None = None) -> ExecutionRecord:
        self._check_safety(config)
        if macroproceso is None and len(expediente.macroprocesos) == 1:
            macroproceso = expediente.macroprocesos[0]
        if macroproceso is None and len(expediente.macroprocesos) > 1:
            raise ValueError("debe indicar macroproceso cuando el expediente pertenece a varios")
        if macroproceso is not None and macroproceso not in expediente.macroprocesos:
            raise ValueError("macroproceso no asociado al expediente")
        adapter_process = getattr(self.adapter, "macroproceso", macroproceso)
        if adapter_process != macroproceso:
            raise ValueError("AgentInput y ejecución deben usar el mismo macroproceso")
        started = datetime.now(timezone.utc)
        monotonic_start = time.perf_counter_ns()
        execution_id = str(uuid4())
        experiment_id = experiment_id or str(uuid4())
        try:
            output = self.adapter.analyze(expediente, config, execution_id=execution_id)
            if not output.results or output.verdict.expediente_id != expediente.expediente_id:
                raise ValueError("salida incompleta o ligada a otro expediente")
            bound_results = tuple(replace(
                item, expediente_id=item.expediente_id or expediente.expediente_id,
                execution_id=item.execution_id or execution_id,
                macroproceso=item.macroproceso or macroproceso) for item in output.results)
            if any(item.expediente_id != expediente.expediente_id
                   or item.execution_id != execution_id
                   or item.macroproceso not in (None, macroproceso) for item in bound_results):
                raise ValueError("resultado ligado a expediente o ejecución incorrectos")
            if any(item.execution_id not in (None, execution_id)
                   for item in output.verdict.criterion_results):
                raise ValueError("dictamen ligado a otra ejecución")
            bound_verdict = replace(output.verdict, criterion_results=bound_results)
            record = ExecutionRecord(
                execution_id, expediente.expediente_id, replica, config,
                ExecutionStatus.SUCCESS, started, datetime.now(timezone.utc),
                time.perf_counter_ns() - monotonic_start, bound_results, bound_verdict,
                telemetry={"python_version": platform.python_version(),
                           "adapter": type(self.adapter).__name__,
                           "effective_mode": self.adapter.mode.value,
                           **output.metadata, "warnings": list(output.warnings)},
                experiment_id=experiment_id, macroproceso=macroproceso)
        except Exception as exc:
            graph_error_codes = tuple(getattr(exc, "error_codes", ()))
            if isinstance(exc, ValueError):
                error_category = ErrorCategory.INCOMPLETE_OUTPUT
            elif any(code.startswith("DOCUMENT_") for code in graph_error_codes):
                error_category = ErrorCategory.DOCUMENT_READ
            elif any(code.startswith("INFERENCE_") for code in graph_error_codes):
                error_category = ErrorCategory.LLM_PROVIDER
            elif graph_error_codes:
                error_category = ErrorCategory.AGENT
            else:
                error_category = ErrorCategory.UNEXPECTED
            record = ExecutionRecord(
                execution_id, expediente.expediente_id, replica, config,
                ExecutionStatus.ERROR, started, datetime.now(timezone.utc),
                time.perf_counter_ns() - monotonic_start,
                error_category=error_category,
                error_type=type(exc).__name__,
                error_message="La ejecución falló; consulte error_type y reproduzca con datos sintéticos.",
                telemetry={"python_version": platform.python_version(),
                           "adapter": type(self.adapter).__name__,
                           "effective_mode": self.adapter.mode.value,
                           "error_codes": list(graph_error_codes),
                           **getattr(exc, "execution_metadata", {})},
                experiment_id=experiment_id, macroproceso=macroproceso)
        try:
            self.store.save(record)
        except Exception:
            if record.status is ExecutionStatus.ERROR and record.error_category is ErrorCategory.PERSISTENCE:
                raise
            record = ExecutionRecord(
                execution_id, expediente.expediente_id, replica, config,
                ExecutionStatus.ERROR, started, datetime.now(timezone.utc),
                time.perf_counter_ns() - monotonic_start,
                error_category=ErrorCategory.PERSISTENCE, error_type="StoreError",
                error_message="No fue posible persistir el registro en el almacén local.",
                telemetry={"python_version": platform.python_version(), "persisted": False,
                           "adapter": type(self.adapter).__name__},
                experiment_id=experiment_id, macroproceso=macroproceso)
        return record

    def run_replicas(self, expediente: Expediente, config: ExperimentConfig,
                     count: int = 5,
                     macroproceso: Macroprocess | None = None) -> list[ExecutionRecord]:
        if count < 1:
            raise ValueError("count debe ser >= 1")
        experiment_id = str(uuid4())
        return [self.run(expediente, config, replica=i, experiment_id=experiment_id,
                         macroproceso=macroproceso)
                for i in range(1, count + 1)]
