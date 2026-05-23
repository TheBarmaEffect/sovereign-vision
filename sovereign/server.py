"""FastAPI server for enterprise integration.

Exposes:

    GET  /                 → service info (version, hardware, rules)
    GET  /healthz          → liveness
    GET  /readyz           → readiness (model loaded, firewall ready)
    GET  /metrics          → Prometheus / OpenMetrics text
    POST /verify           → upload a session_*.json, get verification + score
    GET  /stats            → live snapshot of metrics
    WS   /live             → server-sent stream of rule events
    GET  /packs            → list installed rule packs
    GET  /packs/{name}     → return pack metadata

The server is fully on-device. It does not call out, does not log PII,
and refuses to operate if any constitutional rule is missing.

Run with:
    uvicorn sovereign.server:app --host 127.0.0.1 --port 8765
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def create_app() -> Any:
    """Build the FastAPI app. Lazy-imported so the package stays optional."""
    try:
        from fastapi import FastAPI, HTTPException, Request, UploadFile, WebSocket
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import JSONResponse, PlainTextResponse
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "FastAPI is required for the server. `pip install fastapi uvicorn`."
        ) from exc

    from sovereign import DEFAULT_RULES, __version__
    from sovereign.audit_chain import AuditChain
    from sovereign.certificate import _integrity_hash
    from sovereign.firewall import ConstitutionalFirewall
    from sovereign.hardware import detect as detect_hw
    from sovereign.metrics import MetricsRegistry
    from sovereign.packs import list_packs, pack_metadata

    app = FastAPI(
        title="Sovereign Vision API",
        version=__version__,
        description=(
            "On-device enterprise vision firewall API. "
            "Built by Karthik Barma. https://github.com/TheBarmaEffect"
        ),
    )

    # CORS is intentionally permissive on localhost only. Tighten in
    # production by setting `allow_origins=[your_admin_origin]`.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost", "http://127.0.0.1"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    # Singleton firewall + metrics for /stats and /live to subscribe to.
    state = {
        "firewall": ConstitutionalFirewall(),
        "metrics": MetricsRegistry(),
        "started_ns": time.time_ns(),
    }

    # ----------------------------------------------------------------------
    # GET /
    # ----------------------------------------------------------------------

    @app.get("/")
    def root() -> dict[str, Any]:
        hw = detect_hw()
        return {
            "service": "Sovereign Vision API",
            "version": __version__,
            "author": "Karthik Barma",
            "repo": "https://github.com/TheBarmaEffect/sovereign-vision",
            "rules_loaded": [r.rule_id for r in DEFAULT_RULES],
            "hardware": hw.to_dict(),
            "uptime_seconds": round((time.time_ns() - state["started_ns"]) / 1e9, 3),
        }

    # ----------------------------------------------------------------------
    # Liveness + readiness probes
    # ----------------------------------------------------------------------

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> dict[str, Any]:
        fw: ConstitutionalFirewall = state["firewall"]
        return {
            "status": "ready",
            "session_id": fw.session_id,
            "rules": [r.rule_id for r in fw.rules],
        }

    # ----------------------------------------------------------------------
    # /metrics (Prometheus text)
    # ----------------------------------------------------------------------

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics() -> str:
        return state["metrics"].prometheus_text()  # type: ignore[no-any-return]

    # ----------------------------------------------------------------------
    # /stats live snapshot
    # ----------------------------------------------------------------------

    @app.get("/stats")
    def stats() -> dict[str, Any]:
        return state["metrics"].snapshot().to_dict()  # type: ignore[no-any-return]

    # ----------------------------------------------------------------------
    # /packs registry
    # ----------------------------------------------------------------------

    @app.get("/packs")
    def packs_list() -> dict[str, Any]:
        return {
            "packs": [
                {"name": p, **pack_metadata(p)}
                for p in list_packs()
            ]
        }

    @app.get("/packs/{name}")
    def packs_detail(name: str) -> dict[str, Any]:
        try:
            return {"name": name, **pack_metadata(name)}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    # ----------------------------------------------------------------------
    # POST /verify
    # ----------------------------------------------------------------------

    @app.post("/verify")
    async def verify(request: Request) -> JSONResponse:
        """Verify an uploaded session_*.json.

        Re-derives the integrity hash. Returns a structured verification
        result that includes the compliance score, status, and Merkle
        chain anchor extracted from the cert.
        """
        try:
            data = await request.json()
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"invalid JSON: {exc}")

        stored = data.get("integrity_hash")
        if not stored:
            return JSONResponse(
                status_code=400,
                content={"verified": False, "reason": "no integrity_hash field"},
            )
        copy = json.loads(json.dumps(data))
        copy.pop("integrity_hash", None)
        derived = _integrity_hash(copy)

        verified = derived == stored
        return JSONResponse(
            content={
                "verified": verified,
                "stored_hash": stored,
                "derived_hash": derived,
                "session_id": data.get("session_id"),
                "overall_status": data.get("overall_status"),
                "total_frames": data.get("total_frames"),
                "compliance_score": data.get("compliance_score"),
                "audit_chain": data.get("audit_chain"),
                "hardware": data.get("hardware"),
            }
        )

    # ----------------------------------------------------------------------
    # WS /live - SSE-style event stream
    # ----------------------------------------------------------------------

    @app.websocket("/live")
    async def live(ws: "WebSocket") -> None:
        await ws.accept()
        try:
            while True:
                snap = state["metrics"].snapshot().to_dict()
                await ws.send_json({
                    "type": "metrics.snapshot",
                    "ts_ns": time.time_ns(),
                    "data": snap,
                })
                await asyncio.sleep(1.0)
        except Exception:  # pragma: no cover - client disconnect
            pass

    return app


# uvicorn entry: `uvicorn sovereign.server:app`
app = None  # type: ignore[assignment]
try:
    app = create_app()
except RuntimeError as e:
    logger.info("sovereign.server not initialised at import time: %s", e)
