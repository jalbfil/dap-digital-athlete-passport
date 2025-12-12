from __future__ import annotations
from io import BytesIO
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Response, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import Credential

try:
    import qrcode
except ImportError:
    qrcode = None # Manejo elegante si falta la dependencia

# --- CONFIGURACIÓN ---
router = APIRouter(prefix="/holder", tags=["holder"])

# Configuración de plantillas robusta (independiente del SO)
# Subimos dos niveles (parents[1]) para encontrar la carpeta 'templates'
BASE_DIR = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = BASE_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# --- DEPENDENCIES ---
DBDep = Annotated[AsyncSession, Depends(get_db)]

# --- ENDPOINTS ---

@router.get("", response_class=HTMLResponse, summary="Cartera Digital (UI)")
async def holder_page(request: Request):
    """
    Renderiza la interfaz visual del Holder (Cartera).
    Permite al atleta ver sus credenciales y generar QRs.
    """
    return templates.TemplateResponse("holder.html", {"request": request})

@router.get("/{jti}.json", summary="Obtener Credencial Raw")
async def holder_json(jti: str, db: DBDep):
    """
    Devuelve los datos crudos de la credencial en formato JSON.
    Útil para depuración o para que otras apps consuman la credencial.
    """
    # Consulta optimizada: Buscamos por JTI (que debería tener índice en BD)
    query = select(Credential).where(Credential.jti == jti)
    result = await db.execute(query)
    credential = result.scalar_one_or_none()
    
    if not credential:
        raise HTTPException(status_code=404, detail=f"Credencial con JTI '{jti}' no encontrada.")
    
    # Devolvemos solo lo necesario, evitando exponer campos internos de la BD
    return JSONResponse({
        "jti": credential.jti, 
        "status": credential.status, 
        "token": credential.token,
        "issued_at": credential.created_at.isoformat() if credential.created_at else None
    })

@router.get("/{jti}/qr.png", summary="Generar QR de Presentación")
async def holder_qr(jti: str, db: DBDep):
    """
    Genera dinámicamente un código QR que contiene el Token JWT completo.
    Esto permite la presentación 'offline' o física ante un Verificador.
    """
    # 1. Validación de dependencias
    if qrcode is None:
        raise HTTPException(
            status_code=500, 
            detail="Error de configuración: La librería 'qrcode[pil]' no está instalada."
        )

    # 2. Recuperación del Token
    query = select(Credential).where(Credential.jti == jti)
    result = await db.execute(query)
    credential = result.scalar_one_or_none()
    
    if not credential:
        raise HTTPException(status_code=404, detail="Credencial no encontrada para generar QR.")

    if not credential.token:
        raise HTTPException(status_code=422, detail="La credencial existe pero no tiene un token válido asociado.")

    # 3. Generación del QR en Memoria (IO Bound)
    # Usamos BytesIO para no escribir archivos temporales en disco (mejor rendimiento y limpieza)
    try:
        # Creamos el QR con el contenido del Token JWT
        qr_image = qrcode.make(credential.token)
        
        buffer = BytesIO()
        qr_image.save(buffer, format="PNG")
        
        # CRÍTICO: Rebobinar el puntero del buffer al inicio
        # Si no hacemos esto, al leer el buffer estará al final y enviará 0 bytes.
        buffer.seek(0)
        
        return Response(content=buffer.getvalue(), media_type="image/png")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando imagen QR: {str(e)}")
