from __future__ import annotations
import os
import time
import uuid
import json
from functools import lru_cache
from typing import Any, Dict

import jwt  # PyJWT
from cryptography.hazmat.primitives import serialization

ALG = "RS256"

# --- CACHING DE CLAVES (Critical Performance) ---
@lru_cache(maxsize=1)
def _get_private_key() -> bytes:
    """Carga y cachea la clave privada."""
    env_pem = os.getenv("VC_PRIV")
    if env_pem and not os.path.isfile(env_pem):
        return env_pem.encode("utf-8")
    
    path = env_pem if env_pem else os.path.join(os.path.dirname(__file__), "..", "keys", "private.pem")
    path = os.path.abspath(path)
    
    if not os.path.exists(path):
        raise FileNotFoundError(f"Clave privada no encontrada en: {path}")
    
    with open(path, "rb") as f:
        return f.read()

@lru_cache(maxsize=1)
def _get_public_key() -> bytes:
    """Carga y cachea la clave pública local (Fallback)."""
    env_pub = os.getenv("VC_PUB")
    if env_pub and not os.path.isfile(env_pub):
        return env_pub.encode("utf-8")

    path = env_pub if env_pub else os.path.join(os.path.dirname(__file__), "..", "keys", "public.pem")
    path = os.path.abspath(path)

    if not os.path.exists(path):
        raise FileNotFoundError(f"Clave pública no encontrada en: {path}")
        
    with open(path, "rb") as f:
        return f.read()

# --- NUEVO: DID RESOLVER ABSTRACTION ---
def resolve_did_public_key(did: str) -> bytes:
    """
    Simula un resolutor universal de DIDs.
    - did:web -> Intenta resolver o usa local.
    - did:ebsi -> (Simulado) Podría consultar la Blockchain Europea.
    """
    print(f"🔍 Resolviendo DID: {did}")
    
    # 1. Caso EBSI (Simulación para demostrar compatibilidad)
    if did.startswith("did:ebsi:"):
        # En un caso real, aquí conectaríamos con la API de EBSI o un nodo blockchain.
        # Para el MVP, asumimos que la clave es la misma local (demo).
        print("   -> Detectado DID EBSI. Simulando resolución on-chain...")
        return _get_public_key()

    # 2. Caso DID Web (Estándar actual del proyecto)
    if did.startswith("did:web:"):
        # Aquí iría la lógica de descargar el did.json real.
        # Por simplicidad y robustez en demo, usamos la clave local.
        print("   -> Detectado DID Web. Usando clave local (cacheada).")
        return _get_public_key()

    # Default / Fallback
    return _get_public_key()

# --- LÓGICA DE NEGOCIO ---

def issue_vc_jwt(candidate_vc: Dict[str, Any], subject_did: str, ttl: int = 3600) -> Dict[str, Any]:
    now = int(time.time())
    jti = f"vc-{uuid.uuid4()}"
    iss = candidate_vc.get("issuer") or os.getenv("VC_ISS", "did:web:demo")

    payload = {
        "iss": iss,
        "sub": subject_did,
        "jti": jti,
        "nbf": now,
        "iat": now,
        "exp": now + int(ttl),
        "vc": candidate_vc,
    }

    priv_pem = _get_private_key()
    key = serialization.load_pem_private_key(priv_pem, password=None)
    
    token = jwt.encode(payload, key, algorithm=ALG)
    return {"jti": jti, "token": token, "claims": payload}

def verify_jwt(token: str) -> Dict[str, Any]:
    """
    Verifica el token usando la clave pública asociada al DID del emisor.
    """
    try:
        # 1. Decodificar cabecera sin verificar para leer el 'iss' (Issuer DID)
        unverified_payload = jwt.decode(token, options={"verify_signature": False})
        issuer_did = unverified_payload.get("iss", "")
        
        # 2. Resolver la clave pública correcta para ese DID
        pub_pem = resolve_did_public_key(issuer_did)
        key = serialization.load_pem_public_key(pub_pem)
        
        # 3. Verificar firma y claims
        # verify_aud=False porque en VCs a veces no hay audience definido
        payload = jwt.decode(token, key, algorithms=[ALG], options={"verify_aud": False})
        return {"ok": True, "payload": payload}
        
    except Exception as e:
        return {"ok": False, "error": str(e)}