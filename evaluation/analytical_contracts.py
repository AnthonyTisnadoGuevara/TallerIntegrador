"""Registro separado para salidas analíticas originales, no normativas."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .schemas import Expediente, Macroprocess, _required


class AnalyticalStatus(str, Enum):
    COMPLETED = "completado"
    ERROR = "error"
    UNAVAILABLE = "no_disponible"


class AnalyticalKind(str, Enum):
    ORIGINAL_ANALYTICAL = "analisis_original"
    NORMATIVE_BY_CRITERION = "normativo_por_criterio"


@dataclass(frozen=True)
class AnalyticalInput:
    expediente: Expediente
    macroproceso: Macroprocess
    document_ids: tuple[str, ...]
    text: str
    metadata: dict[str, Any]
    provenance: dict[str, Any] = field(default_factory=lambda: {"source": "synthetic_local"})

    def __post_init__(self) -> None:
        if not isinstance(self.expediente, Expediente):
            raise ValueError("expediente no cumple el contrato experimental")
        if self.expediente.source != "sintetico":
            raise ValueError("este adaptador solo admite expedientes sintéticos")
        if not isinstance(self.macroproceso, Macroprocess):
            raise ValueError("macroproceso inválido")
        if not self.document_ids or any(not item.strip() for item in self.document_ids):
            raise ValueError("se requiere al menos un document_id")
        if len(set(self.document_ids)) != len(self.document_ids):
            raise ValueError("document_id duplicado")
        if self.macroproceso not in self.expediente.macroprocesos:
            raise ValueError("macroproceso no asociado al expediente")
        known_documents = {item.document_id for item in self.expediente.documents}
        if any(item not in known_documents for item in self.document_ids):
            raise ValueError("documento ajeno al expediente")
        if not isinstance(self.text, str):
            raise ValueError("text debe ser una cadena")
        if not isinstance(self.metadata, dict) or not isinstance(self.provenance, dict):
            raise ValueError("metadata y provenance deben ser objetos")
        if self.provenance.get("source", "synthetic_local") != "synthetic_local":
            raise ValueError("el adaptador solo admite procedencia sintética local")

    @property
    def expediente_id(self) -> str:
        return self.expediente.expediente_id


@dataclass(frozen=True)
class AnalyticalExecutionRecord:
    execution_id: str
    expediente_id: str
    macroproceso: Macroprocess
    document_ids: tuple[str, ...]
    kind: AnalyticalKind
    function_name: str
    code_sha256: str | None
    status: AnalyticalStatus
    analysis_data: dict[str, Any] | None
    normative_results: None
    started_at: datetime
    finished_at: datetime
    duration_ns: int
    processing_mode: str
    provenance: dict[str, Any]
    error_type: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        _required(self.execution_id, "execution_id")
        _required(self.expediente_id, "expediente_id")
        _required(self.function_name, "function_name")
        _required(self.processing_mode, "processing_mode")
        if not isinstance(self.macroproceso, Macroprocess):
            raise ValueError("macroproceso inválido")
        if not isinstance(self.kind, AnalyticalKind) or not isinstance(self.status, AnalyticalStatus):
            raise ValueError("kind o status analítico inválido")
        if self.normative_results is not None:
            raise ValueError("un análisis original no puede inventar resultados normativos")
        if self.duration_ns < 0 or self.finished_at < self.started_at:
            raise ValueError("duración o marcas de tiempo inválidas")
        if self.status is AnalyticalStatus.COMPLETED and self.analysis_data is None:
            raise ValueError("análisis completado requiere analysis_data")
        if self.status is not AnalyticalStatus.COMPLETED and not self.error_type:
            raise ValueError("error/no_disponible requiere error_type o causa")
