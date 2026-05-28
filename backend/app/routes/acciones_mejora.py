from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.supabase_client import supabase


router = APIRouter(
    prefix="/api/acciones-mejora",
    tags=["Acciones de Mejora"],
)

PRIORIDADES_VALIDAS = {"alta", "media", "baja"}
ESTADOS_VALIDOS = {"pendiente", "en_proceso", "atendida", "descartada"}


class AccionMejoraCreate(BaseModel):
    origen_tipo: Optional[str] = "manual"
    origen_id: Optional[str] = None
    silabo_id: Optional[str] = None
    ciclo: Optional[int] = None
    asignatura: Optional[str] = None
    titulo: str
    descripcion: str
    recomendacion: Optional[str] = None
    prioridad: Optional[str] = "media"
    estado: Optional[str] = "pendiente"
    responsable: Optional[str] = None
    fecha_limite: Optional[str] = None
    evidencia_url: Optional[str] = None
    observacion: Optional[str] = None


class AccionMejoraUpdate(BaseModel):
    titulo: Optional[str] = None
    descripcion: Optional[str] = None
    recomendacion: Optional[str] = None
    prioridad: Optional[str] = None
    estado: Optional[str] = None
    responsable: Optional[str] = None
    fecha_limite: Optional[str] = None
    evidencia_url: Optional[str] = None
    observacion: Optional[str] = None


def _validar_prioridad(prioridad: Optional[str]) -> Optional[str]:
    if prioridad is None:
        return prioridad

    prioridad_normalizada = prioridad.lower().strip()
    if prioridad_normalizada not in PRIORIDADES_VALIDAS:
        raise HTTPException(
            status_code=400,
            detail="La prioridad debe ser: alta, media o baja.",
        )
    return prioridad_normalizada


def _validar_estado(estado: Optional[str]) -> Optional[str]:
    if estado is None:
        return estado

    estado_normalizado = estado.lower().strip()
    if estado_normalizado not in ESTADOS_VALIDOS:
        raise HTTPException(
            status_code=400,
            detail="El estado debe ser: pendiente, en_proceso, atendida o descartada.",
        )
    return estado_normalizado


def _validar_accion_data(data: dict) -> dict:
    if "prioridad" in data:
        data["prioridad"] = _validar_prioridad(data.get("prioridad"))
    if "estado" in data:
        data["estado"] = _validar_estado(data.get("estado"))
    return data


def _ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/")
def listar_acciones_mejora():
    try:
        response = (
            supabase.table("acciones_mejora")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )

        return {
            "message": "Acciones de mejora obtenidas correctamente",
            "data": response.data,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/")
def crear_accion_mejora(accion: AccionMejoraCreate):
    try:
        data = accion.model_dump()
        data = _validar_accion_data(data)

        response = supabase.table("acciones_mejora").insert(data).execute()
        return {
            "message": "Acción de mejora creada correctamente",
            "data": response.data,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("/{accion_id}")
def actualizar_accion_mejora(accion_id: str, accion: AccionMejoraUpdate):
    try:
        data = accion.model_dump(exclude_unset=True)
        data = _validar_accion_data(data)

        if not data:
            raise HTTPException(status_code=400, detail="No hay datos para actualizar.")

        data["updated_at"] = _ahora_iso()

        response = (
            supabase.table("acciones_mejora")
            .update(data)
            .eq("id", accion_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(status_code=404, detail="Acción de mejora no encontrada.")

        return {
            "message": "Acción de mejora actualizada correctamente",
            "data": response.data,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{accion_id}")
def eliminar_accion_mejora(accion_id: str):
    try:
        response = (
            supabase.table("acciones_mejora")
            .delete()
            .eq("id", accion_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(status_code=404, detail="Acción de mejora no encontrada.")

        return {
            "message": "Acción de mejora eliminada correctamente",
            "data": response.data,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/generar-desde-brechas")
def generar_acciones_desde_brechas():
    try:
        brechas_response = supabase.table("brechas_curriculares").select("*").execute()
        brechas = brechas_response.data or []

        acciones_existentes_response = (
            supabase.table("acciones_mejora")
            .select("origen_id")
            .eq("origen_tipo", "brecha_curricular")
            .execute()
        )
        origenes_existentes = {
            accion.get("origen_id")
            for accion in (acciones_existentes_response.data or [])
            if accion.get("origen_id")
        }

        acciones_nuevas = []
        for brecha in brechas:
            brecha_id = brecha.get("id")
            if not brecha_id or brecha_id in origenes_existentes:
                continue

            prioridad = brecha.get("prioridad") or "media"
            prioridad = prioridad if prioridad in PRIORIDADES_VALIDAS else "media"
            tipo_brecha = brecha.get("tipo_brecha") or "brecha curricular"

            acciones_nuevas.append(
                {
                    "origen_tipo": "brecha_curricular",
                    "origen_id": brecha_id,
                    "silabo_id": brecha.get("silabo_id"),
                    "ciclo": brecha.get("ciclo"),
                    "asignatura": brecha.get("asignatura"),
                    "titulo": f"Atender brecha: {tipo_brecha}",
                    "descripcion": brecha.get("descripcion"),
                    "recomendacion": brecha.get("recomendacion"),
                    "prioridad": prioridad,
                    "estado": "pendiente",
                    "responsable": "Coordinación académica",
                    "observacion": (
                        "Acción generada automáticamente a partir de una brecha "
                        "curricular detectada por el agente."
                    ),
                }
            )

        resultado = []
        if acciones_nuevas:
            insert_response = supabase.table("acciones_mejora").insert(acciones_nuevas).execute()
            resultado = insert_response.data or acciones_nuevas

        return {
            "message": "Acciones de mejora generadas correctamente desde brechas curriculares",
            "total_brechas": len(brechas),
            "total_generadas": len(resultado),
            "data": resultado,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/dashboard")
def dashboard_acciones_mejora():
    try:
        response = supabase.table("acciones_mejora").select("*").execute()
        acciones = response.data or []

        data = {
            "total_acciones": len(acciones),
            "pendientes": sum(1 for item in acciones if item.get("estado") == "pendiente"),
            "en_proceso": sum(1 for item in acciones if item.get("estado") == "en_proceso"),
            "atendidas": sum(1 for item in acciones if item.get("estado") == "atendida"),
            "prioridad_alta": sum(1 for item in acciones if item.get("prioridad") == "alta"),
            "prioridad_media": sum(1 for item in acciones if item.get("prioridad") == "media"),
            "prioridad_baja": sum(1 for item in acciones if item.get("prioridad") == "baja"),
        }

        return {
            "message": "Dashboard de acciones de mejora obtenido correctamente",
            "data": data,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
