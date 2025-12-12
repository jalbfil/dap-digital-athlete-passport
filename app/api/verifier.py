from __future__ import annotations
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
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

# --- CONFIGURACIÓN ---
router = APIRouter(prefix="/verifier", tags=["verifier"])

BASE_DIR = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = BASE_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# --- DEPENDENCIES ---
DBDep = Annotated[AsyncSession, Depends(get_db)]

# --- DTOs ---
class VerifyRequest(BaseModel):
    token: str
    nonce: str | None = None

# --- ENDPOINTS ---

@router.get("", response_class=HTMLResponse, summary="Interfaz del Verificador")
async def verifier_page(request: Request):
    return templates.TemplateResponse("verifier.html", {"request": request})

@router.get("/challenge", summary="Generar Reto (Anti-Replay)")
async def challenge(db: DBDep, ttl: int = Query(60, ge=5, le=600)):
    """
    PASO 1: Protocolo de Desafío/Respuesta.
    Genera un 'Nonce' criptográfico (número de un solo uso) con tiempo de vida corto.
    El Holder debe firmar o presentar su credencial junto con este nonce para probar
    que la presentación es 'en vivo' y no una grabación (Replay Attack).
    """
    # 1. Generar aleatoriedad criptográficamente segura (CSPRNG)
    value = secrets.token_urlsafe(24)
    
    # 2. Definir caducidad (Time-to-Live)
    now_utc = datetime.now(timezone.utc)
    expires_at = now_utc + timedelta(seconds=ttl)
    
    # 3. Persistir el reto
    db.add(Nonce(value=value, expires_at=expires_at))
    await db.commit()
    
    return {
        "nonce": value, 
        "expiresAt": expires_at.isoformat(), 
        "ttl": ttl
    }

@router.post("/verify", summary="Verificar Credencial + Nonce")
async def verify(body: VerifyRequest, db: DBDep):
    """
    PASO 2: Auditoría completa.
    Verifica Criptografía + Integridad del Nonce + Estado de Revocación.
    """
    # --- A. VERIFICACIÓN CRIPTOGRÁFICA (Capa SSI/DID) ---
    # Llama al servicio que resuelve el DID (Web o EBSI) y valida la firma RS256
    crypto_check = verify_jwt(body.token)
    
    if not crypto_check["ok"]:
        return _fail("invalid_signature", {"error": crypto_check["error"]})

    payload = crypto_check["payload"]
    jti = payload.get("jti")

    # --- B. VERIFICACIÓN ANTI-REPLAY (Capa Protocolo) ---
    if body.nonce:
        q = select(Nonce).where(Nonce.value == body.nonce)
        nonce_row = (await db.execute(q)).scalar_one_or_none()
        
        now_utc = datetime.now(timezone.utc)
        
        # 1. ¿Existe el nonce?
        if not nonce_row:
            return _fail("nonce_invalid", {"msg": "Nonce desconocido o falso."})
        
        # 2. ¿Ya fue usado? (Prevención de doble gasto)
        if nonce_row.consumed_at is not None:
            return _fail("nonce_used", {"msg": "Este reto ya fue utilizado. Posible ataque de repetición."})
        
        # 3. ¿Ha caducado?
        # Aseguramos robustez de zona horaria
        db_expire = nonce_row.expires_at
        if db_expire.tzinfo is None:
            db_expire = db_expire.replace(tzinfo=timezone.utc)

        if db_expire < now_utc:
            return _fail("nonce_expired", {"msg": "El tiempo del reto ha expirado."})
            
        # 4. Consumir el nonce (Atomicidad)
        nonce_row.consumed_at = now_utc
        await db.commit()

    # --- C. VERIFICACIÓN DE ESTADO (Capa de Ciclo de Vida) ---
    if not jti:
        return _fail("malformed", {"reason": "El token no tiene JTI"})

    cred = (await db.execute(select(Credential).where(Credential.jti == jti))).scalar_one_or_none()
    
    # Si no existe en nuestra BD (puede ser externo o error)
    if not cred:
        return _fail("unknown_issuer", {"jti": jti, "msg": "Credencial no emitida por este sistema."})
    
    # Chequeo de Revocación
    if cred.status != "valid":
        return _fail("revoked", {"jti": jti, "status": cred.status})

    # --- ÉXITO ---
    return {
        "result": "valid",
        "details": {
            "jti": jti,
            "iss": payload.get("iss"),
            "sub": payload.get("sub"),
            "checks": ["crypto_signature", "nonce_freshness", "revocation_status"]
        }
    }

@router.get("/scan", summary="Verificación por QR (JTI)")
async def verify_by_scan(jti: str, db: DBDep):
    """
    Endpoint simplificado para escaneo de QR.
    Al leer el QR (que contiene el JTI), el sistema recupera el token original
    y lo re-verifica.
    """
    # 1. Recuperar token de BD
    cred = (await db.execute(select(Credential).where(Credential.jti == jti))).scalar_one_or_none()
    
    if not cred:
        return _fail("not_found", {"msg": "Credencial no encontrada."})
    
    if not cred.token:
        return _fail("corrupted", {"msg": "Token no disponible en el registro."})

    # 2. Re-verificar criptografía (por si la clave rotó o expiró hace 1 seg)
    crypto_check = verify_jwt(cred.token)
    if not crypto_check["ok"]:
        return _fail("expired_or_invalid", {"error": crypto_check["error"]})

    # 3. Verificar estado (Revocación)
    if cred.status != "valid":
        return _fail("revoked", {"status": cred.status})

    return {
        "result": "valid",
        "claims": crypto_check["payload"]
    }

def _fail(flag: str, details: dict):
    """Helper para estructurar respuestas de rechazo consistentes."""
    return {
        "result": "invalid", 
        "flag": flag, 
        "details": details
    }
