from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import silabos, dashboard

app = FastAPI(
    title="API de Monitoreo de Gestión de Sílabos",
    description="Backend para el MVP del sistema de monitoreo de mejora continua ISIA",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(silabos.router)
app.include_router(dashboard.router)


@app.get("/")
def home():
    return {
        "message": "API de Monitoreo de Gestión de Sílabos funcionando correctamente"
    }