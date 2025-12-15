from __future__ import annotations
import os
import re
import io
import pytesseract
from PIL import Image

# --- CONFIGURACIÓN TESSERACT ---
# Detectamos si estamos en Windows para desarrollo local.
# En Docker (Linux), no entra en el 'if' y usa el PATH del sistema automáticamente.
if os.name == 'nt':
    POSSIBLE_PATHS = [
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Users\Public\Tesseract-OCR\tesseract.exe"
    ]
    for path in POSSIBLE_PATHS:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            # Fix para versiones antiguas de Tesseract en Windows
            os.environ["TESSDATA_PREFIX"] = os.path.dirname(path)
            print(f"✅ OCR (Windows): Motor vinculado en {path}")
            break

def extract_race_data(image_bytes: bytes) -> dict:
    """
    Función principal de OCR.
    Procesa bytes de imagen y extrae datos estructurados (Dorsal, Tiempo, Evento).
    """
    try:
        # 1. Pre-procesamiento de imagen
        image = Image.open(io.BytesIO(image_bytes))
        image = image.convert('L') # Convertir a escala de grises para mejor contraste
        
        # 2. Ejecutar Motor OCR
        # --psm 6 asume un bloque de texto uniforme (bueno para listas/tablas)
        text = pytesseract.image_to_string(image, config='--psm 6', lang='spa+eng')
        
        # Log para depuración en la consola de Docker
        print(f"\n--- [OCR] Texto crudo detectado ---\n{text.strip()[:100]}...\n-----------------------------------")

        # 3. Extracción de datos (Lógica Regex)
        return {
            "raw_text": text.strip(),
            "event": _find_event(text),
            "bib": _find_dorsal(text),     # 'bib' es el nombre estándar para dorsal
            "time": _find_time(text),
            # Opcional: Nombre si lo detectamos
            "name": _find_name(text)
        }

    except Exception as e:
        print(f"❌ Error procesando OCR: {e}")
        # Degradación controlada: devolvemos vacío en lugar de romper el servidor
        return {
            "error": str(e),
            "raw_text": "",
            "event": None,
            "bib": None,
            "time": None
        }

# --- FUNCIONES AUXILIARES (HELPERS) ---

def _find_event(text: str) -> str | None:
    # Busca la palabra HYROX o similares
    match = re.search(r'(?i).*(hyrox).*', text)
    if match:
        return match.group(0).strip()
    return None

def _find_time(text: str) -> str | None:
    # 1. Busca etiqueta explícita "Tiempo: HH:MM:SS"
    match = re.search(r'(?i)(?:tiempo|time)[:\.\s]+(\d{1,2}:\d{2}(:\d{2})?)', text)
    if match:
        return match.group(1)
    
    # 2. Fallback: Busca formato de hora aislado (HH:MM:SS)
    fallback = re.search(r'\b(\d{1,2}:\d{2}:\d{2})\b', text)
    if fallback:
        return fallback.group(1)
    return None

def _find_dorsal(text: str) -> str | None:
    # 1. Busca etiqueta explícita "Dorsal: 123"
    match = re.search(r'(?i)(?:dorsal|bib|number)[:\.\s]+(\d+)', text)
    if match:
        return match.group(1)
    
    # 2. Fallback: Busca números de 3 a 5 cifras
    # Filtramos los que empiezan por "202" para no confundirlos con el año (2024, 2025)
    numbers = re.findall(r'\b\d{3,5}\b', text)
    for num in numbers:
        if not num.startswith("202"):
            return num
    return None

def _find_name(text: str) -> str | None:
    # Intenta buscar un nombre después de la etiqueta "Nombre:" o "Athlete:"
    match = re.search(r'(?i)(?:nombre|name|atleta|athlete)[:\.\s]+([a-zA-Z\s\.]+)', text)
    if match:
        return match.group(1).strip()
    return None
