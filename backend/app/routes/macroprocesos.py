from datetime import datetime, timezone
import os
import uuid
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app.agents.gestion_academica_graph import ejecutar_grafo_gestion_academica
from app.agents.mejora_continua_coordinator import ejecutar_grafo_coordinador_mejora_continua
from app.agents.planificacion_graph import ejecutar_grafo_planificacion
from app.agents.validacion_evidencia_graph import ejecutar_grafo_validacion_evidencia
from app.services.supabase_client import supabase


router = APIRouter(
    prefix="/api/macroprocesos",
    tags=["Macroprocesos"],
)

ESTADOS_VALIDOS = {"pendiente", "en_proceso", "completado", "observado"}
PRIORIDADES_VALIDAS = {"alta", "media", "baja"}
ORDEN_PRIORIDAD = {"alta": 0, "media": 1, "baja": 2}
ORDEN_ESTADO = {"pendiente": 0, "en_proceso": 1, "observado": 2, "completado": 3}
MACROPROCESOS_ACCIONES_VALIDOS = {"planificacion_estrategica", "gestion_academica"}
MACROPROCESOS_ANALISIS_VALIDOS = {"planificacion_estrategica", "gestion_academica", "mejora_continua"}
TIPOS_ANALISIS_VALIDOS = {
    "analisis_planificacion",
    "analisis_gestion_academica",
    "analisis_integral_mejora_continua",
}
ORDEN_RIESGO = {"bajo": 1, "medio": 2, "alto": 3}
CAMPOS_HISTORIAL = {
    "estado",
    "prioridad",
    "avance",
    "observacion",
    "archivo_url",
    "fecha_cumplimiento",
    "responsable",
    "descripcion",
    "tipo_evidencia",
}
EXTENSIONES_EVIDENCIA = {".pdf", ".docx", ".xlsx", ".png", ".jpg", ".jpeg"}
BUCKET_EVIDENCIAS = "silabos"


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


def _obtener_evidencia_o_404(evidencia_id: str) -> dict:
    response = (
        supabase.table("macroproceso_evidencias")
        .select("*")
        .eq("id", evidencia_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Evidencia no encontrada.")
    return response.data[0]


def _valor_historial(valor) -> Optional[str]:
    if valor is None:
        return None
    return str(valor)


def _registrar_historial_evidencia(
    evidencia: dict,
    campo: str,
    valor_anterior,
    valor_nuevo,
    observacion: Optional[str] = None,
    usuario: str = "backend",
) -> None:
    if _valor_historial(valor_anterior) == _valor_historial(valor_nuevo):
        return

    supabase.table("historial_macroproceso_evidencias").insert(
        {
            "evidencia_id": evidencia.get("id"),
            "macroproceso": evidencia.get("macroproceso"),
            "codigo": evidencia.get("codigo"),
            "titulo": evidencia.get("titulo"),
            "campo_modificado": campo,
            "valor_anterior": _valor_historial(valor_anterior),
            "valor_nuevo": _valor_historial(valor_nuevo),
            "observacion": observacion,
            "usuario": usuario,
        }
    ).execute()


def _registrar_historial_cambios(evidencia_actual: dict, data: dict, observacion: Optional[str] = None) -> None:
    for campo in CAMPOS_HISTORIAL:
        if campo not in data:
            continue
        _registrar_historial_evidencia(
            evidencia_actual,
            campo,
            evidencia_actual.get(campo),
            data.get(campo),
            observacion,
        )


def _texto_evidencia(evidencia: dict) -> str:
    partes = [
        evidencia.get("codigo"),
        evidencia.get("titulo"),
        evidencia.get("descripcion"),
        evidencia.get("tipo_evidencia"),
        evidencia.get("responsable"),
        evidencia.get("observacion"),
    ]
    return " ".join(str(parte or "") for parte in partes).lower()


def _es_evidencia_critica(evidencia: dict) -> bool:
    prioridad = evidencia.get("prioridad")
    estado = evidencia.get("estado")
    avance = int(evidencia.get("avance") or 0)
    texto = _texto_evidencia(evidencia)
    palabras_clave = ["acuerdo", "docente", "estudiante", "silabo", "sílabo", "portafolio", "plan anual"]

    return (
        (prioridad == "alta" and estado == "pendiente")
        or estado == "observado"
        or (avance < 30 and prioridad == "alta")
        or (estado == "completado" and not evidencia.get("archivo_url"))
        or (estado == "en_proceso" and avance < 50)
        or (estado == "pendiente" and any(palabra in texto for palabra in palabras_clave))
    )


def _descripcion_accion_evidencia(evidencia: dict) -> str:
    estado = evidencia.get("estado") or "sin estado"
    avance = evidencia.get("avance") or 0
    descripcion = (
        f"La evidencia {evidencia.get('codigo') or ''} presenta una condicion critica: "
        f"estado {estado}, prioridad {evidencia.get('prioridad') or 'media'} y avance {avance}%. "
        "Se requiere revisar, documentar y cerrar la evidencia dentro del ciclo de mejora continua."
    )
    if evidencia.get("estado") == "completado" and not evidencia.get("archivo_url"):
        descripcion += " La evidencia figura como completada, pero no tiene archivo de sustento."
    return descripcion


def _payload_accion_desde_evidencia(evidencia: dict) -> dict:
    prioridad = evidencia.get("prioridad") or "media"
    if evidencia.get("estado") == "observado":
        prioridad = "alta"
    if prioridad not in PRIORIDADES_VALIDAS:
        prioridad = "media"

    return {
        "origen_tipo": "macroproceso_evidencia",
        "origen_id": evidencia.get("id"),
        "titulo": f"Atender evidencia crítica: {evidencia.get('codigo') or '-'} - {evidencia.get('titulo') or 'Evidencia'}",
        "descripcion": _descripcion_accion_evidencia(evidencia),
        "recomendacion": "Asignar responsable, fecha de cierre y sustento documental verificable.",
        "prioridad": prioridad,
        "estado": "pendiente",
        "responsable": evidencia.get("responsable"),
        "evidencia_url": evidencia.get("archivo_url"),
        "observacion": f"Acción generada desde evidencia del macroproceso {evidencia.get('macroproceso')}.",
    }


def _accion_existente_para_evidencia(evidencia_id: str) -> list:
    response = (
        supabase.table("acciones_mejora")
        .select("*")
        .eq("origen_tipo", "macroproceso_evidencia")
        .eq("origen_id", evidencia_id)
        .execute()
    )
    return response.data or []


def _generar_accion_desde_evidencia(evidencia: dict) -> tuple[bool, dict | None]:
    existentes = _accion_existente_para_evidencia(evidencia.get("id"))
    if existentes:
        return False, existentes[0]

    payload = _payload_accion_desde_evidencia(evidencia)
    response = supabase.table("acciones_mejora").insert(payload).execute()
    accion = response.data[0] if response.data else payload
    return True, accion


def _guardar_historial_analisis_ia(
    macroproceso: str,
    tipo_analisis: str,
    resultado: dict,
    nivel_riesgo: Optional[str],
    resumen: Optional[str],
) -> None:
    try:
        supabase.table("analisis_ia_macroprocesos").insert(
            {
                "macroproceso": macroproceso,
                "tipo_analisis": tipo_analisis,
                "nivel_riesgo": nivel_riesgo,
                "resumen": resumen,
                "resultado_json": resultado,
                "modelo_usado": resultado.get("modelo_usado"),
                "usuario": "backend",
            }
        ).execute()
        print("[Historial IA] Análisis guardado correctamente para:", macroproceso)
    except Exception as e:
        print("[Historial IA] No se pudo guardar el análisis:", type(e).__name__, str(e))


def _resumen_historial_ia(item: dict) -> dict:
    return {
        "id": item.get("id"),
        "macroproceso": item.get("macroproceso"),
        "tipo_analisis": item.get("tipo_analisis"),
        "nivel_riesgo": item.get("nivel_riesgo"),
        "resumen": item.get("resumen"),
        "modelo_usado": item.get("modelo_usado"),
        "created_at": item.get("created_at"),
    }


def _comparar_riesgos(anterior: Optional[str], actual: Optional[str]) -> str:
    if anterior not in ORDEN_RIESGO or actual not in ORDEN_RIESGO:
        return "sin_datos"
    if ORDEN_RIESGO[actual] < ORDEN_RIESGO[anterior]:
        return "mejoro"
    if ORDEN_RIESGO[actual] > ORDEN_RIESGO[anterior]:
        return "empeoro"
    return "se_mantuvo"


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
        _guardar_historial_analisis_ia(
            macroproceso="planificacion_estrategica",
            tipo_analisis="analisis_planificacion",
            resultado=resultado,
            nivel_riesgo=resultado.get("nivel_riesgo"),
            resumen=resultado.get("resumen"),
        )

        return {
            "message": "An?lisis de planificaci?n estrat?gica generado correctamente",
            "data": resultado,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/gestion-academica/analizar")
def analizar_gestion_academica():
    try:
        resultado = ejecutar_grafo_gestion_academica()
        _guardar_historial_analisis_ia(
            macroproceso="gestion_academica",
            tipo_analisis="analisis_gestion_academica",
            resultado=resultado,
            nivel_riesgo=resultado.get("nivel_riesgo"),
            resumen=resultado.get("resumen"),
        )

        return {
            "message": "An?lisis de gesti?n acad?mica generado correctamente",
            "data": resultado,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/mejora-continua/analizar")
def analizar_mejora_continua():
    try:
        resultado = ejecutar_grafo_coordinador_mejora_continua()
        _guardar_historial_analisis_ia(
            macroproceso="mejora_continua",
            tipo_analisis="analisis_integral_mejora_continua",
            resultado=resultado,
            nivel_riesgo=resultado.get("nivel_riesgo_general"),
            resumen=resultado.get("resumen_general"),
        )

        return {
            "message": "An?lisis integral de mejora continua generado correctamente",
            "data": resultado,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/analisis-ia/historial")
def listar_historial_analisis_ia(
    macroproceso: Optional[str] = Query(None),
    tipo_analisis: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    try:
        query = supabase.table("analisis_ia_macroprocesos").select("*")

        if macroproceso:
            macroproceso_normalizado = macroproceso.strip().lower()
            if macroproceso_normalizado not in MACROPROCESOS_ANALISIS_VALIDOS:
                raise HTTPException(status_code=400, detail="Macroproceso de analisis IA no valido.")
            query = query.eq("macroproceso", macroproceso_normalizado)

        if tipo_analisis:
            tipo_normalizado = tipo_analisis.strip().lower()
            if tipo_normalizado not in TIPOS_ANALISIS_VALIDOS:
                raise HTTPException(status_code=400, detail="Tipo de analisis IA no valido.")
            query = query.eq("tipo_analisis", tipo_normalizado)

        response = query.order("created_at", desc=True).limit(limit).execute()
        return {
            "historial": [_resumen_historial_ia(item) for item in (response.data or [])],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/analisis-ia/historial/{analisis_id}")
def obtener_detalle_historial_analisis_ia(analisis_id: str):
    try:
        response = (
            supabase.table("analisis_ia_macroprocesos")
            .select("*")
            .eq("id", analisis_id)
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=404, detail="Analisis IA no encontrado.")

        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/analisis-ia/comparar")
def comparar_historial_analisis_ia(macroproceso: str = Query(...)):
    try:
        macroproceso_normalizado = macroproceso.strip().lower()
        if macroproceso_normalizado not in MACROPROCESOS_ANALISIS_VALIDOS:
            raise HTTPException(status_code=400, detail="Macroproceso de analisis IA no valido.")

        response = (
            supabase.table("analisis_ia_macroprocesos")
            .select("*")
            .eq("macroproceso", macroproceso_normalizado)
            .order("created_at", desc=True)
            .limit(2)
            .execute()
        )
        registros = response.data or []
        actual = registros[0] if len(registros) >= 1 else None
        anterior = registros[1] if len(registros) >= 2 else None

        if not actual or not anterior:
            cambio = "sin_datos"
            resumen = "No hay dos analisis IA disponibles para comparar."
        else:
            cambio = _comparar_riesgos(anterior.get("nivel_riesgo"), actual.get("nivel_riesgo"))
            if cambio == "mejoro":
                resumen = f"El riesgo mejoro de {anterior.get('nivel_riesgo')} a {actual.get('nivel_riesgo')}."
            elif cambio == "empeoro":
                resumen = f"El riesgo empeoro de {anterior.get('nivel_riesgo')} a {actual.get('nivel_riesgo')}."
            elif cambio == "se_mantuvo":
                resumen = f"El riesgo se mantuvo en {actual.get('nivel_riesgo')}."
            else:
                resumen = "No se pudo determinar el cambio de riesgo."

        return {
            "macroproceso": macroproceso_normalizado,
            "analisis_actual": _resumen_historial_ia(actual) if actual else None,
            "analisis_anterior": _resumen_historial_ia(anterior) if anterior else None,
            "comparacion": {
                "riesgo_anterior": anterior.get("nivel_riesgo") if anterior else None,
                "riesgo_actual": actual.get("nivel_riesgo") if actual else None,
                "cambio_riesgo": cambio,
                "resumen": resumen,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/evidencias/{evidencia_id}")
def obtener_evidencia(evidencia_id: str):
    try:
        evidencia = _obtener_evidencia_o_404(evidencia_id)

        return {
            "message": "Evidencia obtenida correctamente",
            "data": evidencia,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/evidencias/{evidencia_id}/validar-ia")
def validar_evidencia_con_ia(evidencia_id: str):
    try:
        evidencia = _obtener_evidencia_o_404(evidencia_id)
        if not evidencia.get("archivo_url"):
            raise HTTPException(
                status_code=400,
                detail="Primero suba un archivo de sustento para validar esta evidencia.",
            )

        try:
            resultado = ejecutar_grafo_validacion_evidencia(evidencia_id)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        return {
            "message": "Validacion IA de evidencia generada correctamente",
            "data": resultado,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/evidencias/{evidencia_id}/validacion-ia")
def obtener_ultima_validacion_evidencia_ia(evidencia_id: str):
    try:
        _obtener_evidencia_o_404(evidencia_id)
        response = (
            supabase.table("validacion_ia_macroproceso_evidencias")
            .select("*")
            .eq("evidencia_id", evidencia_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        return {
            "message": "Ultima validacion IA obtenida correctamente"
            if response.data
            else "No hay validaciones IA registradas para esta evidencia.",
            "data": response.data[0] if response.data else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/evidencias/{evidencia_id}/validacion-ia/historial")
def obtener_historial_validacion_evidencia_ia(evidencia_id: str):
    try:
        _obtener_evidencia_o_404(evidencia_id)
        response = (
            supabase.table("validacion_ia_macroproceso_evidencias")
            .select("*")
            .eq("evidencia_id", evidencia_id)
            .order("created_at", desc=True)
            .execute()
        )

        return {
            "evidencia_id": evidencia_id,
            "historial": response.data or [],
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
        evidencia_actual = _obtener_evidencia_o_404(evidencia_id)
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

        _registrar_historial_cambios(
            evidencia_actual,
            data,
            observacion="Actualización de evidencia desde el sistema",
        )

        return {
            "message": "Evidencia actualizada correctamente",
            "data": response.data,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/evidencias/{evidencia_id}/historial")
def obtener_historial_evidencia(evidencia_id: str):
    try:
        _obtener_evidencia_o_404(evidencia_id)
        response = (
            supabase.table("historial_macroproceso_evidencias")
            .select("*")
            .eq("evidencia_id", evidencia_id)
            .order("created_at", desc=True)
            .execute()
        )

        return {
            "evidencia_id": evidencia_id,
            "historial": response.data or [],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/evidencias/{evidencia_id}/archivo")
async def subir_archivo_evidencia(evidencia_id: str, archivo: UploadFile = File(...)):
    try:
        evidencia = _obtener_evidencia_o_404(evidencia_id)
        nombre_original = archivo.filename or ""
        extension = os.path.splitext(nombre_original)[1].lower()

        if extension not in EXTENSIONES_EVIDENCIA:
            raise HTTPException(
                status_code=400,
                detail="Formato no permitido. Solo se aceptan PDF, DOCX, XLSX, PNG, JPG o JPEG.",
            )

        contenido = await archivo.read()
        if not contenido:
            raise HTTPException(status_code=400, detail="El archivo esta vacio.")

        nombre_seguro = os.path.basename(nombre_original).replace(" ", "_")
        codigo = (evidencia.get("codigo") or evidencia_id).replace("/", "-").replace("\\", "-")
        ruta_storage = (
            f"macroprocesos/{evidencia.get('macroproceso')}/{codigo}/"
            f"{uuid.uuid4()}_{nombre_seguro}"
        )

        supabase.storage.from_(BUCKET_EVIDENCIAS).upload(
            path=ruta_storage,
            file=contenido,
            file_options={
                "content-type": archivo.content_type or "application/octet-stream",
                "upsert": "true",
            },
        )

        archivo_url = supabase.storage.from_(BUCKET_EVIDENCIAS).get_public_url(ruta_storage)
        response = (
            supabase.table("macroproceso_evidencias")
            .update({
                "archivo_url": archivo_url,
                "updated_at": _ahora_iso(),
            })
            .eq("id", evidencia_id)
            .execute()
        )

        _registrar_historial_evidencia(
            evidencia,
            "archivo_url",
            evidencia.get("archivo_url"),
            archivo_url,
            observacion="Archivo de evidencia actualizado",
        )

        return {
            "message": "Evidencia documental subida correctamente.",
            "archivo_url": archivo_url,
            "data": response.data,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/evidencias/{evidencia_id}/generar-accion")
def generar_accion_desde_evidencia(evidencia_id: str):
    try:
        evidencia = _obtener_evidencia_o_404(evidencia_id)
        creada, accion = _generar_accion_desde_evidencia(evidencia)

        if not creada:
            return {
                "message": "Ya existe una acción de mejora para esta evidencia.",
                "accion_existente": accion,
                "data": accion,
            }

        return {
            "message": "Acción de mejora generada correctamente.",
            "data": accion,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/{macroproceso}/generar-acciones-desde-evidencias")
def generar_acciones_desde_evidencias_macroproceso(macroproceso: str):
    try:
        macroproceso_normalizado = macroproceso.strip().lower()
        if macroproceso_normalizado not in MACROPROCESOS_ACCIONES_VALIDOS:
            raise HTTPException(
                status_code=400,
                detail="Macroproceso no permitido. Use planificacion_estrategica o gestion_academica.",
            )

        response = (
            supabase.table("macroproceso_evidencias")
            .select("*")
            .eq("macroproceso", macroproceso_normalizado)
            .execute()
        )
        evidencias = response.data or []
        criticas = [evidencia for evidencia in evidencias if _es_evidencia_critica(evidencia)]
        acciones = []
        acciones_creadas = 0
        acciones_existentes = 0

        for evidencia in criticas:
            creada, accion = _generar_accion_desde_evidencia(evidencia)
            if creada:
                acciones_creadas += 1
            else:
                acciones_existentes += 1
            if accion:
                acciones.append(accion)

        return {
            "message": "Acciones de mejora generadas correctamente",
            "acciones_creadas": acciones_creadas,
            "acciones_existentes": acciones_existentes,
            "acciones": acciones,
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
