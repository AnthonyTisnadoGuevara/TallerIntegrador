"""Cobertura OE3 desde aplicabilidad final validada y resultado explícito."""
from __future__ import annotations

from typing import Iterable

from ..catalog import NormativeCatalog
from ..ground_truth import GroundTruthRecord, GroundTruthStatus
from ..schemas import ApplicabilityStatus, EvaluationState, ExecutionRecord, ExecutionStatus, Macroprocess
from .common import MetricInputError, RunSelection


def calculate_coverage(catalog: NormativeCatalog,
                       ground_truth: Iterable[GroundTruthRecord],
                       selection: RunSelection) -> tuple[dict, list[dict]]:
    ground_truth = tuple(ground_truth)
    gt_by_key = {}
    for record in ground_truth:
        if selection.macroproceso is not None and record.macroproceso is not selection.macroproceso:
            continue
        if selection.macroproceso is None and record.macroproceso is not None:
            continue
        key = (record.expediente_id, record.criterion_id, record.normative_version)
        if key in gt_by_key:
            raise MetricInputError("Ground Truth duplicado para cobertura")
        gt_by_key[key] = record
    rows: list[dict] = []
    total_applicable = total_evaluated = omitted = not_evaluable = 0
    applicability_unknown = not_applicable = technical_errors = insufficient = 0
    for exp_id, execution in sorted(selection.selected_by_expediente.items()):
        for criterion in catalog.criteria:
            key = (exp_id, criterion.criterion_id, catalog.normative_version)
            gt = gt_by_key.get(key)
            base = {"expediente_id": exp_id, "macroproceso": selection.macroproceso.value if selection.macroproceso else None, "criterion_id": criterion.criterion_id,
                    "catalog_id": catalog.catalog_id,
                    "normative_version": catalog.normative_version,
                    "execution_id": execution.execution_id,
                    "experiment_id": selection.experiment_id, "replica": execution.replica,
                    "execution_status": execution.status.value,
                    "applicability": None, "evaluation_state": None,
                    "coverage_counted": False, "reason": None}
            if gt is None:
                insufficient += 1
                rows.append({**base, "reason": "validated_applicability_reference_missing"})
                continue
            if gt.status is not GroundTruthStatus.VALIDATED:
                insufficient += 1
                rows.append({**base, "applicability": gt.final_applicability.value if gt.final_applicability else None,
                             "reason": f"ground_truth_not_validated:{gt.status.value}"})
                continue
            if gt.catalog_id != catalog.catalog_id or gt.normative_version != catalog.normative_version:
                raise MetricInputError("Ground Truth usa catálogo/version incompatible")
            applicability = gt.final_applicability
            base["applicability"] = applicability.value
            if applicability is ApplicabilityStatus.UNDETERMINED:
                applicability_unknown += 1
                rows.append({**base, "reason": "applicability_undetermined"})
                continue
            if applicability is ApplicabilityStatus.NOT_APPLICABLE:
                not_applicable += 1
                rows.append({**base, "reason": "documented_not_applicable"})
                continue

            total_applicable += 1
            if execution.status is ExecutionStatus.ERROR:
                technical_errors += 1
                rows.append({**base, "reason": f"execution_error:{execution.error_category.value}"})
                continue
            candidates = [item for item in execution.results
                          if item.criterion_id == criterion.criterion_id
                          and item.normative_version == catalog.normative_version]
            if len(candidates) > 1:
                raise MetricInputError("resultado duplicado para criterio/versión en cobertura")
            result = candidates[0] if candidates else None
            if result is None:
                omitted += 1
                rows.append({**base, "reason": "criterion_omitted_from_output"})
                continue
            base["evaluation_state"] = result.evaluation_state.value
            linked = (result.expediente_id == exp_id
                      and result.execution_id == execution.execution_id
                      and result.macroproceso == selection.macroproceso
                      and result.catalog_id == catalog.catalog_id
                      and result.normative_version == catalog.normative_version
                      and bool(result.rationale.strip()))
            if not linked:
                insufficient += 1
                rows.append({**base, "reason": "analysis_record_missing_required_links"})
            elif result.evaluation_state is EvaluationState.EVALUATED:
                total_evaluated += 1
                rows.append({**base, "coverage_counted": True,
                             "reason": "explicit_evaluated_result"})
            elif result.evaluation_state is EvaluationState.NOT_EVALUABLE:
                not_evaluable += 1
                rows.append({**base, "reason": "criterion_not_evaluable"})
            elif result.evaluation_state is EvaluationState.SKIPPED:
                omitted += 1
                rows.append({**base, "reason": "criterion_skipped"})
            else:
                technical_errors += 1
                rows.append({**base, "reason": "applicability_result_conflicts_with_reference"})

    summary = {
        "experiment_id": selection.experiment_id,
        "selection_policy": "replica=1 for each expediente in one explicit/unique experiment",
        "catalog_id": catalog.catalog_id,
        "normative_version": catalog.normative_version,
        "criteria_in_catalog": len(catalog.criteria),
        "expedientes": len(selection.selected_by_expediente),
        "total_applicable": total_applicable,
        "explicitly_evaluated": total_evaluated,
        "omitted": omitted,
        "not_evaluable": not_evaluable,
        "applicability_undetermined": applicability_unknown,
        "documented_not_applicable": not_applicable,
        "technical_errors": technical_errors,
        "insufficient_or_unvalidated_records": insufficient,
        "coverage_percent": 100.0 * total_evaluated / total_applicable if total_applicable else None,
        "undefined_reason": "no validated applicable criteria" if not total_applicable else None,
        "definition": "explicitly_evaluated / validated_applicable * 100",
        "coverage_is_not_compliance": True,
        "selection_exclusions": list(selection.exclusions),
    }
    return summary, rows
