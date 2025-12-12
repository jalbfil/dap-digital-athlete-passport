# DAP V1 - Issuer / Holder / Verifier

## Instalación
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Generar claves (si no existen)
```python
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from pathlib import Path
base = Path('app/keys'); base.mkdir(parents=True, exist_ok=True)
priv = base/'private.pem'; pub = base/'public.pem'
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
priv.write_bytes(key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
))
pub.write_bytes(key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
))
print('OK')
```

## Flujo
1. **Issuer**: `POST /issuer/issue?ttl=3600&subject_did=did:example:holder:2305`
2. **Holder**: `GET /holder/{jti}.json` y `GET /holder/{jti}/qr.png`
3. **Verifier**:
   - `GET /verifier/challenge?ttl=60`
   - `POST /verifier/verify` con `{token, nonce}`
