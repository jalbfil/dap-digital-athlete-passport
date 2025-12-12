from __future__ import annotations
import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./dap.db")

engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "0").lower() in ("1", "true", "yes"),
    future=True,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

class Base(DeclarativeBase):
    pass

# --- DEPENDENCY INJECTION CENTRALIZADA ---
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provee una sesión asíncrona única por request."""
    async with SessionLocal() as session:
        yield session