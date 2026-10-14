"""Esquemas autocontenidos para ejecuciones experimentales locales.

Usa dataclasses y validaciones explícitas para no añadir dependencias al backend.
Los localizadores identifican documentos; nunca se registra su contenido completo.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import re
from typing import Any


class EvaluationState(str, Enum):
    EVALUATED = "evaluado"
    SKIPPED = "omitido"
    NOT_EVALUABLE = "no_evaluable"
    NOT_APPLICABLE = "no_aplicable"


class Classification(str, Enum):
    CONFORMING = "conforme"
    NON_CONFORMING = "no_conforme"
    INDETERMINATE = "indeterminado"
    NOT_APPLICABLE = "no_aplicable"


class RunType(str, Enum):
    SYNTHETIC = "sintetico"
    PILOT = "piloto"
    FINAL = "final"


class EffectiveMode(str, Enum):
    SYNTHETIC = "sintetico"
    MOCK = "simulado"
    PROVIDER_LLM = "llm_proveedor"
    RULES_FALLBACK = "fallback_reglas"
    UNKNOWN = "desconocido"


class ExecutionStatus(str, Enum):
    SUCCESS = "completado"
    ERROR = "error"


class ErrorCategory(str, Enum):
    INPUT_VALIDATION = "validacion_entrada"
    DOCUMENT_READ = "lectura_documento"
    AGENT = "agente"
    LLM_PROVIDER = "proveedor_llm"
    TIMEOUT = "tiempo_limite"
    PERSISTENCE = "persistencia"
    INCOMPLETE_OUTPUT = "salida_incompleta"
    UNEXPECTED = "inesperado"


class ApplicabilityStatus(str, Enum):
    APPLICABLE = "aplicable"
    NOT_APPLICABLE = "no_aplicable"
    UNDETERMINED = "indeterminado"


class Macroprocess(str, Enum):
    PLANNING = "planificacion_estrategica"
    ACADEMIC = "gestion_academica"
    SYLLABUS = "gestion_silabos"


class MacroprocessAggregationPolicy(str, Enum):
    SEPARATE = "separado_por_macroproceso"
    APPROVED_AGGREGATION = "agregacion_aprobada"


@dataclass(frozen=True, order=True)
class EvaluationKey:
    expediente_id: str
    macroproceso: Macroprocess
    criterion_id: str
    normative_version: str

    def __post_init__(self) -> None:
        for name in ("expediente_id", "criterion_id", "normative_version"):
            _required(getattr(self, name), name)
        if not isinstance(self.macroproceso, Macroprocess):
            raise ValueError("macroproceso desconocido")


def _required(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} es obligatorio")


def _sha256(value: str | None, name: str, *, optional: bool = False) -> None:
    if value is None and optional:
        return
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", value):
        raise ValueError(f"{name} debe ser un SHA-256 hexadecimal de 64 caracteres")


def _aware_utc(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} debe incluir zona horaria")


@dataclass(frozen=True)
class DocumentReference:
    document_id: str
    name: str
    format: str
    sha256: str
    version: str
    locator: str

    def __post_init__(self) -> None:
        for name in ("document_id", "name", "format", "version", "locator"):
            _required(getattr(self, name), name)
        _sha256(self.sha256, "sha256")


@dataclass(frozen=True)
class Expediente:
    expediente_id: str
    corpus_id: str
    documents: tuple[DocumentReference, ...]
    document_version: str
    content_sha256: str
    source: str = "sintetico"
    source_system_reference: str | None = None
    macroprocesos: tuple[Macroprocess, ...] = ()

    def __post_init__(self) -> None:
        for name in ("expediente_id", "corpus_id", "document_version", "source"):
            _required(getattr(self, name), name)
        _sha256(self.content_sha256, "content_sha256")
        if not self.documents:
            raise ValueError("el expediente debe referenciar al menos un documento")
        ids = [doc.document_id for doc in self.documents]
        if len(ids) != len(set(ids)):
            raise ValueError("document_id duplicado en el expediente")
        if any(not isinstance(item, Macroprocess) for item in self.macroprocesos):
            raise ValueError("macroproceso desconocido en expediente")
        if len(self.macroprocesos) != len(set(self.macroprocesos)):
            raise ValueError("macroproceso duplicado en expediente")


@dataclass(frozen=True)
class Criterion:
    criterion_id: str
    catalog_id: str
    catalog_version: str
    text: str
    applicability_rule: str
    applicability: str = "indeterminada"
    source_reference: str | None = None

    def __post_init__(self) -> None:
        for name in ("criterion_id", "catalog_id", "catalog_version", "text", "applicability_rule"):
            _required(getattr(self, name), name)
        if self.applicability not in {"aplicable", "no_aplicable", "indeterminada"}:
            raise ValueError("estado de aplicabilidad inválido")


@dataclass(frozen=True)
class Evidence:
    document_id: str
    evidence_type: str
    locator: str | None = None
    page: int | None = None
    section: str | None = None
    excerpt_reference: str | None = None
    absence_reason: str | None = None
    expediente_id: str | None = None
    location_status: str | None = None

    def __post_init__(self) -> None:
        _required(self.document_id, "document_id")
        _required(self.evidence_type, "evidence_type")
        if self.page is not None and self.page < 1:
            raise ValueError("page debe ser mayor o igual a 1")
        if self.locator is None and self.absence_reason is None:
            raise ValueError("indique locator o absence_reason para la evidencia")
        if self.location_status is not None and self.location_status not in {"localizado", "no_localizado", "no_verificable"}:
            raise ValueError("location_status inválido")


@dataclass(frozen=True)
class CriterionResult:
    criterion_id: str
    evaluation_state: EvaluationState
    classification: Classification
    rationale: str
    evidence: tuple[Evidence, ...] = ()
    expediente_id: str | None = None
    catalog_id: str | None = None
    normative_version: str | None = None
    execution_id: str | None = None
    macroproceso: Macroprocess | None = None

    def __post_init__(self) -> None:
        _required(self.criterion_id, "criterion_id")
        _required(self.rationale, "rationale")
        if self.macroproceso is not None and not isinstance(self.macroproceso, Macroprocess):
            raise ValueError("macroproceso desconocido en resultado")
        if not isinstance(self.evaluation_state, EvaluationState) or not isinstance(self.classification, Classification):
            raise ValueError("estado de evaluación o clasificación inválido")
        if self.evaluation_state is EvaluationState.NOT_APPLICABLE and self.classification is not Classification.NOT_APPLICABLE:
            raise ValueError("criterio no aplicable debe clasificarse como no_aplicable")
        if self.evaluation_state is not EvaluationState.EVALUATED and self.classification in {Classification.CONFORMING, Classification.NON_CONFORMING}:
            raise ValueError("un resultado no evaluado no puede concluir conformidad")


@dataclass(frozen=True)
class Verdict:
    expediente_id: str
    overall_classification: Classification
    rationale: str
    criterion_results: tuple[CriterionResult, ...]
    format_version: str = "1"
    reference: str | None = None

    def __post_init__(self) -> None:
        _required(self.expediente_id, "expediente_id")
        _required(self.rationale, "rationale")
        _required(self.format_version, "format_version")
        if not isinstance(self.overall_classification, Classification):
            raise ValueError("overall_classification inválida")
        if not self.criterion_results:
            raise ValueError("dictamen debe incluir resultados por criterio")


@dataclass(frozen=True)
class ExperimentConfig:
    config_id: str
    code_sha256: str
    python_version: str
    dependency_versions: dict[str, str]
    provider: str | None
    model: str | None
    model_version: str | None
    model_version_reason: str | None
    temperature: float | None
    seed: int | None
    generation_null_reason: str | None
    prompt_sha256: str
    catalog_sha256: str
    corpus_sha256: str
    run_type: RunType = RunType.SYNTHETIC
    effective_mode: EffectiveMode = EffectiveMode.SYNTHETIC
    external_calls_enabled: bool = False
    business_writes_enabled: bool = False
    macroprocess_aggregation_policy: MacroprocessAggregationPolicy = MacroprocessAggregationPolicy.SEPARATE
    aggregation_approval_reference: str | None = None

    def __post_init__(self) -> None:
        for name in ("config_id", "python_version"):
            _required(getattr(self, name), name)
        for name in ("code_sha256", "prompt_sha256", "catalog_sha256", "corpus_sha256"):
            _sha256(getattr(self, name), name)
        if self.temperature is None and not self.generation_null_reason:
            raise ValueError("explique por qué temperature no está configurada")
        if self.seed is None and not self.generation_null_reason:
            raise ValueError("explique por qué seed no está configurada")
        if self.temperature is not None and self.temperature < 0:
            raise ValueError("temperature no puede ser negativa")
        if not isinstance(self.macroprocess_aggregation_policy, MacroprocessAggregationPolicy):
            raise ValueError("polÃ­tica de agregaciÃ³n de macroprocesos invÃ¡lida")
        if (self.macroprocess_aggregation_policy is MacroprocessAggregationPolicy.APPROVED_AGGREGATION
                and not (self.aggregation_approval_reference or "").strip()):
            raise ValueError("la agregaciÃ³n requiere aprobaciÃ³n metodolÃ³gica documentada")


@dataclass(frozen=True)
class ExecutionRecord:
    execution_id: str
    expediente_id: str
    replica: int
    config: ExperimentConfig
    status: ExecutionStatus
    started_at: datetime
    finished_at: datetime
    duration_ns: int
    results: tuple[CriterionResult, ...] = ()
    verdict: Verdict | None = None
    error_category: ErrorCategory | None = None
    error_type: str | None = None
    error_message: str | None = None
    telemetry: dict[str, Any] = field(default_factory=dict)
    experiment_id: str | None = None
    macroproceso: Macroprocess | None = None

    def __post_init__(self) -> None:
        _required(self.execution_id, "execution_id")
        _required(self.expediente_id, "expediente_id")
        if not isinstance(self.status, ExecutionStatus):
            raise ValueError("status de ejecución inválido")
        if self.replica < 1:
            raise ValueError("replica debe ser >= 1")
        if self.macroproceso is not None and not isinstance(self.macroproceso, Macroprocess):
            raise ValueError("macroproceso desconocido en ejecucion")
        _aware_utc(self.started_at, "started_at")
        _aware_utc(self.finished_at, "finished_at")
        if self.finished_at < self.started_at:
            raise ValueError("finished_at no puede ser anterior a started_at")
        if self.duration_ns < 0:
            raise ValueError("duration_ns no puede ser negativo")
        if self.status is ExecutionStatus.SUCCESS and (not self.results or self.verdict is None):
            raise ValueError("ejecución completada requiere resultados y dictamen")
        if self.status is ExecutionStatus.ERROR and self.error_category is None:
            raise ValueError("ejecución fallida requiere categoría de error")
        if self.verdict is not None and self.verdict.expediente_id != self.expediente_id:
            raise ValueError("el dictamen debe corresponder al expediente de la ejecución")
        for result in self.results:
            if result.expediente_id is not None and result.expediente_id != self.expediente_id:
                raise ValueError("resultado vinculado a otro expediente")
            if result.execution_id is not None and result.execution_id != self.execution_id:
                raise ValueError("resultado vinculado a otra ejecución")


def to_primitive(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if is_dataclass(value):
        return {key: to_primitive(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): to_primitive(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_primitive(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(to_primitive(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
