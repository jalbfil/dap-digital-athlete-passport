# 1. IMAGEN BASE
# Usamos Python 3.11 'slim' (basada en Debian) en lugar de 'alpine'.
# Justificación: Alpine da problemas con librerías C++ como Tesseract y numpy.
# Debian Slim ofrece el equilibrio perfecto entre tamaño y compatibilidad.
FROM python:3.11-slim

# 2. CONFIGURACIÓN DE ENTORNO
# - PYTHONDONTWRITEBYTECODE: Evita crear archivos .pyc (inútiles en contenedores).
# - PYTHONUNBUFFERED: Fuerza a los logs a salir inmediatamente a la consola (vital para debug).
# - PYTHONPATH: Asegura que Python encuentre los módulos en la raíz.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# 3. DIRECTORIO DE TRABAJO
WORKDIR /app

# 4. INSTALACIÓN DE DEPENDENCIAS DE SISTEMA (Capa OS)
# Instalamos:
# - tesseract-ocr: El motor de IA.
# - tesseract-ocr-spa: Datos de entrenamiento para español (mejora precisión).
# - curl: Necesario para el HEALTHCHECK del docker-compose.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-spa \
    libtesseract-dev \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 5. INSTALACIÓN DE DEPENDENCIAS PYTHON (Capa App)
# Copiamos primero SOLO el requirements.txt.
# Truco Docker: Esto permite cachear esta capa. Si cambias el código pero no
# las dependencias, Docker no volverá a instalar todo (build más rápido).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. COPIADO DEL CÓDIGO FUENTE
COPY . .

# 7. PREPARACIÓN DE DIRECTORIOS
# Creamos las carpetas de volúmenes para asegurar que existan con los permisos correctos
RUN mkdir -p dap_data app/keys

# 8. EXPOSICIÓN DE PUERTO
EXPOSE 8000

# 9. COMANDO DE ARRANQUE
# Usamos la sintaxis JSON ["..."] para que el proceso sea PID 1 y reciba señales de parada correctamente.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
