"""Latencia OE4 y disponibilidad explícita de telemetría."""
from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal
import hashlib
from typing import Iterable

from ..schemas import ExecutionRecord, ExecutionStatus, canonical_json
from .common import summarize_numbers


REPORTED_TELEMETRY_FIELDS = (
    "node_durations_ns", "llm_duration_ns", "input_tokens", "output_tokens",
    "cpu_percent", "memory_bytes", "memory_mb",
)


def analyze_telemetry(records: Iterable[ExecutionRecord]) -> tuple[dict, list[dict]]:
    records = tuple(records)
    rows = []
    all_seconds: list[float] = []
    success_seconds: list[float] = []
    failure_seconds: list[float] = []
    by_expediente: dict[str, list[ExecutionRecord]] = defaultdict(list)
    by_process_case: dict[tuple[str | None, str], list[ExecutionRecord]] = defaultdict(list)
    by_status = Counter()
    failure_categories = Counter()
    telemetry_availability = {field: {"available": 0, "absent": 0} for field in REPORTED_TELEMETRY_FIELDS}
    for record in records:
        seconds = float(Decimal(record.duration_ns) / Decimal(1_000_000_000))
        all_seconds.append(seconds)
        by_expediente[record.expediente_id].append(record)
        by_process_case[(record.macroproceso.value if record.macroproceso else None,
                         record.expediente_id)].append(record)
        by_status[record.status.value] += 1
        if record.status is ExecutionStatus.SUCCESS:
            success_seconds.append(seconds)
        else:
            failure_seconds.append(seconds)
            failure_categories[record.error_category.value if record.error_category else "missing"] += 1
        raw = record.telemetry or {}
        criterion_runs = raw.get("criterion_evaluations") or []
        observed = {
            "provider_modes": sorted({item.get("effective_mode") or item.get("provider_mode_attempted")
                                       for item in criterion_runs
                                       if item.get("effective_mode") or item.get("provider_mode_attempted")}),
            "providers": sorted({item["provider"] for item in criterion_runs if item.get("provider")}),
            "models": sorted({item["model"] for item in criterion_runs if item.get("model")}),
            "model_versions": sorted({item["model_version"] for item in criterion_runs
                                       if item.get("model_version")}),
            "inference_statuses": sorted({item["inference_status"] for item in criterion_runs
                                           if item.get("inference_status")}),
        }
        field_status = {}
        for field in REPORTED_TELEMETRY_FIELDS:
            present = raw.get(field) is not None
            telemetry_availability[field]["available" if present else "absent"] += 1
            field_status[field] = "reported" if present else "not_available"
        rows.append({
            "expediente_id": record.expediente_id,
            "macroproceso": record.macroproceso.value if record.macroproceso else None,
            "execution_id": record.execution_id,
            "experiment_id": record.experiment_id, "replica": record.replica,
            "status": record.status.value,
            "effective_mode": record.config.effective_mode.value,
            "config_id": record.config.config_id,
            "configuration_sha256": hashlib.sha256(canonical_json(record.config).encode("utf-8")).hexdigest(),
            "code_sha256": record.config.code_sha256,
            "prompt_sha256": record.config.prompt_sha256,
            "catalog_sha256": record.config.catalog_sha256,
            "corpus_sha256": record.config.corpus_sha256,
            "provider": record.config.provider, "model": record.config.model,
            "model_version": record.config.model_version,
            "temperature": record.config.temperature, "seed": record.config.seed,
            **observed,
            "started_at": record.started_at.isoformat(), "finished_at": record.finished_at.isoformat(),
            "duration_ns": record.duration_ns, "duration_seconds": f"{seconds:.9f}",
            "duration_source": "direct_monotonic_runner_measurement",
            "error_category": record.error_category.value if record.error_category else None,
            "error_type": record.error_type,
            "error_codes": raw.get("error_codes", []),
            "telemetry_fields": {key: raw.get(key) for key in REPORTED_TELEMETRY_FIELDS},
            "telemetry_field_status": field_status,
        })

    per_case = {}
    for expediente_id, case_records in sorted(by_expediente.items()):
        successful = [r.duration_ns / 1_000_000_000 for r in case_records
                      if r.status is ExecutionStatus.SUCCESS]
        failed = [r.duration_ns / 1_000_000_000 for r in case_records
                  if r.status is ExecutionStatus.ERROR]
        per_case[expediente_id] = {
            "execution_count": len(case_records),
            "success_count": len(successful), "error_count": len(failed),
            "successful_latency_seconds": summarize_numbers(successful),
            "failed_latency_seconds": summarize_numbers(failed),
        }
    per_macroprocess = {}
    for (macroproceso, expediente_id), case_records in sorted(by_process_case.items(), key=lambda item: str(item[0])):
        successful = [r.duration_ns / 1_000_000_000 for r in case_records if r.status is ExecutionStatus.SUCCESS]
        failed = [r.duration_ns / 1_000_000_000 for r in case_records if r.status is ExecutionStatus.ERROR]
        per_macroprocess[f"{macroproceso or 'heredado'}:{expediente_id}"] = {
            "macroproceso": macroproceso, "expediente_id": expediente_id,
            "execution_count": len(case_records), "success_count": len(successful),
            "error_count": len(failed),
            "successful_latency_seconds": summarize_numbers(successful),
            "failed_latency_seconds": summarize_numbers(failed),
        }
    summary = {
        "loaded_executions": len(records),
        "completed_executions": by_status[ExecutionStatus.SUCCESS.value],
        "error_executions": by_status[ExecutionStatus.ERROR.value],
        "failure_categories": dict(failure_categories),
        "latency_seconds_all": summarize_numbers(all_seconds),
        "latency_seconds_successful": summarize_numbers(success_seconds),
        "latency_seconds_failed": summarize_numbers(failure_seconds),
        "percentile_method": "linear interpolation h=(n-1)*p (Hyndman-Fan type 7); sample standard deviation",
        "telemetry_availability": telemetry_availability,
        "unobserved_fields_are_null": True,
        "observed_inference_modes": sorted({mode for row in rows for mode in row["provider_modes"]}),
        "observed_providers": sorted({name for row in rows for name in row["providers"]}),
        "observed_models": sorted({name for row in rows for name in row["models"]}),
        "per_expediente": per_case,
        "per_macroproceso_expediente": per_macroprocess,
        "duration_scope": "perf_counter_ns around adapter invocation and output validation; includes graph/document reading; JSONL persistence excluded",
        "limitations": ["synthetic latencies are not representative of production LLM latency",
                        "no node, LLM, token, CPU, or memory telemetry is inferred when absent"],
    }
    return summary, rows
