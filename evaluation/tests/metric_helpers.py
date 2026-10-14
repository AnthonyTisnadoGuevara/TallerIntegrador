from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from evaluation.catalog import load_catalog
from evaluation.factory import synthetic_expediente, synthetic_config
from evaluation.ground_truth import GroundTruthAnnotation, GroundTruthRecord, GroundTruthStatus
from evaluation.contracts import ReviewStatus
from evaluation.schemas import (ApplicabilityStatus, Classification, CriterionResult,
                                EffectiveMode, ErrorCategory, EvaluationState,
                                ExecutionRecord, ExecutionStatus, RunType, Verdict)


FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures"
NOW = datetime(2026, 10, 14, tzinfo=timezone.utc)


def setup_case():
    expediente = synthetic_expediente()
    catalog = load_catalog(FIXTURE_ROOT / "synthetic_catalog.json")
    config = replace(synthetic_config(), catalog_sha256=catalog.content_sha256,
                     corpus_sha256=expediente.content_sha256)
    return expediente, catalog, config


def make_ground_truth(expediente, catalog, criterion_id=None, label=Classification.NON_CONFORMING,
                      applicability=ApplicabilityStatus.APPLICABLE,
                      status=GroundTruthStatus.VALIDATED):
    criterion_id = criterion_id or catalog.criteria[0].criterion_id
    if applicability is ApplicabilityStatus.NOT_APPLICABLE:
        label = Classification.NOT_APPLICABLE
    annotation_status = ReviewStatus.REVIEWED if status is GroundTruthStatus.VALIDATED else ReviewStatus.INDIVIDUAL
    annotations = tuple(GroundTruthAnnotation(
        str(uuid4()), expediente.expediente_id, criterion_id, catalog.normative_version,
        f"synthetic-reviewer-{index}", applicability,
        label if status is GroundTruthStatus.VALIDATED else None,
        "synthetic reference verdict" if status is GroundTruthStatus.VALIDATED else None,
        (), annotation_status, NOW, "synthetic-v1", NOW if status is GroundTruthStatus.VALIDATED else None)
        for index in (1, 2) if status is GroundTruthStatus.VALIDATED)
    if status is not GroundTruthStatus.VALIDATED:
        annotations = (GroundTruthAnnotation(
            str(uuid4()), expediente.expediente_id, criterion_id, catalog.normative_version,
            "synthetic-reviewer", applicability, None, None, (), ReviewStatus.INDIVIDUAL,
            NOW, "synthetic-v1"),)
    return GroundTruthRecord(
        expediente.expediente_id, criterion_id, catalog.catalog_id,
        catalog.normative_version, annotations, status,
        final_applicability=applicability if status is GroundTruthStatus.VALIDATED else None,
        final_label=label if status is GroundTruthStatus.VALIDATED else None,
        reference_verdict="synthetic reference verdict" if status is GroundTruthStatus.VALIDATED else None,
        validated_by="synthetic-validator" if status is GroundTruthStatus.VALIDATED else None,
        validated_at=NOW if status is GroundTruthStatus.VALIDATED else None,
        validation_version="synthetic-validation-v1" if status is GroundTruthStatus.VALIDATED else None)


def make_result(expediente, catalog, config, execution_id, criterion_id=None,
                classification=Classification.NON_CONFORMING,
                state=EvaluationState.EVALUATED, rationale="synthetic criterion verdict"):
    criterion_id = criterion_id or catalog.criteria[0].criterion_id
    if state is EvaluationState.NOT_APPLICABLE:
        classification = Classification.NOT_APPLICABLE
    if state is not EvaluationState.EVALUATED and classification in (
            Classification.CONFORMING, Classification.NON_CONFORMING):
        classification = Classification.INDETERMINATE
    return CriterionResult(criterion_id, state, classification, rationale,
                           expediente_id=expediente.expediente_id,
                           catalog_id=catalog.catalog_id,
                           normative_version=catalog.normative_version,
                           execution_id=execution_id)


def make_execution(expediente, catalog, config, *, replica=1, experiment_id="SYNTH-EXP-1",
                   results=None, status=ExecutionStatus.SUCCESS, execution_id=None,
                   config_override=None, duration_ns=1_000_000_000,
                   telemetry=None, bind_result_links=True):
    execution_id = execution_id or str(uuid4())
    config = config_override or config
    results = tuple(results or ())
    if status is ExecutionStatus.SUCCESS and not results:
        results = (make_result(expediente, catalog, config, execution_id),)
    elif bind_result_links:
        results = tuple(replace(result, execution_id=execution_id,
                                expediente_id=expediente.expediente_id,
                                catalog_id=catalog.catalog_id,
                                normative_version=catalog.normative_version)
                        for result in results)
    now = NOW
    verdict = (Verdict(expediente.expediente_id, Classification.INDETERMINATE,
                       "synthetic overall verdict", results)
               if status is ExecutionStatus.SUCCESS else None)
    return ExecutionRecord(
        execution_id, expediente.expediente_id, replica, config, status,
        now, now, duration_ns, results, verdict,
        error_category=ErrorCategory.UNEXPECTED if status is ExecutionStatus.ERROR else None,
        error_type="SyntheticError" if status is ExecutionStatus.ERROR else None,
        error_message="synthetic technical failure" if status is ExecutionStatus.ERROR else None,
        telemetry=telemetry or {}, experiment_id=experiment_id)
