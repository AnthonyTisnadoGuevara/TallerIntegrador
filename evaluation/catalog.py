"""Carga y validación de catálogos normativos versionados.

Los archivos JSON nunca pueden autoaprobarse. La aprobación representa una
declaración documentada de una persona autorizada y no se autentica aquí.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from enum import Enum
import hashlib
import json
from pathlib import Path


class CatalogValidationError(ValueError):
    def __init__(self, issues: list[str]):
        self.issues = tuple(issues)
        super().__init__("Catálogo inválido: " + "; ".join(issues))


class CatalogStatus(str, Enum):
    PENDING = "pendiente_validacion"
    VALIDATED = "validado_por_revision_humana"


@dataclass(frozen=True)
class NormativeCriterion:
    criterion_id: str
    official_id: str
    catalog_id: str
    normative_version: str
    official_source: str
    text: str
    applicability_rule: str
    effective_from: date | None = None
    effective_to: date | None = None

    def __post_init__(self):
        for name in ("criterion_id", "official_id", "catalog_id", "normative_version",
                     "official_source", "text", "applicability_rule"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} es obligatorio")
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("periodo de vigencia invertido")


@dataclass(frozen=True)
class NormativeCatalog:
    catalog_id: str
    normative_version: str
    official_source: str
    criteria: tuple[NormativeCriterion, ...]
    content_sha256: str
    status: CatalogStatus = CatalogStatus.PENDING
    validated_by: str | None = None
    approval_reference: str | None = None
    validated_at: datetime | None = None

    def __post_init__(self):
        for name in ("catalog_id", "normative_version", "official_source"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} es obligatorio")
        if len(self.content_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.content_sha256.lower()):
            raise ValueError("content_sha256 inválido")
        if not isinstance(self.status, CatalogStatus):
            raise ValueError("estado de catálogo inválido")
        if not self.criteria:
            raise ValueError("el catálogo debe contener criterios")
        if len({c.criterion_id for c in self.criteria}) != len(self.criteria):
            raise ValueError("criterion_id duplicado")
        if len({c.official_id for c in self.criteria}) != len(self.criteria):
            raise ValueError("official_id duplicado")
        if any((c.catalog_id, c.normative_version) != (self.catalog_id, self.normative_version)
               for c in self.criteria):
            raise ValueError("criterio de otro catálogo o versión")
        if self.status is CatalogStatus.VALIDATED:
            if not all((self.validated_by, self.approval_reference, self.validated_at)):
                raise ValueError("catálogo validado requiere revisor, referencia y fecha")
            if self.validated_at.tzinfo is None or self.validated_at.utcoffset() is None:
                raise ValueError("validated_at debe incluir zona horaria")


def _nonempty(value, path: str, errors: list[str]) -> bool:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path}: campo obligatorio ausente o inválido")
        return False
    return True


def load_catalog(path: str | Path, *, expected_sha256: str | None = None) -> NormativeCatalog:
    """Carga JSON; su estado siempre queda pendiente hasta aprobación explícita."""
    raw_bytes = Path(path).read_bytes()
    digest = hashlib.sha256(raw_bytes).hexdigest()
    if expected_sha256 is not None and digest.lower() != expected_sha256.lower():
        raise CatalogValidationError(["sha256: el contenido no coincide con el hash esperado"])
    try:
        data = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CatalogValidationError([f"JSON: contenido ilegible ({type(exc).__name__})"]) from exc
    if not isinstance(data, dict):
        raise CatalogValidationError(["$: se esperaba un objeto JSON"])

    errors: list[str] = []
    allowed_top = {"disclaimer", "catalog_id", "normative_version", "official_source",
                   "validation_status", "criteria"}
    for extra in sorted(set(data) - allowed_top):
        errors.append(f"{extra}: campo no permitido")
    required = ("catalog_id", "normative_version", "official_source", "criteria")
    for key in required:
        if key == "criteria":
            if not isinstance(data.get(key), list) or not data[key]:
                errors.append("criteria: se esperaba una lista no vacía")
        else:
            _nonempty(data.get(key), key, errors)
    # No confiar en un estado de aprobación escrito en el mismo archivo.
    if data.get("validation_status") not in (None, CatalogStatus.PENDING.value):
        errors.append("validation_status: un JSON no puede autoaprobar el catálogo")

    criteria: list[NormativeCriterion] = []
    seen_ids: set[str] = set()
    seen_official: set[str] = set()
    if isinstance(data.get("criteria"), list):
        for index, raw in enumerate(data["criteria"]):
            prefix = f"criteria[{index}]"
            if not isinstance(raw, dict):
                errors.append(f"{prefix}: se esperaba un objeto")
                continue
            allowed_criterion = {"criterion_id", "official_id", "catalog_id", "normative_version",
                                 "official_source", "text", "applicability_rule",
                                 "effective_from", "effective_to"}
            for extra in sorted(set(raw) - allowed_criterion):
                errors.append(f"{prefix}.{extra}: campo no permitido")
            fields = ("criterion_id", "official_id", "catalog_id", "normative_version",
                      "official_source", "text", "applicability_rule")
            valid = True
            for field_name in fields:
                valid = _nonempty(raw.get(field_name), f"{prefix}.{field_name}", errors) and valid
            if not valid:
                continue
            cid = raw["criterion_id"]
            oid = raw["official_id"]
            if cid in seen_ids:
                errors.append(f"{prefix}.criterion_id: identificador duplicado")
            if oid in seen_official:
                errors.append(f"{prefix}.official_id: identificador oficial duplicado")
            seen_ids.add(cid)
            seen_official.add(oid)
            if raw["catalog_id"] != data.get("catalog_id"):
                errors.append(f"{prefix}.catalog_id: no coincide con el catálogo")
            if raw["normative_version"] != data.get("normative_version"):
                errors.append(f"{prefix}.normative_version: versión incompatible")
            dates: dict[str, date | None] = {}
            for date_field in ("effective_from", "effective_to"):
                value = raw.get(date_field)
                try:
                    dates[date_field] = date.fromisoformat(value) if value else None
                except (TypeError, ValueError):
                    errors.append(f"{prefix}.{date_field}: fecha ISO inválida")
                    dates[date_field] = None
            if dates["effective_from"] and dates["effective_to"] and dates["effective_to"] < dates["effective_from"]:
                errors.append(f"{prefix}: periodo de vigencia invertido")
            criteria.append(NormativeCriterion(
                raw["criterion_id"], raw["official_id"], raw["catalog_id"],
                raw["normative_version"], raw["official_source"], raw["text"],
                raw["applicability_rule"], dates["effective_from"], dates["effective_to"]))
    if errors:
        raise CatalogValidationError(errors)
    return NormativeCatalog(data["catalog_id"], data["normative_version"],
                            data["official_source"], tuple(criteria), digest)


def approve_catalog(catalog: NormativeCatalog, *, validated_by: str,
                    approval_reference: str, validated_at: datetime) -> NormativeCatalog:
    """Registra una aprobación declarada por humano; no verifica autoridad externa."""
    if not validated_by.strip() or not approval_reference.strip():
        raise ValueError("se requieren revisor y referencia documental de aprobación")
    if validated_at.tzinfo is None or validated_at.utcoffset() is None:
        raise ValueError("validated_at debe incluir zona horaria")
    return replace(catalog, status=CatalogStatus.VALIDATED, validated_by=validated_by,
                   approval_reference=approval_reference, validated_at=validated_at)
