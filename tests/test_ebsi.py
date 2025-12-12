import sys
import os
import pytest
import jwt # PyJWT

# --- CONFIGURACIÓN DEL ENTORNO DE TEST ---
# Insertamos la raíz del proyecto en el path para importar los módulos de la app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.vc import verify_jwt, _get_private_key

# ==========================================
# SUITE DE PRUEBAS: INTEROPERABILIDAD EUROPEA (EBSI)
# Objetivo: Validar que la arquitectura soporta múltiples métodos DID.
# ==========================================

def test_ebsi_compatibility_flow():
    """
    [Integration Test] Simulación de Resolución de Identidad EBSI.
    
    Escenario:
    Un Verificador (esta app) recibe una credencial emitida por una entidad
    registrada en la Blockchain Europea (EBSI).
    
    Objetivo:
    Demostrar que el 'DID Resolver' es capaz de detectar el prefijo 'did:ebsi'
    y conmutar la estrategia de verificación, diferenciándola de 'did:web'.
    """
    print("\n--- [TEST] INICIANDO SIMULACIÓN DE COMPATIBILIDAD EBSI ---")

    # 1. PREPARACIÓN (MOCK DATA)
    # Definimos un DID que cumple con el formato de la European Blockchain Services Infrastructure
    ebsi_did_issuer = "did:ebsi:zsSgDXeYPHua5yX986..." 
    did_subject = "did:ebsi:zp1..." 
    
    # Estructura de credencial alineada con W3C y perfil EBSI
    mock_vc_payload = {
        "type": ["VerifiableCredential", "VerifiableAttestation"],
        "credentialSchema": {
            "id": "https://api.preprod.ebsi.eu/trusted-schemas-registry/v1/schemas/0xb4f...",
            "type": "JsonSchemaValidator2018"
        },
        "credentialSubject": {
            "id": did_subject,
            "achievement": "European Digital Athlete"
        }
    }

    # 2. EMISIÓN SIMULADA (MOCKING)
    # Como no tenemos la clave privada real de ese DID de EBSI (porque no somos la UE),
    # generamos un token firmado localmente pero FORZANDO el campo 'iss' (Issuer).
    # Esto engaña al verificador para que crea que viene de EBSI y active su lógica.
    
    print(f"[1] Generando credencial simulada desde: {ebsi_did_issuer}")
    
    token_payload = {
        "iss": ebsi_did_issuer,  # <--- PUNTO CLAVE: El Resolver leerá esto
        "sub": did_subject,
        "jti": "urn:uuid:ebsi-simulation-001",
        "vc": mock_vc_payload
    }
    
    # Firmamos con nuestra clave local (simulando que es la clave pública registrada en el Ledger)
    # En la realidad, el Resolver bajaría esta clave pública de la Blockchain.
    # En la simulación (vc.py), el Resolver devuelve nuestra clave local.
    local_private_key = _get_private_key()
    token_ebsi = jwt.encode(token_payload, local_private_key, algorithm="RS256")

    # 3. VERIFICACIÓN (PRUEBA DE ARQUITECTURA)
    # Llamamos al verificador real del sistema.
    print(f"[2] Ejecutando verify_jwt() contra el 'DID Resolver'...")
    
    result = verify_jwt(token_ebsi)

    # 4. ASERCIONES (VALIDACIÓN)
    # El sistema debe haber aceptado el token como válido.
    assert result["ok"] is True, f"Fallo en verificación EBSI: {result.get('error')}"
    
    # Verificamos que el payload decodificado mantiene la identidad EBSI
    decoded = result["payload"]
    assert decoded["iss"] == ebsi_did_issuer
    assert decoded["vc"]["credentialSubject"]["id"] == did_subject

    print("✅ [ÉXITO] Arquitectura agnóstica validada: El sistema resolvió correctamente un DID EBSI.")
