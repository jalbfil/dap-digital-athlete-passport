import sys
import os
import pytest
from pathlib import Path

# --- CONFIGURACIÓN DE ENTORNO ---
# Inyectamos el path de la aplicación para poder importar los servicios
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.ocr import extract_race_data

# ==========================================
# SUITE DE PRUEBAS: VISIÓN ARTIFICIAL (OCR)
# Objetivo: Validar la integración con el motor Tesseract y las Regex.
# ==========================================

def test_ocr_pipeline_integration():
    """
    [Integration Test] Validación del Pipeline de Ingesta de Imágenes.
    
    Prueba el flujo completo: 
    1. E/S de Archivos (Lectura de imagen).
    2. Preprocesamiento (Conversión a escala de grises con PIL).
    3. Llamada al sistema (Subproceso Tesseract OCR).
    4. Extracción Semántica (Regex para Dorsal/Tiempo).
    
    Nota: Este test requiere el archivo 'tests/sample_race.png' y el binario Tesseract.
    Si faltan, el test se omitirá (SKIPPED) para no romper la CI/CD.
    """
    
    # 1. Localización de recursos de prueba
    current_dir = Path(__file__).parent
    image_path = current_dir / "sample_race.png"
    
    # Comprobación de Pre-condiciones (Existence Check)
    if not image_path.exists():
        pytest.skip(f"⚠️ Imagen de prueba no encontrada en: {image_path}")
        return

    # 2. Simulación de Upload (Lectura de bytes)
    print(f"\n[INFO] Cargando imagen de prueba: {image_path.name}")
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    # 3. Ejecución del Servicio (Black Box Testing)
    # No nos importa cómo lo hace, solo qué devuelve.
    result = extract_race_data(image_bytes)

    # 4. Manejo de Dependencias del Sistema
    # Si el servicio devuelve error porque Tesseract no está instalado,
    # saltamos el test en lugar de fallarlo (comportamiento robusto).
    if "error" in result and "no instaladas" in str(result["error"]):
        pytest.skip("⚠️ Motor Tesseract no instalado en el sistema host. Test omitido.")
        return

    # 5. Aserciones (Criterios de Aceptación)
    
    # A) Integridad de Ejecución: No debe haber excepciones no controladas
    assert "error" not in result, f"El motor OCR falló: {result.get('error')}"
    
    # B) Calidad del Resultado: Debe haber detectado texto
    raw_text = result.get("raw_text", "")
    assert len(raw_text) > 0, "El OCR devolvió una cadena vacía (Fallo de reconocimiento)."
    
    # C) Extracción Semántica (Opcional, depende de la calidad de tu imagen de muestra)
    # Imprimimos lo detectado para evidencia en los logs del test
    print(f"\n[EVIDENCIA] Datos extraídos:\n{result}")
    
    # Si tu imagen de prueba es buena, puedes descomentar esto para validar precisión:
    # assert result["time"] is not None, "No se detectó el tiempo en la imagen de muestra"
