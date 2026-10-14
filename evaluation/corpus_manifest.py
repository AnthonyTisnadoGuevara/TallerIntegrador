"""Manifiesto local del corpus y verificaciones de integridad/autorización.

No lee variables de entorno ni servicios. Los paths del manifiesto son siempre
relativos a una raíz documental elegida explícitamente por quien prepara datos.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


AUTH_PENDING = "pendiente"
AUTH_APPROVED = "autorizado"
AUTH_DENIED = "no_autorizado"
MANIFEST_DRAFT = "borrador"
MANIFEST_FROZEN = "congelado"


@dataclass(frozen=True)
class CorpusIssue:
    code: str
    path: str
    message: str


class CorpusManifestError(ValueError):
    def __init__(self, issues: tuple[CorpusIssue, ...]):
        self.issues = issues
        super().__init__("Manifiesto de corpus inválido: " + "; ".join(i.code for i in issues))


def validate_corpus_manifest(manifest: dict[str, Any], document_root: str | Path,
                             *, require_frozen: bool = False,
                             require_authorized: bool = False,
                             verify_hashes: bool = True) -> tuple[CorpusIssue, ...]:
    """Valida estructura y, si existen hashes, contrasta bytes locales sin mostrarlos."""
    issues: list[CorpusIssue] = []
    if not isinstance(manifest, dict):
        return (CorpusIssue("INVALID_MANIFEST", "$", "se requiere un objeto JSON"),)
    root = Path(document_root).resolve()
    _nonempty(manifest.get("corpus_id"), "corpus_id", issues)
    if manifest.get("schema_version") != "1":
        issues.append(CorpusIssue("UNSUPPORTED_SCHEMA_VERSION", "schema_version", "se requiere schema_version 1"))
    target_period = _nonempty(manifest.get("target_period"), "target_period", issues)
    if manifest.get("unit_of_analysis") != "expediente_documental":
        issues.append(CorpusIssue("INVALID_UNIT", "unit_of_analysis", "la unidad debe ser expediente_documental"))
    status = manifest.get("status")
    if status not in {MANIFEST_DRAFT, MANIFEST_FROZEN}:
        issues.append(CorpusIssue("INVALID_MANIFEST_STATUS", "status", "estado de manifiesto desconocido"))
    if require_frozen and status != MANIFEST_FROZEN:
        issues.append(CorpusIssue("CORPUS_NOT_FROZEN", "status", "el dataset definitivo requiere manifiesto congelado"))
    if status == MANIFEST_FROZEN or require_frozen:
        if not _parse_aware(manifest.get("frozen_at")):
            issues.append(CorpusIssue("INVALID_FREEZE_DATE", "frozen_at", "se requiere fecha ISO-8601 con zona horaria"))
        expected_manifest_hash = manifest.get("manifest_sha256")
        if not _is_sha256(expected_manifest_hash):
            issues.append(CorpusIssue("MANIFEST_HASH_MISSING", "manifest_sha256", "falta SHA-256 del manifiesto"))
        elif _manifest_digest(manifest) != expected_manifest_hash.lower():
            issues.append(CorpusIssue("MANIFEST_HASH_MISMATCH", "manifest_sha256", "el manifiesto cambió después de congelarse"))
    elif manifest.get("manifest_sha256") not in (None, ""):
        issues.append(CorpusIssue("DRAFT_HAS_FREEZE_HASH", "manifest_sha256", "un borrador no debe declarar hash de congelación"))

    authorization = manifest.get("authorization")
    if not isinstance(authorization, dict):
        issues.append(CorpusIssue("AUTHORIZATION_MISSING", "authorization", "falta el registro de autorización"))
    else:
        auth_status = authorization.get("status")
        if auth_status not in {AUTH_PENDING, AUTH_APPROVED, AUTH_DENIED}:
            issues.append(CorpusIssue("INVALID_AUTHORIZATION_STATUS", "authorization.status", "estado de autorización desconocido"))
        if require_authorized and auth_status != AUTH_APPROVED:
            issues.append(CorpusIssue("CORPUS_NOT_AUTHORIZED", "authorization.status", "el corpus definitivo requiere autorización institucional"))
        if auth_status == AUTH_APPROVED:
            for field in ("reference", "approved_by"):
                _nonempty(authorization.get(field), f"authorization.{field}", issues)
            if not _parse_aware(authorization.get("approved_at")):
                issues.append(CorpusIssue("INVALID_AUTHORIZATION_DATE", "authorization.approved_at", "se requiere fecha ISO-8601 con zona horaria"))

    restrictions = manifest.get("privacy_restrictions")
    if not isinstance(restrictions, list) or not restrictions or any(not isinstance(x, str) or not x.strip() for x in restrictions):
        issues.append(CorpusIssue("PRIVACY_RESTRICTIONS_MISSING", "privacy_restrictions", "declare restricciones de privacidad"))
    expedientes = manifest.get("expedientes")
    if not isinstance(expedientes, list) or not expedientes:
        issues.append(CorpusIssue("EXPEDIENTES_MISSING", "expedientes", "no hay expedientes documentados"))
        return tuple(issues)

    seen_expedientes: set[str] = set()
    seen_document_ids: set[str] = set()
    seen_paths: set[str] = set()
    for exp_index, expediente in enumerate(expedientes):
        exp_path = f"expedientes[{exp_index}]"
        if not isinstance(expediente, dict):
            issues.append(CorpusIssue("INVALID_EXPEDIENTE", exp_path, "se esperaba un objeto"))
            continue
        exp_id = _nonempty(expediente.get("expediente_id"), f"{exp_path}.expediente_id", issues)
        if exp_id and exp_id in seen_expedientes:
            issues.append(CorpusIssue("DUPLICATE_EXPEDIENTE", f"{exp_path}.expediente_id", "expediente_id duplicado"))
        if exp_id:
            seen_expedientes.add(exp_id)
        document_period = _nonempty(expediente.get("document_period"), f"{exp_path}.document_period", issues)
        if target_period and document_period and target_period != document_period:
            issues.append(CorpusIssue("DOCUMENT_PERIOD_MISMATCH", f"{exp_path}.document_period",
                                      "periodo documental no coincide con el periodo objetivo del corpus"))
        _nonempty(expediente.get("document_version"), f"{exp_path}.document_version", issues)
        macroprocesos = expediente.get("macroprocesos", [])
        if not isinstance(macroprocesos, list) or any(not isinstance(x, str) or not x.strip() for x in macroprocesos):
            issues.append(CorpusIssue("INVALID_MACROPROCESS_METADATA", f"{exp_path}.macroprocesos", "metadatos deben ser una lista de textos"))
        # macroprocesos are metadata only; the manifest never expands them into experiments.
        catalog_ref = expediente.get("catalog_ref")
        if not isinstance(catalog_ref, dict):
            issues.append(CorpusIssue("CATALOG_BINDING_MISSING", f"{exp_path}.catalog_ref", "vincule explícitamente el catálogo y versión"))
        else:
            _nonempty(catalog_ref.get("catalog_id"), f"{exp_path}.catalog_ref.catalog_id", issues)
            _nonempty(catalog_ref.get("normative_version"), f"{exp_path}.catalog_ref.normative_version", issues)
        documents = expediente.get("documents")
        if not isinstance(documents, list) or not documents:
            issues.append(CorpusIssue("DOCUMENTS_MISSING", f"{exp_path}.documents", "cada expediente requiere documentos"))
            continue
        local_ids: set[str] = set()
        for doc_index, document in enumerate(documents):
            doc_path = f"{exp_path}.documents[{doc_index}]"
            if not isinstance(document, dict):
                issues.append(CorpusIssue("INVALID_DOCUMENT", doc_path, "se esperaba un objeto"))
                continue
            doc_id = _nonempty(document.get("document_id"), f"{doc_path}.document_id", issues)
            relative_path = _nonempty(document.get("relative_path"), f"{doc_path}.relative_path", issues)
            _nonempty(document.get("version"), f"{doc_path}.version", issues)
            _nonempty(document.get("format"), f"{doc_path}.format", issues)
            provenance = document.get("provenance")
            if not isinstance(provenance, dict) or not any(isinstance(v, str) and v.strip() for v in provenance.values()):
                issues.append(CorpusIssue("PROVENANCE_MISSING", f"{doc_path}.provenance", "registre procedencia sin copiar contenido documental"))
            doc_auth = document.get("authorization_status")
            if doc_auth not in {AUTH_PENDING, AUTH_APPROVED, AUTH_DENIED}:
                issues.append(CorpusIssue("INVALID_DOCUMENT_AUTHORIZATION", f"{doc_path}.authorization_status", "estado de autorización desconocido"))
            if require_authorized and doc_auth != AUTH_APPROVED:
                issues.append(CorpusIssue("DOCUMENT_NOT_AUTHORIZED", f"{doc_path}.authorization_status", "documento no autorizado para uso definitivo"))
            if doc_id:
                if doc_id in local_ids or doc_id in seen_document_ids:
                    issues.append(CorpusIssue("DUPLICATE_DOCUMENT_ID", f"{doc_path}.document_id", "document_id duplicado"))
                local_ids.add(doc_id)
                seen_document_ids.add(doc_id)
            if relative_path:
                safe_path = _safe_document_path(root, relative_path)
                if safe_path is None:
                    issues.append(CorpusIssue("UNSAFE_DOCUMENT_PATH", f"{doc_path}.relative_path", "la ruta debe permanecer bajo la raíz del corpus"))
                else:
                    normalized = safe_path.as_posix().casefold()
                    if normalized in seen_paths:
                        issues.append(CorpusIssue("DUPLICATE_DOCUMENT_PATH", f"{doc_path}.relative_path", "ruta de documento duplicada"))
                    seen_paths.add(normalized)
                    if not safe_path.is_file():
                        issues.append(CorpusIssue("DOCUMENT_FILE_MISSING", f"{doc_path}.relative_path", "archivo no encontrado bajo la raíz del corpus"))
                    else:
                        expected = document.get("sha256")
                        if expected is None and not require_frozen:
                            pass
                        elif not _is_sha256(expected):
                            issues.append(CorpusIssue("DOCUMENT_HASH_MISSING", f"{doc_path}.sha256", "falta SHA-256 calculado desde el archivo"))
                        elif verify_hashes:
                            actual = _file_sha256(safe_path)
                            if actual != expected.lower():
                                issues.append(CorpusIssue("DOCUMENT_HASH_MISMATCH", f"{doc_path}.sha256", "el hash no coincide con los bytes del archivo"))
    return tuple(issues)


def freeze_corpus_manifest(manifest: dict[str, Any], document_root: str | Path,
                           *, frozen_at: datetime) -> dict[str, Any]:
    """Calcula hashes desde archivos locales y devuelve una copia congelada.

    No escribe el manifiesto ni copia documentos. El caller debe guardar el
    resultado en el almacén de investigación aprobado.
    """
    if frozen_at.tzinfo is None or frozen_at.utcoffset() is None:
        raise ValueError("frozen_at debe incluir zona horaria")
    issues = validate_corpus_manifest(manifest, document_root,
                                      require_authorized=True, verify_hashes=True)
    if issues:
        raise CorpusManifestError(issues)
    frozen = deepcopy(manifest)
    root = Path(document_root).resolve()
    for expediente in frozen["expedientes"]:
        for document in expediente["documents"]:
            path = _safe_document_path(root, document["relative_path"])
            if path is None or not path.is_file():
                raise CorpusManifestError((CorpusIssue("DOCUMENT_FILE_MISSING", "expedientes.documents", "archivo no disponible para congelación"),))
            document["sha256"] = _file_sha256(path)
    frozen["status"] = MANIFEST_FROZEN
    frozen["frozen_at"] = frozen_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    frozen["manifest_sha256"] = _manifest_digest(frozen)
    issues = validate_corpus_manifest(frozen, root, require_frozen=True,
                                      require_authorized=True, verify_hashes=True)
    if issues:
        raise CorpusManifestError(issues)
    return frozen


def _safe_document_path(root: Path, relative_path: str) -> Path | None:
    candidate = Path(relative_path)
    if candidate.is_absolute() or any(part == ".." for part in candidate.parts):
        return None
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return None
    return resolved


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _manifest_digest(manifest: dict[str, Any]) -> str:
    payload = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
        return True
    except ValueError:
        return False


def _parse_aware(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _nonempty(value: Any, path: str, issues: list[CorpusIssue]) -> str | None:
    if not isinstance(value, str) or not value.strip():
        issues.append(CorpusIssue("REQUIRED_FIELD_MISSING", path, "campo obligatorio ausente"))
        return None
    return value.strip()
