"""Instrumento OE5: estructura de cinco réplicas y comparación pareada."""
from __future__ import annotations

import argparse
import json
import sys

from ..metrics.common import (MetricInputError, add_mode_arguments, configuration_provenance, enforce_mode,
                              load_executions, load_mode_catalog, sha256_file,
                              validate_catalog_links, validate_config_manifest,
                              write_report)
from ..metrics.semantic import SemanticDependencyError, SentenceTransformerLocal
from ..metrics.stability import analyze_stability


CSV_COLUMNS = ("expediente_id", "macroproceso", "experiment_id", "replica_left", "replica_right",
               "execution_id_left", "execution_id_right", "normative_version", "status",
               "comparable_conditions", "common_criteria", "label_agreement",
               "changed_conforming_to_nonconforming", "changed_nonconforming_to_conforming",
               "changed_to_indeterminate", "evaluated_criteria_symmetric_difference",
               "omitted_criteria_symmetric_difference", "mode_changed", "run_error_left",
               "run_error_right", "cosine_similarity", "semantic_status", "semantic_error")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True, help="ExecutionRecord JSONL")
    parser.add_argument("--catalog", required=True, help="catálogo/versionado de las ejecuciones")
    parser.add_argument("--embedding-model-dir", help="directorio LOCAL del modelo multilingual-mpnet")
    parser.add_argument("--embedding-revision", help="revisión declarada del artefacto local")
    add_mode_arguments(parser, include_catalog_approval=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        executions = load_executions(args.results)
        config_sha256 = validate_config_manifest(args.config, executions)
        catalog = load_mode_catalog(args.catalog, args.mode,
                                    validated_by=args.catalog_validated_by,
                                    approval_reference=args.catalog_approval_ref,
                                    validated_at=args.catalog_validated_at)
        enforce_mode(args.mode, executions, catalog=catalog,
                     authorization_ref=args.authorization_ref)
        available = {record.experiment_id for record in executions}
        selected_experiment = args.experiment_id
        if selected_experiment is None:
            if len(available) > 1:
                raise MetricInputError("hay varios experiment_id; seleccione uno explícitamente")
            selected_experiment = next(iter(available)) if available else None
        scoped = [record for record in executions if record.experiment_id == selected_experiment
                  and (args.macroproceso is None or (record.macroproceso is not None
                       and record.macroproceso.value == args.macroproceso))]
        if not scoped:
            raise MetricInputError("no hay ejecuciones para el experiment_id seleccionado")
        validate_catalog_links(catalog, (), scoped)
        exclusions = [{"execution_id": record.execution_id,
                       "reason": ("different_experiment" if record.experiment_id != selected_experiment
                                  else "different_or_missing_macroprocess")}
                      for record in executions if record.experiment_id != selected_experiment
                      or (args.macroproceso is not None and (record.macroproceso is None
                          or record.macroproceso.value != args.macroproceso))]
        embedder = None
        block_reason = None
        if not args.embedding_model_dir or not args.embedding_revision:
            block_reason = "requiere --embedding-model-dir y --embedding-revision de un artefacto local; no se descargará un modelo"
        else:
            try:
                embedder = SentenceTransformerLocal(args.embedding_model_dir, args.embedding_revision)
            except SemanticDependencyError as exc:
                block_reason = str(exc)
        summary, pairs = analyze_stability(scoped, catalog.normative_version,
                                           embedder=embedder,
                                           semantic_block_reason=block_reason or "semantic_provider_unavailable")
        semantic_pending = embedder is None
        summary.update({
            "status": "semantic_dependency_blocked" if semantic_pending else "computed",
            "macroproceso": args.macroproceso,
            "mode": args.mode,
            "dataset_label": "synthetic_test" if args.mode == "synthetic_test" else "authorized",
            "catalog_id": catalog.catalog_id,
            "catalog_sha256": catalog.content_sha256,
            "config_manifest_sha256": config_sha256,
            "configuration_provenance": configuration_provenance(scoped),
            "selected_experiment_id": selected_experiment,
            "experiment_exclusions": exclusions,
            "input_sha256": {"executions": sha256_file(args.results),
                             "catalog": sha256_file(args.catalog)},
            "selection_policy": "all replicas 1..5 within one explicitly selected/unique experiment; incompatible conditions remain reported",
        })
        folder = write_report(args.output_dir, "eval_stability", summary, pairs, CSV_COLUMNS)
        print(json.dumps({"report_dir": str(folder), "status": summary["status"],
                          "groups": summary["group_count"],
                          "pair_slots": summary["pair_slots_total"],
                          "semantic_pairs_computed": summary["semantic_pairs_computed"]},
                         ensure_ascii=False))
        if semantic_pending:
            print(f"eval_stability: {block_reason}", file=sys.stderr)
            return 2
        return 0
    except (MetricInputError, OSError, ValueError) as exc:
        print(f"eval_stability: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
