from __future__ import annotations
from io import BytesIO
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Response, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Importamos jwt para decodificar los datos visuales
import jwt
# Importamos qrcode para la generación robusta
import qrcode

from app.db.session import get_db
from app.db.models import Credential

# --- CONFIGURACIÓN ---
router = APIRouter(prefix="/holder", tags=["holder"])

BASE_DIR = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = BASE_DIR / "app" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# --- DEPENDENCIES ---
DBDep = Annotated[AsyncSession, Depends(get_db)]

# --- ENDPOINTS ---

@router.get("", response_class=HTMLResponse, summary="Cartera Digital (Dashboard)")
async def holder_ui(request: Request, db: DBDep):
    """
    Renderiza la Cartera Digital con todas las credenciales activas.
    Combina la persistencia del código nuevo con la robustez visual.
    """
    # 1. Recuperamos credenciales
    result = await db.execute(
        select(Credential).where(Credential.status == "valid").order_by(Credential.created_at.desc())
    )
    creds_rows = result.scalars().all()

    # 2. Procesamos datos para la vista (SSR)
    display_creds = []
    
    for c in creds_rows:
        parsed_data = {
            "jti": c.jti,
            "token": c.token,
            "event": "Desconocido",
            "bib": "-",
            "name": "-",
            "time": "-",
            "date": c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else ""
        }
        
        try:
            # Decodificación segura para visualización
            payload = jwt.decode(c.token, options={"verify_signature": False})
            vc_subject = payload.get("vc", {}).get("credentialSubject", {})
            
            # Corrección de anidamiento (si existe)
            if "credentialSubject" in vc_subject:
                vc_subject = vc_subject["credentialSubject"]
            
            parsed_data["event"] = vc_subject.get("event", "Evento Genérico")
            parsed_data["bib"] = vc_subject.get("bib", "-")
            parsed_data["name"] = vc_subject.get("name", "Atleta")
            
            if "result" in vc_subject and isinstance(vc_subject["result"], dict):
                parsed_data["time"] = vc_subject["result"].get("time", "-")
            else:
                parsed_data["time"] = vc_subject.get("time", "-")
                
        except Exception:
            pass
            
        display_creds.append(parsed_data)

    return templates.TemplateResponse("holder.html", {
        "request": request,
        "credentials": display_creds
    })

@router.get("/{jti}/qr.png", summary="Generar QR (Backend Local)")
async def holder_qr(jti: str, db: DBDep):
    """
    Genera el QR localmente usando la librería qrcode.
    Incluye cabeceras de caché para optimizar el rendimiento en el cliente.
    """
    # 1. Validamos que la credencial existe
    query = select(Credential).where(Credential.jti == jti)
    result = await db.execute(query)
    credential = result.scalar_one_or_none()
    
    if not credential:
        raise HTTPException(status_code=404, detail="Credencial no encontrada")

    # 2. Generación Robusta 
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        
        # Codificamos el JTI (Puntero a la credencial)
        qr.add_data(credential.jti)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        
        # MEJORA: Cache-Control para evitar regeneración innecesaria
        return Response(
            content=buffer.getvalue(), 
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=31536000, immutable"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando QR: {str(e)}")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando QR: {str(e)}")

@router.get("/{jti}.json", summary="JSON Raw")
async def holder_json(jti: str, db: DBDep):
    """Endpoint auxiliar para ver el JSON crudo (Debug)."""
    query = select(Credential).where(Credential.jti == jti)
    result = await db.execute(query)
    credential = result.scalar_one_or_none()
    
    if not credential:
        raise HTTPException(status_code=404, detail="No encontrado")
    
    return JSONResponse({
        "jti": credential.jti, 
        "token": credential.token,
        "status": credential.status
    })
