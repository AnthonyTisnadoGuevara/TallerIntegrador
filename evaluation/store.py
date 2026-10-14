"""Almacén JSONL local, append-only y con huella por registro."""
from __future__ import annotations

import json
import os
from pathlib import Path
import threading
import time
from typing import Iterable

from .schemas import ExecutionRecord, canonical_json, sha256_json, to_primitive


class DuplicateExecutionError(ValueError):
    pass


class IntegrityError(ValueError):
    pass


class LocalExecutionStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else Path(__file__).parent / "outputs" / "runs.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._thread_lock = threading.Lock()

    def _acquire_file_lock(self, timeout: float = 5.0) -> Path:
        lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        deadline = time.monotonic() + timeout
        while True:
            try:
                descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(descriptor)
                return lock_path
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("no se pudo adquirir el bloqueo del almacén local")
                time.sleep(0.025)

    def save(self, record: ExecutionRecord) -> None:
        with self._thread_lock:
            lock = self._acquire_file_lock()
            try:
                records = self.read_all()
                if any(item.execution_id == record.execution_id for item in records):
                    raise DuplicateExecutionError(f"execution_id ya existe: {record.execution_id}")
                if record.experiment_id is not None and any(
                    item.experiment_id == record.experiment_id
                    and item.expediente_id == record.expediente_id
                    and item.macroproceso == record.macroproceso
                    and item.replica == record.replica
                    for item in records
                ):
                    raise DuplicateExecutionError("número de réplica ya existe en este experimento")
                payload = to_primitive(record)
                line = {"record": payload, "integrity_sha256": sha256_json(payload)}
                with self.path.open("a", encoding="utf-8", newline="\n") as stream:
                    stream.write(canonical_json(line) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
            finally:
                lock.unlink(missing_ok=True)

    def read_all(self) -> list[ExecutionRecord]:
        if not self.path.exists():
            return []
        result: list[ExecutionRecord] = []
        seen: set[str] = set()
        with self.path.open("r", encoding="utf-8") as stream:
            for line_number, raw in enumerate(stream, start=1):
                try:
                    envelope = json.loads(raw)
                    payload = envelope["record"]
                    if sha256_json(payload) != envelope["integrity_sha256"]:
                        raise IntegrityError(f"huella no coincide en línea {line_number}")
                    record = record_from_dict(payload)
                    if record.execution_id in seen:
                        raise IntegrityError(f"execution_id duplicado en línea {line_number}")
                    seen.add(record.execution_id)
                    result.append(record)
                except IntegrityError:
                    raise
                except Exception as exc:
                    raise IntegrityError(f"registro inválido en línea {line_number}: {type(exc).__name__}") from exc
        return result

    def query(self, *, expediente_id: str | None = None, replica: int | None = None,
              experiment_id: str | None = None, macroproceso=None) -> list[ExecutionRecord]:
        return [r for r in self.read_all()
                if (expediente_id is None or r.expediente_id == expediente_id)
                and (replica is None or r.replica == replica)
                and (experiment_id is None or r.experiment_id == experiment_id)
                and (macroproceso is None or r.macroproceso == macroproceso)]


def record_from_dict(data: dict) -> ExecutionRecord:
    """Reconstruye y vuelve a validar un registro JSONL."""
    from datetime import datetime
    from .schemas import (Classification, CriterionResult, EffectiveMode, ErrorCategory,
                          EvaluationState, Evidence, ExecutionStatus, ExperimentConfig, Macroprocess,
                          MacroprocessAggregationPolicy, RunType, Verdict)

    def dt(raw: str) -> datetime:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))

    config_data = dict(data["config"])
    config_data["run_type"] = RunType(config_data["run_type"])
    config_data["effective_mode"] = EffectiveMode(config_data["effective_mode"])
    if config_data.get("macroprocess_aggregation_policy"):
        config_data["macroprocess_aggregation_policy"] = MacroprocessAggregationPolicy(
            config_data["macroprocess_aggregation_policy"])
    config = ExperimentConfig(**config_data)

    def result_from(raw: dict) -> CriterionResult:
        evidences = tuple(Evidence(**ev) for ev in raw.get("evidence", []))
        return CriterionResult(raw["criterion_id"], EvaluationState(raw["evaluation_state"]),
                               Classification(raw["classification"]), raw["rationale"], evidences,
                               raw.get("expediente_id"), raw.get("catalog_id"),
                               raw.get("normative_version"), raw.get("execution_id"),
                               Macroprocess(raw["macroproceso"]) if raw.get("macroproceso") else None)

    results = tuple(result_from(item) for item in data.get("results", []))
    verdict_data = data.get("verdict")
    verdict = None
    if verdict_data is not None:
        verdict = Verdict(verdict_data["expediente_id"],
                          Classification(verdict_data["overall_classification"]),
                          verdict_data["rationale"],
                          tuple(result_from(item) for item in verdict_data["criterion_results"]),
                          verdict_data["format_version"], verdict_data.get("reference"))
    category = data.get("error_category")
    return ExecutionRecord(
        execution_id=data["execution_id"], expediente_id=data["expediente_id"],
        replica=data["replica"], config=config, status=ExecutionStatus(data["status"]),
        started_at=dt(data["started_at"]), finished_at=dt(data["finished_at"]),
        duration_ns=data["duration_ns"], results=results, verdict=verdict,
        error_category=ErrorCategory(category) if category else None,
        error_type=data.get("error_type"), error_message=data.get("error_message"),
        telemetry=data.get("telemetry", {}), experiment_id=data.get("experiment_id"),
        macroproceso=Macroprocess(data["macroproceso"]) if data.get("macroproceso") else None)
