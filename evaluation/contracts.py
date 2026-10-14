"""Contratos de aplicabilidad y referencias documentales normativas."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

from .schemas import ApplicabilityStatus, Macroprocess, _required


class ReviewStatus(str, Enum):
    PENDING = "pendiente"
    INDIVIDUAL = "anotacion_individual"
    REVIEWED = "revisado"


class LocationStatus(str, Enum):
    LOCATED = "localizado"
    NOT_LOCATED = "no_localizado"
    NOT_VERIFIABLE = "no_verificable"


@dataclass(frozen=True)
class EvidenceReference:
    expediente_id: str
    document_id: str
    location_status: LocationStatus
    locator: str | None = None
    page: int | None = None
    section: str | None = None
    excerpt_reference: str | None = None
    limitation: str | None = None

    def __post_init__(self):
        _required(self.expediente_id, "expediente_id")
        _required(self.document_id, "document_id")
        if not isinstance(self.location_status, LocationStatus):
            raise ValueError("location_status inválido")
        if self.location_status is LocationStatus.LOCATED and not self.locator:
            raise ValueError("evidencia localizada requiere locator")
        if self.location_status is not LocationStatus.LOCATED and not self.limitation:
            raise ValueError("evidencia no localizada requiere registrar limitación")
        if self.page is not None and self.page < 1:
            raise ValueError("page debe ser >= 1")


@dataclass(frozen=True)
class ApplicabilityRecord:
    expediente_id: str
    criterion_id: str
    catalog_id: str
    normative_version: str
    status: ApplicabilityStatus
    justification: str
    review_status: ReviewStatus
    evidence: tuple[EvidenceReference, ...] = ()
    macroproceso: Macroprocess | None = None

    def __post_init__(self):
        for name in ("expediente_id", "criterion_id", "catalog_id", "normative_version", "justification"):
            _required(getattr(self, name), name)
        if self.macroproceso is not None and not isinstance(self.macroproceso, Macroprocess):
            raise ValueError("macroproceso de aplicabilidad desconocido")
        if not isinstance(self.status, ApplicabilityStatus) or not isinstance(self.review_status, ReviewStatus):
            raise ValueError("estado de aplicabilidad o revisión inválido")
        if self.status is ApplicabilityStatus.UNDETERMINED and self.review_status is ReviewStatus.REVIEWED and not self.justification.strip():
            raise ValueError("aplicabilidad indeterminada revisada requiere justificación")
        if any(item.expediente_id != self.expediente_id for item in self.evidence):
            raise ValueError("evidencia de aplicabilidad pertenece a otro expediente")
