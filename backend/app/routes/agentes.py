from fastapi import APIRouter, HTTPException

from app.agents.syllabus_graph import ejecutar_grafo_analisis_silabo
from app.agents.trazabilidad_graph import ejecutar_grafo_trazabilidad
from app.services.supabase_client import supabase

router = APIRouter(
    prefix="/api/agentes",
    tags=["Agentes"],
)


@router.post("/analizar-silabo/{silabo_id}")
def analizar_silabo(silabo_id: str):
    try:
        resultado = ejecutar_grafo_analisis_silabo(silabo_id)
        silabo = resultado["silabo"]
        texto = resultado.get("texto", "")

        return {
            "message": "Análisis curricular del sílabo generado correctamente con LangGraph",
            "silabo": {
                "id": silabo.get("id"),
                "asignatura": silabo.get("asignatura"),
                "codigo_asignatura": silabo.get("codigo_asignatura"),
                "ciclo": silabo.get("ciclo"),
                "estado": silabo.get("estado"),
                "porcentaje_cumplimiento": silabo.get("porcentaje_cumplimiento"),
            },
            "analisis": resultado["resultado_guardado"],
            "texto_extraido_preview": texto[:500],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/analizar-trazabilidad-curricular")
def analizar_trazabilidad_curricular():
    try:
        resultado = ejecutar_grafo_trazabilidad()
        relaciones = resultado.get("relaciones", [])
        brechas = resultado.get("brechas", [])

        return {
            "message": "Trazabilidad curricular generada correctamente con LangGraph",
            "total_relaciones": len(relaciones),
            "total_brechas": len(brechas),
            "relaciones": relaciones,
            "brechas": brechas,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/analisis-silabo/{silabo_id}")
def obtener_analisis_silabo(silabo_id: str):
    try:
        response = (
            supabase.table("analisis_silabo")
            .select("*")
            .eq("silabo_id", silabo_id)
            .execute()
        )

        return {
            "message": "Análisis del sílabo obtenido correctamente",
            "data": response.data,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/brechas-curriculares")
def listar_brechas_curriculares():
    try:
        response = (
            supabase.table("brechas_curriculares")
            .select("*")
            .execute()
        )
        prioridad_orden = {"alta": 0, "media": 1, "baja": 2}
        brechas = sorted(
            response.data or [],
            key=lambda item: (
                prioridad_orden.get(str(item.get("prioridad", "")).lower(), 3),
                item.get("ciclo") or 0,
                item.get("asignatura") or "",
            ),
        )

        return {
            "message": "Brechas curriculares obtenidas correctamente",
            "data": brechas,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/trazabilidad-curricular")
def listar_trazabilidad_curricular():
    try:
        response = (
            supabase.table("trazabilidad_curricular")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )

        return {
            "message": "Trazabilidad curricular obtenida correctamente",
            "data": response.data,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
