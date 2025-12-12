from __future__ import annotations
import os
import re
import io
from typing import Dict, Any, Optional

# Manejo robusto de la importación de librerías de imagen
try:
    import pytesseract
    from PIL import Image
except ImportError:
    # Esto permite que el código cargue (aunque falle al ejecutar) si faltan deps
    pytesseract = None
    Image = None

# --- CONFIGURACIÓN TESSERACT (Híbrido Windows/Docker) ---
# Intentamos localizar el ejecutable en rutas estándar de Windows para desarrollo local.
# En Docker (Linux), se asume que 'tesseract' está en el PATH del sistema.

POSSIBLE_PATHS = [
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe", # Típico v3.02
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",       # Típico v4/v5
    r"C:\Users\Public\Tesseract-OCR\tesseract.exe"
]

TESSERACT_CMD = None
for path in POSSIBLE_PATHS:
    if os.path.exists(path):
        TESSERACT_CMD = path
        break

if TESSERACT_CMD and pytesseract:
    # ENTORNO WINDOWS (Desarrollo Local)
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    
    # FIX CRÍTICO: Tesseract v3 en Windows a veces pierde la referencia a 'tessdata'.
    # Forzamos la variable de entorno para evitar errores de "Failed loading language 'eng'".
    tess_folder = os.path.dirname(TESSERACT_CMD)
    os.environ["TESSDATA_PREFIX"] = tess_folder
    
    print(f"✅ OCR (Windows): Motor Tesseract vinculado en {TESSERACT_CMD}")
else:
    # ENTORNO DOCKER / LINUX
    print("ℹ️ OCR (Docker/Linux): Usando Tesseract del sistema (PATH por defecto).")


def extract_race_data(image_bytes: bytes) -> Dict[str, Any]:
    """
    Procesa una imagen binaria, aplica OCR y utiliza heurísticas (Regex) 
    para extraer datos estructurados de una clasificación deportiva.

    Args:
        image_bytes (bytes): Contenido crudo de la imagen subida.

    Returns:
        dict: Diccionario con claves 'event', 'bib', 'name', 'time' y 'raw_text'.
    """
    if not pytesseract or not Image:
        return {"error": "Librerías de OCR no instaladas en el servidor."}

    try:
        # 1. Pre-procesamiento de Imagen (Computer Vision básico)
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convertimos a Escala de Grises ('L').
        # Esto elimina ruido de color y mejora significativamente la precisión 
        # del motor OCR en textos negros sobre fondo blanco/gris.
        image = image.convert('L') 
        
        # 2. Ejecución del Motor OCR
        # Configuración '--psm 6': "Assume a single uniform block of text".
        # Ideal para leer tablas o listas estructuradas como una clasificación.
        text = pytesseract.image_to_string(image, config='--psm 6')
        
        # Log para depuración (visible en consola de Docker/Uvicorn)
        print(f"\n--- [OCR DEBUG] Texto extraído ({len(text)} chars) ---")
        print(text.strip())
        print("------------------------------------------------------\n")

        data = {
            "event": None,
            "bib": None,
            "name": None,
            "time": None,
            "raw_text": text.strip()
        }

        # 3. Extracción Semántica mediante Expresiones Regulares (Regex)

        # A) EVENTO: Búsqueda contextual
        # Buscamos la palabra clave "HYROX" (case-insensitive) y capturamos la línea completa.
        event_match = re.search(r'(?i).*(hyrox).*', text)
        if event_match:
            lines = text.split('\n')
            for line in lines:
                if "HYROX" in line.upper():
                    data["event"] = line.strip()
                    break

        # B) TIEMPO: Reconocimiento de patrones numéricos
        # Busca formatos HH:MM:SS o etiquetas explícitas "Tiempo: ..."
        time_match = re.search(r'(?i)(?:tiempo|time)[:\.\s]+(\d{1,2}:\d{2}(:\d{2})?)', text)
        if time_match:
            data["time"] = time_match.group(1)
        else:
            # Fallback: buscar patrón de hora aislado (ej: 01:05:23)
            fallback_time = re.search(r'\b(\d{1,2}:\d{2}:\d{2})\b', text)
            if fallback_time:
                 data["time"] = fallback_time.group(1)

        # C) DORSAL (BIB): Heurística de exclusión
        # Busca etiquetas "Dorsal: 123" o números aislados de 3-5 cifras.
        bib_match = re.search(r'(?i)(?:dorsal|bib)[:\.\s]+(\d+)', text)
        if bib_match:
            data["bib"] = bib_match.group(1)
        else:
            # Fallback: Buscar números sueltos, filtrando posibles años (2023, 2024, 2025...)
            # para evitar falsos positivos con la fecha del evento.
            numbers = re.findall(r'\b\d{3,5}\b', text)
            for num in numbers:
                if num.startswith("202"): continue 
                data["bib"] = num
                break 

        # D) NOMBRE: Búsqueda por etiquetas
        # Requiere que la imagen contenga "Nombre:" o "Athlete:" para ser preciso.
        name_match = re.search(r'(?i)(?:nombre|name|atleta|athlete)[:\.\s]+([a-zA-Z\s\.]+)', text)
        if name_match:
            data["name"] = name_match.group(1).strip()
        
        return data

    except Exception as e:
        print(f"❌ Error CRÍTICO en OCR: {e}")
        return {"error": str(e), "raw_text": ""}
