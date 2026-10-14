"""Adaptadores mínimos a funciones originales cuya ejecución aislada es segura."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib
import inspect
from pathlib import Path
import time
from uuid import uuid4

from .analytical_contracts import (AnalyticalExecutionRecord, AnalyticalInput,
                                  AnalyticalKind, AnalyticalStatus)
from .schemas import Macroprocess


class SyllabusAnalyzerAdapter:
    """Llama la función productiva original en curricular_analyzer.py, no una copia."""
    macroproceso = Macroprocess.SYLLABUS

    def run(self, data: AnalyticalInput) -> AnalyticalExecutionRecord:
        if data.macroproceso is not self.macroproceso:
            raise ValueError("el adaptador requiere macroproceso gestion_silabos")
        started_at = datetime.now(timezone.utc)
        started = time.perf_counter_ns()
        try:
            # El módulo destino solo importa re y unicodedata. No importar syllabus_graph:
            # ese módulo inicializa Supabase y carga Gemini/descarga de documentos.
            from backend.app.agents.curricular_analyzer import analizar_texto_silabo

            source_path = Path(inspect.getsourcefile(analizar_texto_silabo)).resolve()
            digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
            original = analizar_texto_silabo(data.text, data.metadata)
            return AnalyticalExecutionRecord(
                execution_id=str(uuid4()), expediente_id=data.expediente_id,
                macroproceso=data.macroproceso, document_ids=data.document_ids,
                kind=AnalyticalKind.ORIGINAL_ANALYTICAL,
                function_name="backend.app.agents.curricular_analyzer.analizar_texto_silabo",
                code_sha256=digest, status=AnalyticalStatus.COMPLETED,
                analysis_data=original, normative_results=None,
                started_at=started_at, finished_at=datetime.now(timezone.utc),
                duration_ns=time.perf_counter_ns() - started,
                processing_mode="reglas_deterministas_originales",
                provenance={**data.provenance, "module": "backend.app.agents.curricular_analyzer",
                            "source_file": source_path.name,
                            "normative_assessment_performed": False})
        except Exception as exc:
            return AnalyticalExecutionRecord(
                execution_id=str(uuid4()), expediente_id=data.expediente_id,
                macroproceso=data.macroproceso, document_ids=data.document_ids,
                kind=AnalyticalKind.ORIGINAL_ANALYTICAL, code_sha256=None,
                function_name="backend.app.agents.curricular_analyzer.analizar_texto_silabo",
                status=AnalyticalStatus.ERROR, analysis_data=None, normative_results=None,
                started_at=started_at, finished_at=datetime.now(timezone.utc),
                duration_ns=time.perf_counter_ns() - started,
                processing_mode="reglas_deterministas_originales",
                provenance={**data.provenance, "normative_assessment_performed": False},
                error_type=type(exc).__name__, error_message=str(exc)[:500])


class OriginalMacroprocessAdapter:
    """Ejecuta en secuencia las funciones analíticas originales sin importar el grafo."""

    def __init__(self, macroproceso: Macroprocess, module_name: str, function_names: tuple[str, ...]):
        self.macroproceso = macroproceso
        self.module_name = module_name
        self.function_names = function_names
        self.function_name = ",".join(f"{module_name}.{name}" for name in function_names)

    def run(self, data: AnalyticalInput) -> AnalyticalExecutionRecord:
        if data.macroproceso is not self.macroproceso:
            raise ValueError("el adaptador no corresponde al macroproceso solicitado")
        started_at = datetime.now(timezone.utc)
        started = time.perf_counter_ns()
        digest = None
        try:
            evidencias = data.metadata.get("evidencias")
            if not isinstance(evidencias, list) or any(not isinstance(item, dict) for item in evidencias):
                raise ValueError("metadata.evidencias debe ser una lista de objetos sintéticos")
            module = importlib.import_module(self.module_name)
            functions = [getattr(module, name) for name in self.function_names]
            source_path = Path(inspect.getsourcefile(functions[0])).resolve()
            digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
            analysis_state = {"evidencias": evidencias}
            for function in functions:
                analysis_state = function(analysis_state)
            return AnalyticalExecutionRecord(
                execution_id=str(uuid4()), expediente_id=data.expediente_id,
                macroproceso=data.macroproceso, document_ids=data.document_ids,
                kind=AnalyticalKind.ORIGINAL_ANALYTICAL, function_name=self.function_name,
                code_sha256=digest, status=AnalyticalStatus.COMPLETED,
                analysis_data=analysis_state, normative_results=None,
                started_at=started_at, finished_at=datetime.now(timezone.utc),
                duration_ns=time.perf_counter_ns() - started,
                processing_mode="reglas_deterministas_originales",
                provenance={**data.provenance, "module": self.module_name,
                            "source_file": source_path.name,
                            "functions": list(self.function_names),
                            "normative_assessment_performed": False})
        except Exception as exc:
            return AnalyticalExecutionRecord(
                execution_id=str(uuid4()), expediente_id=data.expediente_id,
                macroproceso=data.macroproceso, document_ids=data.document_ids,
                kind=AnalyticalKind.ORIGINAL_ANALYTICAL, function_name=self.function_name,
                code_sha256=digest, status=AnalyticalStatus.ERROR,
                analysis_data=None, normative_results=None, started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                duration_ns=time.perf_counter_ns() - started,
                processing_mode="reglas_deterministas_originales",
                provenance={**data.provenance, "module": self.module_name,
                            "normative_assessment_performed": False},
                error_type=type(exc).__name__, error_message=str(exc)[:500])


ACADEMIC_ADAPTER = OriginalMacroprocessAdapter(
    Macroprocess.ACADEMIC,
    "backend.app.agents.gestion_academica_analysis",
    ("calcular_indicadores_gestion_academica", "clasificar_evidencias_academicas",
     "detectar_riesgos_academicos"))

PLANNING_ADAPTER = OriginalMacroprocessAdapter(
    Macroprocess.PLANNING,
    "backend.app.agents.planificacion_analysis",
    ("calcular_indicadores_planificacion", "detectar_riesgos_estrategicos"))
