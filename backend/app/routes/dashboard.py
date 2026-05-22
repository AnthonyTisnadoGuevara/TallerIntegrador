from fastapi import APIRouter, HTTPException
from app.services.supabase_client import supabase

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/silabos")
def dashboard_silabos():
    try:
        response = supabase.table("dashboard_silabos").select("*").execute()
        return {
            "message": "Dashboard general de sílabos obtenido correctamente",
            "data": response.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/silabos-por-ciclo")
def dashboard_silabos_por_ciclo():
    try:
        response = supabase.table("dashboard_silabos_por_ciclo").select("*").execute()
        return {
            "message": "Dashboard de sílabos por ciclo obtenido correctamente",
            "data": response.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))