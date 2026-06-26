from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.services.vector_context_service import (
    get_vector_supabase_client,
    is_vector_context_enabled,
    process_document_to_vector_db,
    search_vector_context,
)


router = APIRouter(prefix="/api/contexto-vectorial", tags=["Contexto Vectorial"])


def _validar_contexto_vectorial_activo():
    if not is_vector_context_enabled():
        raise HTTPException(
            status_code=503,
            detail="El contexto vectorial está desactivado en este entorno.",
        )


class VectorSearchRequest(BaseModel):
    query: str
    match_count: int = Field(default=5, ge=1, le=20)


@router.post("/documentos")
async def cargar_documento_contexto(
    archivo: UploadFile = File(...),
    origen: Optional[str] = None,
):
    _validar_contexto_vectorial_activo()

    nombre = (archivo.filename or "").lower()
    content_type = (archivo.content_type or "").lower()
    es_pdf = nombre.endswith(".pdf") or content_type == "application/pdf"
    es_docx = (
        nombre.endswith(".docx")
        or content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    if not archivo.filename or not (es_pdf or es_docx):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF o DOCX.")

    try:
        contenido = await archivo.read()
        resultado = process_document_to_vector_db(
            contenido,
            archivo.filename,
            origen=origen,
            content_type=archivo.content_type,
        )
        documento = resultado["documento"]
        duplicado = resultado.get("duplicado", False)

        return {
            "success": True,
            "documento_id": documento.get("id"),
            "nombre": documento.get("nombre", archivo.filename),
            "total_chunks": resultado.get("total_chunks", 0),
            "duplicado": duplicado,
            "message": (
                "Documento ya existía en la base vectorial"
                if duplicado
                else "Documento procesado correctamente"
            ),
        }
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"No se pudo procesar el documento: {error}") from error


@router.post("/buscar")
def buscar_contexto_vectorial(payload: VectorSearchRequest):
    _validar_contexto_vectorial_activo()

    try:
        data = search_vector_context(payload.query, match_count=payload.match_count)
        return {
            "success": True,
            "query": payload.query,
            "match_count": payload.match_count,
            "data": data,
        }
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"No se pudo buscar contexto vectorial: {error}") from error


@router.get("/documentos")
def listar_documentos_contexto():
    _validar_contexto_vectorial_activo()

    try:
        supabase = get_vector_supabase_client()
        response = (
            supabase.table("documentos_contexto")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        return {
            "success": True,
            "data": response.data or [],
        }
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"No se pudieron listar documentos: {error}") from error


@router.get("/documentos/{documento_id}/chunks")
def listar_chunks_documento(documento_id: str):
    _validar_contexto_vectorial_activo()

    try:
        supabase = get_vector_supabase_client()
        response = (
            supabase.table("chunks_contexto")
            .select("*")
            .eq("documento_id", documento_id)
            .order("chunk_index")
            .execute()
        )
        return {
            "success": True,
            "documento_id": documento_id,
            "data": response.data or [],
        }
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"No se pudieron listar chunks: {error}") from error


@router.delete("/documentos/{documento_id}")
def eliminar_documento_contexto(documento_id: str):
    _validar_contexto_vectorial_activo()

    try:
        supabase = get_vector_supabase_client()
        supabase.table("chunks_contexto").delete().eq("documento_id", documento_id).execute()
        response = (
            supabase.table("documentos_contexto")
            .delete()
            .eq("id", documento_id)
            .execute()
        )
        return {
            "success": True,
            "documento_id": documento_id,
            "data": response.data or [],
            "message": "Documento y chunks eliminados correctamente",
        }
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"No se pudo eliminar el documento: {error}") from error
