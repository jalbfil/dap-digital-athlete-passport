
const ROUTES = {
  ISSUE:      "/issuer/issue",
  HOLDER_JSON: (jti) => `/holder/${encodeURIComponent(jti)}.json`,
  HOLDER_QR:   (jti) => `/holder/${encodeURIComponent(jti)}/qr.png`,
  NONCE:      "/verifier/challenge",
  VERIFY:     "/verifier/verify",
};

const btnIssue = document.getElementById("btn-issue");
if (btnIssue) {
  btnIssue.addEventListener("click", async () => {
    const statusEl = document.getElementById("issuer-status");
    const jtiEl    = document.getElementById("issuer-jti");
    const tokEl    = document.getElementById("issuer-token-snippet");
    const aQR      = document.getElementById("issuer-open-qr");
    const aJSON    = document.getElementById("issuer-open-holder-json");

    jtiEl.textContent = "—";
    tokEl.textContent = "—";
    statusEl.textContent = "…";

    const vcText = document.getElementById("vc-input").value.trim();
    const subjectDid = document.getElementById("subject-did").value.trim() || "did:example:holder:2305";
    const ttl = document.getElementById("ttl").value.trim() || "3600";

    try {
      const resp = await fetch(`${ROUTES.ISSUE}?ttl=${encodeURIComponent(ttl)}&subject_did=${encodeURIComponent(subjectDid)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: vcText || "{}",
      });
      if (!resp.ok) throw new Error(await resp.text());
      const data = await resp.json();

      statusEl.textContent = data.status || "ok";
      jtiEl.textContent = data.jti || "—";
      tokEl.textContent = (data.token || "").slice(0, 180) + (data.token ? "..." : "");

      if (data.jti) {
        aQR.href   = ROUTES.HOLDER_QR(data.jti);
        aQR.classList.remove("disabled","opacity-50");
        aJSON.href = ROUTES.HOLDER_JSON(data.jti);
        aJSON.classList.remove("disabled","opacity-50");
      }
    } catch (e) {
      statusEl.textContent = `Error`;
      tokEl.textContent = String(e);
    }
  });
}

const btnHolderLoad = document.getElementById("holder-load");
if (btnHolderLoad) {
  btnHolderLoad.addEventListener("click", async () => {
    const jti = document.getElementById("holder-jti").value.trim();
    const tok = document.getElementById("holder-token-snippet");
    const sum = document.getElementById("holder-summary");
    const aQR = document.getElementById("holder-open-qr");
    const aJSON = document.getElementById("holder-open-json");
    const qrImg = document.getElementById("holder-qr-img");

    tok.textContent = "—"; sum.textContent = "—";

    if (!jti) return;

    try {
      const resp = await fetch(ROUTES.HOLDER_JSON(jti));
      if (!resp.ok) throw new Error(await resp.text());
      const data = await resp.json();

      tok.textContent = (data.token || "").slice(0, 180) + (data.token ? "..." : "—");
      const s = data.summary || {};
      sum.textContent = `event: ${s.event || "-"}\nbib: ${s.bib || "-"}\nname: ${s.name || "-"}\ntime: ${s.time || "-"}`;

      aQR.href = ROUTES.HOLDER_QR(jti);
      aJSON.href = ROUTES.HOLDER_JSON(jti);
      aQR.classList.remove("disabled","opacity-50");
      aJSON.classList.remove("disabled","opacity-50");
      if (qrImg) qrImg.src = aQR.href;
    } catch (e) {
      alert("No se pudo cargar el JTI: " + e);
    }
  });
}

const btnNonce = document.getElementById("btn-nonce");
if (btnNonce) {
  btnNonce.addEventListener("click", async () => {
    const ttl = document.getElementById("nonce-ttl").value.trim() || "60";
    const out = document.getElementById("nonce-out");
    const exp = document.getElementById("nonce-exp");
    if (out) out.textContent = "…";
    if (exp) exp.textContent = "…";
    try {
      const resp = await fetch(`${ROUTES.NONCE}?ttl=${encodeURIComponent(ttl)}`);
      if (!resp.ok) throw new Error(await resp.text());
      const data = await resp.json();
      document.getElementById("verify-nonce").value = data.nonce || "";
      if (out) out.textContent = data.nonce || "—";
      if (exp) exp.textContent = data.expiresAt || "—";
    } catch (e) {
      if (out) out.textContent = String(e);
    }
  });
}

const btnVerify = document.getElementById("btn-verify");
if (btnVerify) {
  btnVerify.addEventListener("click", async () => {
    const token = document.getElementById("verify-token").value.trim();
    const nonce = document.getElementById("verify-nonce").value.trim();

    const r = document.getElementById("verify-result");
    const s = document.getElementById("verify-score");
    const f = document.getElementById("verify-flags");
    const d = document.getElementById("verify-details");

    if (r) r.textContent = "…"; if (s) s.textContent = "…"; if (f) f.textContent = "…"; if (d) d.textContent = "";

    try {
      const resp = await fetch(ROUTES.VERIFY, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, nonce }),
      });
      if (!resp.ok) throw new Error(await resp.text());
      const data = await resp.json();

      if (r) r.textContent = data.result || "—";
      if (s) s.textContent = typeof data.score === "number" ? String(data.score) : "—";
      if (f) f.textContent = (data.flags && data.flags.length) ? data.flags.join(", ") : "—";
      if (d) d.textContent = JSON.stringify(data.details || {}, null, 2);
    } catch (e) {
      if (r) r.textContent = "error";
      if (d) d.textContent = String(e);
    }
  });
}
