"""Instrumento OE3: cobertura de criterios aplicables evaluados explícitamente."""
from __future__ import annotations

import argparse
import json
import sys

from ..metrics.common import (MetricInputError, add_mode_arguments, configuration_provenance, enforce_mode,
                              load_executions, load_ground_truth, load_mode_catalog,
                              select_primary_runs, sha256_file, validate_catalog_links,
                              validate_config_manifest, write_report)
from ..metrics.coverage import calculate_coverage


CSV_COLUMNS = ("expediente_id", "macroproceso", "criterion_id", "catalog_id", "normative_version",
               "execution_id", "experiment_id", "replica", "execution_status",
               "applicability", "evaluation_state", "coverage_counted", "reason")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True, help="ExecutionRecord JSONL")
    parser.add_argument("--ground-truth", required=True, help="Ground Truth JSONL con aplicabilidad final")
    parser.add_argument("--catalog", required=True, help="catálogo/versionado usado")
    add_mode_arguments(parser, include_catalog_approval=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        executions = load_executions(args.results)
        config_sha256 = validate_config_manifest(args.config, executions)
        references = load_ground_truth(args.ground_truth)
        catalog = load_mode_catalog(args.catalog, args.mode,
                                    validated_by=args.catalog_validated_by,
                                    approval_reference=args.catalog_approval_ref,
                                    validated_at=args.catalog_validated_at)
        enforce_mode(args.mode, executions, ground_truth=references, catalog=catalog,
                     authorization_ref=args.authorization_ref)
        selection = select_primary_runs(executions, args.experiment_id, args.macroproceso)
        scoped = [record for record in executions if record.experiment_id == selection.experiment_id
                  and record.macroproceso == selection.macroproceso]
        validate_catalog_links(catalog, references, scoped)
        summary, details = calculate_coverage(catalog, references, selection)
        summary.update({
            "status": "computed", "mode": args.mode,
            "macroproceso": selection.macroproceso.value if selection.macroproceso else None,
            "dataset_label": "synthetic_test" if args.mode == "synthetic_test" else "authorized",
            "catalog_sha256": catalog.content_sha256,
            "config_manifest_sha256": config_sha256,
            "configuration_provenance": configuration_provenance(scoped),
            "input_sha256": {"executions": sha256_file(args.results),
                             "ground_truth": sha256_file(args.ground_truth),
                             "catalog": sha256_file(args.catalog)},
            "limitations": ["coverage is not accreditation compliance",
                            "applicability is taken only from validated Ground Truth records"],
        })
        folder = write_report(args.output_dir, "eval_coverage", summary, details, CSV_COLUMNS)
        print(json.dumps({"report_dir": str(folder), "status": "computed",
                          "total_applicable": summary["total_applicable"],
                          "coverage_percent": summary["coverage_percent"]}, ensure_ascii=False))
        return 0
    except (MetricInputError, OSError, ValueError) as exc:
        print(f"eval_coverage: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
