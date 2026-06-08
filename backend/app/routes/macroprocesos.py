from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.agents.planificacion_graph import ejecutar_grafo_planificacion
from app.services.supabase_client import supabase


router = APIRouter(
    prefix="/api/macroprocesos",
    tags=["Macroprocesos"],
)

ESTADOS_VALIDOS = {"pendiente", "en_proceso", "completado", "observado"}
PRIORIDADES_VALIDAS = {"alta", "media", "baja"}
ORDEN_PRIORIDAD = {"alta": 0, "media": 1, "baja": 2}
ORDEN_ESTADO = {"pendiente": 0, "en_proceso": 1, "observado": 2, "completado": 3}


class EvidenciaCreate(BaseModel):
    macroproceso: str
    codigo: Optional[str] = None
    titulo: str
    descripcion: Optional[str] = None
    tipo_evidencia: Optional[str] = None
    responsable: Optional[str] = None
    mes_programado: Optional[str] = None
    fecha_programada: Optional[str] = None
    fecha_cumplimiento: Optional[str] = None
    estado: Optional[str] = "pendiente"
    prioridad: Optional[str] = "media"
    avance: Optional[int] = Field(0, ge=0, le=100)
    observacion: Optional[str] = None
    archivo_url: Optional[str] = None
    origen_documento: Optional[str] = None


class EvidenciaUpdate(BaseModel):
    macroproceso: Optional[str] = None
    codigo: Optional[str] = None
    titulo: Optional[str] = None
    descripcion: Optional[str] = None
    tipo_evidencia: Optional[str] = None
    responsable: Optional[str] = None
    mes_programado: Optional[str] = None
    fecha_programada: Optional[str] = None
    fecha_cumplimiento: Optional[str] = None
    estado: Optional[str] = None
    prioridad: Optional[str] = None
    avance: Optional[int] = Field(None, ge=0, le=100)
    observacion: Optional[str] = None
    archivo_url: Optional[str] = None
    origen_documento: Optional[str] = None


def _ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalizar_estado(estado: Optional[str]) -> Optional[str]:
    if estado is None:
        return None

    estado_normalizado = estado.strip().lower()
    if estado_normalizado not in ESTADOS_VALIDOS:
        raise HTTPException(
            status_code=400,
            detail="El estado debe ser: pendiente, en_proceso, completado u observado.",
        )
    return estado_normalizado


def _normalizar_prioridad(prioridad: Optional[str]) -> Optional[str]:
    if prioridad is None:
        return None

    prioridad_normalizada = prioridad.strip().lower()
    if prioridad_normalizada not in PRIORIDADES_VALIDAS:
        raise HTTPException(
            status_code=400,
            detail="La prioridad debe ser: alta, media o baja.",
        )
    return prioridad_normalizada


def _normalizar_payload(data: dict) -> dict:
    if "estado" in data:
        data["estado"] = _normalizar_estado(data.get("estado"))
    if "prioridad" in data:
        data["prioridad"] = _normalizar_prioridad(data.get("prioridad"))
    if "macroproceso" in data and data.get("macroproceso"):
        data["macroproceso"] = data["macroproceso"].strip().lower()
    return data


def _ordenar_evidencias(evidencias: list[dict]) -> list[dict]:
    return sorted(
        evidencias,
        key=lambda item: (
            item.get("macroproceso") or "",
            ORDEN_PRIORIDAD.get(item.get("prioridad"), 99),
            ORDEN_ESTADO.get(item.get("estado"), 99),
            item.get("codigo") or "",
        ),
    )


def _resumen_evidencias(evidencias: list[dict]) -> dict:
    total = len(evidencias)
    avance_promedio = 0
    if total:
        avance_promedio = round(
            sum(int(item.get("avance") or 0) for item in evidencias) / total
        )

    return {
        "total": total,
        "pendientes": sum(1 for item in evidencias if item.get("estado") == "pendiente"),
        "en_proceso": sum(1 for item in evidencias if item.get("estado") == "en_proceso"),
        "completadas": sum(1 for item in evidencias if item.get("estado") == "completado"),
        "observadas": sum(1 for item in evidencias if item.get("estado") == "observado"),
        "avance_promedio": avance_promedio,
        "alta": sum(1 for item in evidencias if item.get("prioridad") == "alta"),
        "media": sum(1 for item in evidencias if item.get("prioridad") == "media"),
        "baja": sum(1 for item in evidencias if item.get("prioridad") == "baja"),
    }


@router.get("/evidencias")
def listar_evidencias(
    macroproceso: Optional[str] = Query(None),
    estado: Optional[str] = Query(None),
    prioridad: Optional[str] = Query(None),
    responsable: Optional[str] = Query(None),
):
    try:
        query = supabase.table("macroproceso_evidencias").select("*")

        if macroproceso:
            query = query.eq("macroproceso", macroproceso.strip().lower())
        if estado:
            query = query.eq("estado", _normalizar_estado(estado))
        if prioridad:
            query = query.eq("prioridad", _normalizar_prioridad(prioridad))
        if responsable:
            query = query.ilike("responsable", f"%{responsable.strip()}%")

        response = query.execute()
        evidencias = _ordenar_evidencias(response.data or [])

        return {
            "message": "Evidencias de macroprocesos obtenidas correctamente",
            "data": evidencias,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/planificacion/analizar")
def analizar_planificacion_estrategica():
    try:
        resultado = ejecutar_grafo_planificacion()

        return {
            "message": "Análisis de planificación estratégica generado correctamente",
            "data": resultado,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/evidencias/{evidencia_id}")
def obtener_evidencia(evidencia_id: str):
    try:
        response = (
            supabase.table("macroproceso_evidencias")
            .select("*")
            .eq("id", evidencia_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(status_code=404, detail="Evidencia no encontrada.")

        return {
            "message": "Evidencia obtenida correctamente",
            "data": response.data[0],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/evidencias")
def crear_evidencia(evidencia: EvidenciaCreate):
    try:
        data = _normalizar_payload(evidencia.model_dump())
        response = supabase.table("macroproceso_evidencias").insert(data).execute()

        return {
            "message": "Evidencia creada correctamente",
            "data": response.data,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("/evidencias/{evidencia_id}")
def actualizar_evidencia(evidencia_id: str, evidencia: EvidenciaUpdate):
    try:
        data = evidencia.model_dump(exclude_unset=True)
        data = _normalizar_payload(data)

        if not data:
            raise HTTPException(status_code=400, detail="No hay datos para actualizar.")

        data["updated_at"] = _ahora_iso()

        response = (
            supabase.table("macroproceso_evidencias")
            .update(data)
            .eq("id", evidencia_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(status_code=404, detail="Evidencia no encontrada.")

        return {
            "message": "Evidencia actualizada correctamente",
            "data": response.data,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/evidencias/{evidencia_id}")
def eliminar_evidencia(evidencia_id: str):
    try:
        response = (
            supabase.table("macroproceso_evidencias")
            .delete()
            .eq("id", evidencia_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(status_code=404, detail="Evidencia no encontrada.")

        return {
            "message": "Evidencia eliminada correctamente",
            "data": response.data,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/dashboard")
def obtener_dashboard_macroprocesos():
    try:
        response = supabase.table("macroproceso_evidencias").select("*").execute()
        evidencias = response.data or []
        resumen = _resumen_evidencias(evidencias)

        return {
            "message": "Dashboard de macroprocesos obtenido correctamente",
            "data": {
                "total_evidencias": resumen["total"],
                "total_planificacion_estrategica": sum(
                    1 for item in evidencias if item.get("macroproceso") == "planificacion_estrategica"
                ),
                "total_gestion_academica": sum(
                    1 for item in evidencias if item.get("macroproceso") == "gestion_academica"
                ),
                "pendientes": resumen["pendientes"],
                "en_proceso": resumen["en_proceso"],
                "completadas": resumen["completadas"],
                "observadas": resumen["observadas"],
                "avance_promedio": resumen["avance_promedio"],
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/dashboard/{macroproceso}")
def obtener_dashboard_macroproceso(macroproceso: str):
    try:
        macroproceso_normalizado = macroproceso.strip().lower()
        response = (
            supabase.table("macroproceso_evidencias")
            .select("*")
            .eq("macroproceso", macroproceso_normalizado)
            .execute()
        )
        resumen = _resumen_evidencias(response.data or [])

        return {
            "message": "Dashboard del macroproceso obtenido correctamente",
            "data": resumen,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
