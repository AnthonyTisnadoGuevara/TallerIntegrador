"""Cálculo binario de OE1 con abstenciones y exclusiones explícitas."""
from __future__ import annotations

from typing import Iterable

from ..ground_truth import GroundTruthRecord
from ..schemas import (ApplicabilityStatus, Classification, EvaluationState,
                       ExecutionStatus)
from .common import (MetricInputError, RunSelection, index_final_ground_truth,
                     result_index)


POSITIVE = Classification.NON_CONFORMING
NEGATIVE = Classification.CONFORMING


def calculate_precision_f1(ground_truth: Iterable[GroundTruthRecord],
                           selection: RunSelection) -> tuple[dict, list[dict]]:
    ground_truth = tuple(ground_truth)
    references, excluded_refs = index_final_ground_truth(ground_truth, selection.macroproceso)
    detail: list[dict] = []
    tp = fp = tn = fn = abstentions = 0
    excluded_cases: list[dict] = list(excluded_refs)
    predictions_by_exp = {
        expediente_id: result_index(execution)
        for expediente_id, execution in selection.selected_by_expediente.items()
    }

    for (expediente_id, criterion_id, normative_version), reference in sorted(references.items()):
        identity = {"expediente_id": expediente_id, "macroproceso": reference.macroproceso.value if reference.macroproceso else None, "criterion_id": criterion_id,
                    "normative_version": normative_version}
        if reference.final_applicability is not ApplicabilityStatus.APPLICABLE:
            reason = ("reference_not_applicable" if reference.final_applicability is ApplicabilityStatus.NOT_APPLICABLE
                      else "reference_applicability_undetermined")
            excluded_cases.append({**identity, "reason": reason})
            detail.append({**identity, "case_status": "excluded", "reason": reason,
                           "reference": reference.final_label.value, "prediction": None})
            continue
        if reference.final_label not in (POSITIVE, NEGATIVE):
            reason = "reference_label_not_binary"
            excluded_cases.append({**identity, "reason": reason})
            detail.append({**identity, "case_status": "excluded", "reason": reason,
                           "reference": reference.final_label.value, "prediction": None})
            continue

        execution = selection.selected_by_expediente.get(expediente_id)
        result = predictions_by_exp.get(expediente_id, {}).get(
            (expediente_id, criterion_id, normative_version))
        abstention_reason = None
        if execution is None:
            abstention_reason = "primary_execution_missing"
        elif execution.status is ExecutionStatus.ERROR:
            abstention_reason = f"execution_failed:{execution.error_category.value}"
        elif result is None:
            abstention_reason = "prediction_missing_or_version_unlinked"
        elif (result.evaluation_state is not EvaluationState.EVALUATED
              or result.classification not in (POSITIVE, NEGATIVE)):
            abstention_reason = f"prediction_abstention:{result.evaluation_state.value}:{result.classification.value}"

        predicted = result.classification if result is not None and abstention_reason is None else None
        outcome = "abstention"
        if predicted is None:
            abstentions += 1
            excluded_cases.append({**identity, "execution_id": execution.execution_id if execution else None,
                                   "reason": abstention_reason or "prediction_unavailable"})
        elif reference.final_label is POSITIVE and predicted is POSITIVE:
            tp += 1
            outcome = "TP"
        elif reference.final_label is NEGATIVE and predicted is POSITIVE:
            fp += 1
            outcome = "FP"
        elif reference.final_label is NEGATIVE and predicted is NEGATIVE:
            tn += 1
            outcome = "TN"
        else:
            fn += 1
            outcome = "FN"
        detail.append({**identity, "execution_id": execution.execution_id if execution else None,
                       "experiment_id": selection.experiment_id,
                       "replica": execution.replica if execution else None,
                       "case_status": "abstention" if predicted is None else "evaluated",
                       "outcome": outcome, "reason": abstention_reason,
                       "reference": reference.final_label.value,
                       "prediction": predicted.value if predicted else None})

    evaluated = tp + fp + tn + fn
    precision_denominator = tp + fp
    recall_denominator = tp + fn
    f1_denominator = 2 * tp + fp + fn
    eligible = evaluated + abstentions
    summary = {
        "experiment_id": selection.experiment_id,
        "selection_policy": "exactly replica=1 for each expediente in one explicit/unique experiment",
        "loaded_ground_truth_records": len(ground_truth),
        "eligible_reference_cases": eligible,
        "evaluated_cases": evaluated,
        "abstentions": abstentions,
        "abstention_rate": abstentions / eligible if eligible else None,
        "confusion_matrix": {"positive": "no_conforme", "negative": "conforme",
                             "tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "precision": tp / precision_denominator if precision_denominator else None,
        "recall": tp / recall_denominator if recall_denominator else None,
        "f1": 2 * tp / f1_denominator if f1_denominator else None,
        "undefined_metric_policy": "null if its denominator is zero; abstentions remain in their own count",
        "abstention_interpretation": "classification metrics are conditional on evaluable cases; report abstention_rate alongside them",
        "excluded_cases": excluded_cases,
        "selection_exclusions": list(selection.exclusions),
        "selected_execution_failures": sum(
            record.status is ExecutionStatus.ERROR
            for record in selection.selected_by_expediente.values()),
    }
    return summary, detail
