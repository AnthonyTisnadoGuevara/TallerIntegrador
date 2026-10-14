"""Lector local, acotado a UTF-8 .txt; nunca abre URLs ni importa backend."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import hashlib
from pathlib import Path, PurePosixPath, PureWindowsPath

from .schemas import DocumentReference


class DocumentReadError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class DocumentStatus(str, Enum):
    READ = "leido"
    EMPTY = "vacio"
    UNSUPPORTED = "formato_no_admitido"
    MISSING = "inexistente"
    HASH_MISMATCH = "hash_incompatible"
    INVALID_REFERENCE = "referencia_invalida"
    INVALID_ENCODING = "codificacion_invalida"


@dataclass(frozen=True)
class ExtractedDocument:
    document_id: str
    text: str
    sha256: str
    relative_locator: str
    line_count: int


def read_local_document(document: DocumentReference, root: str | Path,
                        *, max_bytes: int = 10 * 1024 * 1024) -> ExtractedDocument:
    """Lee un .txt bajo root, impidiendo URL, traversal y symlink fuera de root."""
    locator = document.locator.strip()
    windows_locator = PureWindowsPath(locator)
    posix_locator = PurePosixPath(locator.replace("\\", "/"))
    if ("://" in locator or windows_locator.is_absolute() or posix_locator.is_absolute()
            or ".." in windows_locator.parts or ".." in posix_locator.parts
            or windows_locator.drive or not locator):
        raise DocumentReadError("invalid_reference", "referencia documental local inválida")
    if document.format.lower() not in {"txt", "text/plain"} or Path(locator).suffix.lower() != ".txt":
        raise DocumentReadError("unsupported_format", "solo se admite texto plano .txt en esta fase")
    base = Path(root).resolve()
    try:
        candidate = (base / Path(*posix_locator.parts)).resolve(strict=True)
    except FileNotFoundError as exc:
        raise DocumentReadError("document_not_found", "archivo local no encontrado") from exc
    except OSError as exc:
        raise DocumentReadError("document_read_error", "no se pudo resolver el archivo local") from exc
    if not candidate.is_relative_to(base):
        raise DocumentReadError("invalid_reference", "referencia escapa del directorio autorizado")
    if not candidate.is_file():
        raise DocumentReadError("document_not_found", "la referencia no corresponde a un archivo")
    try:
        if candidate.stat().st_size > max_bytes:
            raise DocumentReadError("document_too_large", "archivo supera el tamaño permitido")
        content = candidate.read_bytes()
    except DocumentReadError:
        raise
    except OSError as exc:
        raise DocumentReadError("document_read_error", "no se pudo leer el archivo local") from exc
    digest = hashlib.sha256(content).hexdigest()
    if digest.lower() != document.sha256.lower():
        raise DocumentReadError("hash_mismatch", "hash documental no coincide")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DocumentReadError("invalid_encoding", "el archivo no está codificado en UTF-8") from exc
    if not text.strip():
        raise DocumentReadError("empty_document", "el documento no contiene texto")
    return ExtractedDocument(document.document_id, text, digest, posix_locator.as_posix(),
                             len(text.splitlines()))
