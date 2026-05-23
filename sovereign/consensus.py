"""Multi-camera consensus mode.

A consensus coordinator takes the latest FirewallResult from N cameras
and only fires an ESCALATED event if at least M of N agree (the
M-of-N quorum rule). This kills the false-positive problem that
single-camera CV systems have: a worker who briefly walks behind a
shelf with a phone in hand does not trigger an alert unless multiple
cameras independently agree.

Aggregate counts are summed across cameras for zone occupancy (zones
are global, not per-camera). Per-camera privacy guarantees (SV-001..
SV-007) are preserved because we only consume `FirewallResult` objects,
never raw detections.

Usage:

    from sovereign.consensus import ConsensusCoordinator
    coord = ConsensusCoordinator(camera_ids=["cam-A", "cam-B", "cam-C"],
                                  quorum=2)

    # in your per-camera loop:
    coord.submit("cam-A", result_A)
    coord.submit("cam-B", result_B)
    coord.submit("cam-C", result_C)

    decision = coord.decide()
    # decision.status, decision.zones, decision.agreed_cameras, ...
"""
from __future__ import annotations

import logging
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ConsensusDecision:
    """The N-camera consensus output."""

    status: str
    agreed_cameras: list[str]
    dissenting_cameras: list[str]
    total_zones: dict[str, int]
    per_camera_status: dict[str, str]
    ts_ns: int
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "agreed_cameras": list(self.agreed_cameras),
            "dissenting_cameras": list(self.dissenting_cameras),
            "total_zones": dict(self.total_zones),
            "per_camera_status": dict(self.per_camera_status),
            "ts_ns": int(self.ts_ns),
            "explanation": self.explanation,
        }


class ConsensusCoordinator:
    """M-of-N quorum coordinator across multiple cameras."""

    def __init__(
        self,
        camera_ids: list[str],
        quorum: int = 2,
        staleness_seconds: float = 1.0,
    ) -> None:
        if not camera_ids:
            raise ValueError("camera_ids must not be empty")
        if quorum < 1 or quorum > len(camera_ids):
            raise ValueError(
                f"quorum must be in [1, {len(camera_ids)}], got {quorum}"
            )
        self._camera_ids = tuple(camera_ids)
        self._quorum = quorum
        self._staleness_seconds = staleness_seconds
        self._latest: dict[str, tuple[Any, float]] = {}

    # -- ingest --------------------------------------------------------------

    def submit(self, camera_id: str, firewall_result: Any) -> None:
        if camera_id not in self._camera_ids:
            raise ValueError(f"unknown camera_id {camera_id}")
        self._latest[camera_id] = (firewall_result, time.time())

    # -- decide --------------------------------------------------------------

    def decide(self) -> ConsensusDecision:
        now = time.time()
        active: dict[str, Any] = {}
        for cam, (result, ts) in self._latest.items():
            if now - ts <= self._staleness_seconds:
                active[cam] = result

        per_status: dict[str, str] = {
            cam: getattr(r, "constitutional_status", "?")
            for cam, r in active.items()
        }
        counts = Counter(per_status.values())

        # Status precedence: BLOCKED > ESCALATED > CLEAR
        decided = "CLEAR"
        agreed: list[str] = []
        explanation = "no cameras active above quorum"
        for candidate in ("BLOCKED", "ESCALATED", "CLEAR"):
            agree = [c for c, s in per_status.items() if s == candidate]
            if len(agree) >= self._quorum:
                decided = candidate
                agreed = agree
                explanation = (
                    f"{len(agree)} of {len(active)} cameras agreed on "
                    f"{candidate} (quorum={self._quorum})"
                )
                break

        dissenting = [c for c in active if c not in agreed]
        total_zones = self._sum_zones(active.values())

        return ConsensusDecision(
            status=decided,
            agreed_cameras=agreed,
            dissenting_cameras=dissenting,
            total_zones=total_zones,
            per_camera_status=per_status,
            ts_ns=int(now * 1e9),
            explanation=explanation,
        )

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _sum_zones(results) -> dict[str, int]:
        out: dict[str, int] = defaultdict(int)
        for r in results:
            zc = getattr(getattr(r, "frame_aggregate", None), "zone_counts", None)
            if not zc:
                continue
            for k, v in zc.items():
                out[k] += int(v)
        return dict(out)

    @property
    def camera_ids(self) -> tuple[str, ...]:
        return self._camera_ids

    @property
    def quorum(self) -> int:
        return self._quorum
