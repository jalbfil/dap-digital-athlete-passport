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

# --- CONFIGURACIÓN DE RUTAS ---
BASE_DIR = pathlib.Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Crear directorios si no existen (robustez)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# --- LIFESPAN (Arranque moderno) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicio: Crear tablas y verificar DB
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Check de salud silencioso al arrancar
        await conn.execute(text("SELECT 1"))
    yield
    # Apagado: Aquí cerraríamos pools externos (Redis, etc.) si los hubiera
    await engine.dispose()

# --- APP ---
app = FastAPI(
    title="DAP V1 — Issuer / Holder / Verifier / Admin",
    lifespan=lifespan
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# --- ROUTERS ---
app.include_router(issuer.router)
app.include_router(holder.router)
app.include_router(verifier.router)
app.include_router(admin.router)

# --- LANDING ---
@app.get("/")
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return PlainTextResponse("", status_code=204)

@app.get("/health")
async def health():
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        return {"status": "error", "db": str(e)}