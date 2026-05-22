from fastapi import APIRouter, HTTPException
from app.services.supabase_client import supabase

router = APIRouter(prefix="/api/silabos", tags=["Sílabos"])


@router.get("/")
def listar_silabos():
    try:
        response = supabase.table("silabos").select("*").execute()
        return {
            "message": "Listado de sílabos obtenido correctamente",
            "data": response.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/observados")
def listar_silabos_observados():
    try:
        response = (
            supabase.table("silabos")
            .select("*")
            .in_("estado", ["observado", "incompleto", "pendiente"])
            .execute()
        )

        return {
            "message": "Sílabos con alertas obtenidos correctamente",
            "data": response.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))