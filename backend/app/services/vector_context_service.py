import hashlib
import os
from functools import lru_cache
from io import BytesIO

from supabase import Client, create_client

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover - dependency may not be installed yet
    fitz = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover - dependency may not be installed yet
    SentenceTransformer = None


BATCH_SIZE = 50
DEFAULT_MODEL_NAME = "BAAI/bge-m3"


@lru_cache(maxsize=1)
def get_embedding_model():
    if SentenceTransformer is None:
        raise RuntimeError("sentence-transformers no está instalado.")

    model_name = os.getenv("EMBEDDING_MODEL_NAME", DEFAULT_MODEL_NAME).strip() or DEFAULT_MODEL_NAME
    return SentenceTransformer(model_name)


@lru_cache(maxsize=1)
def get_vector_supabase_client() -> Client:
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    service_role_key = os.getenv("SUPABASE_KEY", "").strip()

    if not supabase_url:
        raise RuntimeError("Falta configurar SUPABASE_URL.")
    if not service_role_key:
        raise RuntimeError("Falta configurar SUPABASE_KEY para contexto vectorial.")

    return create_client(supabase_url, service_role_key)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    if fitz is None:
        raise RuntimeError("PyMuPDF no está instalado.")
    if not file_bytes:
        raise ValueError("El archivo PDF está vacío.")

    try:
        with fitz.open(stream=BytesIO(file_bytes), filetype="pdf") as document:
            textos = [page.get_text("text") for page in document]
    except Exception as error:
        raise ValueError(f"Error al extraer texto del PDF: {error}") from error

    texto = "\n".join(textos).strip()
    if not texto:
        raise ValueError("El PDF no contiene texto extraíble.")

    return texto


def chunk_text(texto: str, size: int = 2000, overlap: int = 200) -> list[str]:
    texto_limpio = " ".join((texto or "").split())
    if not texto_limpio:
        return []
    if size <= 0:
        raise ValueError("El tamaño de chunk debe ser mayor a cero.")
    if overlap < 0 or overlap >= size:
        raise ValueError("El overlap debe ser mayor o igual a cero y menor que el tamaño del chunk.")

    chunks = []
    inicio = 0
    while inicio < len(texto_limpio):
        fin = inicio + size
        chunk = texto_limpio[inicio:fin].strip()
        if chunk:
            chunks.append(chunk)
        if fin >= len(texto_limpio):
            break
        inicio = fin - overlap

    return chunks


def generate_embedding(text: str) -> list[float]:
    if not text or not text.strip():
        raise ValueError("No se puede generar embedding de texto vacío.")

    try:
        model = get_embedding_model()
        embedding = model.encode(text, normalize_embeddings=True)
    except Exception as error:
        raise RuntimeError(f"Error al generar embedding: {error}") from error

    if hasattr(embedding, "tolist"):
        return [float(valor) for valor in embedding.tolist()]

    return [float(valor) for valor in embedding]


def _calcular_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def _buscar_documento_por_hash(supabase: Client, hash_archivo: str) -> dict | None:
    try:
        response = (
            supabase.table("documentos_contexto")
            .select("*")
            .eq("hash_archivo", hash_archivo)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None
    except Exception:
        return None


def _insertar_documento(supabase: Client, filename: str, origen: str | None, hash_archivo: str) -> dict:
    registro = {
        "nombre": filename,
        "origen": origen,
        "hash_archivo": hash_archivo,
    }

    try:
        response = supabase.table("documentos_contexto").insert(registro).execute()
    except Exception:
        response = (
            supabase.table("documentos_contexto")
            .insert({"nombre": filename, "origen": origen})
            .execute()
        )

    if not response.data:
        raise RuntimeError("Supabase no devolvió el documento insertado.")

    return response.data[0]


def _insertar_chunks(supabase: Client, documento_id: str, chunks: list[str]) -> list[dict]:
    registros = []
    for index, contenido in enumerate(chunks):
        registros.append(
            {
                "documento_id": documento_id,
                "chunk_index": index,
                "contenido": contenido,
                "embedding": generate_embedding(contenido),
            }
        )

    insertados = []
    for inicio in range(0, len(registros), BATCH_SIZE):
        lote = registros[inicio:inicio + BATCH_SIZE]
        response = supabase.table("chunks_contexto").insert(lote).execute()
        insertados.extend(response.data or [])

    return insertados


def process_pdf_to_vector_db(file_bytes: bytes, filename: str, origen: str | None = None) -> dict:
    if not filename.lower().endswith(".pdf"):
        raise ValueError("Solo se aceptan archivos PDF para la base vectorial.")

    texto = extract_text_from_pdf(file_bytes)
    chunks = chunk_text(texto, size=2000, overlap=200)
    if not chunks:
        raise ValueError("No se generaron chunks a partir del PDF.")

    supabase = get_vector_supabase_client()
    hash_archivo = _calcular_hash(file_bytes)
    documento_existente = _buscar_documento_por_hash(supabase, hash_archivo)

    if documento_existente:
        return {
            "documento": documento_existente,
            "total_chunks": 0,
            "duplicado": True,
        }

    documento = _insertar_documento(supabase, filename, origen, hash_archivo)
    documento_id = documento.get("id")
    if not documento_id:
        raise RuntimeError("El documento insertado no contiene id.")

    chunks_insertados = _insertar_chunks(supabase, documento_id, chunks)

    return {
        "documento": documento,
        "total_chunks": len(chunks_insertados) or len(chunks),
        "duplicado": False,
    }


def search_vector_context(query: str, match_count: int = 5) -> list[dict]:
    if not query or not query.strip():
        raise ValueError("La consulta de búsqueda no puede estar vacía.")

    query_embedding = generate_embedding(query)
    supabase = get_vector_supabase_client()

    response = supabase.rpc(
        "match_chunks",
        {
            "query_embedding": query_embedding,
            "match_count": match_count,
        },
    ).execute()

    return response.data or []


def format_context_chunks_for_prompt(chunks: list[dict]) -> str:
    if not chunks:
        return ""

    lineas = ["Contexto documental recuperado desde la base vectorial:"]
    for index, chunk in enumerate(chunks, start=1):
        documento = chunk.get("nombre_documento") or chunk.get("nombre") or chunk.get("documento") or "Documento"
        contenido = chunk.get("contenido") or chunk.get("content") or chunk.get("texto") or ""
        similarity = chunk.get("similarity") or chunk.get("similitud") or chunk.get("score")
        lineas.append(
            f"{index}. Documento: {documento}\n"
            f"Similarity: {similarity if similarity is not None else '-'}\n"
            f"Fragmento: {contenido}"
        )

    return "\n\n".join(lineas)


def search_vector_context_for_prompt(query: str, match_count: int = 5) -> str:
    try:
        chunks = search_vector_context(query, match_count=match_count)
        return format_context_chunks_for_prompt(chunks)
    except Exception as error:
        print("[Contexto Vectorial] No se pudo recuperar contexto:", type(error).__name__, str(error))
        return ""
