from __future__ import annotations
import os
import secrets
from pathlib import Path
from typing import Annotated, Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request, Query, Body, status
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import Credential, Nonce

# --- CONFIGURACIÓN ---
router = APIRouter(prefix="/admin", tags=["admin"])
security = HTTPBasic()

BASE_DIR = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = BASE_DIR / "app" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# --- DEPENDENCIES ---
DBDep = Annotated[AsyncSession, Depends(get_db)]

# --- SEGURIDAD (MEJORADA: HTTP Basic Auth RFC 7617) ---
def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    """
    Verifica usuario y contraseña usando comparación segura (tiempo constante).
    Elimina la necesidad de pasar tokens por URL.
    """
    # En producción leeríamos de .env, aquí hardcodeamos para la demo segura
    # Usuario: admin
    # Pass: dap-secret
    
    # Intenta leer de variables de entorno si existen, si no usa los default
    env_user = os.getenv("ADMIN_USER", "admin")
    env_pass = os.getenv("ADMIN_PASS", "dap-secret")
    
    correct_username = secrets.compare_digest(credentials.username, env_user)
    correct_password = secrets.compare_digest(credentials.password, env_pass)

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# --- DTOs ---
class RevokeRequest(BaseModel):
    jti: str
    reason: str | None = None

# --- ENDPOINTS ---

@router.get("/db", summary="Volcado de base de datos (Debug)")
async def admin_db(
    request: Request, 
    db: DBDep, 
    username: str = Depends(get_current_username)
):
    """Devuelve un JSON con el estado crudo de las tablas (Protegido)."""
    
    creds_rows = (await db.execute(select(Credential))).scalars().all()
    credentials_data = [
        {
            "jti": c.jti,
            "status": c.status,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "token_snippet": (c.token[:30] + "...") if c.token else None,
        }
        for c in creds_rows
    ]

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
    username: str = Depends(get_current_username)
):
    """Renderiza el Dashboard de administración (Protegido con Basic Auth)."""
    
    creds_rows = (await db.execute(
        select(Credential).order_by(Credential.created_at.desc())
    )).scalars().all()
    
    nonces_rows = (await db.execute(
        select(Nonce).order_by(Nonce.expires_at.desc())
    )).scalars().all()

    def fmt_dt(dt):
        return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "-"

    context = {
        "request": request,
        "user": username,
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
                "is_active": n.consumed_at is None
            } for n in nonces_rows
        ]
    }

    return templates.TemplateResponse("admin.html", context)

@router.post("/revoke", summary="Revocación de Credencial")
async def revoke_credential(
    request: Request,
    db: DBDep,
    body: RevokeRequest,
    username: str = Depends(get_current_username)
):
    """Ejecuta la revocación lógica (Protegido)."""
    
    stmt = select(Credential).where(Credential.jti == body.jti)
    result = await db.execute(stmt)
    credential = result.scalar_one_or_none()

    if not credential:
        raise HTTPException(status_code=404, detail=f"Credencial con JTI '{body.jti}' no encontrada.")
    
    credential.status = "revoked"
    await db.commit()
    
    return {
        "status": "ok",
        "action": "revocation",
        "target_jti": body.jti,
        "new_status": "revoked",
        "admin_user": username
    }
