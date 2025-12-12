import os
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# --- PARÁMETROS CRIPTOGRÁFICOS (Estándares NIST/W3C) ---
# Tamaño de clave: 2048 bits es el estándar mínimo actual para RSA.
# Provee un equilibrio adecuado entre seguridad y rendimiento para firmas JWT.
KEY_SIZE = 2048

# Exponente público: 65537 (Fermat F4).
# Es el estándar industrial porque permite una verificación de firma muy rápida
# y es seguro contra ataques a exponentes pequeños.
PUBLIC_EXPONENT = 65537

def generate_keys():
    """
    Genera un par de claves RSA (Pública/Privada) para la firma de credenciales.
    Este script actúa como el proceso de 'Bootstrapping' de la identidad del Emisor.
    """
    
    # 1. Configuración de Rutas (Pathlib para robustez Cross-OS)
    base_dir = Path(__file__).resolve().parent
    keys_dir = base_dir / "app" / "keys"
    
    # Crear directorio si no existe (mkdir -p)
    keys_dir.mkdir(parents=True, exist_ok=True)
    
    private_key_path = keys_dir / "private.pem"
    public_key_path = keys_dir / "public.pem"

    # Aviso de seguridad si ya existen
    if private_key_path.exists():
        print(f"⚠️  ATENCIÓN: Las claves ya existen en '{keys_dir}'.")
        print("   Sobrescribirlas invalidará todas las credenciales emitidas anteriormente.")
        # En un entorno real pediríamos confirmación, para el MVP sobrescribimos/regeneramos.

    print(f"🔄 Generando nuevo par de claves RSA ({KEY_SIZE} bits)...")

    # 2. Generación de la Clave Privada
    private_key = rsa.generate_private_key(
        public_exponent=PUBLIC_EXPONENT,
        key_size=KEY_SIZE,
    )

    # 3. Serialización (Guardado en disco)
    
    # A) Clave Privada
    # Formato: PKCS#8 (Estándar moderno para claves privadas)
    # Cifrado: NoEncryption (Para que Docker pueda arrancar sin pedir password manual)
    pem_private = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    # B) Clave Pública
    # Formato: SubjectPublicKeyInfo (Estándar X.509 para compartir claves públicas)
    pem_public = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    # 4. Escritura de Archivos
    with open(private_key_path, "wb") as f:
        f.write(pem_private)
        
    with open(public_key_path, "wb") as f:
        f.write(pem_public)

    print("\n✅ [ÉXITO] Infraestructura de Claves Pública (PKI) inicializada.")
    print(f"   🔑 Privada: {private_key_path} (¡NO COMPARTIR!)")
    print(f"   🌍 Pública: {public_key_path} (Para el Verificador)")

if __name__ == "__main__":
    generate_keys()
