from fastapi import APIRouter, HTTPException
from app.services.supabase_client import supabase

router = APIRouter(
    prefix="/api/agentes",
    tags=["Agentes"]
)


@router.post("/analizar-silabo/{silabo_id}")
def analizar_silabo(silabo_id: str):
    try:
        # 1. Verificar si existe el sílabo
        silabo_response = (
            supabase.table("silabos")
            .select("*")
            .eq("id", silabo_id)
            .execute()
        )

        if not silabo_response.data:
            raise HTTPException(status_code=404, detail="Sílabo no encontrado")

        silabo = silabo_response.data[0]

        # 2. Obtener validaciones ya registradas del sílabo
        validacion_response = (
            supabase.table("validacion_silabo")
            .select("*")
            .eq("silabo_id", silabo_id)
            .execute()
        )

        validaciones = validacion_response.data or []

        secciones_faltantes = [
            item["seccion"]
            for item in validaciones
            if item.get("cumple") is False
        ]

        # 3. Generar análisis básico inicial
        resumen = (
            f"El sílabo corresponde a la asignatura {silabo.get('asignatura')}, "
            f"código {silabo.get('codigo_asignatura')}, del ciclo {silabo.get('ciclo')} "
            f"del programa {silabo.get('programa_estudios')}."
        )

        sugerencias = []

        if not silabo.get("archivo_url"):
            sugerencias.append("Se recomienda cargar el documento oficial del sílabo en Google Drive.")

        if secciones_faltantes:
            sugerencias.append(
                "Se recomienda completar las secciones faltantes detectadas en la validación del documento."
            )

        if silabo.get("porcentaje_cumplimiento", 0) < 90:
            sugerencias.append(
                "El porcentaje de cumplimiento es menor al esperado. Se recomienda revisar la estructura institucional del sílabo."
            )

        if not sugerencias:
            sugerencias.append(
                "El sílabo presenta un cumplimiento favorable. Se recomienda mantener actualizada la información y bibliografía."
            )

        porcentaje = silabo.get("porcentaje_cumplimiento") or 0

        if porcentaje >= 90:
            nivel_riesgo = "bajo"
        elif porcentaje >= 70:
            nivel_riesgo = "medio"
        else:
            nivel_riesgo = "alto"

        # 4. Eliminar análisis anterior del mismo sílabo para evitar duplicados
        (
            supabase.table("analisis_silabo")
            .delete()
            .eq("silabo_id", silabo_id)
            .execute()
        )

        # 5. Guardar análisis en Supabase
        analisis_data = {
            "silabo_id": silabo_id,
            "resumen": resumen,
            "competencias_detectadas": [],
            "contenidos_detectados": [],
            "resultados_aprendizaje": [],
            "secciones_faltantes": secciones_faltantes,
            "sugerencias": sugerencias,
            "nivel_riesgo": nivel_riesgo,
            "estado_analisis": "analizado",
            "modelo_usado": "analisis_basico_backend",
            "observacion_general": "Análisis inicial generado desde el backend. Pendiente de integración con LangGraph."
        }

        insert_response = (
            supabase.table("analisis_silabo")
            .insert(analisis_data)
            .execute()
        )

        return {
            "message": "Análisis del sílabo generado correctamente",
            "silabo": {
                "id": silabo.get("id"),
                "asignatura": silabo.get("asignatura"),
                "codigo_asignatura": silabo.get("codigo_asignatura"),
                "ciclo": silabo.get("ciclo"),
                "estado": silabo.get("estado"),
                "porcentaje_cumplimiento": silabo.get("porcentaje_cumplimiento")
            },
            "analisis": insert_response.data
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
            "data": response.data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/brechas-curriculares")
def listar_brechas_curriculares():
    try:
        response = (
            supabase.table("brechas_curriculares")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )

        return {
            "message": "Brechas curriculares obtenidas correctamente",
            "data": response.data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
            "data": response.data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))