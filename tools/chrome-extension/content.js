// Sovereign Vision content script.
//
// When the page is a raw JSON view of a Sovereign Vision session
// certificate, inject a verification banner at the top of the page
// so anyone reading the cert sees the verified status without leaving
// the browser tab.

(async function () {
  // We only act on JSON responses that look like a Sovereign Vision cert.
  const pre = document.querySelector("body > pre");
  if (!pre) return;
  let data;
  try {
    data = JSON.parse(pre.textContent || "");
  } catch {
    return;
  }
  if (!data || data.cert_type !== "session" || !data.integrity_hash) {
    return;
  }

  const ok = await verifyIntegrity(data);

  const banner = document.createElement("div");
  banner.style.cssText = `
    position: fixed; top: 0; left: 0; right: 0;
    z-index: 999999; padding: 12px 16px;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display",
                 system-ui, sans-serif;
    background: ${ok ? "rgba(48,209,88,0.12)" : "rgba(255,69,58,0.12)"};
    color: ${ok ? "#30D158" : "#FF453A"};
    border-bottom: 1px solid ${ok ? "#30D158" : "#FF453A"};
    font-size: 13px; font-weight: 600;
  `;
  banner.textContent = ok
    ? `Sovereign Vision certificate verified  ·  session ${
        (data.session_id || "").slice(0, 8)
      }  ·  ${data.total_frames} frames  ·  Merkle root ${
        ((data.audit_chain && data.audit_chain.merkle_root) || "").slice(0, 12)
      }...`
    : `Sovereign Vision certificate FAILED verification (integrity hash mismatch)`;
  document.body.prepend(banner);
})();

async function verifyIntegrity(data) {
  const stored = data.integrity_hash;
  if (!stored) return false;
  const copy = JSON.parse(JSON.stringify(data));
  delete copy.integrity_hash;
  const canonical = JSON.stringify(sortKeys(copy));
  const bytes = new TextEncoder().encode(canonical);
  const buf = await crypto.subtle.digest("SHA-256", bytes);
  const hex = Array.from(new Uint8Array(buf))
    .map(b => b.toString(16).padStart(2, "0")).join("");
  return hex === stored;
}

function sortKeys(v) {
  if (Array.isArray(v)) return v.map(sortKeys);
  if (v && typeof v === "object") {
    return Object.keys(v).sort().reduce((acc, k) => {
      acc[k] = sortKeys(v[k]);
      return acc;
    }, {});
  }
  return v;
}
