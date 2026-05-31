from fastapi import APIRouter, HTTPException
from app.services.supabase_client import supabase

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/silabos")
def dashboard_silabos():
    try:
        response = supabase.table("silabos").select("estado").execute()
        silabos = response.data or []

        total_silabos = len(silabos)
        silabos_completos = sum(1 for item in silabos if item.get("estado") == "completo")
        silabos_observados = sum(1 for item in silabos if item.get("estado") == "observado")
        silabos_pendientes = sum(1 for item in silabos if item.get("estado") == "pendiente")
        cumplimiento_promedio = round((silabos_completos / total_silabos) * 100) if total_silabos > 0 else 0
        return {
            "message": "Dashboard general de sílabos obtenido correctamente",
            "data": {
                "total_silabos": total_silabos,
                "silabos_completos": silabos_completos,
                "silabos_observados": silabos_observados,
                "silabos_pendientes": silabos_pendientes,
                "cumplimiento_promedio": cumplimiento_promedio
            }
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
