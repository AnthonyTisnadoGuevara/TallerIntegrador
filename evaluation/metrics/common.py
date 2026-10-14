"""Lectura, selección reproducible y exportación segura de métricas."""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from ..catalog import NormativeCatalog, approve_catalog, load_catalog
from ..ground_truth import GroundTruthRecord, GroundTruthStatus
from ..ground_truth_store import GroundTruthStore
from ..schemas import (Classification, EffectiveMode, ExecutionRecord, ExecutionStatus,
                       ExperimentConfig, Macroprocess, RunType, canonical_json, to_primitive)
from ..store import LocalExecutionStore


class MetricInputError(ValueError):
    """Entrada ausente, ambigua, corrupta o incompatible con el instrumento."""


@dataclass(frozen=True)
class RunSelection:
    experiment_id: str | None
    selected_by_expediente: dict[str, ExecutionRecord]
    exclusions: tuple[dict[str, str], ...]
    loaded_count: int
    matching_experiment_count: int
    macroproceso: Macroprocess | None = None


def load_executions(path: str | Path) -> list[ExecutionRecord]:
    source = Path(path)
    if not source.is_file():
        raise MetricInputError("el archivo de ejecuciones no existe o no es un archivo")
    try:
        # read_all valida SHA-256 del sobre y reconstruye cada dataclass sin reescribir.
        records = LocalExecutionStore(source).read_all()
    except Exception as exc:
        raise MetricInputError(f"JSONL de ejecuciones inválido ({type(exc).__name__})") from exc
    if not records:
        raise MetricInputError("el JSONL de ejecuciones no contiene registros")
    return records


def load_ground_truth(path: str | Path) -> list[GroundTruthRecord]:
    source = Path(path)
    if not source.is_file():
        raise MetricInputError("el archivo Ground Truth no existe o no es un archivo")
    try:
        return GroundTruthStore(source).read_all()
    except Exception as exc:
        raise MetricInputError(f"JSONL Ground Truth inválido ({type(exc).__name__})") from exc


def load_metric_catalog(path: str | Path) -> NormativeCatalog:
    source = Path(path)
    if not source.is_file():
        raise MetricInputError("el archivo de catálogo no existe o no es un archivo")
    try:
        return load_catalog(source)
    except Exception as exc:
        raise MetricInputError(f"catálogo inválido ({type(exc).__name__})") from exc


def load_mode_catalog(path: str | Path, mode: str, *, validated_by: str | None = None,
                      approval_reference: str | None = None,
                      validated_at: str | None = None) -> NormativeCatalog:
    catalog = load_metric_catalog(path)
    if mode != "authorized":
        return catalog
    if not all((validated_by, approval_reference, validated_at)):
        raise MetricInputError(
            "authorized requiere --catalog-validated-by, --catalog-approval-ref y --catalog-validated-at")
    try:
        timestamp = datetime.fromisoformat(validated_at.replace("Z", "+00:00"))
        return approve_catalog(catalog, validated_by=validated_by,
                               approval_reference=approval_reference, validated_at=timestamp)
    except Exception as exc:
        raise MetricInputError(f"metadatos de aprobación del catálogo inválidos ({type(exc).__name__})") from exc


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add_mode_arguments(parser: argparse.ArgumentParser, *, require_experiment: bool = False,
                       include_experiment: bool = True,
                       include_catalog_approval: bool = False) -> None:
    parser.add_argument("--mode", choices=("synthetic_test", "authorized"),
                        default="synthetic_test",
                        help="synthetic_test por defecto; authorized requiere declaración explícita")
    parser.add_argument("--authorization-ref",
                        help="referencia de autorización; obligatoria con --mode authorized")
    parser.add_argument("--config", help="JSON opcional de ExperimentConfig esperado; normalmente está embebido en el JSONL")
    if include_catalog_approval:
        parser.add_argument("--catalog-validated-by", help="responsable que declaró aprobar el catálogo")
        parser.add_argument("--catalog-approval-ref", help="referencia documental de aprobación declarada")
        parser.add_argument("--catalog-validated-at", help="fecha ISO-8601 con zona, p. ej. 2026-10-14T12:00:00Z")
    if include_experiment:
        parser.add_argument("--experiment-id", required=require_experiment,
                            help="experimento a seleccionar; por defecto se exige que sea inequívoco")
    parser.add_argument("--output-dir", default="evaluation/outputs/metrics",
                        help="directorio raíz de reportes; cada ejecución crea una carpeta nueva")
    parser.add_argument("--macroproceso", choices=tuple(item.value for item in Macroprocess),
                        help="selección estratificada por macroproceso")


def enforce_mode(mode: str, records: Iterable[ExecutionRecord], *,
                 ground_truth: Iterable[GroundTruthRecord] = (),
                 catalog: NormativeCatalog | None = None,
                 authorization_ref: str | None = None) -> None:
    records, ground_truth = tuple(records), tuple(ground_truth)
    if mode not in {"synthetic_test", "authorized"}:
        raise MetricInputError("modo de evaluación desconocido")
    if mode == "authorized" and not (authorization_ref and authorization_ref.strip()):
        raise MetricInputError("--mode authorized requiere --authorization-ref")
    if mode == "synthetic_test":
        if any(record.config.run_type is not RunType.SYNTHETIC
               or record.config.effective_mode is not EffectiveMode.SYNTHETIC
               for record in records):
            raise MetricInputError("synthetic_test solo admite ejecuciones sintéticas")
        if catalog is not None and not catalog.catalog_id.upper().startswith("SYNTH"):
            raise MetricInputError("synthetic_test requiere un catalog_id sintético")
        if any(not item.expediente_id.upper().startswith("SYNTH")
               or not item.catalog_id.upper().startswith("SYNTH") for item in ground_truth):
            raise MetricInputError("synthetic_test requiere Ground Truth claramente sintético")


def select_primary_runs(records: Iterable[ExecutionRecord],
                        experiment_id: str | None = None,
                        macroproceso: str | Macroprocess | None = None) -> RunSelection:
    records = tuple(records)
    if isinstance(macroproceso, str):
        try:
            macroproceso = Macroprocess(macroproceso)
        except ValueError as exc:
            raise MetricInputError("macroproceso desconocido") from exc
    processes = {record.macroproceso for record in records if record.macroproceso is not None}
    if macroproceso is None and len(processes) > 1:
        raise MetricInputError("hay varios macroprocesos; seleccione uno explÃ­citamente")
    if macroproceso is None and len(processes) == 1:
        macroproceso = next(iter(processes))
    if macroproceso is not None:
        records = tuple(record for record in records if record.macroproceso is macroproceso)
        if not records:
            raise MetricInputError("no hay ejecuciones para el macroproceso solicitado")
    experiment_ids = {record.experiment_id for record in records}
    if experiment_id is None:
        if len(experiment_ids) > 1:
            raise MetricInputError("hay varios experiment_id; seleccione uno explícitamente")
        experiment_id = next(iter(experiment_ids)) if experiment_ids else None
    matching = [record for record in records if record.experiment_id == experiment_id]
    if not matching:
        raise MetricInputError("no hay ejecuciones para el experiment_id solicitado")

    selected: dict[str, ExecutionRecord] = {}
    exclusions: list[dict[str, str]] = []
    for record in records:
        if record.experiment_id != experiment_id:
            exclusions.append({"execution_id": record.execution_id,
                               "reason": "different_experiment"})
            continue
        if record.replica != 1:
            exclusions.append({"execution_id": record.execution_id,
                               "reason": "primary_policy_uses_replica_1"})
            continue
        if record.expediente_id in selected:
            raise MetricInputError("más de una ejecución primaria para expediente y experimento")
        selected[record.expediente_id] = record
    return RunSelection(experiment_id, selected, tuple(exclusions), len(records), len(matching), macroproceso)


def validate_config_manifest(path: str | Path | None,
                             records: Iterable[ExecutionRecord]) -> str | None:
    if path is None:
        return None
    source = Path(path)
    if not source.is_file():
        raise MetricInputError("archivo de configuración no encontrado")
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("se esperaba objeto JSON")
        data = dict(raw)
        data["run_type"] = RunType(data["run_type"])
        from ..schemas import EffectiveMode
        data["effective_mode"] = EffectiveMode(data["effective_mode"])
        from ..schemas import MacroprocessAggregationPolicy
        if data.get("macroprocess_aggregation_policy"):
            data["macroprocess_aggregation_policy"] = MacroprocessAggregationPolicy(
                data["macroprocess_aggregation_policy"])
        expected = ExperimentConfig(**data)
    except Exception as exc:
        raise MetricInputError(f"ExperimentConfig JSON inválido ({type(exc).__name__})") from exc
    if any(record.config != expected for record in records):
        raise MetricInputError("el manifiesto ExperimentConfig no coincide exactamente con el JSONL")
    return sha256_file(source)


def configuration_provenance(records: Iterable[ExecutionRecord]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for record in records:
        config = record.config
        item = {
            "config_id": config.config_id,
            "configuration_sha256": hashlib.sha256(canonical_json(config).encode("utf-8")).hexdigest(),
            "code_sha256": config.code_sha256,
            "prompt_sha256": config.prompt_sha256,
            "catalog_sha256": config.catalog_sha256,
            "corpus_sha256": config.corpus_sha256,
            "dependency_versions": config.dependency_versions,
            "provider": config.provider, "model": config.model,
            "model_version": config.model_version,
            "temperature": config.temperature, "seed": config.seed,
            "run_type": config.run_type.value,
            "effective_mode": config.effective_mode.value,
            "macroprocess_aggregation_policy": config.macroprocess_aggregation_policy.value,
            "aggregation_approval_reference": config.aggregation_approval_reference,
        }
        unique[item["configuration_sha256"]] = item
    return [unique[key] for key in sorted(unique)]


def index_final_ground_truth(records: Iterable[GroundTruthRecord],
                             macroproceso: Macroprocess | None = None) -> tuple[
        dict[tuple[str, str, str], GroundTruthRecord], list[dict[str, str]]]:
    index: dict[tuple[str, str, str], GroundTruthRecord] = {}
    exclusions: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for record in records:
        if macroproceso is not None and record.macroproceso is not macroproceso:
            exclusions.append({"expediente_id": record.expediente_id,
                               "criterion_id": record.criterion_id,
                               "normative_version": record.normative_version,
                               "reason": "different_or_missing_macroprocess"})
            continue
        if macroproceso is None and record.macroproceso is not None:
            exclusions.append({"expediente_id": record.expediente_id,
                               "criterion_id": record.criterion_id,
                               "normative_version": record.normative_version,
                               "reason": "macroprocess_not_selected"})
            continue
        key = (record.expediente_id, record.criterion_id, record.normative_version)
        if key in seen:
            raise MetricInputError("Ground Truth duplicado para expediente/criterio/versión")
        seen.add(key)
        if record.status is not GroundTruthStatus.VALIDATED:
            exclusions.append({"expediente_id": record.expediente_id,
                               "criterion_id": record.criterion_id,
                               "normative_version": record.normative_version,
                               "reason": f"reference_status:{record.status.value}"})
            continue
        index[key] = record
    return index, exclusions


def validate_catalog_links(catalog: NormativeCatalog,
                           ground_truth: Iterable[GroundTruthRecord],
                           records: Iterable[ExecutionRecord]) -> None:
    allowed_criteria = {criterion.criterion_id for criterion in catalog.criteria}
    for reference in ground_truth:
        if (reference.catalog_id, reference.normative_version) != (
                catalog.catalog_id, catalog.normative_version):
            raise MetricInputError("Ground Truth usa catálogo o versión incompatible")
        if reference.criterion_id not in allowed_criteria:
            raise MetricInputError("Ground Truth contiene criterio ausente del catálogo")
    for execution in records:
        if execution.config.catalog_sha256 != catalog.content_sha256:
            raise MetricInputError("hash del catálogo no coincide con la configuración de ejecución")
        for result in execution.results:
            if result.catalog_id not in (None, catalog.catalog_id):
                raise MetricInputError("resultado vinculado a otro catálogo")
            if result.normative_version is not None and result.normative_version != catalog.normative_version:
                raise MetricInputError("resultado vinculado a otra versión normativa")
            if result.criterion_id not in allowed_criteria:
                raise MetricInputError("resultado contiene criterio ausente del catálogo")


def result_index(execution: ExecutionRecord) -> dict[tuple[str, str, str], Any]:
    indexed: dict[tuple[str, str, str], Any] = {}
    for result in execution.results:
        if result.expediente_id != execution.expediente_id:
            continue
        if result.execution_id != execution.execution_id:
            continue
        if not result.normative_version:
            continue
        if result.macroproceso != execution.macroproceso:
            continue
        key = (result.expediente_id, result.criterion_id, result.normative_version)
        if key in indexed:
            raise MetricInputError("resultado duplicado para ejecución/criterio/versión")
        indexed[key] = result
    return indexed


def summarize_numbers(values: Iterable[float]) -> dict[str, float | int | None]:
    """Descriptivos; P90/P95 usan interpolación lineal tipo Hyndman-Fan 7."""
    from statistics import mean, median, stdev
    data = sorted(float(value) for value in values)
    if not data:
        return {"n": 0, "mean": None, "median": None, "min": None, "max": None,
                "sample_stdev": None, "p90_linear": None, "p95_linear": None}

    def percentile(p: float) -> float:
        position = (len(data) - 1) * p
        lower = int(position)
        upper = min(lower + 1, len(data) - 1)
        fraction = position - lower
        return data[lower] + (data[upper] - data[lower]) * fraction

    return {"n": len(data), "mean": mean(data), "median": median(data),
            "min": data[0], "max": data[-1],
            "sample_stdev": stdev(data) if len(data) > 1 else None,
            "p90_linear": percentile(.90), "p95_linear": percentile(.95)}


def write_report(output_root: str | Path, instrument: str, summary: dict[str, Any],
                 rows: Iterable[dict[str, Any]], columns: Iterable[str]) -> Path:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    for suffix in range(1000):
        folder_name = f"{instrument}_{timestamp}" + (f"_{suffix}" if suffix else "")
        folder = root / folder_name
        try:
            folder.mkdir(exist_ok=False)
            break
        except FileExistsError:
            continue
    else:
        raise MetricInputError("no se pudo reservar una carpeta nueva para exportación")

    final_summary = {"instrument": instrument, "instrument_version": "1.0.0",
                     "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                     **summary}
    json_path = folder / "summary.json"
    with json_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(to_primitive(final_summary), stream, ensure_ascii=False,
                  sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
    csv_path = folder / "details.csv"
    with csv_path.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in writer.fieldnames})
    return folder


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(to_primitive(value), ensure_ascii=False, sort_keys=True)
    if hasattr(value, "value"):
        return value.value
    return value
