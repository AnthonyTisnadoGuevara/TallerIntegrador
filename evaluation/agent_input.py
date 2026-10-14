"""Allowlist de entrada del agente. Este módulo no importa Ground Truth."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from .catalog import CatalogStatus, NormativeCatalog
from .contracts import ApplicabilityRecord
from .schemas import DocumentReference, Expediente, Macroprocess


class AgentInputValidationError(ValueError):
    pass


@dataclass(frozen=True)
class AgentInput:
    expediente: Expediente
    catalog: NormativeCatalog
    authorized_rules: tuple[str, ...]
    applicability_records: tuple[ApplicabilityRecord, ...] = ()
    macroproceso: Macroprocess | None = None

    def __post_init__(self):
        if self.catalog.status is not CatalogStatus.VALIDATED:
            raise AgentInputValidationError("solo se puede entregar al agente un catálogo aprobado")
        if not self.authorized_rules or any(not rule.strip() for rule in self.authorized_rules):
            raise AgentInputValidationError("se requieren reglas autorizadas no vacías")
        if self.macroproceso is not None and self.macroproceso not in self.expediente.macroprocesos:
            raise AgentInputValidationError("macroproceso no asociado al expediente")
        if len(self.expediente.macroprocesos) > 1 and self.macroproceso is None:
            raise AgentInputValidationError("debe seleccionar macroproceso para este expediente")
        doc_ids = {doc.document_id for doc in self.expediente.documents}
        criterion_ids = {criterion.criterion_id for criterion in self.catalog.criteria}
        seen = set()
        for record in self.applicability_records:
            if (record.expediente_id, record.catalog_id, record.normative_version) != (
                    self.expediente.expediente_id, self.catalog.catalog_id, self.catalog.normative_version):
                raise AgentInputValidationError("registro de aplicabilidad incompatible con la entrada")
            if record.macroproceso is not None and record.macroproceso not in self.expediente.macroprocesos:
                raise AgentInputValidationError("aplicabilidad de otro macroproceso")
            if self.macroproceso is not None and record.macroproceso is not self.macroproceso:
                raise AgentInputValidationError("aplicabilidad de otro macroproceso")
            if record.criterion_id not in criterion_ids:
                raise AgentInputValidationError("aplicabilidad refiere criterio inexistente")
            key = record.criterion_id
            if key in seen:
                raise AgentInputValidationError("aplicabilidad duplicada para criterio")
            seen.add(key)
            if any(ev.document_id not in doc_ids for ev in record.evidence):
                raise AgentInputValidationError("aplicabilidad refiere documento ajeno al expediente")


_ALLOWED_TOP_LEVEL = {"expediente", "catalog", "authorized_rules", "applicability_records"}
_FORBIDDEN_KEYS = {"ground_truth", "reference_label", "reference_verdict", "adjudication",
                   "disagreement_resolution", "evaluator_id", "validated_by"}


def validate_agent_payload_shape(payload: dict[str, Any]) -> None:
    """Rechaza campos extra y claves de referencia en cualquier nivel."""
    if not isinstance(payload, dict) or set(payload) not in (
            _ALLOWED_TOP_LEVEL, _ALLOWED_TOP_LEVEL | {"macroproceso"}):
        raise AgentInputValidationError("entrada del agente contiene campos ausentes o no permitidos")
    if payload.get("macroproceso") is not None:
        try:
            Macroprocess(payload["macroproceso"])
        except (ValueError, TypeError) as exc:
            raise AgentInputValidationError("macroproceso desconocido en entrada") from exc
    def walk(value):
        if isinstance(value, dict):
            if any(str(key).lower() in _FORBIDDEN_KEYS for key in value):
                raise AgentInputValidationError("entrada del agente contiene campos exclusivos de evaluación")
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(payload)


def build_agent_input(expediente: Expediente, catalog: NormativeCatalog,
                      authorized_rules: tuple[str, ...],
                      applicability_records: tuple[ApplicabilityRecord, ...] = (),
                      macroproceso: Macroprocess | str | None = None) -> AgentInput:
    # Construcción mediante tipos allowlist; no acepta un objeto arbitrario ni Ground Truth.
    if not isinstance(expediente, Expediente) or not all(isinstance(d, DocumentReference) for d in expediente.documents):
        raise AgentInputValidationError("expediente no cumple contrato")
    if not isinstance(catalog, NormativeCatalog):
        raise AgentInputValidationError("catálogo no cumple contrato")
    if isinstance(macroproceso, str):
        try:
            macroproceso = Macroprocess(macroproceso)
        except ValueError as exc:
            raise AgentInputValidationError("macroproceso desconocido") from exc
    if macroproceso is None and len(expediente.macroprocesos) == 1:
        macroproceso = expediente.macroprocesos[0]
    return AgentInput(expediente, catalog, authorized_rules, applicability_records, macroproceso)
