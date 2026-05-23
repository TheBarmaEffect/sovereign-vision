// Sovereign Vision - Chrome extension popup
//
// Verifies a session_*.json: re-derives the integrity hash and the
// chain head using SubtleCrypto SHA-256. Nothing leaves the browser.

const drop = document.getElementById("drop");
const file = document.getElementById("file");
const result = document.getElementById("result");

["dragenter","dragover"].forEach(e => drop.addEventListener(e, ev => {
  ev.preventDefault();
  drop.classList.add("hover");
}));
["dragleave","drop"].forEach(e => drop.addEventListener(e, ev => {
  ev.preventDefault();
  drop.classList.remove("hover");
}));
drop.addEventListener("drop", async ev => {
  const f = ev.dataTransfer.files[0];
  if (f) await handle(f);
});
file.addEventListener("change", async () => {
  if (file.files[0]) await handle(file.files[0]);
});

async function handle(f) {
  const text = await f.text();
  let data;
  try { data = JSON.parse(text); }
  catch { alert("Not valid JSON"); return; }

  result.style.display = "block";

  const status = data.overall_status || "-";
  const sEl = document.getElementById("status");
  sEl.textContent = status;
  sEl.style.color =
    status === "CLEAR" ? "var(--green)" :
    status === "ESCALATED" ? "var(--amber)" :
    status === "TAMPERED" ? "var(--red)" :
    "var(--text)";

  document.getElementById("session").textContent =
    (data.session_id || "-").slice(0, 8);
  document.getElementById("frames").textContent = data.total_frames ?? "-";
  document.getElementById("duration").textContent =
    (data.duration_seconds ?? 0).toFixed(2) + "s";
  document.getElementById("chainlen").textContent =
    data.audit_chain ? data.audit_chain.chain_length : "-";

  const scoreObj = data.compliance_score;
  if (scoreObj) {
    document.getElementById("score").textContent =
      `${scoreObj.score} (${scoreObj.grade})`;
  } else {
    document.getElementById("score").textContent = "-";
  }

  const ok = await verifyIntegrity(data);
  document.getElementById("verify").innerHTML = ok
    ? '<span class="badge ok">OK</span>'
    : '<span class="badge fail">MISMATCH</span>';
}

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
