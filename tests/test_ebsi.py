import sys
import os
import pytest

# Añadir raíz al path para importar la app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.vc import issue_vc_jwt, verify_jwt

def test_ebsi_compatibility_flow():
    """
    Prueba que la arquitectura soporta DIDs con formato EBSI (did:ebsi:...)
    simulando la resolución de identidad.
    """
    print("\n--- INICIANDO TEST DE COMPATIBILIDAD EBSI ---")

    # 1. DATOS DE PRUEBA "EUROPEOS"
    # Usamos un DID con el formato oficial de EBSI
    ebsi_did = "did:ebsi:zx812389123..." 
    
    mock_data = {
        "credentialSchema": {
            "id": "https://api.preprod.ebsi.eu/trusted-schemas-registry/v1/schemas/...",
            "type": "JsonSchemaValidator2018"
        },
        "credentialSubject": {
            "id": "did:ebsi:athlete456",
            "achievement": "Hyrox Finisher"
        }
    }

    # 2. EMISIÓN (El sistema firma actuando como un nodo EBSI simulado)
    print(f"[1] Emitiendo credencial con Issuer DID: {ebsi_did}")
    issued = issue_vc_jwt(mock_data, subject_did="did:ebsi:athlete456")
    
    # Forzamos manualmente que el 'iss' en el token sea el de EBSI
    # (ya que issue_vc_jwt podría usar el de .env por defecto)
    # Nota: En un caso real, cambiaríamos la config. Aquí verificamos la validación.
    
    # Vamos a verificar el token generado asumiendo que el issuer fuera EBSI
    # Para la prueba, usaremos el token tal cual, pero el 'resolve_did' interceptará
    # el DID si modificamos la llamada o si el token lleva el DID correcto.
    
    # TRUCO DE TEST: Creamos un token manual con 'iss' = 'did:ebsi:...'
    # para probar exclusivamente el verificador.
    from app.services.vc import _get_private_key
    import jwt
    
    payload = {
        "iss": ebsi_did, # <--- LA CLAVE: Decimos que somos EBSI
        "sub": "did:ebsi:athlete",
        "jti": "test-ebsi-01",
        "vc": mock_data
    }
    # Firmamos con nuestra clave local (simulando que es la clave registrada en EBSI)
    token_ebsi = jwt.encode(payload, _get_private_key(), algorithm="RS256")

    # 3. VERIFICACIÓN (El momento de la verdad)
    print(f"[2] Verificando token EBSI...")
    result = verify_jwt(token_ebsi)

    # 4. ASERCIONES
    assert result["ok"] is True
    assert result["payload"]["iss"] == ebsi_did
    print("✅ El sistema aceptó y resolvió el DID EBSI correctamente.")