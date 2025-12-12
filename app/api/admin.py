from __future__ import annotations
import os
from pathlib import Path
from typing import Annotated, Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request, Query, Body
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import Credential, Nonce

# --- CONFIGURACIÓN ---
router = APIRouter(prefix="/admin", tags=["admin"])

# Configuración de plantillas usando pathlib para mayor robustez entre SO
# Buscamos la carpeta 'templates' subiendo dos niveles desde este archivo
BASE_DIR = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = BASE_DIR / "app" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# --- DEPENDENCIES ---
# Inyección de dependencia para la sesión de base de datos asíncrona
DBDep = Annotated[AsyncSession, Depends(get_db)]

# --- SEGURIDAD ---
def verify_admin_access(request: Request, token_query: str | None) -> None:
    """
    Middleware de seguridad manual para proteger rutas de administración.
    Implementa una estrategia dual de autenticación:
    1. Vía Query Param (?token=...): Útil para acceso rápido desde navegador/UI.
    2. Vía Header (Authorization: Bearer ...): Estándar para llamadas API/Postman.
    """
    expected_token = os.getenv("ADMIN_TOKEN")
    
    # Fail-safe: Si no hay token configurado en el servidor, bloqueamos todo por seguridad.
    if not expected_token:
        raise HTTPException(status_code=500, detail="Error de configuración: ADMIN_TOKEN no definido.")
    
    # 1. Estrategia Query Parameter
    if token_query == expected_token:
        return

    # 2. Estrategia Header Bearer
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        # Extraemos el token después de 'Bearer '
        if auth_header.split(" ", 1)[1].strip() == expected_token:
            return

    # Si ninguna estrategia valida, rechazamos la petición
    raise HTTPException(status_code=401, detail="Acceso denegado: Credenciales de administrador inválidas.")

# --- DTOs (Data Transfer Objects) ---
class RevokeRequest(BaseModel):
    """Modelo para la petición de revocación."""
    jti: str
    reason: str | None = None # Opcional: Razón de la revocación para auditoría

# --- ENDPOINTS ---

@router.get("/db", summary="Volcado de base de datos (Debug)")
async def admin_db(
    request: Request, 
    db: DBDep, 
    token: str | None = Query(None)
):
    """
    Devuelve un JSON con el estado crudo de las tablas.
    Útil para auditoría técnica y depuración sin acceder al servidor SQL.
    """
    verify_admin_access(request, token)

    # 1. Recuperar Credenciales
    # Usamos scalars() para obtener objetos ORM puros
    creds_rows = (await db.execute(select(Credential))).scalars().all()
    credentials_data = [
        {
            "jti": c.jti,
            "status": c.status,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            # Truncamos el token por seguridad y legibilidad en logs
            "token_snippet": (c.token[:30] + "...") if c.token else None,
        }
        for c in creds_rows
    ]

    # 2. Recuperar Nonces (Retos criptográficos)
    nonces_rows = (await db.execute(select(Nonce))).scalars().all()
    nonces_data = [
        {
            "value": n.value,
            "expires_at": n.expires_at.isoformat() if n.expires_at else None,
            "consumed_at": n.consumed_at.isoformat() if n.consumed_at else None,
        }
        for n in nonces_rows
    ]

    return JSONResponse({
        "summary": {
            "total_credentials": len(credentials_data),
            "total_nonces": len(nonces_data)
        },
        "credentials": credentials_data,
        "nonces": nonces_data
    })

@router.get("/ui", response_class=HTMLResponse, summary="Panel de Control Web")
async def admin_ui(
    request: Request, 
    db: DBDep, 
    token: str | None = Query(None)
):
    """
    Renderiza el Dashboard de administración (Server-Side Rendering).
    Muestra tablas ordenadas cronológicamente para facilitar la gestión.
    """
    verify_admin_access(request, token)

    # Consultas ordenadas por fecha descendente (lo más nuevo arriba)
    creds_rows = (await db.execute(
        select(Credential).order_by(Credential.created_at.desc())
    )).scalars().all()
    
    nonces_rows = (await db.execute(
        select(Nonce).order_by(Nonce.expires_at.desc())
    )).scalars().all()

    # Helper para formatear fechas en la vista (evita lógica compleja en Jinja2)
    def fmt_dt(dt):
        return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "-"

    # Preparamos el contexto para la plantilla
    context = {
        "request": request,
        "token": token or "", # Mantenemos el token en los enlaces de la UI
        "creds": [
            {
                "jti": c.jti,
                "status": c.status,
                "created_at": fmt_dt(c.created_at),
                "token_start": (c.token[:50] + "...") if c.token else "N/A",
            } for c in creds_rows
        ],
        "nonces": [
            {
                "value": n.value,
                "expires_at": fmt_dt(n.expires_at),
                "consumed_at": fmt_dt(n.consumed_at),
                "is_active": n.consumed_at is None # Flag visual para la UI
            } for n in nonces_rows
        ]
    }

    return templates.TemplateResponse("admin.html", context)

@router.post("/revoke", summary="Revocación de Credencial")
async def revoke_credential(
    request: Request,
    db: DBDep,
    body: RevokeRequest,
    token: str | None = Query(None)
):
    """
    Ejecuta la revocación lógica de una credencial.
    Cambia el estado en BD a 'revoked', lo que impedirá verificaciones futuras.
    """
    verify_admin_access(request, token)

    # Búsqueda eficiente por índice (jti)
    stmt = select(Credential).where(Credential.jti == body.jti)
    result = await db.execute(stmt)
    credential = result.scalar_one_or_none()

    if not credential:
        raise HTTPException(status_code=404, detail=f"Credencial con JTI '{body.jti}' no encontrada.")
    
    # Actualización de estado (Atomicidad garantizada por el commit final)
    credential.status = "revoked"
    await db.commit()
    
    # Opcional: Podríamos refrescar el objeto para devolver el estado actualizado
    # await db.refresh(credential)

    return {
        "status": "ok",
        "action": "revocation",
        "target_jti": body.jti,
        "new_status": "revoked",
        "timestamp": credential.created_at.isoformat() if credential.created_at else None
    }
