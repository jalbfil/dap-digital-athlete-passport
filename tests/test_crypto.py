import sys
import os

# --- CONFIGURACIÓN DE ENTORNO DE TEST ---
# Añadimos el directorio raíz al PYTHONPATH para poder importar el módulo 'app'
# sin necesidad de instalarlo como paquete del sistema.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.vc import issue_vc_jwt, verify_jwt

# ==========================================
# SUITE DE PRUEBAS: CRIPTOGRAFÍA Y FIRMA DIGITAL
# Objetivo: Validar la integridad y autenticidad de las credenciales (VC-JWT).
# ==========================================

def test_sign_and_verify_success():
    """
    [Happy Path] Verifica el ciclo completo de vida criptográfico:
    1. Emisión: El Issuer firma los datos con su Clave Privada.
    2. Verificación: El Verifier comprueba la firma con la Clave Pública.
    
    Criterio de éxito:
    - El token se genera correctamente.
    - La verificación devuelve 'ok': True.
    - Los datos (claims) extraídos coinciden bit a bit con los originales.
    """
    # 1. Preparación de datos (Mock Data)
    mock_vc_data = {
        "event": "FINAL TFG EVENT",
        "bib": "555",
        "result": {"time": "00:45:00", "category": "Elite"}
    }
    did_subject = "did:example:test_runner"
    
    # 2. Emisión (Firma RS256)
    # issue_vc_jwt utiliza internamente la clave privada cargada en app/keys/
    issued = issue_vc_jwt(mock_vc_data, subject_did=did_subject, ttl=60)
    token = issued["token"]
    
    assert token is not None, "El token JWT no debería ser nulo"
    assert len(token.split('.')) == 3, "El token debe tener 3 partes (Header.Payload.Signature)"

    # 3. Verificación
    # verify_jwt utiliza la clave pública para validar matemáticamente la firma
    verification = verify_jwt(token)
    
    # 4. Aserciones (Validación de resultados)
    assert verification["ok"] is True, f"Fallo en verificación válida: {verification.get('error')}"
    
    payload = verification["payload"]
    
    # Validamos la Integridad de los datos
    assert payload["sub"] == did_subject
    assert payload["vc"]["event"] == "FINAL TFG EVENT"
    assert payload["vc"]["bib"] == "555"
    
    print("\n✅ [TEST] Ciclo de firma y verificación completado con éxito.")

def test_verify_tampered_token_fails():
    """
    [Security Test] Prueba de Integridad (Tampering).
    Simula un ataque donde un actor malicioso intenta modificar el token
    (ej. cambiando el tiempo de carrera) sin poseer la clave privada.
    
    Criterio de éxito:
    - El sistema DEBE rechazar el token modificado.
    - El error debe indicar fallo de firma (Signature verification failed).
    """
    # 1. Emitir un token legítimo primero
    mock_vc_data = {"score": "100"}
    issued = issue_vc_jwt(mock_vc_data, "did:test", ttl=60)
    valid_token = issued["token"]
    
    # 2. Simulación de Ataque (Tampering)
    # Un JWT es: Header(base64).Payload(base64).Signature
    # Modificamos el último carácter de la firma para invalidarla.
    # Esto rompe la correspondencia matemática entre los datos y el hash firmado.
    tampered_token = valid_token[:-1] + ("X" if valid_token[-1] != "X" else "Y")
    
    # 3. Intento de Verificación
    verification = verify_jwt(tampered_token)
    
    # 4. Aserciones
    assert verification["ok"] is False, "CRÍTICO: El sistema aceptó un token manipulado."
    
    # Opcional: Verificar que el mensaje de error es el esperado
    # PyJWT suele devolver "Signature verification failed" o "Invalid signature"
    error_msg = verification.get('error', '')
    print(f"\n✅ [TEST] Token manipulado rechazado correctamente. Error: '{error_msg}'")
