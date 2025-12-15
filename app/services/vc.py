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
@lru_cache(maxsize=1)
def _get_private_key() -> bytes:
    """Carga la clave privada del Emisor (Issuer)."""
    env_pem = os.getenv("VC_PRIV")
    if env_pem and not os.path.isfile(env_pem):
        return env_pem.encode("utf-8")
    
    path = env_pem if env_pem else os.path.join(os.path.dirname(__file__), "..", "keys", "private.pem")
    path = os.path.abspath(path)
    
    if not os.path.exists(path):
        # Generación al vuelo si no existe (para evitar crash en Docker limpio)
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.asymmetric import rsa
        print("⚠️ Claves no encontradas. Generando par temporal...")
        priv = rsa.generate_private_key(65537, 2048, default_backend())
        # Guardamos para la sesión
        return priv.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
    
    with open(path, "rb") as f:
        return f.read()

@lru_cache(maxsize=1)
def _get_public_key() -> bytes:
    """Carga la clave pública local."""
    # Si generamos la privada al vuelo arriba, necesitamos derivar la pública aquí
    # Pero para simplificar el código, asumimos que existen en disco o fallamos.
    env_pub = os.getenv("VC_PUB")
    path = env_pub if env_pub else os.path.join(os.path.dirname(__file__), "..", "keys", "public.pem")
    path = os.path.abspath(path)

    if not os.path.exists(path):
        # Fallback de emergencia: derivar de la privada
        priv_pem = _get_private_key()
        priv = serialization.load_pem_private_key(priv_pem, password=None)
        return priv.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
    with open(path, "rb") as f:
        return f.read()

# --- CAPA DE ABSTRACCIÓN DE IDENTIDAD (DID RESOLVER) ---

def resolve_did_public_key(did: str) -> bytes:
    """
    RESOLUTOR HÍBRIDO (Strategy Pattern).
    Simula la obtención de la clave pública según el prefijo del DID.
    """
    print(f"🔍 [DID Resolver] Analizando identidad: {did}")
    
    # ESTRATEGIA 1: EBSI (Simulación Mock)
    if did.startswith("did:ebsi:"):
        print("   -> 🇪🇺 Detectado DID EBSI. Iniciando protocolo de simulación...")
        print("      [MOCK] Consultando Trusted Issuer Registry (EBSI API v2)... OK")
        print("      [MOCK] Verificando integridad on-chain... OK")
        # TRUCO: Devolvemos la clave local para que la matemática RSA funcione,
        # pero para el sistema parece que vino de la blockchain europea.
        return _get_public_key()

    # ESTRATEGIA 2: DID Web
    if did.startswith("did:web:"):
        print("   -> 🌐 Detectado DID Web. Resolviendo vía HTTPS (Simulado).")
        return _get_public_key()

    # FALLBACK
    print("   -> ⚠️ DID Genérico/Local. Usando clave por defecto.")
    return _get_public_key()

# --- LÓGICA DE NEGOCIO (EMISIÓN Y VERIFICACIÓN) ---

def issue_vc_jwt(candidate_vc: Dict[str, Any], subject_did: str, ttl: int = 3600) -> Dict[str, Any]:
    """
    Genera una Verifiable Credential firmada.
    **Lógica EBSI:** Si el issuer es did:ebsi, inyecta el esquema obligatorio automáticamente.
    """
    now = int(time.time())
    jti = f"urn:uuid:{uuid.uuid4()}"
    
    # Determinamos el Issuer
    # Si viene en el candidato lo usamos, si no, usamos uno por defecto.
    iss = candidate_vc.get("issuer") or os.getenv("VC_ISS", "did:web:demo")

    # LÓGICA DE SIMULACIÓN EBSI
    credential_schema = []
    if iss.startswith("did:ebsi:"):
        # EBSI requiere que definas qué esquema de datos usas
        credential_schema = [{
            "id": "https://api.preprod.ebsi.eu/trusted-schemas-registry/v1/schemas/0x944...",
            "type": "JsonSchemaValidator2018"
        }]

    # Construcción del Payload W3C
    vc_payload = {
        "@context": ["https://www.w3.org/2018/credentials/v1"],
        "type": ["VerifiableCredential", "VerifiableAttestation"],
        "credentialSubject": candidate_vc
    }
    
    # Inyectamos el schema si existe (solo para EBSI)
    if credential_schema:
        vc_payload["credentialSchema"] = credential_schema

    full_payload = {
        "iss": iss,
        "sub": subject_did,
        "jti": jti,
        "nbf": now,
        "iat": now,
        "exp": now + int(ttl),
        "vc": vc_payload
    }

    # Firma
    priv_pem = _get_private_key()
    key = serialization.load_pem_private_key(priv_pem, password=None)
    token = jwt.encode(full_payload, key, algorithm=ALG)
    
    # Asegurar string (PyJWT devuelve bytes o str según versión)
    if isinstance(token, bytes):
        token = token.decode('utf-8')

    return {"jti": jti, "token": token, "claims": full_payload}

def verify_jwt(token: str) -> Dict[str, Any]:
    """
    Verifica criptográficamente un token.
    Utiliza el resolve_did_public_key para encontrar la clave correcta.
    """
    try:
        # 1. Leer header sin verificar firma (para saber el ISSUER)
        unverified = jwt.decode(token, options={"verify_signature": False})
        issuer_did = unverified.get("iss", "")
        
        # 2. Resolver Clave Pública (Aquí ocurre la magia de la simulación)
        pub_pem = resolve_did_public_key(issuer_did)
        key = serialization.load_pem_public_key(pub_pem)
        
        # 3. Verificar Firma matemática
        payload = jwt.decode(token, key, algorithms=[ALG], options={"verify_aud": False})
        
        return {"ok": True, "payload": payload}
        
    except jwt.ExpiredSignatureError:
        return {"ok": False, "error": "El token ha expirado (TTL vencido)."}
    except Exception as e:
        return {"ok": False, "error": str(e)}
