"""Instrumento OE4: latencia y telemetría efectivamente disponible."""
from __future__ import annotations

import argparse
import json
import sys

from ..metrics.common import (MetricInputError, add_mode_arguments, configuration_provenance, enforce_mode,
                              load_executions, sha256_file, validate_config_manifest,
                              write_report)
from ..metrics.telemetry import analyze_telemetry


CSV_COLUMNS = ("expediente_id", "macroproceso", "execution_id", "experiment_id", "replica", "status",
               "effective_mode", "config_id", "configuration_sha256", "code_sha256",
               "prompt_sha256", "catalog_sha256", "corpus_sha256", "provider", "model",
               "model_version", "temperature", "seed", "provider_modes", "providers", "models",
               "model_versions", "inference_statuses", "started_at", "finished_at", "duration_ns",
               "duration_seconds", "duration_source", "error_category", "error_type",
               "error_codes", "telemetry_fields", "telemetry_field_status")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True, help="ExecutionRecord JSONL")
    parser.add_argument("--experiment-id", help="opcional: filtrar un experimento")
    add_mode_arguments(parser, include_experiment=False)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        records = load_executions(args.results)
        config_sha256 = validate_config_manifest(args.config, records)
        enforce_mode(args.mode, records, authorization_ref=args.authorization_ref)
        if args.macroproceso:
            records = [record for record in records
                       if record.macroproceso is not None and record.macroproceso.value == args.macroproceso]
            if not records:
                raise MetricInputError("no hay ejecuciones para el macroproceso solicitado")
        elif len({record.macroproceso for record in records if record.macroproceso is not None}) > 1:
            raise MetricInputError("hay varios macroprocesos; seleccione --macroproceso")
        if args.experiment_id is not None:
            records = [record for record in records if record.experiment_id == args.experiment_id]
            if not records:
                raise MetricInputError("experiment_id no encontrado")
        summary, details = analyze_telemetry(records)
        summary.update({"status": "computed", "mode": args.mode,
                        "macroproceso": args.macroproceso,
                        "dataset_label": "synthetic_test" if args.mode == "synthetic_test" else "authorized",
                        "config_manifest_sha256": config_sha256,
                        "configuration_provenance": configuration_provenance(records),
                        "input_sha256": {"executions": sha256_file(args.results)}})
        folder = write_report(args.output_dir, "eval_telemetry", summary, details, CSV_COLUMNS)
        print(json.dumps({"report_dir": str(folder), "status": "computed",
                          "executions": summary["loaded_executions"],
                          "errors": summary["error_executions"]}, ensure_ascii=False))
        return 0
    except (MetricInputError, OSError, ValueError) as exc:
        print(f"eval_telemetry: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
