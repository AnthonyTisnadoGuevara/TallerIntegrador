"""Grafo normativo aislado; por ahora transporta datos, no decide cumplimiento."""
from __future__ import annotations
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, TypedDict
from uuid import uuid4

from .agent_input import AgentInput
from .catalog import CatalogStatus, NormativeCriterion
from .contracts import ApplicabilityRecord, EvidenceReference, LocationStatus, ReviewStatus
from .document_reader import DocumentReadError, ExtractedDocument, read_local_document
from .normative_evaluator import CriterionEvaluation
from .schemas import (ApplicabilityStatus, Classification, CriterionResult,
                      EffectiveMode, EvaluationState, ExperimentConfig, RunType, Verdict)


GRAPH_VERSION = "normative-evaluation-2b.1"


class GraphDependencyUnavailable(RuntimeError):
    pass


class EvaluationPortConfigurationError(RuntimeError):
    pass


class NormativeGraphState(TypedDict, total=False):
    request: AgentInput
    document_root: str
    config: ExperimentConfig
    execution_id: str
    expediente_id: str
    catalog_id: str
    normative_version: str
    documents: tuple[ExtractedDocument, ...]
    applicability: tuple[ApplicabilityRecord, ...]
    evaluation_units: tuple[tuple[NormativeCriterion, ApplicabilityRecord], ...]
    results: tuple[CriterionResult, ...]
    verdict: Verdict | None
    errors: tuple[dict[str, str], ...]
    status: str
    metadata: dict[str, Any]


class NormativeCriterionEvaluator(Protocol):
    """Puerto futuro. Una implementación real requiere reglas y aprobación aparte."""
    def evaluate(self, expediente, criterion, documents, applicability, config) -> CriterionResult | CriterionEvaluation: ...


class TransportOnlyEvaluator:
    """No infiere: confirma transporte y devuelve explícitamente no_evaluable."""
    mode = "synthetic_transport_only"

    def evaluate(self, expediente, criterion, documents, evidence, config) -> CriterionEvaluation:
        result = CriterionResult(
            criterion_id=criterion.criterion_id,
            evaluation_state=EvaluationState.NOT_EVALUABLE,
            classification=Classification.INDETERMINATE,
            rationale="No hay reglas institucionales aprobadas ni evaluador normativo configurado.",
            evidence=(), expediente_id=expediente.expediente_id,
            catalog_id=criterion.catalog_id, normative_version=criterion.normative_version)
        return CriterionEvaluation(result, {"effective_mode": "synthetic_transport_only",
                                            "warnings": ["no_normative_evaluator"]})


@dataclass(frozen=True)
class EvidenceCheck:
    results: tuple[CriterionResult, ...]
    errors: tuple[dict[str, str], ...]


def validate_result_evidence(results: tuple[CriterionResult, ...], expediente_docs,
                             extracted_docs: tuple[ExtractedDocument, ...]) -> EvidenceCheck:
    """Comprueba pertenencia y localizadores verificables en los textos cargados."""
    document_ids = {doc.document_id for doc in expediente_docs}
    extracted_by_id = {doc.document_id: doc for doc in extracted_docs}
    errors = []
    checked_results = []
    for result in results:
        checked_evidence = []
        for evidence in result.evidence:
            if evidence.document_id not in document_ids:
                errors.append({"code": "FOREIGN_EVIDENCE_DOCUMENT", "message": "evidencia refiere documento ajeno al expediente"})
                continue
            if evidence.expediente_id not in (None, result.expediente_id):
                errors.append({"code": "EVIDENCE_EXPEDIENTE_MISMATCH", "message": "evidencia vinculada a otro expediente"})
                continue
            extracted = extracted_by_id.get(evidence.document_id)
            status = "no_verificable"
            reason = evidence.absence_reason
            locator = evidence.locator
            if extracted is not None and locator:
                if locator.startswith("line:"):
                    try:
                        span = locator[5:].split("-")
                        start, end = int(span[0]), int(span[-1])
                        status = "localizado" if 1 <= start <= end <= extracted.line_count else "no_localizado"
                        reason = None if status == "localizado" else "rango de líneas fuera del documento"
                    except (ValueError, IndexError):
                        status, reason = "no_verificable", "formato de localizador de línea inválido"
                elif locator.startswith("page:"):
                    status, reason = "no_verificable", "el lector TXT no proporciona paginación"
                elif locator.startswith("section:"):
                    section = locator[len("section:"):].strip()
                    found = bool(section) and section.casefold() in extracted.text.casefold()
                    status = "localizado" if found else "no_localizado"
                    reason = None if found else "sección no encontrada en el texto extraído"
                else:
                    status, reason = "no_verificable", "formato de localizador no soportado"
            elif locator:
                status, reason = "no_verificable", "documento no disponible para contrastar el localizador"
            checked_evidence.append(replace(evidence, location_status=status,
                                            absence_reason=reason or evidence.absence_reason,
                                            expediente_id=result.expediente_id))
        checked_results.append(replace(result, evidence=tuple(checked_evidence)))
    return EvidenceCheck(tuple(checked_results), tuple(errors))


def validate_input_node(state: NormativeGraphState) -> NormativeGraphState:
    if set(state) - {"request", "document_root", "config", "execution_id"}:
        # No hacer eco de la entrada rechazada: podría contener datos de referencia.
        return {"status": "failed", "errors": ({"code": "INPUT_FIELDS_NOT_ALLOWED",
                                                   "message": "entrada contiene campos no permitidos"},)}
    if state.get("status") == "failed":
        return state
    request = state.get("request")
    config = state.get("config")
    root = state.get("document_root")
    if not isinstance(request, AgentInput):
        return _fail(state, "INVALID_INPUT", "se requiere AgentInput validado")
    if not isinstance(config, ExperimentConfig) or config.run_type is not RunType.SYNTHETIC or config.effective_mode is not EffectiveMode.SYNTHETIC:
        return _fail(state, "UNSAFE_CONFIG", "esta versión solo admite configuración sintética")
    if config.external_calls_enabled or config.business_writes_enabled:
        return _fail(state, "UNSAFE_CONFIG", "llamadas externas y escrituras deben permanecer deshabilitadas")
    if not isinstance(root, str) or not root.strip():
        return _fail(state, "INVALID_DOCUMENT_ROOT", "se requiere raíz documental local")
    execution_id = state.get("execution_id") or str(uuid4())
    if not isinstance(execution_id, str) or not execution_id.strip():
        return _fail(state, "INVALID_EXECUTION_ID", "execution_id inválido")
    return {**state, "execution_id": execution_id, "expediente_id": request.expediente.expediente_id,
            "catalog_id": request.catalog.catalog_id, "normative_version": request.catalog.normative_version,
            "status": "running", "errors": (),
            "metadata": {"graph_version": GRAPH_VERSION, "adapter": "TransportOnlyEvaluator",
                         "run_type": "sintetico", "external_calls": False,
                         "effective_mode": config.effective_mode.value,
                         "config_id": config.config_id,
                         "catalog_sha256": request.catalog.content_sha256,
                         "business_writes": False, "started_at": datetime.now(timezone.utc).isoformat()}}


def prepare_expedient_node(state: NormativeGraphState) -> NormativeGraphState:
    if state.get("status") == "failed":
        return state
    request = state["request"]
    if not request.expediente.documents:
        return _fail(state, "EMPTY_EXPEDIENTE", "expediente sin documentos")
    return {**state, "expediente_id": request.expediente.expediente_id}


def verify_catalog_node(state: NormativeGraphState) -> NormativeGraphState:
    if state.get("status") == "failed":
        return state
    catalog = state["request"].catalog
    if catalog.status is not CatalogStatus.VALIDATED:
        return _fail(state, "CATALOG_NOT_APPROVED", "catálogo pendiente de aprobación documentada")
    ids = [criterion.criterion_id for criterion in catalog.criteria]
    if len(ids) != len(set(ids)):
        return _fail(state, "DUPLICATE_CRITERION", "catálogo contiene criterios duplicados")
    return {**state, "catalog_id": catalog.catalog_id, "normative_version": catalog.normative_version}


def resolve_applicability_node(state: NormativeGraphState) -> NormativeGraphState:
    if state.get("status") == "failed":
        return state
    request = state["request"]
    by_id = {item.criterion_id: item for item in request.applicability_records}
    records = []
    for criterion in request.catalog.criteria:
        record = by_id.get(criterion.criterion_id)
        if record is None:
            records.append(ApplicabilityRecord(
                request.expediente.expediente_id, criterion.criterion_id,
                request.catalog.catalog_id, request.catalog.normative_version,
                ApplicabilityStatus.UNDETERMINED,
                "No se proporcionó registro de aplicabilidad revisado.", ReviewStatus.PENDING))
        elif record.review_status is not ReviewStatus.REVIEWED:
            records.append(replace(record, status=ApplicabilityStatus.UNDETERMINED,
                                   justification="Registro de aplicabilidad aún no revisado."))
        else:
            records.append(record)
    return {**state, "applicability": tuple(records)}


def process_documents_node(state: NormativeGraphState) -> NormativeGraphState:
    if state.get("status") == "failed":
        return state
    documents = []
    try:
        for document in state["request"].expediente.documents:
            documents.append(read_local_document(document, state["document_root"]))
    except DocumentReadError as exc:
        return _fail(state, exc.code.upper(), str(exc))
    metadata = dict(state.get("metadata", {}))
    metadata["document_sha256"] = {doc.document_id: doc.sha256 for doc in documents}
    return {**state, "documents": tuple(documents), "metadata": metadata}


def prepare_evaluation_units_node(state: NormativeGraphState) -> NormativeGraphState:
    if state.get("status") == "failed":
        return state
    app = {item.criterion_id: item for item in state["applicability"]}
    units = tuple((criterion, app[criterion.criterion_id]) for criterion in state["request"].catalog.criteria)
    return {**state, "evaluation_units": units}


def evaluate_criteria_node(state: NormativeGraphState,
                           injected_evaluator: NormativeCriterionEvaluator | None = None) -> NormativeGraphState:
    if state.get("status") == "failed":
        return state
    evaluator = injected_evaluator or TransportOnlyEvaluator()
    request = state["request"]
    docs = state["documents"]
    results = []
    evaluation_metadata = []
    for criterion, applicability in state["evaluation_units"]:
        if applicability.status is ApplicabilityStatus.NOT_APPLICABLE:
            result = CriterionResult(criterion.criterion_id, EvaluationState.NOT_APPLICABLE,
                                    Classification.NOT_APPLICABLE,
                                    "Criterio marcado no aplicable en el registro de entrada revisado.",
                                    expediente_id=request.expediente.expediente_id,
                                    catalog_id=criterion.catalog_id,
                                    normative_version=criterion.normative_version)
        elif applicability.status is ApplicabilityStatus.UNDETERMINED:
            result = CriterionResult(criterion.criterion_id, EvaluationState.NOT_EVALUABLE,
                                    Classification.INDETERMINATE,
                                    "Aplicabilidad indeterminada; no se emite decisión normativa.",
                                    expediente_id=request.expediente.expediente_id,
                                    catalog_id=criterion.catalog_id,
                                    normative_version=criterion.normative_version)
            evaluation_metadata.append({"criterion_id": criterion.criterion_id,
                                        "effective_mode": "not_invoked",
                                        "warnings": ["applicability_undetermined"]})
        elif injected_evaluator is not None and criterion.applicability_rule not in request.authorized_rules:
            result = CriterionResult(criterion.criterion_id, EvaluationState.NOT_EVALUABLE,
                                    Classification.INDETERMINATE,
                                    "La regla de aplicabilidad no está en la allowlist autorizada.",
                                    expediente_id=request.expediente.expediente_id,
                                    catalog_id=criterion.catalog_id,
                                    normative_version=criterion.normative_version)
            evaluation_metadata.append({"criterion_id": criterion.criterion_id,
                                        "effective_mode": "not_invoked",
                                        "warnings": ["applicability_rule_not_authorized"]})
        else:
            evaluated = evaluator.evaluate(request.expediente, criterion, docs,
                                           applicability, state["config"])
            if isinstance(evaluated, CriterionEvaluation):
                result = evaluated.result
                evaluation_metadata.append({"criterion_id": criterion.criterion_id,
                                            **evaluated.metadata})
            elif isinstance(evaluated, CriterionResult):
                result = evaluated
                evaluation_metadata.append({"criterion_id": criterion.criterion_id,
                                            "effective_mode": getattr(evaluator, "mode", "unknown")})
            else:
                raise TypeError("evaluador devolvió un tipo incompatible")
        results.append(replace(result, execution_id=state["execution_id"]))
    metadata = dict(state.get("metadata", {}))
    metadata["criterion_evaluations"] = evaluation_metadata
    metadata["evaluator_mode"] = getattr(evaluator, "mode", "unknown")
    return {**state, "results": tuple(results), "metadata": metadata}


def verify_evidence_node(state: NormativeGraphState) -> NormativeGraphState:
    if state.get("status") == "failed":
        return state
    checked = validate_result_evidence(state.get("results", ()),
                                       state["request"].expediente.documents,
                                       state["documents"])
    if checked.errors:
        return {**state, "results": checked.results, "errors": checked.errors, "status": "failed"}
    results = []
    warnings = []
    for result in checked.results:
        if (result.evaluation_state is EvaluationState.EVALUATED
                and result.classification in {Classification.CONFORMING, Classification.NON_CONFORMING}
                and not any(item.location_status == "localizado" for item in result.evidence)):
            result = replace(result, evaluation_state=EvaluationState.NOT_EVALUABLE,
                             classification=Classification.INDETERMINATE,
                             rationale=(result.rationale +
                                        " Evidencia no localizada; decisión normativa abstendida."))
            warnings.append({"code": "NONCONFORMITY_EVIDENCE_NOT_LOCATED",
                             "criterion_id": result.criterion_id})
        results.append(result)
    metadata = dict(state.get("metadata", {}))
    metadata["evidence_warnings"] = warnings
    return {**state, "results": tuple(results), "metadata": metadata}


def consolidate_results_node(state: NormativeGraphState) -> NormativeGraphState:
    if state.get("status") == "failed":
        return state
    results = state.get("results", ())
    expected = {item.criterion_id for item in state["request"].catalog.criteria}
    actual = [item.criterion_id for item in results]
    if set(actual) != expected or len(actual) != len(expected):
        return _fail(state, "INCOMPLETE_OUTPUT", "faltan resultados o hay criterios repetidos")
    return state


def generate_verdict_node(state: NormativeGraphState) -> NormativeGraphState:
    if state.get("status") == "failed":
        return state
    verdict = Verdict(
        expediente_id=state["expediente_id"],
        overall_classification=Classification.INDETERMINATE,
        rationale="Salida de transporte sintético: no hay evaluador ni reglas normativas aprobadas.",
        criterion_results=state.get("results", ()),
        reference=None)
    return {**state, "verdict": verdict, "status": "completed_not_normatively_evaluated"}


def validate_output_node(state: NormativeGraphState) -> NormativeGraphState:
    if state.get("status") == "failed":
        return state
    verdict = state.get("verdict")
    if verdict is None or verdict.expediente_id != state.get("expediente_id"):
        return _fail(state, "INVALID_OUTPUT", "dictamen ausente o ligado a otro expediente")
    result_ids = [result.criterion_id for result in verdict.criterion_results]
    expected = [criterion.criterion_id for criterion in state["request"].catalog.criteria]
    if result_ids != expected:
        return _fail(state, "INVALID_OUTPUT", "dictamen no conserva orden/completitud de criterios")
    metadata = dict(state.get("metadata", {}))
    metadata["finished_at"] = datetime.now(timezone.utc).isoformat()
    return {**state, "metadata": metadata}


_PIPELINE = (validate_input_node, prepare_expedient_node, verify_catalog_node,
             resolve_applicability_node, process_documents_node, prepare_evaluation_units_node,
             evaluate_criteria_node, verify_evidence_node, consolidate_results_node,
             generate_verdict_node, validate_output_node)


def run_normative_pipeline(request: AgentInput, document_root: str | Path,
                           config: ExperimentConfig,
                           evaluator: NormativeCriterionEvaluator | None = None) -> NormativeGraphState:
    """Ejecuta nodos puros/locales para pruebas cuando LangGraph no está instalado."""
    state: NormativeGraphState = {"request": request, "document_root": str(document_root), "config": config}
    for node in _PIPELINE:
        state = (node(state, evaluator) if node is evaluate_criteria_node else node(state))
    return state


def build_normative_graph(evaluator: NormativeCriterionEvaluator | None = None):
    """Compila el grafo LangGraph cuando el paquete ya está disponible localmente."""
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:
        raise GraphDependencyUnavailable("LangGraph no está instalado; no se instaló automáticamente") from exc
    graph = StateGraph(NormativeGraphState)
    nodes = (
        ("validate_input", validate_input_node),
        ("prepare_expedient", prepare_expedient_node),
        ("verify_catalog", verify_catalog_node),
        ("resolve_applicability", resolve_applicability_node),
        ("process_documents", process_documents_node),
        ("prepare_evaluation_units", prepare_evaluation_units_node),
        ("evaluate_criteria", lambda state: evaluate_criteria_node(state, evaluator)),
        ("verify_evidence", verify_evidence_node),
        ("consolidate_results", consolidate_results_node),
        ("generate_verdict", generate_verdict_node),
        ("validate_output", validate_output_node),
    )
    for name, node in nodes:
        graph.add_node(name, node)
    graph.add_edge(START, nodes[0][0])
    for (current, _), (next_node, _) in zip(nodes, nodes[1:]):
        graph.add_edge(current, next_node)
    graph.add_edge(nodes[-1][0], END)
    return graph.compile()


def _fail(state: NormativeGraphState, code: str, message: str) -> NormativeGraphState:
    return {**state, "status": "failed",
            "errors": tuple(state.get("errors", ())) + ({"code": code, "message": message},)}
