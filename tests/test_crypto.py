import pytest
import time
# Importamos las funciones del servicio
from app.services.vc import issue_vc_jwt, verify_jwt

# --- DATOS DE PRUEBA ---
MOCK_DID_ISSUER = "did:web:dap-project.org"
MOCK_DID_HOLDER = "did:web:athlete:test-123"
MOCK_VC_DATA = {
    "dorsal": "999",
    "event": "Test Event 2025",
    "time": "00:45:30"
}

def test_sign_and_verify_success():
    """
    [Happy Path] Verifica el ciclo completo con el formato estándar (URN).
    """
    # 1. Emisión
    issued = issue_vc_jwt(
        candidate_vc=MOCK_VC_DATA, 
        subject_did=MOCK_DID_HOLDER, 
        ttl=60
    )
    
    token = issued["token"]
    
    # Validaciones básicas de estructura
    assert token is not None
    
    # ACTUALIZACIÓN: Ahora validamos el formato estándar URN
    # Antes era: assert issued["jti"].startswith("vc-")
    assert issued["jti"].startswith("urn:uuid:"), f"El JTI no cumple formato estándar: {issued['jti']}"
    
    # Validamos que los datos dentro del 'vc' son correctos
    # Nota: Según tu implementación, candidate_vc puede estar anidado o plano, 
    # ajustamos la comprobación para ser flexibles.
    claims = issued["claims"]["vc"]
    # Si credentialSubject existe (formato W3C estricto)
    if "credentialSubject" in claims:
        assert claims["credentialSubject"]["dorsal"] == "999"
    else:
        # Si está plano (formato simple)
        assert claims["dorsal"] == "999"

    # 2. Verificación
    verification = verify_jwt(token)
    
    # Validaciones de resultado
    assert verification["ok"] is True, f"Error en verificación: {verification.get('error')}"
    payload = verification["payload"]
    
    # Validar integridad de datos
    assert payload["sub"] == MOCK_DID_HOLDER


def test_verify_tampered_token_fails():
    """
    [Security Test] Prueba de integridad (Tampering).
    Simula un ataque de modificación de firma.
    """
    # 1. Emitir token válido
    issued = issue_vc_jwt(MOCK_VC_DATA, MOCK_DID_HOLDER, ttl=60)
    valid_token = issued["token"]
    
    # 2. Manipular la firma DE FORMA ROBUSTA
    # Dividimos el token en sus 3 partes (Header.Payload.Signature)
    parts = valid_token.split('.')
    
    # Sustituimos la firma real (parte 3) por basura
    fake_signature = "Est0EsUnaFirmaFalsaQueFallaraSeguro12345"
    tampered_token = f"{parts[0]}.{parts[1]}.{fake_signature}"
    
    # 3. Verificar
    verification = verify_jwt(tampered_token)
    
    # 4. Aserción: Debe fallar
    assert verification["ok"] is False, "CRÍTICO: El sistema aceptó una firma falsa."
    
    # Verificamos que el error sea de firma o de decodificación
    error_msg = str(verification.get("error")).lower()
    assert any(x in error_msg for x in ["signature", "invalid", "decode", "padding"]), \
        f"El error no fue el esperado: {error_msg}"


def test_verify_expired_token_fails():
    """
    [Time Test] Prueba de expiración (TTL).
    """
    # 1. Emitir token con TTL negativo (expirado hace 1 segundo)
    issued = issue_vc_jwt(MOCK_VC_DATA, MOCK_DID_HOLDER, ttl=-1)
    expired_token = issued["token"]
    
    # 2. Verificar
    verification = verify_jwt(expired_token)
    
    # 3. Aserción: Debe fallar por expiración
    assert verification["ok"] is False
    
    # FIX: Buscamos "expirado" (español) o "expired" (inglés) para ser robustos
    error_msg = str(verification.get("error")).lower()
    assert "expirado" in error_msg or "expired" in error_msg

