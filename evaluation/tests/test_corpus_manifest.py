from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import tempfile
from pathlib import Path
import unittest

from evaluation.catalog import approve_catalog, load_catalog
from evaluation.contracts import EvidenceReference, LocationStatus
from evaluation.corpus_manifest import (CorpusManifestError, freeze_corpus_manifest,
                                        validate_corpus_manifest)
from evaluation.dataset import validate_final_dataset
from evaluation.ground_truth import (GroundTruthAnnotation, GroundTruthRecord,
                                     GroundTruthStatus)
from evaluation.schemas import (ApplicabilityStatus, Classification, DocumentReference,
                                Expediente)
from evaluation.contracts import ReviewStatus


FIXTURES = Path(__file__).parents[1] / "fixtures"
NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)


class CorpusManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.file = self.root / "exp-001" / "documento.txt"
        self.file.parent.mkdir(parents=True)
        self.file.write_text("contenido sintético de prueba", encoding="utf-8")
        self.catalog = load_catalog(FIXTURES / "synthetic_catalog.json")
        self.manifest = {
            "schema_version": "1",
            "corpus_id": "SYNTH-CORPUS-TEST",
            "target_period": "2025",
            "unit_of_analysis": "expediente_documental",
            "status": "borrador",
            "frozen_at": None,
            "manifest_sha256": None,
            "authorization": {
                "status": "autorizado", "reference": "synthetic-test-approval",
                "approved_by": "synthetic-reviewer", "approved_at": NOW.isoformat(),
            },
            "privacy_restrictions": ["datos exclusivamente sintéticos de prueba"],
            "expedientes": [{
                "expediente_id": "SYNTH-EXP-001",
                "document_period": "2025",
                "document_version": "v1",
                "catalog_ref": {"catalog_id": self.catalog.catalog_id,
                                "normative_version": self.catalog.normative_version},
                "macroprocesos": ["gestion_academica", "gestion_silabos"],
                "documents": [{
                    "document_id": "SYNTH-DOC-001", "relative_path": "exp-001/documento.txt",
                    "version": "v1", "format": "txt", "sha256": None,
                    "provenance": {"source_system": "synthetic_fixture"},
                    "authorization_status": "autorizado",
                }],
            }],
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_freeze_computes_real_file_hash_and_reproducible_manifest_hash(self):
        frozen = freeze_corpus_manifest(self.manifest, self.root, frozen_at=NOW)
        self.assertEqual(frozen["expedientes"][0]["documents"][0]["sha256"],
                         hashlib.sha256(self.file.read_bytes()).hexdigest())
        self.assertEqual(validate_corpus_manifest(frozen, self.root,
                                                   require_frozen=True,
                                                   require_authorized=True), ())
        self.assertEqual(self.manifest["status"], "borrador")  # pure copy; source not mutated

    def test_tampered_document_or_manifest_is_rejected(self):
        frozen = freeze_corpus_manifest(self.manifest, self.root, frozen_at=NOW)
        self.file.write_text("contenido cambiado", encoding="utf-8")
        codes = {issue.code for issue in validate_corpus_manifest(
            frozen, self.root, require_frozen=True, require_authorized=True)}
        self.assertIn("DOCUMENT_HASH_MISMATCH", codes)
        self.file.write_text("contenido sintético de prueba", encoding="utf-8")
        frozen["expedientes"][0]["document_version"] = "v2"
        codes = {issue.code for issue in validate_corpus_manifest(
            frozen, self.root, require_frozen=True, require_authorized=True)}
        self.assertIn("MANIFEST_HASH_MISMATCH", codes)

    def test_freeze_rejects_pending_authorization_and_unsafe_path(self):
        self.manifest["authorization"]["status"] = "pendiente"
        with self.assertRaises(CorpusManifestError):
            freeze_corpus_manifest(self.manifest, self.root, frozen_at=NOW)
        self.manifest["authorization"]["status"] = "autorizado"
        self.manifest["expedientes"][0]["documents"][0]["relative_path"] = "../outside.txt"
        codes = {issue.code for issue in validate_corpus_manifest(self.manifest, self.root)}
        self.assertIn("UNSAFE_DOCUMENT_PATH", codes)

    def test_freeze_rejects_a_supplied_hash_that_does_not_match_the_file(self):
        self.manifest["expedientes"][0]["documents"][0]["sha256"] = "0" * 64
        with self.assertRaises(CorpusManifestError) as caught:
            freeze_corpus_manifest(self.manifest, self.root, frozen_at=NOW)
        self.assertIn("DOCUMENT_HASH_MISMATCH", {issue.code for issue in caught.exception.issues})

    def test_document_period_must_match_the_declared_study_period(self):
        self.manifest["expedientes"][0]["document_period"] = "2024"
        codes = {issue.code for issue in validate_corpus_manifest(self.manifest, self.root)}
        self.assertIn("DOCUMENT_PERIOD_MISMATCH", codes)

    def test_duplicate_document_identifiers_and_paths_are_reported(self):
        duplicate = dict(self.manifest["expedientes"][0]["documents"][0])
        self.manifest["expedientes"][0]["documents"].append(duplicate)
        codes = {issue.code for issue in validate_corpus_manifest(self.manifest, self.root)}
        self.assertIn("DUPLICATE_DOCUMENT_ID", codes)
        self.assertIn("DUPLICATE_DOCUMENT_PATH", codes)

    def test_final_dataset_requires_ground_truth_for_each_catalog_criterion(self):
        frozen = freeze_corpus_manifest(self.manifest, self.root, frozen_at=NOW)
        catalog = approve_catalog(self.catalog, validated_by="synthetic-reviewer",
                                  approval_reference="synthetic-test-approval", validated_at=NOW)
        file_hash = frozen["expedientes"][0]["documents"][0]["sha256"]
        document = DocumentReference("SYNTH-DOC-001", "synthetic document", "txt",
                                     file_hash, "v1", "exp-001/documento.txt")
        expediente = Expediente("SYNTH-EXP-001", "SYNTH-CORPUS-TEST", (document,),
                                 "v1", file_hash, source="sintetico")
        issues = validate_final_dataset(manifest=frozen, document_root=self.root,
                                        expedientes=(expediente,), catalogs=(catalog,),
                                        ground_truth=())
        self.assertIn("GROUND_TRUTH_MISSING", {issue.code for issue in issues})

    def test_final_dataset_accepts_complete_synthetic_contract_only(self):
        frozen = freeze_corpus_manifest(self.manifest, self.root, frozen_at=NOW)
        catalog = approve_catalog(self.catalog, validated_by="synthetic-reviewer",
                                  approval_reference="synthetic-test-approval", validated_at=NOW)
        file_hash = frozen["expedientes"][0]["documents"][0]["sha256"]
        doc_id = "SYNTH-DOC-001"
        document = DocumentReference(doc_id, "synthetic document", "txt", file_hash,
                                     "v1", "exp-001/documento.txt")
        expediente = Expediente("SYNTH-EXP-001", "SYNTH-CORPUS-TEST", (document,),
                                 "v1", file_hash, source="sintetico")
        criterion_id = catalog.criteria[0].criterion_id
        evidence = (EvidenceReference(expediente.expediente_id, doc_id,
                                      LocationStatus.LOCATED, locator="line:1"),)
        annotations = tuple(GroundTruthAnnotation(
            f"SYNTH-ANN-{index}", expediente.expediente_id, criterion_id,
            catalog.normative_version, f"synthetic-evaluator-{index}",
            ApplicabilityStatus.APPLICABLE, Classification.CONFORMING,
            "Dictamen sintético de prueba.", evidence, ReviewStatus.REVIEWED,
            NOW, "synthetic-v1", NOW)
            for index in (1, 2))
        reference = GroundTruthRecord(
            expediente.expediente_id, criterion_id, catalog.catalog_id,
            catalog.normative_version, annotations, GroundTruthStatus.VALIDATED,
            final_applicability=ApplicabilityStatus.APPLICABLE,
            final_label=Classification.CONFORMING,
            reference_verdict="Dictamen sintético de prueba.",
            validated_by="synthetic-adjudicator", validated_at=NOW,
            validation_version="synthetic-gt-v1")
        issues = validate_final_dataset(manifest=frozen, document_root=self.root,
                                        expedientes=(expediente,), catalogs=(catalog,),
                                        ground_truth=(reference,))
        self.assertEqual(issues, ())
        no_evidence = replace(reference, annotations=tuple(
            replace(annotation, evidence=()) for annotation in reference.annotations))
        issues = validate_final_dataset(manifest=frozen, document_root=self.root,
                                        expedientes=(expediente,), catalogs=(catalog,),
                                        ground_truth=(no_evidence,))
        self.assertIn("REFERENCE_EVIDENCE_MISSING", {issue.code for issue in issues})


if __name__ == "__main__":
    unittest.main()
