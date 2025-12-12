import sys
import os
from pathlib import Path

# Añadir raíz al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.ocr import extract_race_data

def test_ocr_extraction():
    """
    Prueba de integración real con el motor Tesseract.
    Requiere que exista 'tests/sample_race.png'.
    """
    # 1. Localizar imagen de prueba
    current_dir = Path(__file__).parent
    image_path = current_dir / "sample_race.png"
    
    if not image_path.exists():
        # Si no hay imagen, saltamos el test con un aviso (para no romper CI/CD)
        print(f"\n[WARN] No se encontró {image_path}. Test de OCR saltado.")
        return

    # 2. Leer bytes de la imagen (simulando subida de fichero)
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    # 3. Ejecutar servicio OCR
    print("\n[INFO] Ejecutando Tesseract sobre imagen de prueba...")
    data = extract_race_data(image_bytes)

    # 4. Aserciones
    # Verificamos que NO haya error
    assert "error" not in data or not data["error"], f"El OCR falló: {data.get('error')}"
    
    # Verificamos que haya detectado ALGO de texto
    assert data["raw_text"], "El OCR no devolvió texto crudo"
    
    print(f"[INFO] Datos detectados: {data}")

    # Opcional: Si usas la imagen del dorsal 0059, descomenta esto:
    # assert data["bib"] == "0059" or "59" in data["raw_text"]
    # assert data["time"] == "01:01:50"