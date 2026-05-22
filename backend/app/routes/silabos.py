from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services.supabase_client import supabase

router = APIRouter(prefix="/api/silabos", tags=["Sílabos"])


class SilaboCreate(BaseModel):
    semestre_academico: str
    facultad: Optional[str] = None
    programa_estudios: Optional[str] = None
    asignatura: str
    codigo_asignatura: str
    ciclo: int
    modalidad: Optional[str] = None
    creditos: Optional[int] = None
    total_horas_semestrales: Optional[int] = None
    total_horas_semanales: Optional[int] = None
    fecha_inicio: Optional[str] = None
    fecha_culminacion: Optional[str] = None
    duracion_semanas: Optional[int] = None
    docente_responsable: Optional[str] = None
    correo_docente: Optional[str] = None
    archivo_url: Optional[str] = None
    estado: Optional[str] = "pendiente"
    porcentaje_cumplimiento: Optional[float] = 0
    observacion_general: Optional[str] = None


class EstadoUpdate(BaseModel):
    estado: str
    observacion_general: Optional[str] = None


@router.get("/")
def listar_silabos():
    try:
        response = supabase.table("silabos").select("*").order("ciclo").execute()
        return {
            "message": "Listado de sílabos obtenido correctamente",
            "data": response.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{silabo_id}")
def obtener_silabo(silabo_id: str):
    try:
        response = (
            supabase.table("silabos")
            .select("*")
            .eq("id", silabo_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(status_code=404, detail="Sílabo no encontrado")

        return {
            "message": "Sílabo obtenido correctamente",
            "data": response.data[0]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/")
def crear_silabo(silabo: SilaboCreate):
    try:
        estados_validos = ["pendiente", "completo", "observado", "incompleto"]

        if silabo.estado not in estados_validos:
            raise HTTPException(
                status_code=400,
                detail="Estado inválido. Use: pendiente, completo, observado o incompleto"
            )

        if silabo.ciclo < 1 or silabo.ciclo > 10:
            raise HTTPException(
                status_code=400,
                detail="El ciclo debe estar entre 1 y 10"
            )

        response = (
            supabase.table("silabos")
            .insert(silabo.model_dump())
            .execute()
        )

        return {
            "message": "Sílabo registrado correctamente",
            "data": response.data
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{silabo_id}/estado")
def actualizar_estado_silabo(silabo_id: str, datos: EstadoUpdate):
    try:
        estados_validos = ["pendiente", "completo", "observado", "incompleto"]

        if datos.estado not in estados_validos:
            raise HTTPException(
                status_code=400,
                detail="Estado inválido. Use: pendiente, completo, observado o incompleto"
            )

        silabo_actual = (
            supabase.table("silabos")
            .select("*")
            .eq("id", silabo_id)
            .execute()
        )

        if not silabo_actual.data:
            raise HTTPException(status_code=404, detail="Sílabo no encontrado")

        estado_anterior = silabo_actual.data[0]["estado"]

        response = (
            supabase.table("silabos")
            .update({
                "estado": datos.estado,
                "observacion_general": datos.observacion_general
            })
            .eq("id", silabo_id)
            .execute()
        )

        supabase.table("historial_silabo").insert({
            "silabo_id": silabo_id,
            "estado_anterior": estado_anterior,
            "estado_nuevo": datos.estado,
            "observacion": datos.observacion_general,
            "usuario": "backend"
        }).execute()

        return {
            "message": "Estado del sílabo actualizado correctamente",
            "data": response.data
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{silabo_id}")
def eliminar_silabo(silabo_id: str):
    try:
        silabo_actual = (
            supabase.table("silabos")
            .select("*")
            .eq("id", silabo_id)
            .execute()
        )

        if not silabo_actual.data:
            raise HTTPException(status_code=404, detail="Sílabo no encontrado")

        response = (
            supabase.table("silabos")
            .delete()
            .eq("id", silabo_id)
            .execute()
        )

        return {
            "message": "Sílabo eliminado correctamente",
            "data": response.data
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/estado/alertas")
def listar_silabos_con_alertas():
    try:
        response = (
            supabase.table("silabos")
            .select("*")
            .in_("estado", ["observado", "incompleto", "pendiente"])
            .order("ciclo")
            .execute()
        )

        return {
            "message": "Sílabos con alertas obtenidos correctamente",
            "data": response.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/{silabo_id}/historial")
def obtener_historial_silabo(silabo_id: str):
    try:
        # Verificar si el sílabo existe
        silabo_actual = (
            supabase.table("silabos")
            .select("*")
            .eq("id", silabo_id)
            .execute()
        )

        if not silabo_actual.data:
            raise HTTPException(status_code=404, detail="Sílabo no encontrado")

        # Consultar historial del sílabo
        response = (
            supabase.table("historial_silabo")
            .select("*")
            .eq("silabo_id", silabo_id)
            .order("created_at", desc=True)
            .execute()
        )

        return {
            "message": "Historial del sílabo obtenido correctamente",
            "silabo": {
                "id": silabo_actual.data[0]["id"],
                "asignatura": silabo_actual.data[0]["asignatura"],
                "codigo_asignatura": silabo_actual.data[0]["codigo_asignatura"],
                "estado_actual": silabo_actual.data[0]["estado"]
            },
            "historial": response.data
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))