"""Estabilidad OE5: estructura de cinco réplicas y diez pares independientes."""
from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations
from typing import Iterable

from ..schemas import (Classification, EvaluationState, ExecutionRecord,
                       ExecutionStatus, canonical_json)
from .common import summarize_numbers
from .semantic import EmbeddingProvider, cosine_similarity


EXPECTED_REPLICAS = (1, 2, 3, 4, 5)


def analyze_stability(records: Iterable[ExecutionRecord], normative_version: str,
                      embedder: EmbeddingProvider | None = None,
                      semantic_block_reason: str = "embedding_model_not_configured") -> tuple[dict, list[dict]]:
    records = tuple(records)
    coarse_groups: dict[tuple[str, str | None, str | None], list[ExecutionRecord]] = defaultdict(list)
    for record in records:
        coarse_groups[(record.expediente_id, record.macroproceso.value if record.macroproceso else None,
                       record.experiment_id)].append(record)
    summaries, pair_rows = [], []
    for (expediente_id, macroproceso, experiment_id), group in sorted(coarse_groups.items(), key=lambda item: str(item[0])):
        by_replica: dict[int, list[ExecutionRecord]] = defaultdict(list)
        signatures = set()
        for record in group:
            by_replica[record.replica].append(record)
            signature = (record.config.corpus_sha256, normative_version,
                         canonical_json(record.config))
            signatures.add(signature)
        duplicate_replicas = sorted(replica for replica, items in by_replica.items() if len(items) > 1)
        condition_conflicts = len(signatures) > 1
        present = sorted(by_replica)
        missing = sorted(set(EXPECTED_REPLICAS) - set(present))
        extra = sorted(set(present) - set(EXPECTED_REPLICAS))
        pairs = []
        for left_replica, right_replica in combinations(EXPECTED_REPLICAS, 2):
            left_items = by_replica.get(left_replica, [])
            right_items = by_replica.get(right_replica, [])
            left = left_items[0] if len(left_items) == 1 else None
            right = right_items[0] if len(right_items) == 1 else None
            row = _compare_pair(left, right, expediente_id, macroproceso, experiment_id,
                                left_replica, right_replica, normative_version,
                                condition_conflicts, embedder, semantic_block_reason)
            pairs.append(row)
            pair_rows.append(row)
        success_count = sum(record.status is ExecutionStatus.SUCCESS for record in group)
        error_count = len(group) - success_count
        controlled = (len(group) == 5 and not missing and not extra and not duplicate_replicas
                      and not condition_conflicts and success_count == 5)
        label_agreements = [row["label_agreement"] for row in pairs
                            if row["label_agreement"] is not None and row["comparable_conditions"]]
        semantic_values = [row["cosine_similarity"] for row in pairs
                           if row["cosine_similarity"] is not None]
        summaries.append({
            "expediente_id": expediente_id, "macroproceso": macroproceso, "experiment_id": experiment_id,
            "normative_version": normative_version,
            "execution_ids_by_replica": {
                str(replica): [record.execution_id for record in by_replica.get(replica, [])]
                for replica in EXPECTED_REPLICAS},
            "records_available": len(group), "successful_runs": success_count,
            "failed_runs": error_count, "missing_replicas": missing,
            "unexpected_replicas": extra, "duplicate_replicas": duplicate_replicas,
            "condition_variants": len(signatures), "controlled_group": controlled,
            "pair_slots": 10, "comparable_pair_count": sum(r["comparable_conditions"] for r in pairs),
            "mean_pair_label_agreement": (sum(label_agreements) / len(label_agreements)
                                           if label_agreements else None),
            "semantic_cosine": summarize_numbers(semantic_values),
            "semantic_status": ("computed_with_local_model" if semantic_values
                                else "blocked_or_no_comparable_pairs"),
            "limitations": ["five synthetic runs do not establish LLM stability",
                            "a group is controlled only with replicas 1..5, identical config/corpus/version and five successes"],
        })
    return {"groups": summaries, "group_count": len(summaries),
            "all_groups_controlled": bool(summaries) and all(g["controlled_group"] for g in summaries),
            "pair_slots_total": len(pair_rows),
            "semantic_pairs_computed": sum(row["cosine_similarity"] is not None for row in pair_rows),
            "semantic_model": embedder.metadata if embedder is not None else None,
            "semantic_block_reason": semantic_block_reason if embedder is None else None,
            "pairing_policy": "all C(5,2)=10 replica slots per expediente/experiment",
            "interpretation_limit": "infrastructure stability is not evidence of multi-agent LLM stability"}, pair_rows


def _compare_pair(left: ExecutionRecord | None, right: ExecutionRecord | None,
                  expediente_id: str, macroproceso: str | None, experiment_id: str | None,
                  left_replica: int, right_replica: int, normative_version: str,
                  condition_conflicts: bool, embedder: EmbeddingProvider | None,
                  semantic_block_reason: str) -> dict:
    row = {"expediente_id": expediente_id, "macroproceso": macroproceso, "experiment_id": experiment_id,
           "replica_left": left_replica, "replica_right": right_replica,
           "execution_id_left": left.execution_id if left else None,
           "execution_id_right": right.execution_id if right else None,
           "normative_version": normative_version, "status": None,
           "comparable_conditions": not condition_conflicts,
           "label_agreement": None, "common_criteria": 0,
           "changed_conforming_to_nonconforming": 0,
           "changed_nonconforming_to_conforming": 0,
           "changed_to_indeterminate": 0,
           "evaluated_criteria_symmetric_difference": None,
           "omitted_criteria_symmetric_difference": None,
           "mode_changed": (left.config.effective_mode.value != right.config.effective_mode.value)
                           if left and right else None,
           "run_error_left": left.error_category.value if left and left.error_category else None,
           "run_error_right": right.error_category.value if right and right.error_category else None,
           "cosine_similarity": None, "semantic_status": None, "semantic_error": None}
    if left is None or right is None:
        row.update({"status": "missing_or_duplicate_replica",
                    "semantic_status": "not_calculable_missing_run"})
        return row
    if condition_conflicts:
        row.update({"status": "incompatible_conditions",
                    "semantic_status": "not_calculable_incompatible_conditions"})
        return row
    if left.status is ExecutionStatus.ERROR or right.status is ExecutionStatus.ERROR:
        row.update({"status": "one_or_both_runs_failed",
                    "semantic_status": "not_calculable_failed_run"})
        return row

    left_results = _result_by_criterion(left, normative_version)
    right_results = _result_by_criterion(right, normative_version)
    common = set(left_results) & set(right_results)
    row["common_criteria"] = len(common)
    if common:
        matches = sum(left_results[key].classification is right_results[key].classification for key in common)
        row["label_agreement"] = matches / len(common)
        for key in common:
            before, after = left_results[key].classification, right_results[key].classification
            if before is Classification.CONFORMING and after is Classification.NON_CONFORMING:
                row["changed_conforming_to_nonconforming"] += 1
            if before is Classification.NON_CONFORMING and after is Classification.CONFORMING:
                row["changed_nonconforming_to_conforming"] += 1
            if before is not Classification.INDETERMINATE and after is Classification.INDETERMINATE:
                row["changed_to_indeterminate"] += 1
    left_evaluated = {key for key, result in left_results.items()
                      if result.evaluation_state is EvaluationState.EVALUATED}
    right_evaluated = {key for key, result in right_results.items()
                       if result.evaluation_state is EvaluationState.EVALUATED}
    left_omitted = {key for key, result in left_results.items()
                    if result.evaluation_state is EvaluationState.SKIPPED}
    right_omitted = {key for key, result in right_results.items()
                     if result.evaluation_state is EvaluationState.SKIPPED}
    row["evaluated_criteria_symmetric_difference"] = len(left_evaluated ^ right_evaluated)
    row["omitted_criteria_symmetric_difference"] = len(left_omitted ^ right_omitted)

    left_text = left.verdict.rationale if left.verdict else ""
    right_text = right.verdict.rationale if right.verdict else ""
    if not left_text.strip() or not right_text.strip():
        row.update({"status": "missing_verdict_text", "semantic_status": "not_calculable_empty_dictamen"})
    elif embedder is None:
        row.update({"status": "structural_only", "semantic_status": semantic_block_reason})
    else:
        try:
            left_vector, right_vector = embedder.embed_pair(left_text, right_text)
            row["cosine_similarity"] = cosine_similarity(left_vector, right_vector)
            row.update({"status": "compared", "semantic_status": "computed"})
        except Exception as exc:
            row.update({"status": "semantic_error", "semantic_status": "not_calculable",
                        "semantic_error": type(exc).__name__})
    return row


def _result_by_criterion(record: ExecutionRecord, normative_version: str) -> dict:
    result = {}
    for item in record.results:
        if (item.expediente_id == record.expediente_id
                and item.execution_id == record.execution_id
                and item.normative_version == normative_version):
            key = item.criterion_id
            if key in result:
                raise ValueError("criterio duplicado dentro de una ejecución de estabilidad")
            result[key] = item
    return result
