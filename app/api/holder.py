from __future__ import annotations
from io import BytesIO
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Response, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import Credential

router = APIRouter(prefix="/holder", tags=["holder"])

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# --- DEPENDENCIES ---
DBDep = Annotated[AsyncSession, Depends(get_db)]

# --- ENDPOINTS ---

@router.get("", response_class=HTMLResponse)
async def holder_page(request: Request):
    return templates.TemplateResponse("holder.html", {"request": request})

@router.get("/{jti}.json")
async def holder_json(jti: str, db: DBDep):
    # Consulta eficiente por Primary Key
    row = (await db.execute(select(Credential).where(Credential.jti == jti))).scalar_one_or_none()
    
    if not row:
        raise HTTPException(status_code=404, detail="Credencial no encontrada (JTI inválido)")
    
    return {
        "jti": row.jti, 
        "status": row.status, 
        "token": row.token
    }

@router.get("/{jti}/qr.png")
async def holder_qr(jti: str, db: DBDep):
    # 1. Recuperar Token
    row = (await db.execute(select(Credential).where(Credential.jti == jti))).scalar_one_or_none()
    
    if not row:
        raise HTTPException(status_code=404, detail="Credencial no encontrada")

    # 2. Generar QR
    try:
        import qrcode
    except ImportError:
        raise HTTPException(
            status_code=500, 
            detail="Librería 'qrcode' no instalada. Ejecuta: pip install 'qrcode[pil]'"
        )

    # Generamos la imagen en memoria
    qr_img = qrcode.make(row.token)
    buf = BytesIO()
    qr_img.save(buf, format="PNG")
    buf.seek(0) # Rebobinar puntero

    return Response(content=buf.getvalue(), media_type="image/png")