from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import os

def generate_keys():
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    os.makedirs("app/keys", exist_ok=True)
    
    with open("app/keys/private.pem", "wb") as f:
        f.write(private_pem)
        
    with open("app/keys/public.pem", "wb") as f:
        f.write(public_pem)
        
    print("✅ Claves generadas en app/keys/")

if __name__ == "__main__":
    generate_keys()