import os
import re
import io
import pytesseract
from PIL import Image

# --- CONFIGURACIÓN TESSERACT (Híbrido Windows/Docker) ---
POSSIBLE_PATHS = [
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Users\Public\Tesseract-OCR\tesseract.exe"
]

TESSERACT_CMD = None
for path in POSSIBLE_PATHS:
    if os.path.exists(path):
        TESSERACT_CMD = path
        break

if TESSERACT_CMD:
    # ESTAMOS EN WINDOWS
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    tess_folder = os.path.dirname(TESSERACT_CMD)
    os.environ["TESSDATA_PREFIX"] = tess_folder
    print(f"✅ OCR (Windows): Tesseract encontrado en {TESSERACT_CMD}")
else:
    # ESTAMOS EN DOCKER / LINUX (O Windows sin configurar)
    # En Docker, tesseract ya está en el PATH, no hace falta configurar nada extra.
    print("ℹ️ OCR (Docker/Linux): Usando Tesseract del sistema (PATH por defecto).")

def extract_race_data(image_bytes: bytes) -> dict:
    """
    Extrae: Evento, Dorsal, Nombre y Tiempo.
    """
    try:
        # 1. Pre-procesamiento
        image = Image.open(io.BytesIO(image_bytes))
        image = image.convert('L') # Escala de grises
        
        # 2. Ejecutar OCR
        text = pytesseract.image_to_string(image, config='--psm 6')
        
        print("\n--- TEXTO LEÍDO POR OCR ---")
        print(text)
        print("---------------------------\n")

        data = {
            "event": None,
            "bib": None,
            "name": None,
            "time": None,
            "raw_text": text.strip()
        }

        # 3. ANÁLISIS POR REGEX (Patrones)

        # A) EVENTO (Busca la palabra HYROX y captura toda la línea)
        # Patrón: Cualquier cosa + HYROX + Cualquier cosa
        event_match = re.search(r'(?i).*(hyrox).*', text)
        if event_match:
            # Capturamos la línea completa del texto original donde aparece Hyrox
            # (Limpiamos saltos de línea extra)
            lines = text.split('\n')
            for line in lines:
                if "HYROX" in line.upper():
                    data["event"] = line.strip()
                    break

        # B) TIEMPO (Busca etiquetas o formato HH:MM:SS)
        time_match = re.search(r'(?i)(?:tiempo|time)[:\.\s]+(\d{1,2}:\d{2}(:\d{2})?)', text)
        if time_match:
            data["time"] = time_match.group(1)
        else:
            fallback_time = re.search(r'\b(\d{1,2}:\d{2}:\d{2})\b', text)
            if fallback_time:
                 data["time"] = fallback_time.group(1)

        # C) DORSAL (Busca etiquetas o números de 3-5 cifras)
        bib_match = re.search(r'(?i)(?:dorsal|bib)[:\.\s]+(\d+)', text)
        if bib_match:
            data["bib"] = bib_match.group(1)
        else:
            numbers = re.findall(r'\b\d{3,5}\b', text)
            for num in numbers:
                if "202" in num: continue # Evitar años
                data["bib"] = num
                break 

        # D) NOMBRE (Busca etiquetas Nombre/Name/Atleta)
        # Patrón: "Nombre:" seguido de texto hasta el final de la línea
        name_match = re.search(r'(?i)(?:nombre|name|atleta|athlete)[:\.\s]+([a-zA-Z\s\.]+)', text)
        if name_match:
            data["name"] = name_match.group(1).strip()
        
        return data

    except Exception as e:
        print(f"❌ Error CRÍTICO en OCR: {e}")
        return {"error": str(e), "raw_text": ""}