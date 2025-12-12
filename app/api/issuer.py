from __future__ import annotations
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Body, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import Credential
from app.services.vc import verify_jwt

# --- CONFIGURACIÓN ---
router = APIRouter(prefix="/verifier", tags=["verifier"])

# --- DEPENDENCIES ---
DBDep = Annotated[AsyncSession, Depends(get_db)]

# --- DTOs (Modelos de Entrada) ---
class VerifyRequest(BaseModel):
    token: str

# --- ENDPOINTS ---

@router.post("/verify", summary="Verificación Criptográfica + Estado")
async def verify_token(
    db: DBDep,
    body: VerifyRequest = Body(...)
):
    """
    Realiza una auditoría completa de la credencial recibida (VC-JWT).
    
    Flujo de Validación (Academic Standard):
    1. **Integridad y Autenticidad**: Verifica la firma digital (RS256) resolviendo
       la clave pública del emisor a través de su DID (Web o EBSI).
    2. **Validez Temporal**: Comprueba que el token no haya expirado ('exp').
    3. **Estado de Ciclo de Vida**: Consulta la BD para asegurar que la credencial
       no ha sido REVOCADA por el organizador.
    """
    token = body.token
    
    # 1. Verificación Criptográfica (Capa DID/SSI)
    # Llama al servicio que contiene la lógica del 'DID Resolver' inteligente.
    # Si el issuer es 'did:ebsi:...', simulará la resolución en Blockchain.
    verification = verify_jwt(token)
    
    if not verification["ok"]:
        return {
            "valid": False, 
            "reason": f"Firma o estructura inválida: {verification.get('error')}"
        }

    payload = verification["payload"]
    jti = payload.get("jti")

    if not jti:
        return {"valid": False, "reason": "El token no contiene identificador único (JTI)."}

    # 2. Verificación de Estado (Capa de Persistencia)
    # Buscamos el ID en la base de datos para comprobar si sigue siendo válido.
    query = select(Credential).where(Credential.jti == jti)
    result = await db.execute(query)
    credential = result.scalar_one_or_none()

    # Caso A: La credencial no existe en nuestra BD (puede venir de otro sistema)
    # En un sistema federado real, aquí consultaríamos una 'Revocation List' externa.
    if not credential:
        return {"valid": False, "reason": "Credencial desconocida (JTI no encontrado)."}

    # Caso B: La credencial fue revocada manualmente (Botón rojo del Admin)
    if credential.status == "revoked":
        return {"valid": False, "reason": "La credencial ha sido REVOCADA por el emisor."}

    # ¡ÉXITO!
    return {
        "valid": True,
        "claims": payload  # Devolvemos los datos certificados al verificador
    }

@router.get("/scan", summary="Verificación por Referencia (QR)")
async def verify_by_jti(
    db: DBDep,
    jti: str = Query(..., description="ID único de la credencial (del QR)")
):
    """
    Endpoint utilizado al escanear el código QR.
    En lugar de recibir el token pesado, recibe el ID (JTI), recupera el token
    de la base de datos y ejecuta la misma lógica de validación.
    """
    # 1. Recuperación
    query = select(Credential).where(Credential.jti == jti)
    result = await db.execute(query)
    credential = result.scalar_one_or_none()

    if not credential:
        return {"valid": False, "reason": "Credencial no encontrada."}

    if not credential.token:
        return {"valid": False, "reason": "Registro corrupto: Token no disponible."}

    # 2. Reutilización de Lógica
    # Incluso si viene de BD, volvemos a verificar la firma y la expiración
    # para garantizar que el token almacenado sigue siendo criptográficamente válido
    # en el momento presente (ej. si la clave rotó o si acaba de caducar hace 1 seg).
    verification = verify_jwt(credential.token)

    if not verification["ok"]:
        return {"valid": False, "reason": f"Token expirado o inválido: {verification.get('error')}"}

    # 3. Comprobación de Revocación
    if credential.status == "revoked":
        return {"valid": False, "reason": "La credencial está REVOCADA."}

    return {
        "valid": True, 
        "claims": verification["payload"]
    }
