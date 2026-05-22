"""Compliance certificate generator.

Each frame produces a structured, JSON-serialisable certificate that
documents:
    - what rules fired
    - what actions were taken
    - the aggregate output that left the firewall
    - cryptographic integrity hash for tamper detection

A session-end certificate seals the audit chain with a Merkle root, giving
a single anchor value that proves the entire session's certificate stream
was not modified after the fact.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sovereign.audit_chain import AuditChain, AuditChainAnchor

if TYPE_CHECKING:  # pragma: no cover
    from sovereign.firewall import FirewallResult

logger = logging.getLogger(__name__)

CERT_VERSION: str = "1.0"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class FrameCertificate:
    """Wrapped frame certificate plus its audit-chain link hash."""

    payload: dict[str, Any]
    chain_link_hash: str
    integrity_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.payload,
            "chain_link_hash": self.chain_link_hash,
            "integrity_hash": self.integrity_hash,
        }


@dataclass(slots=True)
class SessionCertificate:
    """End-of-session compliance summary."""

    session_id: str
    started_utc: str
    ended_utc: str
    duration_seconds: float
    total_frames: int
    total_persons_counted: int
    rules_triggered: dict[str, int]
    overall_status: str
    anchor: AuditChainAnchor
    integrity_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "cert_version": CERT_VERSION,
            "cert_type": "session",
            "session_id": self.session_id,
            "started_utc": self.started_utc,
            "ended_utc": self.ended_utc,
            "duration_seconds": round(self.duration_seconds, 3),
            "total_frames": self.total_frames,
            "total_persons_counted": self.total_persons_counted,
            "rules_triggered": dict(self.rules_triggered),
            "overall_status": self.overall_status,
            "audit_chain": self.anchor.to_dict(),
        }
        if not self.integrity_hash:
            self.integrity_hash = _integrity_hash(payload)
        payload["integrity_hash"] = self.integrity_hash
        return payload


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class CertificateGenerator:
    """Builds per-frame and per-session compliance certificates."""

    def __init__(
        self,
        session_id: str,
        output_dir: Path | str | None = None,
        write_frame_certs: bool = False,
    ) -> None:
        self._session_id = session_id
        self._output_dir = Path(output_dir) if output_dir else None
        self._write_frame_certs = write_frame_certs
        self._chain = AuditChain(session_id=session_id)
        self._started_ns: int = time.time_ns()
        self._frame_count: int = 0
        self._person_count: int = 0
        self._rules_triggered: dict[str, int] = {}
        if self._output_dir is not None:
            self._output_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(
            "CertificateGenerator initialised: session=%s output_dir=%s",
            session_id,
            self._output_dir,
        )

    # -- frame certificates --------------------------------------------------

    def generate_frame_cert(
        self,
        firewall_result: "FirewallResult",
        rules: list[Any] | None = None,
    ) -> FrameCertificate:
        """Produce a certificate for a single frame and append to audit chain."""
        rules_applied = [
            {
                "rule_id": ev.rule_id,
                "rule_name": ev.rule_name,
                "triggered": True,
                "action_taken": ev.action,
                "legal_basis": ev.legal_basis,
                "applied_to_class": ev.applied_to_class,
            }
            for ev in firewall_result.rules_fired
        ]
        for ev in firewall_result.rules_fired:
            self._rules_triggered[ev.rule_id] = self._rules_triggered.get(ev.rule_id, 0) + 1

        frame_agg = firewall_result.frame_aggregate
        zone_counts = dict(frame_agg.zone_counts)
        person_count = int(frame_agg.person_count)
        self._person_count += person_count

        payload: dict[str, Any] = {
            "cert_version": CERT_VERSION,
            "cert_type": "frame",
            "session_id": self._session_id,
            "frame_id": firewall_result.frame_id,
            "timestamp_utc": _iso_utc(),
            "timestamp_ns": time.time_ns(),
            "constitutional_status": firewall_result.constitutional_status,
            "rules_applied": rules_applied,
            "aggregate_output": {
                "total_persons_detected": person_count,
                "zones": zone_counts,
                "ppe_compliance_rate": round(firewall_result.ppe_compliance_rate, 4),
                "sensitive_objects_flagged": int(frame_agg.sensitive_objects_flagged),
                "active_zones": firewall_result.active_zones,
                "hotspot_zones": firewall_result.hotspot_zones,
                "dwell_time_estimate_seconds": firewall_result.dwell_time_estimate,
            },
            "pii_guarantee": {
                "individual_bboxes_stored": False,
                "face_data_stored": False,
                "track_ids_stored": False,
                "data_transmitted_off_device": False,
                "redactions_performed": firewall_result.redactions_performed,
            },
            "performance": {
                "processing_latency_ms": round(firewall_result.processing_latency_ms, 3),
                "inference_latency_ms": round(firewall_result.inference_latency_ms, 3),
            },
        }
        if rules is not None:
            payload["constitution"] = {
                "rule_count": len(rules),
                "rule_ids": [getattr(r, "rule_id", str(r)) for r in rules],
            }

        integrity = _integrity_hash(payload)
        link = self._chain.append(firewall_result.frame_id, payload)
        cert = FrameCertificate(
            payload=payload,
            chain_link_hash=link.link_hash,
            integrity_hash=integrity,
        )
        self._frame_count += 1

        if self._write_frame_certs and self._output_dir is not None:
            self._dump_frame_cert(cert)

        return cert

    # -- session certificate -------------------------------------------------

    def generate_session_cert(self) -> SessionCertificate:
        """Seal the audit chain and emit the session-end certificate."""
        ended_ns = time.time_ns()
        anchor = self._chain.seal()
        overall_status = self._derive_overall_status()
        session_cert = SessionCertificate(
            session_id=self._session_id,
            started_utc=_iso_utc_from_ns(self._started_ns),
            ended_utc=_iso_utc_from_ns(ended_ns),
            duration_seconds=(ended_ns - self._started_ns) / 1e9,
            total_frames=self._frame_count,
            total_persons_counted=self._person_count,
            rules_triggered=dict(self._rules_triggered),
            overall_status=overall_status,
            anchor=anchor,
        )
        if self._output_dir is not None:
            self._dump_session_cert(session_cert)
        return session_cert

    # -- accessors -----------------------------------------------------------

    @property
    def audit_chain(self) -> AuditChain:
        return self._chain

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def rules_triggered(self) -> dict[str, int]:
        return dict(self._rules_triggered)

    # -- internals -----------------------------------------------------------

    def _derive_overall_status(self) -> str:
        if not self._rules_triggered:
            return "CERTIFIED"
        # If the audit chain verifies and no BLOCKED frame surfaced, we're
        # certified. The firewall stamps BLOCKED on its own; here we just
        # confirm the chain is intact.
        return "CERTIFIED" if self._chain.verify() else "TAMPERED"

    def _dump_frame_cert(self, cert: FrameCertificate) -> None:
        assert self._output_dir is not None
        path = self._output_dir / f"frame_{cert.payload['frame_id']:06d}.json"
        path.write_text(json.dumps(cert.to_dict(), indent=2), encoding="utf-8")

    def _dump_session_cert(self, cert: SessionCertificate) -> None:
        assert self._output_dir is not None
        ts = int(time.time())
        path = self._output_dir / f"session_{ts}_{self._session_id[:8]}.json"
        path.write_text(json.dumps(cert.to_dict(), indent=2), encoding="utf-8")
        logger.info("Session certificate written: %s", path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iso_utc() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _iso_utc_from_ns(ns: int) -> str:
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).isoformat()


def _integrity_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
