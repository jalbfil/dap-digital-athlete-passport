from __future__ import annotations
import os
import pathlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from app.db.session import engine, Base
from app.api import issuer, holder, verifier, admin

# --- 1. CONFIGURACIÓN ROBUSTA DE RUTAS ---
# Usamos pathlib para garantizar que las rutas funcionen igual en Windows, Linux y Docker.
# .resolve().parent nos da la ruta absoluta de la carpeta 'app', sin importar desde dónde se ejecute.
BASE_DIR = pathlib.Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Auto-creación de directorios para evitar errores en el primer despliegue
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# --- 2. GESTIÓN DEL CICLO DE VIDA (LIFESPAN) ---
# Este es el estándar moderno de FastAPI (v0.93+) para manejar recursos de inicio/cierre.
# Sustituye a los eventos deprecados @app.on_event("startup").
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context Manager que controla lo que ocurre antes de arrancar y al apagar.
    """
    # --- STARTUP (Antes de recibir peticiones) ---
    async with engine.begin() as conn:
        # Crea las tablas automáticamente si no existen (Auto-migration para el MVP)
        await conn.run_sync(Base.metadata.create_all)
        # 'Heartbeat': Ejecutamos una query simple para asegurar que la BD está viva
        await conn.execute(text("SELECT 1"))
    
    yield # Aquí la aplicación comienza a funcionar
    
    # --- SHUTDOWN (Al pulsar Ctrl+C o parar el contenedor) ---
    # Cerramos el pool de conexiones limpiamente para evitar fugas de recursos
    await engine.dispose()

# --- 3. DEFINICIÓN DE LA API ---
app = FastAPI(
    title="DAP v1.3 — Digital Athlete Passport",
    description="Infraestructura SSI para certificación deportiva (Issuer/Holder/Verifier).",
    version="1.3.0",
    lifespan=lifespan # Inyectamos la lógica de inicio/cierre definida arriba
)

# Montamos la carpeta 'static' para servir CSS/Imágenes
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# --- 4. ARQUITECTURA MODULAR (ROUTERS) ---
# Integramos los módulos funcionales. Esto mantiene el código desacoplado por roles.
app.include_router(issuer.router)   # Emisión + OCR
app.include_router(holder.router)   # Cartera + QR
app.include_router(verifier.router) # Verificación + DID Resolver
app.include_router(admin.router)    # Gestión y Revocación

# --- 5. ENDPOINTS GLOBALES ---

@app.get("/")
def index(request: Request):
    """Renderiza la Landing Page (punto de entrada visual)."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Evita errores 404 molestos en los logs del navegador."""
    return PlainTextResponse("", status_code=204)

@app.get("/health")
async def health():
    """
    Endpoint de salud para orquestadores (Docker/K8s).
    Comprueba conexión real a BD, no solo que el servidor HTTP responda.
    """
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected", "version": "1.3.0"}
    except Exception as e:
        return {"status": "error", "db_error": str(e)}
