import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()

if not SUPABASE_URL:
    raise ValueError("Falta configurar SUPABASE_URL en el archivo .env")

if not SUPABASE_KEY:
    raise ValueError("Falta configurar SUPABASE_KEY en el archivo .env")