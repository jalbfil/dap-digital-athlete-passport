from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, func
from .session import Base

class Credential(Base):
    """
    Representa una Credencial Verificable (VC) emitida por el sistema.
    Almacena el token firmado y su estado de ciclo de vida (válido/revocado).
    """
    __tablename__ = "credentials"
    
    # Utilizamos JTI (JWT ID) como Clave Primaria Natural.
    # Al ser PK, garantiza unicidad y tiene índice automático.
    jti: Mapped[str] = mapped_column(String(128), primary_key=True)
    
    # El token JWT completo (Header.Payload.Signature). 
    # Se almacena como Texto largo.
    token: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Estado de revocación. Indexado para que el endpoint de verificación sea rápido.
    # Valores: 'valid', 'revoked'.
    status: Mapped[str] = mapped_column(String(16), default="valid", index=True)
    
    # Auditoría: Fecha de creación.
    # IMPORTANTE: timezone=True asegura que se guarde como UTC explícito,
    # evitando errores de comparación de fechas entre servidores.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<Credential(jti='{self.jti}', status='{self.status}')>"

class Nonce(Base):
    """
    Token criptográfico de un solo uso (Challenge-Response).
    Se utiliza para prevenir ataques de repetición (Replay Attacks) en la verificación.
    """
    __tablename__ = "nonces"
    
    # El valor aleatorio generado (URL-safe string)
    value: Mapped[str] = mapped_column(String(64), primary_key=True)
    
    # Fecha límite de validez. Si el reloj actual > expires_at, se rechaza.
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Marca de consumo. Si no es None, el nonce ya fue usado y debe rechazarse.
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    def __repr__(self) -> str:
        return f"<Nonce(val='{self.value[:10]}...', consumed={self.consumed_at is not None})>"
