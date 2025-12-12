# 1. Usamos una imagen base de Python oficial (ligera)
FROM python:3.11-slim

# 2. Evitamos que Python genere archivos .pyc y bufferee la salida
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Directorio de trabajo dentro del contenedor
WORKDIR /app

# 4. INSTALACIÓN DE SISTEMA (Lo crucial para el OCR)
# Actualizamos listas e instalamos Tesseract y dependencias de imagen
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-spa \
    libtesseract-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 5. Copiamos los requisitos e instalamos dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copiamos todo el código del proyecto
COPY . .

# 7. Exponemos el puerto 8000
EXPOSE 8000

# 8. Comando de arranque
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]