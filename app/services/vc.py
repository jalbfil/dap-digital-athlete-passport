from __future__ import annotations
import os
import time
import uuid
import json
from functools import lru_cache
from typing import Any, Dict

import jwt  # PyJWT
from cryptography.hazmat.primitives import serialization

# Algoritmo estándar para firmas en el ecosistema SSI (RSA con SHA-256)
ALG = "RS256"

# --- CACHING DE CLAVES (Optimización de Rendimiento) ---
# Usamos lru_cache para evitar lecturas de disco repetitivas en cada petición.
# Esto reduce la latencia de I/O a cero para operaciones criptográficas frecuentes.

@lru_cache(maxsize=1)
def _get_private_key() -> bytes:
    """
    Carga la clave privada del Emisor (Issuer).
    Soporta carga desde archivo (producción) o variable de entorno (CI/CD).
    """
    env_pem = os.getenv("VC_PRIV")
    # Si la variable de entorno contiene la clave directamente (no una ruta)
    if env_pem and not os.path.isfile(env_pem):
        return env_pem.encode("utf-8")
    
    # Ruta por defecto relativa al proyecto
    path = env_pem if env_pem else os.path.join(os.path.dirname(__file__), "..", "keys", "private.pem")
    path = os.path.abspath(path)
    
    if not os.path.exists(path):
        raise FileNotFoundError(f"Clave privada no encontrada en: {path}")
    
    with open(path, "rb") as f:
        return f.read()

@lru_cache(maxsize=1)
def _get_public_key() -> bytes:
    """
    Carga la clave pública local.
    Se utiliza como 'Fallback' cuando la resolución DID remota falla o en modo offline.
    """
    env_pub = os.getenv("VC_PUB")
    if env_pub and not os.path.isfile(env_pub):
        return env_pub.encode("utf-8")

    path = env_pub if env_pub else os.path.join(os.path.dirname(__file__), "..", "keys", "public.pem")
    path = os.path.abspath(path)

    if not os.path.exists(path):
        raise FileNotFoundError(f"Clave pública no encontrada en: {path}")
        
    with open(path, "rb") as f:
        return f.read()

# --- CAPA DE ABSTRACCIÓN DE IDENTIDAD (DID RESOLVER) ---

def resolve_did_public_key(did: str) -> bytes:
    """
    Implementa un 'Resolver' universal simulado.
    Patrón de diseño Strategy para soportar múltiples métodos DID (Web, EBSI, Key).
    
    Args:
        did (str): El Identificador Descentralizado (ej. did:web:example.com)
        
    Returns:
        bytes: El contenido PEM de la clave pública resuelta.
    """
    print(f"🔍 [DID Resolver] Resolviendo identidad: {did}")
    
    # ESTRATEGIA 1: Ecosistema Europeo (EBSI/ESSIF)
    # Simulación de resolución on-chain o contra API de Trusted Schema Registry.
    if did.startswith("did:ebsi:"):
        print("   -> 🇪🇺 Detectado DID EBSI. Simulando resolución segura on-chain...")
        # En producción, aquí haríamos una llamada RPC al nodo blockchain.
        return _get_public_key()

    # ESTRATEGIA 2: DID Web (W3C Standard)
    # Resolución basada en DNS/HTTPS (did.json).
    if did.startswith("did:web:"):
        print("   -> 🌐 Detectado DID Web. Usando clave local (cacheada) para demo.")
        # En producción, aquí haríamos un GET https://<domain>/.well-known/did.json
        return _get_public_key()

    # ESTRATEGIA 3: Fallback / Local
    print("   -> ⚠️ Método DID no reconocido o local. Usando clave por defecto.")
    return _get_public_key()

# --- LÓGICA DE NEGOCIO (EMISIÓN Y VERIFICACIÓN) ---

def issue_vc_jwt(candidate_vc: Dict[str, Any], subject_did: str, ttl: int = 3600) -> Dict[str, Any]:
    """
    Genera una Verifiable Credential firmada en formato JWT.
    
    Args:
        candidate_vc: Datos del claim (atleta, evento, tiempo).
        subject_did: DID del titular (Holder).
        ttl: Tiempo de vida en segundos.
    """
    now = int(time.time())
    jti = f"vc-{uuid.uuid4()}" # Identificador único global de la credencial
    
    # El emisor se define en el payload o por configuración
    iss = candidate_vc.get("issuer") or os.getenv("VC_ISS", "did:web:demo")

    # Payload estándar JWT + W3C VC
    payload = {
        "iss": iss,
        "sub": subject_did,
        "jti": jti,
        "nbf": now,          # Not Before
        "iat": now,          # Issued At
        "exp": now + int(ttl), # Expiration
        "vc": candidate_vc,  # Los datos de negocio van anidados aquí
    }

    # Firma con clave privada (RS256)
    priv_pem = _get_private_key()
    key = serialization.load_pem_private_key(priv_pem, password=None)
    
    token = jwt.encode(payload, key, algorithm=ALG)
    
    # Devolvemos estructura completa para facilitar la respuesta API
    return {"jti": jti, "token": token, "claims": payload}

def verify_jwt(token: str) -> Dict[str, Any]:
    """
    Verifica criptográficamente un token VC-JWT.
    
    Flujo:
    1. Decodifica header (sin verificar) para saber QUIÉN firma (iss).
    2. Resuelve la clave pública de ese emisor (DID Resolver).
    3. Verifica la firma y la caducidad con esa clave.
    """
    try:
        # 1. Inspección previa (Unverified)
        unverified_payload = jwt.decode(token, options={"verify_signature": False})
        issuer_did = unverified_payload.get("iss", "")
        
        # 2. Resolución de Identidad (Dynamic Key Loading)
        pub_pem = resolve_did_public_key(issuer_did)
        key = serialization.load_pem_public_key(pub_pem)
        
        # 3. Verificación Estricta
        # verify_aud=False es estándar en VCs genéricas (no hay un 'audience' único)
        payload = jwt.decode(token, key, algorithms=[ALG], options={"verify_aud": False})
        
        return {"ok": True, "payload": payload}
        
    except Exception as e:
        # Capturamos cualquier error (Expiración, Firma inválida, Malformación)
        return {"ok": False, "error": str(e)}
