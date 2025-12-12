/* * rol.js - Lógica del Frontend para el Digital Athlete Passport (DAP)
 * Gestiona la interacción con la API para los roles Issuer, Holder y Verifier.
 */

// --- CONFIGURACIÓN DE RUTAS ---
const ROUTES = {
  ISSUE:       "/issuer/issue",
  HOLDER_JSON: (jti) => `/holder/${encodeURIComponent(jti)}.json`,
  HOLDER_QR:   (jti) => `/holder/${encodeURIComponent(jti)}/qr.png`,
  NONCE:       "/verifier/challenge",
  VERIFY:      "/verifier/verify",
};

// --- ROL: ISSUER (Emisor) ---
const btnIssue = document.getElementById("btn-issue");
if (btnIssue) {
  btnIssue.addEventListener("click", async () => {
    // Referencias a elementos del DOM
    const statusEl = document.getElementById("issuer-status");
    const jtiEl    = document.getElementById("issuer-jti");
    const tokEl    = document.getElementById("issuer-token-snippet");
    const aQR      = document.getElementById("issuer-open-qr");
    const aJSON    = document.getElementById("issuer-open-holder-json");

    // Limpiar estado previo
    jtiEl.textContent = "—";
    tokEl.textContent = "—";
    statusEl.textContent = "Procesando...";
    
    // Obtener valores del formulario
    const vcText = document.getElementById("vc-input").value.trim();
    const subjectDid = document.getElementById("subject-did").value.trim() || "did:example:holder:2305";
    const ttl = document.getElementById("ttl").value.trim() || "3600";

    // Validar JSON de entrada (básico)
    let payload = {};
    try {
        if(vcText) payload = JSON.parse(vcText);
    } catch(e) {
        statusEl.textContent = "Error: JSON inválido";
        alert("El JSON de la credencial no es válido. Revisa la sintaxis.");
        return;
    }

    try {
      // Llamada a la API
      const resp = await fetch(`${ROUTES.ISSUE}?ttl=${encodeURIComponent(ttl)}&subject_did=${encodeURIComponent(subjectDid)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
          const errData = await resp.json();
          throw new Error(errData.detail || "Error en el servidor");
      }
      
      const data = await resp.json();

      // Actualizar UI con éxito
      statusEl.textContent = data.status || "ok";
      statusEl.style.color = "#4ade80"; // Verde éxito
      jtiEl.textContent = data.jti || "—";
      // Mostrar snippet del token (primeros 180 caracteres)
      tokEl.textContent = (data.token || "").slice(0, 180) + (data.token && data.token.length > 180 ? "..." : "");

      // Activar enlaces si hay JTI
      if (data.jti) {
        aQR.href   = ROUTES.HOLDER_QR(data.jti);
        aQR.classList.remove("disabled", "opacity-50");
        aQR.target = "_blank"; // Abrir en nueva pestaña
        
        aJSON.href = ROUTES.HOLDER_JSON(data.jti);
        aJSON.classList.remove("disabled", "opacity-50");
        aJSON.target = "_blank";
      }
    } catch (e) {
      statusEl.textContent = "Error";
      statusEl.style.color = "#f87171"; // Rojo error
      tokEl.textContent = String(e.message);
      console.error("Error en emisión:", e);
    }
  });
}

// --- ROL: HOLDER (Titular) ---
const btnHolderLoad = document.getElementById("holder-load");
if (btnHolderLoad) {
  btnHolderLoad.addEventListener("click", async () => {
    const jtiInput = document.getElementById("holder-jti");
    const jti = jtiInput ? jtiInput.value.trim() : "";
    
    const tok = document.getElementById("holder-token-snippet");
    const sum = document.getElementById("holder-summary");
    const aQR = document.getElementById("holder-open-qr");
    const aJSON = document.getElementById("holder-open-json");
    const qrImg = document.getElementById("holder-qr-img");

    // Reset UI
    tok.textContent = "—"; 
    sum.textContent = "—";
    if (qrImg) qrImg.src = ""; // Limpiar imagen anterior

    if (!jti) {
        alert("Por favor, introduce un JTI válido.");
        return;
    }

    try {
      const resp = await fetch(ROUTES.HOLDER_JSON(jti));
      if (!resp.ok) throw new Error("Credencial no encontrada o error de red");
      
      const data = await resp.json();

      // Mostrar datos
      tok.textContent = (data.token || "").slice(0, 180) + (data.token ? "..." : "—");
      
      // Intentar decodificar payload para el resumen (si el backend no lo envía ya parseado)
      // Nota: En un entorno real, el backend podría enviar un campo 'summary' ya preparado.
      // Aquí asumimos que recibimos el objeto completo.
      const s = data.summary || {}; 
      // Si summary viene vacío, intentamos sacarlo del token (esto es solo visualización)
      
      sum.textContent = `Evento: ${s.event || "-"}\nDorsal: ${s.bib || "-"}\nNombre: ${s.name || "-"}\nTiempo: ${s.time || "-"}`;

      // Configurar enlaces
      const qrUrl = ROUTES.HOLDER_QR(jti);
      aQR.href = qrUrl;
      aJSON.href = ROUTES.HOLDER_JSON(jti);
      
      aQR.classList.remove("disabled", "opacity-50");
      aJSON.classList.remove("disabled", "opacity-50");
      
      // Cargar imagen QR directamente en la página si existe el elemento img
      if (qrImg) {
          qrImg.src = qrUrl;
          qrImg.style.display = "block";
      }
      
    } catch (e) {
      alert("No se pudo cargar el JTI: " + e.message);
      console.error(e);
    }
  });
}

// --- ROL: VERIFIER (Verificador) - Paso 1: Challenge ---
const btnNonce = document.getElementById("btn-nonce");
if (btnNonce) {
  btnNonce.addEventListener("click", async () => {
    const ttl = document.getElementById("nonce-ttl").value.trim() || "60";
    const out = document.getElementById("nonce-out");
    const exp = document.getElementById("nonce-exp");
    
    if (out) out.textContent = "Generando...";
    if (exp) exp.textContent = "Calculando...";
    
    try {
      const resp = await fetch(`${ROUTES.NONCE}?ttl=${encodeURIComponent(ttl)}`);
      if (!resp.ok) throw new Error(await resp.text());
      
      const data = await resp.json();
      
      // Auto-rellenar el campo nonce del formulario de verificación para facilitar la demo
      const verifyNonceInput = document.getElementById("verify-nonce");
      if (verifyNonceInput) verifyNonceInput.value = data.nonce || "";
      
      if (out) out.textContent = data.nonce || "—";
      if (exp) exp.textContent = data.expiresAt || "—";
      
    } catch (e) {
      if (out) out.textContent = "Error: " + String(e);
    }
  });
}

// --- ROL: VERIFIER (Verificador) - Paso 2: Verify ---
const btnVerify = document.getElementById("btn-verify");
if (btnVerify) {
  btnVerify.addEventListener("click", async () => {
    const token = document.getElementById("verify-token").value.trim();
    const nonce = document.getElementById("verify-nonce").value.trim();

    const r = document.getElementById("verify-result");
    const s = document.getElementById("verify-score"); // Si tu API devuelve score
    const f = document.getElementById("verify-flags"); // Si devuelve flags de error
    const d = document.getElementById("verify-details");

    // UI Loading
    if (r) { r.textContent = "Verificando..."; r.className = ""; } // Reset clases de color
    if (d) d.textContent = "";

    try {
      const resp = await fetch(ROUTES.VERIFY, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, nonce }),
      });
      
      if (!resp.ok) {
          const errText = await resp.text();
          throw new Error(errText);
      }
      
      const data = await resp.json();

      // Mostrar Resultado
      if (r) {
          r.textContent = data.result ? data.result.toUpperCase() : "UNKNOWN";
          // Colorear según resultado
          if (data.result === "valid") {
              r.style.color = "#4ade80"; // Verde
          } else {
              r.style.color = "#f87171"; // Rojo
          }
      }
      
      // Mostrar Detalles Técnicos (Claims decodificados o razón de fallo)
      if (d) {
          if (data.result === "valid") {
              d.textContent = JSON.stringify(data.claims || {}, null, 2);
          } else {
              d.textContent = `Razón: ${data.reason || "Desconocida"}`;
          }
      }
      
    } catch (e) {
      if (r) { r.textContent = "ERROR DE SISTEMA"; r.style.color = "orange"; }
      if (d) d.textContent = String(e.message);
    }
  });
}
