from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from app.services.supabase_client import supabase
from fastapi import APIRouter, HTTPException, UploadFile, File
import uuid
import os
from app.utils.document_reader import (
    extraer_texto_desde_url,
    extraer_texto_docx,
    extraer_texto_pdf,
    validar_secciones_silabo,
)
from app.utils.silabo_extractor import extraer_datos_silabo_desde_texto

router = APIRouter(prefix="/api/silabos", tags=["Sílabos"])


class SilaboCreate(BaseModel):
    semestre_academico: str
    facultad: Optional[str] = None
    programa_estudios: Optional[str] = None
    asignatura: str
    codigo_asignatura: str
    ciclo: int = Field(..., ge=1, le=10)
    modalidad: Optional[str] = None
    creditos: Optional[int] = Field(None, ge=0)
    total_horas_semestrales: Optional[int] = Field(None, ge=0)
    total_horas_semanales: Optional[int] = Field(None, ge=0)
    fecha_inicio: Optional[str] = None
    fecha_culminacion: Optional[str] = None
    duracion_semanas: Optional[int] = Field(None, gt=0)
    docente_responsable: Optional[str] = None
    correo_docente: Optional[str] = None
    archivo_url: Optional[str] = None
    estado: Optional[str] = "pendiente"
    porcentaje_cumplimiento: Optional[float] = 0
    observacion_general: Optional[str] = None


class EstadoUpdate(BaseModel):
    estado: str
    observacion_general: Optional[str] = None

class SilaboUpdate(BaseModel):
    semestre_academico: Optional[str] = None
    facultad: Optional[str] = None
    programa_estudios: Optional[str] = None
    asignatura: Optional[str] = None
    codigo_asignatura: Optional[str] = None
    ciclo: Optional[int] = Field(None, ge=1, le=10)
    modalidad: Optional[str] = None
    creditos: Optional[int] = Field(None, ge=0)
    total_horas_semestrales: Optional[int] = Field(None, ge=0)
    total_horas_semanales: Optional[int] = Field(None, ge=0)
    fecha_inicio: Optional[str] = None
    fecha_culminacion: Optional[str] = None
    duracion_semanas: Optional[int] = Field(None, gt=0)
    docente_responsable: Optional[str] = None
    correo_docente: Optional[str] = None
    archivo_url: Optional[str] = None
    observacion_general: Optional[str] = None

def normalizar_porcentaje_por_estado(silabo: dict) -> dict:
    estado = silabo.get("estado")
    porcentaje = silabo.get("porcentaje_cumplimiento")
    try:
        porcentaje_numero = float(porcentaje or 0)
    except (TypeError, ValueError):
        porcentaje_numero = 0

    if estado == "completo" and (porcentaje is None or porcentaje_numero == 0):
        silabo["porcentaje_cumplimiento"] = 100
    elif estado == "pendiente" and porcentaje is None:
        silabo["porcentaje_cumplimiento"] = 0

    return silabo


@router.get("/")
def listar_silabos():
    try:
        response = supabase.table("silabos").select("*").order("ciclo").execute()
        silabos = [normalizar_porcentaje_por_estado(item) for item in (response.data or [])]
        return {
            "message": "Listado de sílabos obtenido correctamente",
            "data": silabos
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extraer-datos-archivo")
async def extraer_datos_archivo_silabo(archivo: UploadFile = File(...)):
    try:
        nombre_original = archivo.filename or ""
        extension = os.path.splitext(nombre_original)[1].lower()

        if extension not in [".docx", ".pdf"]:
            raise HTTPException(
                status_code=400,
                detail="Formato no permitido. Solo se aceptan archivos DOCX o PDF."
            )

        contenido = await archivo.read()
        if not contenido:
            raise HTTPException(status_code=400, detail="El archivo esta vacio.")

        try:
            if extension == ".docx":
                texto = extraer_texto_docx(contenido)
            else:
                texto = extraer_texto_pdf(contenido)
        except ValueError as error:
            mensaje_error = str(error)
            if "no contiene texto" in mensaje_error.lower() or "texto extra" in mensaje_error.lower():
                raise HTTPException(
                    status_code=400,
                    detail="No se pudo extraer texto del documento. Si es PDF escaneado, conviertalo a PDF con texto seleccionable o a DOCX."
                ) from error
            raise HTTPException(status_code=400, detail=mensaje_error) from error

        if not texto.strip():
            raise HTTPException(
                status_code=400,
                detail="No se pudo extraer texto del documento. Si es PDF escaneado, conviertalo a PDF con texto seleccionable o a DOCX."
            )

        datos = extraer_datos_silabo_desde_texto(texto)

        return {
            "message": "Datos extraidos correctamente",
            "data": datos,
            "preview_texto": texto[:500]
        }

    except HTTPException:
        raise
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

        datos_silabo = silabo.model_dump()
        if datos_silabo["estado"] == "completo":
            datos_silabo["porcentaje_cumplimiento"] = 100
        elif datos_silabo["estado"] == "pendiente":
            datos_silabo["porcentaje_cumplimiento"] = 0

        response = (
            supabase.table("silabos")
            .insert(datos_silabo)
            .execute()
        )

        return {
            "message": "Sílabo registrado correctamente",
            "data": response.data[0] if response.data else None
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
        datos_actualizar = {
            "estado": datos.estado,
            "observacion_general": datos.observacion_general
        }

        if datos.estado == "completo":
            datos_actualizar["porcentaje_cumplimiento"] = 100
        elif datos.estado == "pendiente":
            datos_actualizar["porcentaje_cumplimiento"] = 0

        response = (
            supabase.table("silabos")
            .update(datos_actualizar)
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
@router.post("/{silabo_id}/archivo")
async def subir_archivo_silabo(silabo_id: str, archivo: UploadFile = File(...)):
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

        # Validar extensión del archivo
        nombre_original = archivo.filename
        extension = os.path.splitext(nombre_original)[1].lower()

        extensiones_permitidas = [".pdf", ".docx"]

        if extension not in extensiones_permitidas:
            raise HTTPException(
                status_code=400,
                detail="Formato no permitido. Solo se aceptan archivos PDF o DOCX."
            )

        # Leer contenido del archivo
        contenido = await archivo.read()

        # Crear nombre único para evitar duplicados
        nombre_archivo = f"{silabo_id}_{uuid.uuid4()}{extension}"

        # Ruta dentro del bucket
        ruta_storage = f"silabos/{nombre_archivo}"

        # Subir archivo a Supabase Storage
        supabase.storage.from_("silabos").upload(
            path=ruta_storage,
            file=contenido,
            file_options={
                "content-type": archivo.content_type or "application/octet-stream",
                "upsert": "true"
            }
        )

        # Obtener URL pública del archivo
        archivo_url = supabase.storage.from_("silabos").get_public_url(ruta_storage)

        # Actualizar campo archivo_url en tabla silabos
        response = (
            supabase.table("silabos")
            .update({
                "archivo_url": archivo_url,
                "updated_at": datetime.now(timezone.utc).isoformat()
            })
            .eq("id", silabo_id)
            .execute()
        )

        return {
            "message": "Archivo del silabo actualizado correctamente.",
            "archivo_url": archivo_url,
            "data": response.data
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.post("/{silabo_id}/validar-documento")
def validar_documento_silabo(silabo_id: str):
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

        silabo = silabo_actual.data[0]
        archivo_url = silabo.get("archivo_url")

        if not archivo_url:
            raise HTTPException(
                status_code=400,
                detail="El sílabo no tiene archivo cargado para validar."
            )

        archivo_url_limpia = archivo_url.lower().split("?")[0]
        if archivo_url_limpia.endswith(".doc"):
            raise HTTPException(
                status_code=400,
                detail="El formato .doc antiguo no está soportado. Convierta el archivo a .docx o PDF con texto seleccionable."
            )

        # Extraer texto del documento DOCX o PDF mediante el lector central
        try:
            texto = extraer_texto_desde_url(archivo_url)
        except ValueError as error:
            mensaje_error = str(error)
            if "PDF no contiene texto extra" in mensaje_error:
                raise HTTPException(
                    status_code=400,
                    detail="No se pudo extraer texto del documento. Si es PDF escaneado, conviértalo a PDF con texto seleccionable o a DOCX."
                ) from error
            if "formato .doc antiguo" in mensaje_error.lower():
                raise HTTPException(
                    status_code=400,
                    detail="El formato .doc antiguo no está soportado. Convierta el archivo a .docx o PDF con texto seleccionable."
                ) from error
            raise HTTPException(
                status_code=400,
                detail="Solo se permite validar documentos .docx o PDF con texto extraíble."
            ) from error
        except RuntimeError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        if not texto.strip():
            raise HTTPException(
                status_code=400,
                detail="No se pudo extraer texto del documento. Si es PDF escaneado, conviértalo a PDF con texto seleccionable o a DOCX."
            )

        # Validar secciones obligatorias
        resultados = validar_secciones_silabo(texto)

        # Eliminar validaciones anteriores del mismo sílabo
        supabase.table("validacion_silabo").delete().eq("silabo_id", silabo_id).execute()

        # Insertar nuevas validaciones
        registros_validacion = [
            {
                "silabo_id": silabo_id,
                "seccion": item["seccion"],
                "cumple": item["cumple"],
                "observacion": item["observacion"]
            }
            for item in resultados
        ]

        supabase.table("validacion_silabo").insert(registros_validacion).execute()

        total = len(resultados)
        cumplidas = sum(1 for item in resultados if item["cumple"])
        porcentaje = round((cumplidas / total) * 100, 2)

        if porcentaje >= 90:
            nuevo_estado = "completo"
        elif porcentaje >= 70:
            nuevo_estado = "observado"
        else:
            nuevo_estado = "incompleto"

        estado_anterior = silabo.get("estado")

        # Actualizar sílabo
        response = (
            supabase.table("silabos")
            .update({
                "porcentaje_cumplimiento": porcentaje,
                "estado": nuevo_estado,
                "observacion_general": f"Validación automática: {cumplidas} de {total} secciones identificadas."
            })
            .eq("id", silabo_id)
            .execute()
        )

        # Registrar historial
        supabase.table("historial_silabo").insert({
            "silabo_id": silabo_id,
            "estado_anterior": estado_anterior,
            "estado_nuevo": nuevo_estado,
            "observacion": f"Validación automática del documento: {cumplidas} de {total} secciones identificadas.",
            "usuario": "backend"
        }).execute()

        return {
            "message": "Documento del sílabo validado correctamente",
            "silabo_id": silabo_id,
            "secciones_cumplidas": cumplidas,
            "total_secciones": total,
            "porcentaje_cumplimiento": porcentaje,
            "estado": nuevo_estado,
            "validacion": resultados,
            "data": response.data
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/{silabo_id}/validacion")
def obtener_validacion_silabo(silabo_id: str):
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

        silabo = silabo_actual.data[0]

        # Obtener validaciones del sílabo
        response = (
            supabase.table("validacion_silabo")
            .select("*")
            .eq("silabo_id", silabo_id)
            .order("seccion")
            .execute()
        )

        return {
            "message": "Validación del sílabo obtenida correctamente",
            "silabo": {
                "id": silabo["id"],
                "asignatura": silabo["asignatura"],
                "codigo_asignatura": silabo["codigo_asignatura"],
                "estado": silabo["estado"],
                "porcentaje_cumplimiento": silabo["porcentaje_cumplimiento"],
                "archivo_url": silabo["archivo_url"]
            },
            "validacion": response.data
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.put("/{silabo_id}")
def actualizar_silabo(silabo_id: str, datos: SilaboUpdate):
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

        datos_actualizar = datos.model_dump(exclude_unset=True)

        if not datos_actualizar:
            raise HTTPException(
                status_code=400,
                detail="No se enviaron datos para actualizar"
            )

        if "ciclo" in datos_actualizar:
            if datos_actualizar["ciclo"] < 1 or datos_actualizar["ciclo"] > 10:
                raise HTTPException(
                    status_code=400,
                    detail="El ciclo debe estar entre 1 y 10"
                )

        response = (
            supabase.table("silabos")
            .update(datos_actualizar)
            .eq("id", silabo_id)
            .execute()
        )

        # Registrar trazabilidad de edición
        supabase.table("historial_silabo").insert({
            "silabo_id": silabo_id,
            "estado_anterior": silabo_actual.data[0]["estado"],
            "estado_nuevo": silabo_actual.data[0]["estado"],
            "observacion": "Se actualizó información general del sílabo.",
            "usuario": "frontend"
        }).execute()

        return {
            "message": "Información del sílabo actualizada correctamente",
            "data": response.data
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
