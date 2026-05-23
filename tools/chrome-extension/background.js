// Sovereign Vision background service worker.
//
// Watches downloads. When a session_*.json file is downloaded, fires a
// notification with the verification result so the user knows whether
// the certificate is intact without having to open the popup.

chrome.downloads.onChanged.addListener(async (delta) => {
  if (!delta.state || delta.state.current !== "complete") return;

  const items = await chrome.downloads.search({ id: delta.id });
  if (!items.length) return;
  const item = items[0];
  if (!/session.*\.json$/i.test(item.filename)) return;

  try {
    const url = "file://" + item.filename;
    const res = await fetch(url);
    const data = await res.json();
    const ok = await verifyIntegrity(data);

    chrome.notifications.create({
      type: "basic",
      iconUrl: "icon128.png",
      title: ok
        ? "Sovereign Vision certificate verified"
        : "Sovereign Vision certificate FAILED",
      message: ok
        ? `Session ${(data.session_id || "").slice(0, 8)} | ${data.total_frames} frames | score ${(data.compliance_score && data.compliance_score.score) || "?"}`
        : "Integrity hash mismatch. Reject this certificate.",
      priority: 2,
    });
  } catch (e) {
    // file:// is restricted in MV3 by default. The popup remains the
    // primary verification path; this listener is best-effort.
  }
});

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
