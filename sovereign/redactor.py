"""PII redaction engine.

Every primitive that touches PII lives here. The rest of the codebase calls
into this module so there is exactly one place where redaction happens — the
firewall is then easy to audit: if a code path bypasses `PIIRedactor`, it
shows up immediately.

Design invariants:
  - Bounding-box coordinates for redacted detections are zeroed out and the
    `redaction_applied` flag is set. Original coords are NEVER stored.
  - Face / person regions are SHA-256 hashed and only the hex digest is kept.
  - Track IDs are dropped to None on the way through.
  - All redactions are logged with rule_id + timestamp for audit trail.
"""
from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

HASH_ALGORITHM: str = "sha256"
HASH_DIGEST_LENGTH: int = 64
ZONE_GRID_ROWS: int = 3
ZONE_GRID_COLS: int = 3
ZONE_LABELS: tuple[tuple[str, ...], ...] = (
    ("zone_TL", "zone_TC", "zone_TR"),
    ("zone_ML", "zone_MC", "zone_MR"),
    ("zone_BL", "zone_BC", "zone_BR"),
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RedactedBbox:
    """A bbox after redaction. All coordinates are zero by construction.

    We keep the shape of the type but not the location.
    """

    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0
    redaction_applied: bool = True
    rule_id: str = "SV-001"

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.w, self.h)


@dataclass(slots=True)
class AnonDetection:
    """An anonymised detection ready to be aggregated.

    Carries only what the enterprise layer is allowed to see:
      - class_name and confidence (needed for aggregation rules)
      - zone_id (rough quadrant, never exact coordinates)
      - region_hash (a SHA-256 digest, irreversible)
      - redaction_log (audit trail)
    """

    class_name: str
    confidence: float
    zone_id: str
    region_hash: str | None = None
    redaction_log: list[str] = field(default_factory=list)
    original_bbox: None = None  # invariant: always None
    track_id: None = None  # invariant: always None
    timestamp_ns: int = 0

    def __post_init__(self) -> None:
        if self.timestamp_ns == 0:
            self.timestamp_ns = time.time_ns()

    def to_dict(self) -> dict[str, Any]:
        return {
            "class_name": self.class_name,
            "confidence": round(float(self.confidence), 4),
            "zone_id": self.zone_id,
            "region_hash": self.region_hash,
            "redaction_log": list(self.redaction_log),
            "original_bbox": None,
            "track_id": None,
            "timestamp_ns": int(self.timestamp_ns),
        }


# ---------------------------------------------------------------------------
# Redactor
# ---------------------------------------------------------------------------


class PIIRedactor:
    """The only legal way to handle person-related data in this system."""

    def __init__(self, hash_salt: bytes | None = None) -> None:
        # The salt is per-session, ephemeral, and never persisted. Even if
        # a face hash leaks, it cannot be correlated across sessions.
        self._salt: bytes = hash_salt if hash_salt is not None else _generate_session_salt()
        self._redactions_performed: int = 0
        logger.debug("PIIRedactor initialised with %d-byte session salt", len(self._salt))

    # -- primitive operations ------------------------------------------------

    def redact_bbox(
        self,
        bbox: tuple[float, float, float, float],
        frame_shape: tuple[int, int, int] | tuple[int, int],
        rule_id: str = "SV-001",
    ) -> RedactedBbox:
        """Return a zero-coordinate bbox. Original coords are not retained."""
        # We deliberately do not store `bbox`. The argument is consumed and
        # discarded — Python's gc will handle the reference; we hold none.
        _ = bbox  # not stored
        _ = frame_shape  # not stored
        self._redactions_performed += 1
        logger.debug("redact_bbox: applied rule %s", rule_id)
        return RedactedBbox(rule_id=rule_id)

    def hash_region(
        self,
        frame: Any,
        bbox: tuple[float, float, float, float],
        rule_id: str = "SV-002",
    ) -> str:
        """Extract a region, SHA-256 hash its pixel bytes, return the digest.

        The region bytes are read into a hasher and immediately go out of
        scope. The digest is irreversible.
        """
        x, y, w, h = (int(v) for v in bbox)
        x = max(0, x)
        y = max(0, y)

        region_bytes = _extract_region_bytes(frame, x, y, w, h)
        digest = hashlib.sha256(self._salt + region_bytes).hexdigest()
        self._redactions_performed += 1
        logger.debug("hash_region: applied rule %s, digest=%s...", rule_id, digest[:8])
        return digest

    def suppress_track_id(self, track_id: int | str | None, rule_id: str = "SV-003") -> None:
        """Any incoming track_id is dropped. Return value is always None."""
        if track_id is not None:
            logger.debug("suppress_track_id: dropped id under rule %s", rule_id)
            self._redactions_performed += 1
        return None

    # -- composite operation -------------------------------------------------

    def anonymize_detection(
        self,
        class_name: str,
        confidence: float,
        bbox: tuple[float, float, float, float],
        frame: Any,
        frame_shape: tuple[int, int, int] | tuple[int, int],
        rules_applied: list[str],
        is_person: bool,
    ) -> AnonDetection:
        """Run the full redaction pipeline for a single detection.

        Returns an AnonDetection that is safe to aggregate. The caller MUST
        discard the raw detection after this call — there is no API to
        retrieve the original bbox from an AnonDetection.
        """
        zone_id = self._zone_for_bbox(bbox, frame_shape)
        region_hash: str | None = None

        if is_person:
            region_hash = self.hash_region(frame, bbox)
            # Redaction happens in place (we don't carry bbox forward at all)
            _ = self.redact_bbox(bbox, frame_shape)
            _ = self.suppress_track_id(None)

        return AnonDetection(
            class_name=class_name,
            confidence=float(confidence),
            zone_id=zone_id,
            region_hash=region_hash,
            redaction_log=list(rules_applied),
        )

    # -- diagnostics ---------------------------------------------------------

    @property
    def redactions_performed(self) -> int:
        return self._redactions_performed

    # -- internals -----------------------------------------------------------

    @staticmethod
    def _zone_for_bbox(
        bbox: tuple[float, float, float, float],
        frame_shape: tuple[int, int, int] | tuple[int, int],
    ) -> str:
        """Map a bbox to a 3x3 zone label using only its rough quadrant.

        We deliberately quantise to a 3x3 grid so the spatial information
        leaving this function is coarse-grained — coarse enough that the
        SV-004 aggregation rule's anonymisation guarantee holds.
        """
        if len(frame_shape) >= 2:
            h_frame, w_frame = frame_shape[0], frame_shape[1]
        else:
            h_frame = w_frame = 1
        if w_frame <= 0 or h_frame <= 0:
            return "zone_MC"

        x, y, w, h = bbox
        cx = (x + w / 2.0) / float(w_frame)
        cy = (y + h / 2.0) / float(h_frame)
        cx = min(max(cx, 0.0), 0.999)
        cy = min(max(cy, 0.0), 0.999)
        col = int(cx * ZONE_GRID_COLS)
        row = int(cy * ZONE_GRID_ROWS)
        return ZONE_LABELS[row][col]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _generate_session_salt() -> bytes:
    """16 bytes of OS entropy. Never persisted, never logged."""
    import os

    return os.urandom(16)


def _extract_region_bytes(frame: Any, x: int, y: int, w: int, h: int) -> bytes:
    """Best-effort region extraction. Works with numpy arrays and falls back
    gracefully when frame is a placeholder (e.g. during unit tests).
    """
    try:
        import numpy as np  # local import keeps top-level import light

        if isinstance(frame, np.ndarray):
            h_frame, w_frame = frame.shape[:2]
            x2 = min(x + w, w_frame)
            y2 = min(y + h, h_frame)
            x = max(0, x)
            y = max(0, y)
            if x2 <= x or y2 <= y:
                return b""
            region = frame[y:y2, x:x2]
            return bytes(region.tobytes())
    except Exception:  # pragma: no cover — numpy missing in minimal envs
        logger.debug("numpy not available; using fallback region bytes")

    # Fallback: hash a deterministic representation. Still irreversible.
    return f"region:{x}:{y}:{w}:{h}".encode("utf-8")
