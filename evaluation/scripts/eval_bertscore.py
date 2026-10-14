"""Instrumento OE2: BERTScore y coseno entre dictámenes por criterio."""
from __future__ import annotations

import argparse
import json
import sys

from ..metrics.common import (MetricInputError, add_mode_arguments, configuration_provenance, enforce_mode,
                              load_executions, load_ground_truth, load_mode_catalog,
                              select_primary_runs, sha256_file, validate_catalog_links,
                              validate_config_manifest, write_report)
from ..metrics.semantic import (BertScoreLocal, SemanticDependencyError,
                                SentenceTransformerLocal, build_semantic_pairs,
                                score_semantic_pairs, semantic_dependency_inventory)


CSV_COLUMNS = ("expediente_id", "macroproceso", "criterion_id", "normative_version", "execution_id",
               "experiment_id", "replica", "status", "bertscore_precision",
               "bertscore_recall", "bertscore_f1", "cosine_similarity",
               "bertscore_error", "cosine_error", "candidate_truncated",
               "reference_truncated")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True, help="ExecutionRecord JSONL")
    parser.add_argument("--ground-truth", required=True, help="Ground Truth JSONL validado")
    parser.add_argument("--catalog", required=True, help="catálogo para validar versión/criterios")
    parser.add_argument("--bert-model-dir", help="directorio LOCAL de bert-base-multilingual-cased")
    parser.add_argument("--embedding-model-dir", help="directorio LOCAL de paraphrase-multilingual-mpnet-base-v2")
    parser.add_argument("--response-kind", choices=("criterion_verdict",), required=True,
                        help="confirma comparar rationale por criterio con reference_verdict")
    parser.add_argument("--bert-revision", help="revisión declarada del artefacto BERT local")
    parser.add_argument("--embedding-revision", help="revisión declarada del artefacto de embeddings")
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
        scoped_executions = [record for record in executions
                             if record.experiment_id == selection.experiment_id
                             and record.macroproceso == selection.macroproceso]
        validate_catalog_links(catalog, references, scoped_executions)
        pairs, exclusions = build_semantic_pairs(references, selection)
        base = {
            "status": "computed", "mode": args.mode,
            "dataset_label": "synthetic_test" if args.mode == "synthetic_test" else "authorized",
            "experiment_id": selection.experiment_id,
            "macroproceso": selection.macroproceso.value if selection.macroproceso else None,
            "selection_policy": "replica=1, one explicit/unique experiment; per-criterion rationale only",
            "catalog_id": catalog.catalog_id, "normative_version": catalog.normative_version,
            "config_manifest_sha256": config_sha256,
            "configuration_provenance": configuration_provenance(scoped_executions),
            "matched_pairs": len(pairs), "excluded_pairs": exclusions,
            "input_sha256": {"executions": sha256_file(args.results),
                             "ground_truth": sha256_file(args.ground_truth),
                             "catalog": sha256_file(args.catalog)},
            "semantic_dependencies_available": semantic_dependency_inventory(),
            "pairing_policy": "expediente_id + macroproceso + criterion_id + normative_version; only validated applicable references",
            "response_kind": args.response_kind,
            "interpretation_limit": "semantic similarity is not evidence of normative correctness",
        }
        if not pairs:
            base.update({"status": "no_comparable_pairs", "bertscore_f1": None,
                         "cosine_similarity": None,
                         "dependency_status": "not_needed_no_pairs"})
            rows = []
            exit_code = 0
        else:
            try:
                if not all((args.bert_model_dir, args.embedding_model_dir,
                            args.bert_revision, args.embedding_revision)):
                    raise SemanticDependencyError(
                        "requiere --bert-model-dir/--bert-revision y --embedding-model-dir/--embedding-revision locales")
                bert = BertScoreLocal(args.bert_model_dir, args.bert_revision)
                embedder = SentenceTransformerLocal(args.embedding_model_dir, args.embedding_revision)
                rows, metrics = score_semantic_pairs(pairs, bert, embedder)
                base.update(metrics)
                base["dependency_status"] = "loaded_local_models"
                exit_code = 0
            except SemanticDependencyError as exc:
                rows = [{"expediente_id": pair.expediente_id, "macroproceso": pair.macroproceso, "criterion_id": pair.criterion_id,
                         "normative_version": pair.normative_version,
                         "execution_id": pair.execution_id, "experiment_id": pair.experiment_id,
                         "replica": pair.replica, "status": "blocked_dependency",
                         "bertscore_error": str(exc), "cosine_error": str(exc)} for pair in pairs]
                base.update({"status": "blocked_dependency", "dependency_status": str(exc),
                             "missing_dependencies": [name for name, available in semantic_dependency_inventory().items()
                                                      if not available],
                             "bertscore_f1": None, "cosine_similarity": None})
                exit_code = 2
        folder = write_report(args.output_dir, "eval_bertscore", base, rows, CSV_COLUMNS)
        print(json.dumps({"report_dir": str(folder), "status": base["status"],
                          "matched_pairs": len(pairs), "excluded_pairs": len(exclusions)},
                         ensure_ascii=False))
        if exit_code:
            print(f"eval_bertscore: {base['dependency_status']}", file=sys.stderr)
        return exit_code
    except (MetricInputError, OSError, ValueError) as exc:
        print(f"eval_bertscore: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
