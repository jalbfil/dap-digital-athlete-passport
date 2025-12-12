from __future__ import annotations
from pathlib import Path
from typing import Any, Annotated

# AÑADIDO: UploadFile y File para recibir imágenes
from fastapi import APIRouter, HTTPException, Body, Query, Depends, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.vc import issue_vc_jwt
from app.db.session import get_db
from app.db.models import Credential

# AÑADIDO: Importamos el servicio OCR
from app.services.ocr import extract_race_data

router = APIRouter(prefix="/issuer", tags=["issuer"])

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# --- DEPENDENCIES ---
DBDep = Annotated[AsyncSession, Depends(get_db)]

# --- MODELS ---
class VCModel(BaseModel):
    # Aceptamos lista de strings (estándar) o string único (por compatibilidad)
    type: list[str] | str 
    issuer: str | None = None
    credentialSubject: dict[str, Any]
    # Permitimos campos extra por si metemos @context o credentialSchema
    model_config = {"extra": "allow"}

# --- ENDPOINTS ---

@router.get("", response_class=HTMLResponse)
async def issuer_page(request: Request):
    return templates.TemplateResponse("issuer.html", {"request": request})

# --- NUEVO ENDPOINT OCR ---
@router.post("/ocr")
async def process_ocr(file: UploadFile = File(...)):
    """Recibe una imagen, extrae texto e intenta adivinar dorsal y tiempo."""
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="El archivo debe ser una imagen")
    
    content = await file.read()
    data = extract_race_data(content)
    
    return data
# ---------------------------

@router.post("/issue")
async def issue(
    db: DBDep,
    vc: VCModel = Body(...),
    ttl: int = Query(3600, ge=60, le=31536000), 
    subject_did: str = Query(..., alias="subject_did"),
):
    try:
        vc_dict = vc.model_dump() if hasattr(vc, "model_dump") else vc.dict()
        
        # --- MEJORA EBSI: Inyección de Esquema ---
        # Aseguramos que la credencial cumple con estándares europeos simulados
        if "credentialSchema" not in vc_dict:
            vc_dict["credentialSchema"] = {
                "id": "https://api.preprod.ebsi.eu/trusted-schemas-registry/v1/schemas/0x123...",
                "type": "JsonSchemaValidator2018"
            }
        # -----------------------------------------

        res = issue_vc_jwt(vc_dict, subject_did=subject_did, ttl=ttl)
    
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Configuración de claves incompleta: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cred = Credential(
        jti=res["jti"], 
        token=res["token"], 
        status="valid"
    )
    db.add(cred)
    await db.commit()

    subject_data = res["claims"].get("vc", {}).get("credentialSubject", {})
    
    return {
        "status": "ok",
        "jti": res["jti"],
        "token": res["token"],
        "claims": res["claims"],
        "summary": {
            "event": subject_data.get("event"),
            "bib":   subject_data.get("bib"),
            "name":  subject_data.get("name"),
            "time":  subject_data.get("result", {}).get("time"),
        },
    }