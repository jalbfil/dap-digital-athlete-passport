from __future__ import annotations
import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

# --- CONFIGURACIÓN DE CONEXIÓN ---
# Usamos 'sqlite+aiosqlite' para que la conexión a SQLite sea no bloqueante.
# En un entorno síncrono estándar se usaría solo 'sqlite://'.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./dap.db")

# Configuración específica para SQLite en entornos multihilo/async
connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}

# --- MOTOR DE BASE DE DATOS (ENGINE) ---
engine = create_async_engine(
    DATABASE_URL,
    connect_args=connect_args,
    # 'echo=True' permite ver las SQL queries en la consola (útil para depuración)
    echo=os.getenv("SQL_ECHO", "0").lower() in ("1", "true", "yes"),
    future=True, # Activa compatibilidad estricta con SQLAlchemy 2.0
)

# --- FÁBRICA DE SESIONES (SESSION FACTORY) ---
SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    # IMPORTANTE: expire_on_commit=False es crítico en contextos asíncronos.
    # Evita que SQLAlchemy intente refrescar atributos accediendo a la BD
    # fuera de un 'await', lo que causaría errores de "Missing Greenlet".
    expire_on_commit=False, 
)

# --- CLASE BASE ORM ---
# Todas las tablas (modelos) heredarán de esta clase para ser registradas.
class Base(DeclarativeBase):
    pass

# --- INYECCIÓN DE DEPENDENCIAS (Dependency Injection) ---
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Provee una sesión de base de datos asíncrona para cada petición HTTP.
    
    Patrón 'Unit of Work':
    1. Crea la sesión al inicio de la request.
    2. La entrega al endpoint (yield).
    3. Cierra la sesión automáticamente al terminar (context manager),
       incluso si hubo errores, evitando fugas de conexiones.
    """
    async with SessionLocal() as session:
        yield session
