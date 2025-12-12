from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, func
from .session import Base

class Credential(Base):
    __tablename__ = "credentials"
    
    # JTI es PK, así que ya tiene índice.
    jti: Mapped[str] = mapped_column(String(128), primary_key=True)
    token: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="valid", index=True) # Indexado para búsquedas rápidas de revocación
    # Usamos func.now() para delegar la fecha a la DB (más preciso)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Nonce(Base):
    __tablename__ = "nonces"
    
    value: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)