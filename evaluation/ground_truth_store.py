"""Almacén JSONL local separado para anotaciones de referencia (nunca agente)."""
from __future__ import annotations
import json
import os
from pathlib import Path
import threading
import time
from uuid import uuid4

from .ground_truth import (DisagreementResolution, GroundTruthAnnotation,
                           GroundTruthRecord, GroundTruthStatus)
from .contracts import EvidenceReference, LocationStatus, ReviewStatus
from .schemas import ApplicabilityStatus, Classification, Macroprocess, canonical_json, sha256_json


class GroundTruthStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else Path(__file__).parent / "outputs" / "ground_truth.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def save_snapshot(self, record: GroundTruthRecord) -> str:
        payload = _serialize(record)
        digest = sha256_json(payload)
        with self._lock:
            lock_path = self.path.with_suffix(self.path.suffix + ".lock")
            deadline = time.monotonic() + 5
            while True:
                try:
                    fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                    os.close(fd)
                    break
                except FileExistsError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("almacén Ground Truth ocupado")
                    time.sleep(0.025)
            try:
                existing = self.read_all()
                if any(sha256_json(_serialize(item)) == digest for item in existing):
                    raise ValueError("snapshot Ground Truth duplicado")
                snapshot_id = str(uuid4())
                envelope = {"snapshot_id": snapshot_id, "record": payload,
                            "integrity_sha256": digest}
                with self.path.open("a", encoding="utf-8", newline="\n") as stream:
                    stream.write(canonical_json(envelope) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                return snapshot_id
            finally:
                lock_path.unlink(missing_ok=True)

    def read_all(self) -> list[GroundTruthRecord]:
        if not self.path.exists():
            return []
        records = []
        seen_ids = set()
        with self.path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                try:
                    envelope = json.loads(line)
                    payload = envelope["record"]
                    if sha256_json(payload) != envelope["integrity_sha256"]:
                        raise ValueError("huella incompatible")
                    if envelope["snapshot_id"] in seen_ids:
                        raise ValueError("snapshot duplicado")
                    seen_ids.add(envelope["snapshot_id"])
                    records.append(_deserialize(payload))
                except Exception as exc:
                    raise ValueError(f"registro Ground Truth inválido en línea {line_number}: {type(exc).__name__}") from exc
        return records


def _serialize(record: GroundTruthRecord) -> dict:
    from .schemas import to_primitive
    return to_primitive(record)


def _deserialize(data: dict) -> GroundTruthRecord:
    def evidence(raw):
        return EvidenceReference(**{**raw, "location_status": LocationStatus(raw["location_status"])})

    annotations = tuple(GroundTruthAnnotation(
        annotation_id=item["annotation_id"], expediente_id=item["expediente_id"],
        criterion_id=item["criterion_id"], normative_version=item["normative_version"],
        evaluator_id=item["evaluator_id"], applicability=ApplicabilityStatus(item["applicability"]),
        reference_label=Classification(item["reference_label"]) if item["reference_label"] else None,
        reference_verdict=item["reference_verdict"], evidence=tuple(evidence(ev) for ev in item["evidence"]),
        review_status=ReviewStatus(item["review_status"]),
        annotated_at=_datetime(item["annotated_at"]), annotation_version=item["annotation_version"],
        reviewed_at=_datetime(item["reviewed_at"]) if item.get("reviewed_at") else None,
        macroproceso=Macroprocess(item["macroproceso"]) if item.get("macroproceso") else None)
        for item in data["annotations"])
    resolution_data = data.get("disagreement_resolution")
    resolution = None
    if resolution_data:
        resolution = DisagreementResolution(
            tuple(resolution_data["annotation_ids"]),
            ApplicabilityStatus(resolution_data["resolved_applicability"]),
            Classification(resolution_data["resolved_label"]) if resolution_data["resolved_label"] else None,
            resolution_data["rationale"], resolution_data["adjudicator_id"],
            _datetime(resolution_data["resolved_at"]))
    return GroundTruthRecord(
        expediente_id=data["expediente_id"], criterion_id=data["criterion_id"],
        catalog_id=data["catalog_id"], normative_version=data["normative_version"],
        annotations=annotations, status=GroundTruthStatus(data["status"]),
        disagreement_resolution=resolution,
        final_applicability=ApplicabilityStatus(data["final_applicability"]) if data.get("final_applicability") else None,
        final_label=Classification(data["final_label"]) if data.get("final_label") else None,
        reference_verdict=data.get("reference_verdict"), validated_by=data.get("validated_by"),
        validated_at=_datetime(data["validated_at"]) if data.get("validated_at") else None,
        validation_version=data.get("validation_version"),
        macroproceso=Macroprocess(data["macroproceso"]) if data.get("macroproceso") else None)


def _datetime(value: str):
    from datetime import datetime
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
