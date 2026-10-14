"""Interfaz versionada para un evaluador normativo inyectable y fail-closed.

No implementa un cliente Gemini ni hace llamadas externas. Un proveedor futuro
debe aprobarse por separado y declararse explícitamente en sus capacidades.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Protocol

from .catalog import NormativeCriterion
from .contracts import ApplicabilityRecord, ReviewStatus
from .document_reader import ExtractedDocument
from .schemas import (ApplicabilityStatus, Classification, CriterionResult,
                      EffectiveMode, EvaluationState, Evidence, ExperimentConfig,
                      Expediente)


PROMPT_VERSION = "normative-criterion-v1"
PROMPT_TEMPLATE = """Eres un asistente de análisis documental. Evalúa únicamente el criterio aprobado incluido abajo y solo con los documentos autorizados proporcionados.
No inventes normas, citas, páginas, secciones ni hechos. Si falta información, la evidencia es insuficiente o la ubicación no puede sustentarse, abstente con estado no_evaluable e indeterminado. No conviertas una sección ausente por sí sola en no_conforme.
Para una posible no conformidad, aporta al menos un localizador verificable del documento y una justificación explícitamente vinculada al criterio. Devuelve exclusivamente una respuesta estructurada conforme al contrato del proveedor.

EXPEDIENTE: {expediente_id}
CRITERIO APROBADO ({criterion_id}, versión {normative_version}): {criterion_text}
REGLA DE APLICABILIDAD AUTORIZADA: {applicability_rule}
TEXTO DOCUMENTAL AUTORIZADO: {documents}
EVIDENCIAS HUMANAS REVISADAS: {evidence}
"""
PROMPT_SHA256 = hashlib.sha256(PROMPT_TEMPLATE.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ProviderResponse:
    evaluation_state: EvaluationState
    classification: Classification
    rationale: str
    evidence: tuple[Evidence, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CriterionEvaluation:
    result: CriterionResult
    metadata: dict


class InferenceProvider(Protocol):
    provider_name: str
    model_name: str
    model_version: str | None
    effective_mode: EffectiveMode
    external_calls_enabled: bool
    business_writes_enabled: bool

    def generate(self, prompt: str, config: ExperimentConfig) -> ProviderResponse: ...


class NormativeCriterionEvaluator(Protocol):
    mode: str
    external_calls_enabled: bool
    business_writes_enabled: bool

    def evaluate(self, expediente: Expediente, criterion: NormativeCriterion,
                 documents: tuple[ExtractedDocument, ...], applicability: ApplicabilityRecord,
                 config: ExperimentConfig) -> CriterionEvaluation: ...


class InferenceFailure(RuntimeError):
    """Fallo explícito del proveedor; nunca se convierte en fallback silencioso."""

    def __init__(self, message: str, *, provider: InferenceProvider):
        super().__init__(message)
        self.error_codes = ("INFERENCE_PROVIDER_FAILURE",)
        self.execution_metadata = {
            "provider_mode_attempted": provider.effective_mode.value,
            "provider": provider.provider_name, "model": provider.model_name,
            "model_version": provider.model_version,
            "inference_status": "failed_no_fallback",
        }


class PromptedNormativeEvaluator:
    """Traduce una respuesta tipada de proveedor a CriterionResult.

    Acepta exclusivamente proveedores locales sin llamadas externas/escrituras.
    El modo puede ser mock o sintético; IA externa queda fuera de esta fase.
    """
    mode = "injected_local_provider"
    external_calls_enabled = False
    business_writes_enabled = False

    def __init__(self, provider: InferenceProvider, *, catalog_sha256: str):
        if getattr(provider, "external_calls_enabled", True) is not False:
            raise ValueError("proveedor externo no autorizado en esta fase")
        if getattr(provider, "business_writes_enabled", True) is not False:
            raise ValueError("proveedor con escrituras no autorizado")
        if getattr(provider, "effective_mode", None) not in {
                EffectiveMode.SYNTHETIC, EffectiveMode.MOCK}:
            raise ValueError("solo se admiten proveedores sintéticos o mock locales")
        if (len(catalog_sha256) != 64
                or any(char not in "0123456789abcdef" for char in catalog_sha256.lower())):
            raise ValueError("se requiere SHA-256 del catálogo aprobado")
        self.provider = provider
        self.catalog_sha256 = catalog_sha256.lower()

    def evaluate(self, expediente: Expediente, criterion: NormativeCriterion,
                 documents: tuple[ExtractedDocument, ...], applicability: ApplicabilityRecord,
                 config: ExperimentConfig) -> CriterionEvaluation:
        if config.prompt_sha256 != PROMPT_SHA256:
            raise ValueError("prompt_sha256 no coincide con la plantilla versionada")
        if config.catalog_sha256.lower() != self.catalog_sha256:
            raise ValueError("catalog_sha256 no coincide con el catálogo aprobado del evaluador")
        if (config.provider != self.provider.provider_name
                or config.model != self.provider.model_name
                or config.model_version != self.provider.model_version):
            raise ValueError("proveedor/modelo no coincide con ExperimentConfig")
        if not documents:
            return self._not_evaluable(expediente, criterion, "No hay documentos extraídos para evaluar.", "documentos_ausentes")
        if any(document.document_id not in {item.document_id for item in expediente.documents}
               for document in documents):
            raise ValueError("documento extraído ajeno al expediente")
        if (applicability.status is not ApplicabilityStatus.APPLICABLE
                or applicability.review_status is not ReviewStatus.REVIEWED):
            return self._not_evaluable(expediente, criterion, "Las evidencias de aplicabilidad no están revisadas.", "evidencia_no_revisada")

        # Se excluyen expresamente Ground Truth y cualquier anotación de referencia.
        document_payload = "\n".join(
            f"[document_id={doc.document_id}; locator={doc.relative_locator}]\n{doc.text}"
            for doc in documents)
        evidence_payload = "\n".join(
            f"{item.document_id}: {item.locator or item.limitation or item.location_status.value}"
            for item in applicability.evidence)
        prompt = PROMPT_TEMPLATE.format(
            expediente_id=expediente.expediente_id,
            criterion_id=criterion.criterion_id,
            normative_version=criterion.normative_version,
            criterion_text=criterion.text,
            applicability_rule=criterion.applicability_rule,
            documents=document_payload, evidence=evidence_payload or "sin referencias revisadas")
        try:
            response = self.provider.generate(prompt, config)
        except Exception as exc:
            raise InferenceFailure(f"fallo del proveedor ({type(exc).__name__}); sin fallback",
                                   provider=self.provider) from exc
        if not isinstance(response, ProviderResponse):
            raise InferenceFailure("respuesta de proveedor no cumple ProviderResponse; sin fallback",
                                   provider=self.provider)

        state, label = response.evaluation_state, response.classification
        warning_list = list(response.warnings)
        if not isinstance(state, EvaluationState) or not isinstance(label, Classification):
            raise InferenceFailure("respuesta de proveedor contiene estados inválidos; sin fallback",
                                   provider=self.provider)
        if state is EvaluationState.NOT_APPLICABLE or label is Classification.NOT_APPLICABLE:
            state, label = EvaluationState.NOT_EVALUABLE, Classification.INDETERMINATE
            warning_list.append("el_modelo_no_decide_aplicabilidad")
        # Solo una clasificación binaria evaluada puede entrar en OE1; no conformidad
        # requiere evidencia localizable candidata; el grafo también la verifica.
        if (state is EvaluationState.EVALUATED
                and label in {Classification.CONFORMING, Classification.NON_CONFORMING}):
            known_docs = {doc.document_id for doc in documents}
            if not any(item.document_id in known_docs and item.locator for item in response.evidence):
                state, label = EvaluationState.NOT_EVALUABLE, Classification.INDETERMINATE
                warning_list.append("clasificacion_binaria_sin_evidencia_localizable")
        if state is not EvaluationState.EVALUATED and label in {
                Classification.CONFORMING, Classification.NON_CONFORMING}:
            state, label = EvaluationState.NOT_EVALUABLE, Classification.INDETERMINATE
            warning_list.append("respuesta_inconsistente_convertida_en_abstencion")
        result = CriterionResult(
            criterion_id=criterion.criterion_id, evaluation_state=state,
            classification=label, rationale=response.rationale,
            evidence=response.evidence, expediente_id=expediente.expediente_id,
            catalog_id=criterion.catalog_id, normative_version=criterion.normative_version)
        return CriterionEvaluation(result, {
            "effective_mode": self.provider.effective_mode.value,
            "provider": self.provider.provider_name, "model": self.provider.model_name,
            "model_version": self.provider.model_version,
            "temperature": config.temperature, "seed": config.seed,
            "prompt_version": PROMPT_VERSION, "prompt_sha256": PROMPT_SHA256,
            "catalog_sha256": self.catalog_sha256,
            "warnings": warning_list,
        })

    @staticmethod
    def _not_evaluable(expediente, criterion, rationale, warning):
        return CriterionEvaluation(CriterionResult(
            criterion.criterion_id, EvaluationState.NOT_EVALUABLE,
            Classification.INDETERMINATE, rationale, expediente_id=expediente.expediente_id,
            catalog_id=criterion.catalog_id, normative_version=criterion.normative_version),
            {"effective_mode": "not_invoked", "prompt_version": PROMPT_VERSION,
             "prompt_sha256": PROMPT_SHA256, "warnings": [warning]})
