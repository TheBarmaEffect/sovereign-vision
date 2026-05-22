"""Lightweight performance + constitutional metrics.

We track three things:
  - Performance: FPS, inference latency, firewall latency
  - Constitutional: rules-fired-per-frame, redactions-performed, status mix
  - System: memory, queue depth (placeholder hook)

A `MetricsRegistry` accumulates everything in-process. Optional Prometheus
export is provided through `prometheus_text()` so it can be scraped by an
enterprise monitoring stack without pulling in a new dependency.
"""
from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Iterable

from sovereign.firewall import FirewallResult

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class MetricsSnapshot:
    """Point-in-time view of the metrics registry."""

    fps: float
    avg_inference_ms: float
    avg_firewall_ms: float
    total_frames: int
    total_rules_fired: int
    total_redactions: int
    status_certified: int
    status_escalated: int
    status_blocked: int

    def to_dict(self) -> dict[str, float | int]:
        return {
            "fps": round(self.fps, 2),
            "avg_inference_ms": round(self.avg_inference_ms, 3),
            "avg_firewall_ms": round(self.avg_firewall_ms, 3),
            "total_frames": self.total_frames,
            "total_rules_fired": self.total_rules_fired,
            "total_redactions": self.total_redactions,
            "status_certified": self.status_certified,
            "status_escalated": self.status_escalated,
            "status_blocked": self.status_blocked,
        }


class MetricsRegistry:
    """Rolling performance + constitutional metrics."""

    def __init__(self, window: int = 120) -> None:
        self._window = window
        self._frame_ts: deque[float] = deque(maxlen=window)
        self._inference_ms: deque[float] = deque(maxlen=window)
        self._firewall_ms: deque[float] = deque(maxlen=window)
        self._total_frames: int = 0
        self._total_rules_fired: int = 0
        self._total_redactions: int = 0
        self._status_counts: dict[str, int] = {
            "CERTIFIED": 0,
            "ESCALATED": 0,
            "BLOCKED": 0,
        }

    def record(self, result: FirewallResult) -> None:
        now = time.perf_counter()
        self._frame_ts.append(now)
        self._inference_ms.append(result.inference_latency_ms)
        self._firewall_ms.append(result.processing_latency_ms)
        self._total_frames += 1
        self._total_rules_fired += len(result.rules_fired)
        self._total_redactions = max(self._total_redactions, result.redactions_performed)
        self._status_counts[result.constitutional_status] = (
            self._status_counts.get(result.constitutional_status, 0) + 1
        )

    def snapshot(self) -> MetricsSnapshot:
        return MetricsSnapshot(
            fps=self._fps(),
            avg_inference_ms=_avg(self._inference_ms),
            avg_firewall_ms=_avg(self._firewall_ms),
            total_frames=self._total_frames,
            total_rules_fired=self._total_rules_fired,
            total_redactions=self._total_redactions,
            status_certified=self._status_counts.get("CERTIFIED", 0),
            status_escalated=self._status_counts.get("ESCALATED", 0),
            status_blocked=self._status_counts.get("BLOCKED", 0),
        )

    def prometheus_text(self) -> str:
        """Render an OpenMetrics-style text payload (no client lib required)."""
        snap = self.snapshot()
        lines = [
            "# HELP sovereign_fps Live frames per second.",
            "# TYPE sovereign_fps gauge",
            f"sovereign_fps {snap.fps}",
            "# HELP sovereign_inference_latency_ms Mean inference latency in ms.",
            "# TYPE sovereign_inference_latency_ms gauge",
            f"sovereign_inference_latency_ms {snap.avg_inference_ms}",
            "# HELP sovereign_firewall_latency_ms Mean firewall processing in ms.",
            "# TYPE sovereign_firewall_latency_ms gauge",
            f"sovereign_firewall_latency_ms {snap.avg_firewall_ms}",
            "# HELP sovereign_total_frames Total frames processed since start.",
            "# TYPE sovereign_total_frames counter",
            f"sovereign_total_frames {snap.total_frames}",
            "# HELP sovereign_total_rules_fired Total constitutional rules fired.",
            "# TYPE sovereign_total_rules_fired counter",
            f"sovereign_total_rules_fired {snap.total_rules_fired}",
            "# HELP sovereign_total_redactions Total PII redactions performed.",
            "# TYPE sovereign_total_redactions counter",
            f"sovereign_total_redactions {snap.total_redactions}",
            "# HELP sovereign_status_count Count of frames per constitutional status.",
            "# TYPE sovereign_status_count counter",
            f'sovereign_status_count{{status="CERTIFIED"}} {snap.status_certified}',
            f'sovereign_status_count{{status="ESCALATED"}} {snap.status_escalated}',
            f'sovereign_status_count{{status="BLOCKED"}} {snap.status_blocked}',
        ]
        return "\n".join(lines) + "\n"

    # -- internals -----------------------------------------------------------

    def _fps(self) -> float:
        if len(self._frame_ts) < 2:
            return 0.0
        span = self._frame_ts[-1] - self._frame_ts[0]
        if span <= 0:
            return 0.0
        return (len(self._frame_ts) - 1) / span


def _avg(buf: Iterable[float]) -> float:
    seq = list(buf)
    if not seq:
        return 0.0
    return sum(seq) / float(len(seq))
