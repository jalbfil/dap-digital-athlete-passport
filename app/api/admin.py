from __future__ import annotations
import os
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Query, Body
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import Credential, Nonce

router = APIRouter(prefix="/admin", tags=["admin"])

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))

# --- DEPENDENCIES ---
DBDep = Annotated[AsyncSession, Depends(get_db)]

def _check_admin_token(request: Request, token_query: str | None):
    """Valida el token de admin vía Query Param o Header Bearer."""
    expected = os.getenv("ADMIN_TOKEN")
    if not expected:
        raise HTTPException(status_code=500, detail="ADMIN_TOKEN no configurado en entorno")
    
    # 1. Intentar Query Param
    if token_query == expected:
        return

    # 2. Intentar Header Authorization
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer ") and auth.split(" ", 1)[1].strip() == expected:
        return

    raise HTTPException(status_code=401, detail="Credenciales de administrador inválidas")

# --- MODELS ---
class RevokeRequest(BaseModel):
    jti: str

# --- ENDPOINTS ---

@router.get("/db")
async def admin_db(
    request: Request, 
    db: DBDep, 
    token: str | None = Query(None)
):
    _check_admin_token(request, token)

    # Credentials
    creds_rows = (await db.execute(select(Credential))).scalars().all()
    credentials = []
    for c in creds_rows:
        credentials.append({
            "jti": c.jti,
            "status": c.status,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "token_snippet": (c.token[:30] + "...") if c.token else None,
        })

    # Nonces
    nonces_rows = (await db.execute(select(Nonce))).scalars().all()
    nonces = []
    for n in nonces_rows:
        nonces.append({
            "value": n.value,
            "expires_at": n.expires_at.isoformat() if n.expires_at else None,
            "consumed_at": n.consumed_at.isoformat() if n.consumed_at else None,
        })

    return JSONResponse({"credentials": credentials, "nonces": nonces})

@router.get("/ui", response_class=HTMLResponse)
async def admin_ui(
    request: Request, 
    db: DBDep, 
    token: str | None = Query(None)
):
    _check_admin_token(request, token)

    # Obtener datos
    creds_rows = (await db.execute(select(Credential).order_by(Credential.created_at.desc()))).scalars().all()
    nonces_rows = (await db.execute(select(Nonce).order_by(Nonce.expires_at.desc()))).scalars().all()

    def fmt_dt(dt):
        if not dt: return ""
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    creds_ctx = [{
        "jti": c.jti,
        "status": c.status,
        "created_at": fmt_dt(c.created_at),
        "token_start": (c.token[:50] + "...") if c.token else "",
    } for c in creds_rows]

    nonces_ctx = [{
        "value": n.value,
        "expires_at": fmt_dt(n.expires_at),
        "consumed_at": fmt_dt(n.consumed_at),
    } for n in nonces_rows]

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "creds": creds_ctx,
            "nonces": nonces_ctx,
            "token": token or "" 
        }
    )

@router.post("/revoke")
async def revoke_credential(
    request: Request,
    db: DBDep,
    body: RevokeRequest,
    token: str | None = Query(None)
):
    """Endpoint para revocar una credencial."""
    _check_admin_token(request, token)

    row = (await db.execute(select(Credential).where(Credential.jti == body.jti))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="JTI no encontrado")
    
    row.status = "revoked"
    await db.commit()
    
    return {"status": "ok", "jti": body.jti, "new_status": "revoked"}