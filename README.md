# DAP - Digital Athlete Passport

> **Trabajo de Fin de Grado (TFG) - Ingeniería en Ingeniería de Tecnologías y Servicios de Telecomunicación** > Infraestructura de Identidad Soberana (SSI) para la emisión y verificación de resultados deportivos mediante Credenciales Verificables (VC) e Identificadores Descentralizados (DID).

![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-Async-009688?logo=fastapi)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)
![Coverage](https://img.shields.io/badge/Tests-Passing-success)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 📖 Descripción

**DAP** soluciona el problema del fraude en las certificaciones deportivas (Hyrox, CrossFit, etc) eliminando la dependencia de PDFs falsificables o plataformas centralizadas propietarias.

El sistema implementa una arquitectura **Issuer-Holder-Verifier** alineada con los estándares de la **W3C** y diseñada para ser compatible con el marco europeo **EBSI/ESSIF**.

### Características Principales
* **🔐 Seguridad Criptográfica:** Firmas digitales **RS256** y protección **Anti-Replay** (Challenge/Response).
* **🇪🇺 EBSI-Ready:** Arquitectura agnóstica al método DID. Soporta 'did:web' y está preparada para la resolución on-chain ('did:ebsi').
* **⚡ Stack Moderno:** Backend 100% asíncrono con **FastAPI** y **SQLAlchemy**.
* **🐳 Despliegue en un Click:** Contenerización completa con **Docker**.
* **🧪 Código:** Tests unitarios y de integración ('pytest').
* **📸 Ingesta Inteligente:** (Experimental) Módulo OCR con Tesseract para digitalizar clasificaciones.

---

## 🚀 Guía de Inicio Rápido

Puedes ejecutar el proyecto de dos formas. **Recomendamos la Opción A (Docker)** para evitar configurar entornos.

### Opción A: Despliegue con Docker (Recomendado) 🐳
Requisito: Tener Docker Desktop instalado (https://www.docker.com/)

1.  **Clona el repositorio:**
    ```bash
    git clone [https://github.com/TU_USUARIO/dap-digital-athlete-passport.git](https://github.com/TU_USUARIO/dap-digital-athlete-passport.git)
    cd dap-digital-athlete-passport
    ```
2.  **Arranca el sistema:**
    ```bash
    docker-compose up --build
    ```
3.  **¡Listo!** Abre tu navegador en:
    * **App:** [http://localhost:8000](http://localhost:8000)
    * **Documentación API:** [http://localhost:8000/docs](http://localhost:8000/docs)

> Docker se encarga de instalar Python, Tesseract OCR, dependencias y configurar la base de datos automáticamente.

---

### Opción B: Ejecución Local (Desarrollo)
Si prefieres ejecutarlo nativamente en tu máquina.

1.  **Prepara el entorno:**
    ```bash
    # Crear entorno virtual
    python -m venv .venv
    # Activar (Windows PowerShell)
    .\.venv\Scripts\Activate
    # Instalar dependencias
    pip install -r requirements.txt
    ```

2.  **Configura las variables:**
    ```bash
    # Copia la plantilla de entorno
    copy .env.example .env
    ```

3.  **Genera las claves criptográficas:**
    Hemos incluido un script para generar el par de claves RSA (2048 bits) automáticamente.
    ```bash
    python gen_keys.py
    # Esto creará la carpeta app/keys/ con private.pem y public.pem
    ```

4.  **Ejecuta el servidor:**
    ```bash
    uvicorn app.main:app --reload
    ```

---

## 🕹️ Cómo usar la Aplicación (Flujo Típico)

El sistema expone una interfaz web visual para los tres roles.

### 1. 🏛️ ISSUER (El Organizador)
Ve a `/issuer`.
* Rellena los datos del atleta (o sube una foto de la tabla de tiempos para usar el OCR).
* Pulsa **"Firmar y Emitir"**.
* Obtendrás un **Token JWT** firmado y un **JTI** (ID único).

### 2. 📱 HOLDER (El Atleta)
Ve a '/holder'.
* Aquí el atleta custodia sus credenciales.
* Puede ver el **Código QR** de su credencial para presentarla ante un juez.

### 3. 🔍 VERIFIER (El Juez)
Ve a '/verifier'.
* **Paso 1 (Challenge):** Pide un "Reto" (Nonce) al servidor.
* **Paso 2 (Verify):** Introduce el Token del atleta junto con el Nonce.
* El sistema validará: Firma RSA + Caducidad + Estado de Revocación + Integridad del Nonce.

### 4. 🔧 ADMIN (Gestión)
Ve a '/admin/ui?token=supersecreto123'
* Panel de control para ver todas las credenciales emitidas.
* **Botón Rojo:** Permite **REVOCAR** una credencial en tiempo real.

---

## 🏗️ Arquitectura del Proyecto

```text
C:.
├── app/
│   ├── api/          # Controladores (Endpoints)
│   ├── core/         # Configuración y Criptografía
│   ├── db/           # Modelos y Sesión Async
│   ├── services/     # Lógica de Negocio (DID Resolver, OCR)
│   ├── templates/    # Frontend (Jinja2)
│   └── main.py       # Punto de entrada
├── tests/            # Tests automáticos (pytest)
├── dap_data/         # Persistencia Docker
├── Dockerfile        # Definición de la imagen
└── docker-compose.yml
