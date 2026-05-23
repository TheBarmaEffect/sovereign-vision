"""Zone aggregator - turns redacted detections into enterprise metrics.

This is the only legal source of "what the enterprise sees". It produces
coarse-grained, time-windowed, statistical outputs:
    - per-zone occupancy counts
    - rolling-window occupancy averages
    - PPE compliance rate
    - aggregate dwell time

Nothing here ever references an individual.
"""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Iterable

from sovereign.redactor import ZONE_GRID_COLS, ZONE_GRID_ROWS, ZONE_LABELS, AnonDetection

logger = logging.getLogger(__name__)

DEFAULT_ROLLING_WINDOW: int = 30
DEFAULT_PPE_WINDOW: int = 10
PPE_RELATED_CLASSES: tuple[str, ...] = ("hardhat", "vest", "goggles", "safety helmet", "mask")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class FrameAggregate:
    """Aggregate state produced for a single frame."""

    frame_id: int
    zone_counts: dict[str, int] = field(default_factory=dict)
    class_counts: dict[str, int] = field(default_factory=dict)
    person_count: int = 0
    sensitive_objects_flagged: int = 0
    ppe_items_present: int = 0
    timestamp_ns: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "frame_id": self.frame_id,
            "zone_counts": dict(self.zone_counts),
            "class_counts": dict(self.class_counts),
            "person_count": self.person_count,
            "sensitive_objects_flagged": self.sensitive_objects_flagged,
            "ppe_items_present": self.ppe_items_present,
            "timestamp_ns": self.timestamp_ns,
        }


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------


class ZoneAggregator:
    """Produces aggregate-only metrics from anonymised detections."""

    def __init__(
        self,
        rolling_window: int = DEFAULT_ROLLING_WINDOW,
        ppe_window: int = DEFAULT_PPE_WINDOW,
        zone_aliases: dict[str, str] | None = None,
    ) -> None:
        self._rolling_window = rolling_window
        self._ppe_window = ppe_window
        self._zone_aliases = zone_aliases or {}
        self._history: deque[FrameAggregate] = deque(maxlen=max(rolling_window, ppe_window))
        self._zone_history: dict[str, deque[int]] = {
            label: deque(maxlen=rolling_window) for row in ZONE_LABELS for label in row
        }

    # -- per-frame aggregation ----------------------------------------------

    def aggregate(
        self,
        frame_id: int,
        detections: Iterable[AnonDetection],
        sensitive_classes: tuple[str, ...] = (),
    ) -> FrameAggregate:
        """Produce a FrameAggregate from a stream of anonymised detections."""
        agg = FrameAggregate(frame_id=frame_id)
        for det in detections:
            zone = det.zone_id
            agg.zone_counts[zone] = agg.zone_counts.get(zone, 0) + 1
            agg.class_counts[det.class_name] = agg.class_counts.get(det.class_name, 0) + 1

            if det.class_name == "person":
                agg.person_count += 1
            if det.class_name in PPE_RELATED_CLASSES:
                agg.ppe_items_present += 1
            if det.class_name in sensitive_classes:
                agg.sensitive_objects_flagged += 1

        # ensure all 9 zones are represented for the dashboard
        for row in ZONE_LABELS:
            for label in row:
                agg.zone_counts.setdefault(label, 0)
                self._zone_history[label].append(agg.zone_counts[label])

        self._history.append(agg)
        return agg

    # -- rolling metrics -----------------------------------------------------

    def rolling_average(self, zone_id: str) -> float:
        """Rolling-window mean occupancy for a zone."""
        bucket = self._zone_history.get(zone_id)
        if not bucket:
            return 0.0
        return sum(bucket) / float(len(bucket))

    def active_zones(self, threshold: float = 0.5) -> int:
        """How many zones have a rolling average above `threshold`."""
        return sum(1 for row in ZONE_LABELS for z in row if self.rolling_average(z) > threshold)

    def compute_ppe_compliance(self) -> float:
        """Ratio of recent frames where PPE items were present alongside persons."""
        recent = list(self._history)[-self._ppe_window :]
        if not recent:
            return 1.0
        compliant = 0
        person_frames = 0
        for agg in recent:
            if agg.person_count > 0:
                person_frames += 1
                if agg.ppe_items_present >= agg.person_count:
                    compliant += 1
        if person_frames == 0:
            return 1.0
        return compliant / float(person_frames)

    def compute_dwell_time_estimate(self, fps: float = 30.0) -> dict[str, float]:
        """Estimate aggregate dwell time per zone in seconds.

        This is NOT individual tracking - it is the average lifetime of
        non-zero occupancy windows. Computed from the rolling occupancy
        deque, with no per-person tracking.
        """
        out: dict[str, float] = {}
        for row in ZONE_LABELS:
            for z in row:
                bucket = self._zone_history[z]
                if not bucket:
                    out[z] = 0.0
                    continue
                # average run-length of non-zero occupancy
                runs: list[int] = []
                run = 0
                for v in bucket:
                    if v > 0:
                        run += 1
                    elif run > 0:
                        runs.append(run)
                        run = 0
                if run > 0:
                    runs.append(run)
                avg_frames = sum(runs) / len(runs) if runs else 0.0
                out[z] = avg_frames / max(fps, 1e-6)
        return out

    def hotspot_zones(self, top_k: int = 3) -> list[tuple[str, float]]:
        """Return the top-K zones by rolling average occupancy."""
        scores = [
            (z, self.rolling_average(z))
            for row in ZONE_LABELS
            for z in row
        ]
        scores.sort(key=lambda kv: kv[1], reverse=True)
        return scores[:top_k]

    def total_persons_observed(self) -> int:
        """Sum of person_count across the rolling window. Not unique persons."""
        return sum(agg.person_count for agg in self._history)

    # -- introspection -------------------------------------------------------

    @property
    def grid_shape(self) -> tuple[int, int]:
        return (ZONE_GRID_ROWS, ZONE_GRID_COLS)

    def reset(self) -> None:
        self._history.clear()
        for bucket in self._zone_history.values():
            bucket.clear()
