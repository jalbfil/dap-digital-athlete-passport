from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
import secrets
from typing import Annotated

from fastapi import APIRouter, Body, Query, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.vc import verify_jwt
from app.db.session import get_db
from app.db.models import Nonce, Credential

router = APIRouter(prefix="/verifier", tags=["verifier"])

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Tipo Helper para la DB
DBDep = Annotated[AsyncSession, Depends(get_db)]

@router.get("", response_class=HTMLResponse)
async def verifier_page(request: Request):
    return templates.TemplateResponse("verifier.html", {"request": request})

@router.get("/challenge")
async def challenge(db: DBDep, ttl: int = Query(60, ge=5, le=600)):
    # Usamos URL safe token
    value = secrets.token_urlsafe(24)
    # FECHAS UTC SIEMPRE
    now_utc = datetime.now(timezone.utc)
    expires_at = now_utc + timedelta(seconds=ttl)
    
    db.add(Nonce(value=value, expires_at=expires_at))
    await db.commit()
    
    return {
        "nonce": value, 
        "expiresAt": expires_at.isoformat(), 
        "ttl": ttl
    }

class VerifyIn(BaseModel):
    token: str
    nonce: str | None = None

@router.post("/verify")
async def verify(body: VerifyIn, db: DBDep):
    # 1. Verificar firma criptográfica
    sig = verify_jwt(body.token)
    if not sig["ok"]:
        return _fail("invalid_signature", {"error": sig["error"]})

    payload = sig["payload"]
    jti = payload.get("jti")

    # 2. Verificar Nonce (Anti-Replay)
    if body.nonce:
        q = select(Nonce).where(Nonce.value == body.nonce)
        row = (await db.execute(q)).scalar_one_or_none()
        
        # Fecha actual segura
        now_utc = datetime.now(timezone.utc)
        
        if not row:
            return _fail("nonce_invalid", {"nonce": "not_found"})
        
        if row.consumed_at is not None:
            return _fail("nonce_invalid", {"nonce": "already_used", "consumed_at": str(row.consumed_at)})
        
        # --- FIX ROBUSTEZ FECHAS ---
        # Aseguramos que la fecha de DB tenga zona horaria para poder compararla
        db_expire = row.expires_at
        if db_expire.tzinfo is None:
            db_expire = db_expire.replace(tzinfo=timezone.utc)

        if db_expire < now_utc:
            return _fail("nonce_invalid", {"nonce": "expired"})
            
        # Consumir nonce
        row.consumed_at = now_utc
        await db.commit()

    # 3. Verificar estado en DB (Revocación)
    if not jti:
        return _fail("malformed", {"reason": "no-jti"})

    cred = (await db.execute(select(Credential).where(Credential.jti == jti))).scalar_one_or_none()
    
    if not cred:
        return _fail("unknown_jti", {"jti": jti, "msg": "Credential not issued by this platform"})
    
    if cred.status != "valid":
        return _fail("revoked", {"jti": jti, "status": cred.status})

    # 4. Éxito
    return {
        "result": "valid",
        "score": 100,
        "flags": [],
        "details": {
            "jti": jti,
            "iss": payload.get("iss"),
            "sub": payload.get("sub"),
            "nonce": "ok" if body.nonce else "skipped",
            "signature": "ok",
        },
    }

def _fail(flag: str, details: dict):
    """Helper para respuestas de error consistentes"""
    return {
        "result": "invalid", 
        "score": 0, 
        "flags": [flag], 
        "details": details
    }