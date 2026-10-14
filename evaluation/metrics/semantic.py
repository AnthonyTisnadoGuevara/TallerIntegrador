"""Interfaces semánticas y carga local-only de BERTScore/embeddings."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import importlib.metadata
import importlib.util
import math
import os
from pathlib import Path
from typing import Protocol, Iterable

from ..ground_truth import GroundTruthRecord
from ..schemas import ApplicabilityStatus, EvaluationState, ExecutionStatus
from .common import RunSelection, index_final_ground_truth, result_index


class SemanticDependencyError(RuntimeError):
    pass


def semantic_dependency_inventory() -> dict[str, bool]:
    return {name: importlib.util.find_spec(name) is not None
            for name in ("bert_score", "torch", "transformers", "sentence_transformers")}


class BertScoreProvider(Protocol):
    metadata: dict

    def score_pair(self, candidate: str, reference: str) -> dict: ...


class EmbeddingProvider(Protocol):
    metadata: dict

    def embed_pair(self, candidate: str, reference: str) -> tuple[list[float], list[float]]: ...


@dataclass(frozen=True)
class SemanticPair:
    expediente_id: str
    macroproceso: str | None
    criterion_id: str
    normative_version: str
    execution_id: str
    experiment_id: str | None
    replica: int
    candidate: str
    reference: str


def build_semantic_pairs(ground_truth: Iterable[GroundTruthRecord],
                         selection: RunSelection) -> tuple[list[SemanticPair], list[dict]]:
    refs, exclusions = index_final_ground_truth(ground_truth, selection.macroproceso)
    pairs: list[SemanticPair] = []
    result_indexes = {exp_id: result_index(run)
                      for exp_id, run in selection.selected_by_expediente.items()}
    for key, reference in sorted(refs.items()):
        exp_id, criterion_id, version = key
        reason = None
        if reference.final_applicability is not ApplicabilityStatus.APPLICABLE:
            reason = "reference_applicability_not_applicable_or_undetermined"
        elif not reference.reference_verdict or not reference.reference_verdict.strip():
            reason = "reference_dictamen_empty"
        execution = selection.selected_by_expediente.get(exp_id)
        if reason is None and execution is None:
            reason = "primary_execution_missing"
        elif reason is None and execution.status is ExecutionStatus.ERROR:
            reason = "execution_failed"
        result = result_indexes.get(exp_id, {}).get(key) if execution is not None else None
        if reason is None and result is None:
            reason = "criterion_or_version_not_matched"
        elif reason is None and result.evaluation_state is not EvaluationState.EVALUATED:
            reason = f"prediction_not_evaluated:{result.evaluation_state.value}"
        elif reason is None and not result.rationale.strip():
            reason = "candidate_dictamen_empty"
        if reason:
            exclusions.append({"expediente_id": exp_id, "criterion_id": criterion_id,
                               "normative_version": version, "reason": reason})
            continue
        pairs.append(SemanticPair(exp_id, selection.macroproceso.value if selection.macroproceso else None, criterion_id, version, execution.execution_id,
                                  execution.experiment_id, execution.replica,
                                  result.rationale, reference.reference_verdict))
    return pairs, exclusions


def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    a, b = tuple(float(v) for v in left), tuple(float(v) for v in right)
    if not a or len(a) != len(b):
        raise ValueError("embeddings vacíos o de dimensiones distintas")
    if not all(math.isfinite(value) for value in (*a, *b)):
        raise ValueError("embedding contiene valores no finitos")
    norm_a = math.sqrt(sum(value * value for value in a))
    norm_b = math.sqrt(sum(value * value for value in b))
    if norm_a == 0 or norm_b == 0:
        raise ValueError("similitud coseno no definida para vector cero")
    return sum(x * y for x, y in zip(a, b)) / (norm_a * norm_b)


def score_semantic_pairs(pairs: Iterable[SemanticPair], bert: BertScoreProvider,
                         embedder: EmbeddingProvider) -> tuple[list[dict], dict]:
    rows = []
    bert_scores, cosine_scores = [], []
    for pair in pairs:
        row = {"expediente_id": pair.expediente_id, "criterion_id": pair.criterion_id,
               "normative_version": pair.normative_version,
               "execution_id": pair.execution_id, "experiment_id": pair.experiment_id,
               "replica": pair.replica, "status": "computed", "bertscore_error": None,
               "cosine_error": None,
               "bertscore_precision": None, "bertscore_recall": None,
               "bertscore_f1": None, "cosine_similarity": None}
        try:
            bert_values = bert.score_pair(pair.candidate, pair.reference)
            row.update({"bertscore_precision": bert_values["precision"],
                        "bertscore_recall": bert_values["recall"],
                        "bertscore_f1": bert_values["f1"],
                        "candidate_truncated": bert_values.get("candidate_truncated"),
                        "reference_truncated": bert_values.get("reference_truncated")})
            bert_scores.append(bert_values["f1"])
        except Exception as exc:
            row["bertscore_error"] = type(exc).__name__
        try:
            vectors = embedder.embed_pair(pair.candidate, pair.reference)
            cosine = cosine_similarity(*vectors)
            row["cosine_similarity"] = cosine
            cosine_scores.append(cosine)
        except Exception as exc:
            row["cosine_error"] = type(exc).__name__
        row["status"] = ("computed" if row["bertscore_error"] is None and row["cosine_error"] is None
                         else "partially_calculable" if row["bertscore_error"] is None or row["cosine_error"] is None
                         else "not_calculable")
        rows.append(row)
    from .common import summarize_numbers
    summary = {
        "matched_pairs": len(rows),
        "fully_computed_pairs": sum(row["status"] == "computed" for row in rows),
        "partially_calculable_pairs": sum(row["status"] == "partially_calculable" for row in rows),
        "not_calculable_pairs": sum(row["status"] == "not_calculable" for row in rows),
        "bertscore_valid_pairs": sum(row["bertscore_error"] is None for row in rows),
        "cosine_valid_pairs": sum(row["cosine_error"] is None for row in rows),
        "bertscore_f1": summarize_numbers(bert_scores),
        "cosine_similarity": summarize_numbers(cosine_scores),
        "bert_model": bert.metadata,
        "embedding_model": embedder.metadata,
        "interpretation_limit": "semantic similarity is not evidence of normative correctness",
    }
    return rows, summary


class BertScoreLocal:
    """BERTScore es real; exige pesos locales para impedir descargas implícitas."""
    MODEL = "bert-base-multilingual-cased"
    TOKENIZER = "AutoTokenizer (slow; same local model directory)"
    MAX_CONTENT_TOKENS = 510

    def __init__(self, model_dir: str | Path, model_revision: str):
        self.model_dir = _require_local_dir(model_dir, "BERTScore")
        self.revision = _require_revision(model_revision)
        missing = [name for name in ("bert_score", "torch", "transformers")
                   if importlib.util.find_spec(name) is None]
        if missing:
            raise SemanticDependencyError("BERTScore bloqueado; faltan dependencias: " + ", ".join(missing))
        try:
            from transformers import AutoTokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(
                str(self.model_dir), local_files_only=True, use_fast=False)
            from bert_score import score as bert_score
        except Exception as exc:
            raise SemanticDependencyError(f"no se pudo cargar el modelo/tokenizador local ({type(exc).__name__})") from exc
        self._score = bert_score
        self.metadata = {
            "metric": "BERTScore", "model_name": self.MODEL,
            "model_dir_label": self.model_dir.name, "model_revision_declared": self.revision,
            "library": "bert-score", "library_version": _version("bert-score"),
            "transformers_version": _version("transformers"),
            "tokenizer": self.TOKENIZER, "language": "es", "num_layers": 9,
            "device": "cpu", "idf": False, "baseline_rescaling": False,
            "max_content_tokens": self.MAX_CONTENT_TOKENS,
            "truncation": "BERTScore tokenizer truncates to model max; >510 content tokens is flagged",
            "normalization": "BERTScore contextual-token matching; no baseline rescaling",
            "revision_verification": "full Hub commit SHA supplied; local directory-to-commit mapping is not independently checked",
        }

    def score_pair(self, candidate: str, reference: str) -> dict:
        cand_tokens = len(self._tokenizer.encode(candidate, add_special_tokens=False))
        ref_tokens = len(self._tokenizer.encode(reference, add_special_tokens=False))
        with _offline_model_loading():
            scores, _ = self._score(
                [candidate], [reference], model_type=str(self.model_dir), num_layers=9,
                lang="es", verbose=False, idf=False, device="cpu", batch_size=1,
                return_hash=True, rescale_with_baseline=False, use_fast_tokenizer=False)
        precision, recall, f1 = scores
        return {"precision": float(precision[0].item()), "recall": float(recall[0].item()),
                "f1": float(f1[0].item()),
                "candidate_truncated": cand_tokens > self.MAX_CONTENT_TOKENS,
                "reference_truncated": ref_tokens > self.MAX_CONTENT_TOKENS}


class SentenceTransformerLocal:
    """Embedding coseno real usando exclusivamente un directorio local."""
    MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

    def __init__(self, model_dir: str | Path, model_revision: str):
        self.model_dir = _require_local_dir(model_dir, "sentence-transformers")
        self.revision = _require_revision(model_revision)
        if importlib.util.find_spec("sentence_transformers") is None:
            raise SemanticDependencyError("similitud coseno bloqueada; falta sentence-transformers")
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(str(self.model_dir), device="cpu",
                                              local_files_only=True, trust_remote_code=False)
        except Exception as exc:
            raise SemanticDependencyError(f"no se pudo cargar el modelo de embeddings local ({type(exc).__name__})") from exc
        self.metadata = {
            "metric": "cosine_similarity", "model_name": self.MODEL,
            "model_dir_label": self.model_dir.name, "model_revision_declared": self.revision,
            "library": "sentence-transformers",
            "library_version": _version("sentence-transformers"),
            "tokenizer": "tokenizer incluido en el artefacto SentenceTransformer local",
            "device": "cpu", "normalization": "vectores L2-normalizados antes del coseno",
            "embedding_dimension": self._model.get_sentence_embedding_dimension(),
            "max_sequence_length": getattr(self._model, "max_seq_length", None),
            "revision_verification": "full Hub commit SHA supplied; local directory-to-commit mapping is not independently checked",
        }

    def embed_pair(self, candidate: str, reference: str) -> tuple[list[float], list[float]]:
        with _offline_model_loading():
            vectors = self._model.encode([candidate, reference], convert_to_numpy=True,
                                         normalize_embeddings=True, show_progress_bar=False)
        return vectors[0].tolist(), vectors[1].tolist()


def _require_local_dir(model_dir: str | Path, label: str) -> Path:
    path = Path(model_dir).expanduser()
    if not path.is_dir():
        raise SemanticDependencyError(f"{label}: se requiere un directorio local de modelo; no se descargará ninguno")
    return path.resolve()


def _require_revision(value: str) -> str:
    if not value or not value.strip():
        raise SemanticDependencyError("indique --model-revision para registrar la revisión del modelo local")
    revision = value.strip().lower()
    if len(revision) != 40 or any(character not in "0123456789abcdef" for character in revision):
        raise SemanticDependencyError("model-revision debe ser el commit SHA completo de 40 caracteres")
    return revision


def _version(package: str) -> str | None:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return None


@contextmanager
def _offline_model_loading():
    keys = ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")
    old = {key: os.environ.get(key) for key in keys}
    try:
        for key in keys:
            os.environ[key] = "1"
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
