"""RFC 3161 trusted timestamping for session certificates.

A Sovereign Vision session ends with a Merkle root that is the
fingerprint of every frame certificate in the run. Signing that root
with a public RFC 3161 Time Stamping Authority (TSA) produces a
timestamp token (TSR) which proves the root existed at a specific
moment in time. The TSA's signature is independently verifiable later
without contacting Sovereign Vision.

Default TSA:
    http://timestamp.digicert.com    (free, public, no auth)

Configurable via environment variable:
    SOVEREIGN_TSA_URL                # override the TSA endpoint

Usage from Python:

    from sovereign.notary import notarise_session

    tsr_bytes = notarise_session(session_cert_dict, out_dir="certificates")
    # writes certificates/session_<id>.tsr alongside the .json

The token can be verified later with:
    openssl ts -verify -in session_xyz.tsr -queryfile session_xyz.tsq \\
        -CAfile tsa-root.pem
"""
from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TSA_URL: str = "http://timestamp.digicert.com"
FALLBACK_TSA_URL: str = "http://freetsa.org/tsr"


def notarise_session(
    session_cert: dict[str, Any],
    out_dir: str | Path,
    tsa_url: str | None = None,
) -> bytes | None:
    """Submit the session's Merkle root to a TSA and save the TSR token.

    Returns the TSR bytes on success, None if the TSA is unreachable
    or `openssl ts` is not installed. Notarisation is intentionally
    best-effort: if it fails, the session certificate is still
    cryptographically intact, just not externally timestamped.
    """
    if shutil.which("openssl") is None:
        logger.warning("openssl not installed; skipping notarisation")
        return None

    chain = session_cert.get("audit_chain") or {}
    merkle_root_hex = chain.get("merkle_root")
    if not merkle_root_hex:
        logger.warning("session cert has no merkle_root; skipping notarisation")
        return None

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    session_id = session_cert.get("session_id", "session")
    base = out / f"session_{session_id[:8]}_notary"

    # 1. write the root to a binary file for the TS query
    root_bin = base.with_suffix(".root.bin")
    root_bin.write_bytes(bytes.fromhex(merkle_root_hex))

    # 2. construct the TimeStamp request (TSQ) with openssl
    tsq = base.with_suffix(".tsq")
    try:
        subprocess.run(
            ["openssl", "ts", "-query", "-data", str(root_bin),
             "-no_nonce", "-sha256", "-cert", "-out", str(tsq)],
            check=True, capture_output=True, timeout=10,
        )
    except subprocess.CalledProcessError as exc:
        logger.warning("openssl ts -query failed: %s", exc.stderr.decode(errors="ignore"))
        return None

    # 3. POST the TSQ to the TSA, save the TSR
    url = tsa_url or os.environ.get("SOVEREIGN_TSA_URL", DEFAULT_TSA_URL)
    tsr_bytes = _post_tsr(url, tsq.read_bytes())
    if tsr_bytes is None and url != FALLBACK_TSA_URL:
        logger.info("primary TSA failed, trying fallback %s", FALLBACK_TSA_URL)
        tsr_bytes = _post_tsr(FALLBACK_TSA_URL, tsq.read_bytes())

    if tsr_bytes is None:
        return None

    tsr = base.with_suffix(".tsr")
    tsr.write_bytes(tsr_bytes)

    # 4. produce a human-readable text dump alongside the TSR
    try:
        dump = subprocess.run(
            ["openssl", "ts", "-reply", "-in", str(tsr), "-text"],
            check=True, capture_output=True, timeout=10,
        )
        base.with_suffix(".tsr.txt").write_bytes(dump.stdout)
    except subprocess.CalledProcessError as exc:
        logger.warning("openssl ts -reply text dump failed: %s",
                       exc.stderr.decode(errors="ignore"))

    logger.info(
        "RFC 3161 timestamp written: %s (root %s..., %s)",
        tsr, merkle_root_hex[:16], url,
    )
    return tsr_bytes


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _post_tsr(url: str, tsq: bytes) -> bytes | None:
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        url, data=tsq, method="POST",
        headers={"Content-Type": "application/timestamp-query"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read()
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        logger.warning("TSA POST to %s failed: %s", url, exc)
        return None


def merkle_fingerprint(session_cert: dict[str, Any]) -> str:
    """Re-derive the Merkle root SHA-256 fingerprint (sanity helper)."""
    chain = session_cert.get("audit_chain") or {}
    root = chain.get("merkle_root", "")
    return hashlib.sha256(bytes.fromhex(root) if root else b"").hexdigest()
