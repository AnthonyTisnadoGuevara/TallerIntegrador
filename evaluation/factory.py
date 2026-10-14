"""Constructores del fixture técnico sintético, no datos de investigación."""
from __future__ import annotations
import json
from pathlib import Path
import platform
from .schemas import DocumentReference, EffectiveMode, ExperimentConfig, Expediente, RunType


def synthetic_expediente() -> Expediente:
    raw = json.loads((Path(__file__).parent / "fixtures" / "synthetic_expediente.json").read_text(encoding="utf-8"))
    doc = DocumentReference(**raw["document"])
    return Expediente(raw["expediente_id"], raw["corpus_id"], (doc,), raw["document_version"], "b" * 64)


def synthetic_config() -> ExperimentConfig:
    return ExperimentConfig(
        config_id="synthetic-smoke-v1", code_sha256="c" * 64,
        python_version=platform.python_version(), dependency_versions={"python-stdlib": platform.python_version()},
        provider=None, model=None, model_version=None,
        model_version_reason="No se usa proveedor ni modelo en el simulador.",
        temperature=None, seed=None,
        generation_null_reason="Ejecución determinista local; no hay generación LLM.",
        prompt_sha256="d" * 64, catalog_sha256="e" * 64, corpus_sha256="f" * 64,
        run_type=RunType.SYNTHETIC, effective_mode=EffectiveMode.SYNTHETIC)
