from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, func
from .session import Base

# ... imports iguales ...

class Credential(Base):
    __tablename__ = "credentials"
    
    # unique=True es redundante si es primary_key, pero explícito es mejor.
    jti: Mapped[str] = mapped_column(String(128), primary_key=True, unique=True)
    token: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="valid", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<Credential(jti='{self.jti}', status='{self.status}')>"

class Nonce(Base):
    __tablename__ = "nonces"
    
    # Al ser PK, la base de datos impedirá físicamente insertar duplicados.
    value: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    def __repr__(self) -> str:
        return f"<Nonce(val='{self.value[:10]}...', consumed={self.consumed_at is not None})>"
