"""Modelos de anotación humana y adjudicación, separados de la entrada del agente."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .contracts import EvidenceReference, ReviewStatus
from .schemas import ApplicabilityStatus, Classification, Macroprocess, _required


class GroundTruthStatus(str, Enum):
    DRAFT = "borrador"
    IN_REVIEW = "en_revision"
    DISAGREEMENT = "desacuerdo"
    ADJUDICATED = "adjudicado"
    VALIDATED = "referencia_final_validada"


@dataclass(frozen=True)
class GroundTruthAnnotation:
    annotation_id: str
    expediente_id: str
    criterion_id: str
    normative_version: str
    evaluator_id: str
    applicability: ApplicabilityStatus
    reference_label: Classification | None
    reference_verdict: str | None
    evidence: tuple[EvidenceReference, ...]
    review_status: ReviewStatus
    annotated_at: datetime
    annotation_version: str
    reviewed_at: datetime | None = None
    macroproceso: Macroprocess | None = None

    def __post_init__(self):
        for field in ("annotation_id", "expediente_id", "criterion_id", "normative_version",
                      "evaluator_id", "annotation_version"):
            _required(getattr(self, field), field)
        _aware(self.annotated_at, "annotated_at")
        if self.macroproceso is not None and not isinstance(self.macroproceso, Macroprocess):
            raise ValueError("macroproceso de anotación desconocido")
        if not isinstance(self.review_status, ReviewStatus):
            raise ValueError("review_status inválido")
        if not isinstance(self.applicability, ApplicabilityStatus):
            raise ValueError("applicability inválida")
        if self.reference_label is not None and not isinstance(self.reference_label, Classification):
            raise ValueError("reference_label inválida")
        if self.review_status is ReviewStatus.REVIEWED:
            if self.reviewed_at is None:
                raise ValueError("anotación revisada requiere reviewed_at")
            _aware(self.reviewed_at, "reviewed_at")
            if self.reference_label is None or not self.reference_verdict:
                raise ValueError("anotación revisada requiere etiqueta y dictamen")
        if self.applicability is ApplicabilityStatus.NOT_APPLICABLE and self.reference_label not in (None, Classification.NOT_APPLICABLE):
            raise ValueError("criterio no aplicable no admite etiqueta de conformidad")
        if self.applicability is ApplicabilityStatus.UNDETERMINED and self.reference_label in (Classification.CONFORMING, Classification.NON_CONFORMING):
            raise ValueError("aplicabilidad indeterminada no admite etiqueta binaria")
        if any(ev.expediente_id != self.expediente_id for ev in self.evidence):
            raise ValueError("evidencia de anotación pertenece a otro expediente")


@dataclass(frozen=True)
class DisagreementResolution:
    annotation_ids: tuple[str, ...]
    resolved_applicability: ApplicabilityStatus
    resolved_label: Classification | None
    rationale: str
    adjudicator_id: str
    resolved_at: datetime

    def __post_init__(self):
        if len(set(self.annotation_ids)) < 2:
            raise ValueError("resolución requiere al menos dos anotaciones distintas")
        for field in ("rationale", "adjudicator_id"):
            _required(getattr(self, field), field)
        _aware(self.resolved_at, "resolved_at")
        if not isinstance(self.resolved_applicability, ApplicabilityStatus):
            raise ValueError("resolved_applicability inválida")
        if self.resolved_label is not None and not isinstance(self.resolved_label, Classification):
            raise ValueError("resolved_label inválida")
        if self.resolved_applicability is ApplicabilityStatus.NOT_APPLICABLE and self.resolved_label not in (None, Classification.NOT_APPLICABLE):
            raise ValueError("resolución no aplicable no puede ser conforme/no conforme")
        if self.resolved_applicability is ApplicabilityStatus.UNDETERMINED and self.resolved_label in (Classification.CONFORMING, Classification.NON_CONFORMING):
            raise ValueError("resolución indeterminada no admite etiqueta binaria")


@dataclass(frozen=True)
class GroundTruthRecord:
    expediente_id: str
    criterion_id: str
    catalog_id: str
    normative_version: str
    annotations: tuple[GroundTruthAnnotation, ...]
    status: GroundTruthStatus = GroundTruthStatus.DRAFT
    disagreement_resolution: DisagreementResolution | None = None
    final_applicability: ApplicabilityStatus | None = None
    final_label: Classification | None = None
    reference_verdict: str | None = None
    validated_by: str | None = None
    validated_at: datetime | None = None
    validation_version: str | None = None
    macroproceso: Macroprocess | None = None

    def __post_init__(self):
        for field in ("expediente_id", "criterion_id", "catalog_id", "normative_version"):
            _required(getattr(self, field), field)
        if not isinstance(self.status, GroundTruthStatus):
            raise ValueError("status Ground Truth inválido")
        if self.macroproceso is not None and not isinstance(self.macroproceso, Macroprocess):
            raise ValueError("macroproceso de Ground Truth desconocido")
        if not self.annotations:
            raise ValueError("Ground Truth requiere al menos una anotación independiente")
        ids = [a.annotation_id for a in self.annotations]
        if len(ids) != len(set(ids)):
            raise ValueError("annotation_id duplicado")
        if any((a.expediente_id, a.criterion_id, a.normative_version, a.macroproceso) !=
               (self.expediente_id, self.criterion_id, self.normative_version, self.macroproceso)
               for a in self.annotations):
            raise ValueError("anotaciones mezclan expediente, macroproceso, criterio o versión normativa")
        evaluator_ids = [a.evaluator_id for a in self.annotations]
        if len(evaluator_ids) != len(set(evaluator_ids)):
            raise ValueError("las anotaciones deben ser independientes por evaluador")
        if self.status is GroundTruthStatus.ADJUDICATED and self.disagreement_resolution is None:
            raise ValueError("estado adjudicado requiere resolución documentada")
        if self.status is GroundTruthStatus.VALIDATED and self.disagreement_resolution is not None:
            if not set(self.disagreement_resolution.annotation_ids).issubset(set(ids)):
                raise ValueError("resolución refiere anotación inexistente")
            if (self.final_applicability, self.final_label) != (
                    self.disagreement_resolution.resolved_applicability,
                    self.disagreement_resolution.resolved_label):
                raise ValueError("decisión final no coincide con la resolución")
        if self.status is GroundTruthStatus.DISAGREEMENT and self.disagreement_resolution is not None:
            raise ValueError("registro con desacuerdo no puede tener resolución marcada como pendiente")
        if self.status is GroundTruthStatus.VALIDATED:
            if len(self.annotations) < 2 or any(a.review_status is not ReviewStatus.REVIEWED for a in self.annotations):
                raise ValueError("referencia validada requiere al menos dos anotaciones revisadas")
            if not all((self.final_applicability, self.final_label, self.reference_verdict,
                        self.validated_by, self.validated_at, self.validation_version)):
                raise ValueError("referencia validada incompleta")
            if self.validated_at is None:
                raise ValueError("validated_at obligatorio")
            _aware(self.validated_at, "validated_at")
            if not isinstance(self.final_applicability, ApplicabilityStatus):
                raise ValueError("final_applicability inválida")
            if not isinstance(self.final_label, Classification):
                raise ValueError("final_label inválida")
            if self.final_applicability is ApplicabilityStatus.NOT_APPLICABLE and self.final_label not in (None, Classification.NOT_APPLICABLE):
                raise ValueError("referencia no aplicable no puede etiquetarse como conforme/no conforme")
            if self.final_applicability is ApplicabilityStatus.UNDETERMINED and self.final_label in (Classification.CONFORMING, Classification.NON_CONFORMING):
                raise ValueError("aplicabilidad indeterminada no admite etiqueta binaria")
            if self.status is GroundTruthStatus.VALIDATED and _has_disagreement(self.annotations) and self.disagreement_resolution is None:
                raise ValueError("desacuerdo debe resolverse antes de validar Ground Truth")


def _aware(value: datetime, name: str):
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} debe incluir zona horaria")


def _has_disagreement(annotations: tuple[GroundTruthAnnotation, ...]) -> bool:
    return len({(a.applicability, a.reference_label) for a in annotations}) > 1


def has_disagreement(record: GroundTruthRecord) -> bool:
    return _has_disagreement(record.annotations)
