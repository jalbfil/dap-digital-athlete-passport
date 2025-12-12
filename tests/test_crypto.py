import sys
import os

# Añadimos el directorio raíz al path para poder importar 'app'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.vc import issue_vc_jwt, verify_jwt

def test_sign_and_verify_success():
    """
    Prueba que un token emitido legítimamente se verifica correctamente.
    """
    # 1. Datos de prueba
    mock_vc_data = {
        "event": "TEST EVENT",
        "bib": "123",
        "result": {"time": "01:00:00"}
    }
    did_subject = "did:example:test_runner"
    
    # 2. Emitir (Firmar)
    # Nota: Esto usa tus claves reales en app/keys/. Si fallase, revisa que existan.
    issued = issue_vc_jwt(mock_vc_data, subject_did=did_subject, ttl=60)
    token = issued["token"]
    
    assert token is not None
    assert len(token) > 0

    # 3. Verificar
    verification = verify_jwt(token)
    
    # 4. Aserciones (Lo que esperamos que pase)
    assert verification["ok"] is True, "La verificación de un token válido falló"
    payload = verification["payload"]
    assert payload["sub"] == did_subject
    assert payload["vc"]["event"] == "TEST EVENT"

def test_verify_tampered_token_fails():
    """
    Prueba que si un hacker altera un solo carácter del token, la firma falla.
    """
    # 1. Emitir token válido
    mock_vc_data = {"test": "data"}
    issued = issue_vc_jwt(mock_vc_data, "did:test", ttl=60)
    valid_token = issued["token"]
    
    # 2. Tampering (Alteración maliciosa)
    # Un JWT son 3 partes: Header.Payload.Signature
    # Vamos a cambiar la última letra de la firma
    tampered_token = valid_token[:-1] + ("A" if valid_token[-1] != "A" else "B")
    
    # 3. Verificar token corrupto
    verification = verify_jwt(tampered_token)
    
    # 4. Aserciones
    assert verification["ok"] is False, "El sistema aceptó un token manipulado"
    # El error suele ser "Signature verification failed" o "Invalid signature"
    print(f"\n[INFO] Error capturado correctamente: {verification.get('error')}")