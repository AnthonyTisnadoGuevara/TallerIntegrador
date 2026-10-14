"""Validación cruzada de datasets; los mensajes describen campos, no su contenido."""
from __future__ import annotations
from dataclasses import dataclass

from .catalog import CatalogStatus, NormativeCatalog
from .contracts import ApplicabilityRecord
from .ground_truth import GroundTruthRecord, GroundTruthStatus, has_disagreement
from .schemas import CriterionResult, ExecutionRecord, Expediente
from .corpus_manifest import validate_corpus_manifest


@dataclass(frozen=True)
class DatasetIssue:
    code: str
    path: str
    message: str


def validate_dataset(*, expedientes: tuple[Expediente, ...], catalogs: tuple[NormativeCatalog, ...],
                     applicability: tuple[ApplicabilityRecord, ...] = (),
                     results: tuple[CriterionResult, ...] = (),
                     executions: tuple[ExecutionRecord, ...] = (),
                     ground_truth: tuple[GroundTruthRecord, ...] = ()) -> tuple[DatasetIssue, ...]:
    issues: list[DatasetIssue] = []
    exp_by_id: dict[str, Expediente] = {}
    for i, exp in enumerate(expedientes):
        if exp.expediente_id in exp_by_id:
            issues.append(DatasetIssue("DUPLICATE_EXPEDIENTE", f"expedientes[{i}]", "expediente_id duplicado"))
        exp_by_id[exp.expediente_id] = exp
    catalog_by_key = {}
    crit_by_key = {}
    for i, catalog in enumerate(catalogs):
        key = (catalog.catalog_id, catalog.normative_version)
        if key in catalog_by_key:
            issues.append(DatasetIssue("DUPLICATE_CATALOG_VERSION", f"catalogs[{i}]", "catálogo/version duplicado"))
        catalog_by_key[key] = catalog
        for criterion in catalog.criteria:
            ckey = (catalog.catalog_id, catalog.normative_version, criterion.criterion_id)
            crit_by_key[ckey] = criterion

    seen_app = set()
    for i, item in enumerate(applicability):
        path = f"applicability[{i}]"
        key = (item.expediente_id, item.macroproceso, item.criterion_id, item.catalog_id, item.normative_version)
        if key in seen_app:
            issues.append(DatasetIssue("DUPLICATE_APPLICABILITY", path, "relación expediente/criterio duplicada"))
        seen_app.add(key)
        exp = exp_by_id.get(item.expediente_id)
        if exp is None:
            issues.append(DatasetIssue("UNKNOWN_EXPEDIENTE", path, "expediente inexistente"))
        elif item.macroproceso is not None and item.macroproceso not in exp.macroprocesos:
            issues.append(DatasetIssue("MACROPROCESS_MISMATCH", path, "aplicabilidad no corresponde al expediente"))
        elif item.macroproceso is None and exp.macroprocesos:
            issues.append(DatasetIssue("LEGACY_MACROPROCESS_MISSING", path, "aplicabilidad heredada sin macroproceso"))
        ckey = (item.catalog_id, item.normative_version, item.criterion_id)
        if ckey not in crit_by_key:
            issues.append(DatasetIssue("UNKNOWN_OR_INCOMPATIBLE_CRITERION", path, "criterio o versión normativa inexistente"))
        _validate_evidence(item.evidence, exp, path, issues)

    seen_results = set()
    for i, result in enumerate(results):
        path = f"results[{i}]"
        _validate_result(result, path, exp_by_id, crit_by_key, issues)
        if result.execution_id:
            rkey = (result.execution_id, result.macroproceso, result.criterion_id)
            if rkey in seen_results:
                issues.append(DatasetIssue("DUPLICATE_RESULT", path, "resultado repetido para ejecución y criterio"))
            seen_results.add(rkey)
        if result.expediente_id:
            _validate_evidence(result.evidence, exp_by_id.get(result.expediente_id), path, issues)

    seen_replicas = set()
    for i, execution in enumerate(executions):
        path = f"executions[{i}]"
        if execution.experiment_id is not None:
            rkey = (execution.experiment_id, execution.expediente_id,
                    execution.macroproceso, execution.replica)
            if rkey in seen_replicas:
                issues.append(DatasetIssue("DUPLICATE_REPLICA", path, "réplica duplicada en el conjunto experimental"))
            seen_replicas.add(rkey)
        if execution.expediente_id not in exp_by_id:
            issues.append(DatasetIssue("UNKNOWN_EXPEDIENTE", path, "expediente inexistente"))
        elif execution.macroproceso is not None and execution.macroproceso not in exp_by_id[execution.expediente_id].macroprocesos:
            issues.append(DatasetIssue("MACROPROCESS_MISMATCH", path, "ejecuciÃ³n no corresponde al expediente"))
        elif execution.macroproceso is None and exp_by_id[execution.expediente_id].macroprocesos:
            issues.append(DatasetIssue("LEGACY_MACROPROCESS_MISSING", path, "ejecuciÃ³n heredada sin macroproceso"))
        for result in execution.results:
            if result.execution_id not in (None, execution.execution_id):
                issues.append(DatasetIssue("EXECUTION_LINK_MISMATCH", path, "resultado vinculado a otra ejecución"))
            _validate_result(result, path, exp_by_id, crit_by_key, issues)
        if execution.verdict is not None and execution.verdict.expediente_id != execution.expediente_id:
            issues.append(DatasetIssue("VERDICT_LINK_MISMATCH", path, "dictamen vinculado a otro expediente"))

    seen_gt = set()
    seen_annotation_ids = set()
    for i, record in enumerate(ground_truth):
        path = f"ground_truth[{i}]"
        key = (record.expediente_id, record.macroproceso, record.criterion_id, record.normative_version)
        if key in seen_gt:
            issues.append(DatasetIssue("DUPLICATE_GROUND_TRUTH", path, "registro de referencia duplicado"))
        seen_gt.add(key)
        exp = exp_by_id.get(record.expediente_id)
        if exp is None:
            issues.append(DatasetIssue("UNKNOWN_EXPEDIENTE", path, "expediente inexistente"))
        elif record.macroproceso is not None and record.macroproceso not in exp.macroprocesos:
            issues.append(DatasetIssue("MACROPROCESS_MISMATCH", path, "referencia no corresponde al expediente"))
        elif record.macroproceso is None and exp.macroprocesos:
            issues.append(DatasetIssue("LEGACY_MACROPROCESS_MISSING", path, "referencia heredada sin macroproceso"))
        if (record.catalog_id, record.normative_version, record.criterion_id) not in crit_by_key:
            issues.append(DatasetIssue("UNKNOWN_OR_INCOMPATIBLE_CRITERION", path, "criterio o versión normativa inexistente"))
        for annotation in record.annotations:
            if annotation.annotation_id in seen_annotation_ids:
                issues.append(DatasetIssue("DUPLICATE_ANNOTATION", path, "annotation_id duplicado"))
            seen_annotation_ids.add(annotation.annotation_id)
            if annotation.review_status.value == "revisado" and (
                    annotation.reference_label is None or not annotation.reference_verdict):
                issues.append(DatasetIssue("INCOMPLETE_ANNOTATION", path, "anotación revisada incompleta"))
            _validate_evidence(annotation.evidence, exp, path, issues)
        resolution = record.disagreement_resolution
        if resolution is not None:
            annotation_ids = {a.annotation_id for a in record.annotations}
            if not set(resolution.annotation_ids).issubset(annotation_ids):
                issues.append(DatasetIssue("UNKNOWN_ANNOTATION", path, "resolución referencia anotación inexistente"))
        if has_disagreement(record) and resolution is None:
            issues.append(DatasetIssue("UNADJUDICATED_REFERENCE", path, "referencia con desacuerdo no adjudicada"))
        if record.status is not GroundTruthStatus.VALIDATED:
            issues.append(DatasetIssue("REFERENCE_NOT_VALIDATED", path, "referencia no validada; no usar para métricas"))
        elif any(not annotation.evidence for annotation in record.annotations):
            issues.append(DatasetIssue("REFERENCE_EVIDENCE_MISSING", path,
                                       "cada anotación final requiere evidencia o limitación documentada"))
        catalog = catalog_by_key.get((record.catalog_id, record.normative_version))
        if record.status is GroundTruthStatus.VALIDATED and catalog is not None and catalog.status is not CatalogStatus.VALIDATED:
            issues.append(DatasetIssue("UNVALIDATED_CATALOG", path, "catálogo no tiene aprobación documentada"))
    return tuple(issues)


def validate_final_dataset(*, manifest: dict, document_root,
                           expedientes: tuple[Expediente, ...],
                           catalogs: tuple[NormativeCatalog, ...],
                           ground_truth: tuple[GroundTruthRecord, ...],
                           applicability: tuple[ApplicabilityRecord, ...] = (),
                           results: tuple[CriterionResult, ...] = (),
                           executions: tuple[ExecutionRecord, ...] = ()) -> tuple[DatasetIssue, ...]:
    """Validación estricta previa a congelar/usar un dataset definitivo.

    La completitud se comprueba por expediente + criterio + catálogo/versión.
    `macroprocesos` del manifiesto se conservan como metadatos y no se expanden
    automáticamente en experimentos duplicados.
    """
    issues = [DatasetIssue(issue.code, issue.path, issue.message)
              for issue in validate_corpus_manifest(
                  manifest, document_root, require_frozen=True,
                  require_authorized=True, verify_hashes=True)]
    issues.extend(validate_dataset(expedientes=expedientes, catalogs=catalogs,
                                   applicability=applicability, results=results,
                                   executions=executions, ground_truth=ground_truth))

    manifest_expedientes = manifest.get("expedientes", []) if isinstance(manifest, dict) else []
    manifest_by_id = {item.get("expediente_id"): item for item in manifest_expedientes
                      if isinstance(item, dict) and isinstance(item.get("expediente_id"), str)}
    typed_by_id = {item.expediente_id: item for item in expedientes}
    for exp_id in sorted(set(manifest_by_id) - set(typed_by_id)):
        issues.append(DatasetIssue("EXPEDIENTE_CONTRACT_MISSING", f"expedientes.{exp_id}",
                                   "falta el Expediente validado correspondiente al manifiesto"))
    for exp_id in sorted(set(typed_by_id) - set(manifest_by_id)):
        issues.append(DatasetIssue("EXPEDIENTE_NOT_IN_CORPUS", f"expedientes.{exp_id}",
                                   "el expediente no está en el manifiesto congelado"))

    catalogs_by_key = {(item.catalog_id, item.normative_version): item for item in catalogs}
    for catalog in catalogs:
        if catalog.status is not CatalogStatus.VALIDATED:
            issues.append(DatasetIssue("UNVALIDATED_CATALOG", f"catalogs.{catalog.catalog_id}",
                                       "el catálogo requiere aprobación institucional documentada"))

    expected_ground_truth: set[tuple[str, str, str, str]] = set()
    for exp_id, manifest_exp in manifest_by_id.items():
        ref = manifest_exp.get("catalog_ref")
        if not isinstance(ref, dict):
            continue
        catalog_id, version = ref.get("catalog_id"), ref.get("normative_version")
        catalog = catalogs_by_key.get((catalog_id, version))
        if catalog is None:
            issues.append(DatasetIssue("CATALOG_BINDING_UNRESOLVED", f"expedientes.{exp_id}.catalog_ref",
                                       "el catálogo/version del expediente no está cargado"))
            continue
        expected_ground_truth.update((exp_id, criterion.criterion_id, catalog_id, version)
                                     for criterion in catalog.criteria)
        typed = typed_by_id.get(exp_id)
        if typed is not None:
            raw_documents = manifest_exp.get("documents", [])
            if not isinstance(raw_documents, list):
                raw_documents = []
            manifest_docs = {doc.get("document_id"): doc for doc in raw_documents
                             if isinstance(doc, dict)}
            typed_docs = {doc.document_id: doc for doc in typed.documents}
            if set(manifest_docs) != set(typed_docs):
                issues.append(DatasetIssue("DOCUMENT_SET_MISMATCH", f"expedientes.{exp_id}.documents",
                                           "documentos del contrato y manifiesto no coinciden"))
            for doc_id in set(manifest_docs) & set(typed_docs):
                source_doc, contract_doc = manifest_docs[doc_id], typed_docs[doc_id]
                if (source_doc.get("sha256"), source_doc.get("version"), source_doc.get("format")) != (
                        contract_doc.sha256, contract_doc.version, contract_doc.format):
                    issues.append(DatasetIssue("DOCUMENT_METADATA_MISMATCH",
                                               f"expedientes.{exp_id}.documents.{doc_id}",
                                               "hash, versión o formato difiere del manifiesto"))
            if typed.document_version != manifest_exp.get("document_version"):
                issues.append(DatasetIssue("DOCUMENT_VERSION_MISMATCH", f"expedientes.{exp_id}.document_version",
                                           "versión documental difiere del manifiesto"))

    found_ground_truth = {(item.expediente_id, item.criterion_id, item.catalog_id, item.normative_version)
                          for item in ground_truth}
    for key in sorted(expected_ground_truth - found_ground_truth):
        issues.append(DatasetIssue("GROUND_TRUTH_MISSING",
                                   f"ground_truth.{key[0]}.{key[1]}",
                                   "falta referencia final para expediente/criterio/catálogo"))
    for key in sorted(found_ground_truth - expected_ground_truth):
        issues.append(DatasetIssue("GROUND_TRUTH_OUT_OF_SCOPE",
                                   f"ground_truth.{key[0]}.{key[1]}",
                                   "la referencia no corresponde al catálogo enlazado al expediente"))
    return tuple(issues)


def _validate_result(result: CriterionResult, path: str, expedientes: dict,
                     criteria: dict, issues: list[DatasetIssue]) -> None:
    if result.expediente_id is None and result.catalog_id is None and result.normative_version is None:
        return  # Compatibilidad con registros sintéticos históricos no normativos.
    if not all((result.expediente_id, result.catalog_id, result.normative_version)):
        issues.append(DatasetIssue("INCOMPLETE_RESULT_LINK", path, "resultado normativo requiere expediente, catálogo y versión"))
        return
    if result.expediente_id not in expedientes:
        issues.append(DatasetIssue("UNKNOWN_EXPEDIENTE", path, "expediente inexistente"))
    elif result.macroproceso is not None and result.macroproceso not in expedientes[result.expediente_id].macroprocesos:
        issues.append(DatasetIssue("MACROPROCESS_MISMATCH", path, "resultado no corresponde al expediente"))
    elif result.macroproceso is None and expedientes[result.expediente_id].macroprocesos:
        issues.append(DatasetIssue("LEGACY_MACROPROCESS_MISSING", path, "resultado heredado sin macroproceso"))
    if (result.catalog_id, result.normative_version, result.criterion_id) not in criteria:
        issues.append(DatasetIssue("UNKNOWN_OR_INCOMPATIBLE_CRITERION", path, "criterio o versión normativa inexistente"))


def _validate_evidence(evidence, expediente, path: str, issues: list[DatasetIssue]) -> None:
    for index, item in enumerate(evidence):
        epath = f"{path}.evidence[{index}]"
        if expediente is None:
            issues.append(DatasetIssue("UNKNOWN_EXPEDIENTE", epath, "no se puede validar documento sin expediente"))
            continue
        if item.document_id not in {doc.document_id for doc in expediente.documents}:
            issues.append(DatasetIssue("FOREIGN_DOCUMENT", epath, "documento no pertenece al expediente"))
        if getattr(item, "expediente_id", None) not in (None, expediente.expediente_id):
            issues.append(DatasetIssue("EVIDENCE_EXPEDIENTE_MISMATCH", epath, "evidencia vinculada a otro expediente"))
