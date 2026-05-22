"""Tests for the zone aggregator."""
from __future__ import annotations

import pytest

from sovereign.aggregator import ZoneAggregator
from sovereign.redactor import AnonDetection, ZONE_LABELS


def _det(class_name: str, zone: str, conf: float = 0.9) -> AnonDetection:
    return AnonDetection(
        class_name=class_name,
        confidence=conf,
        zone_id=zone,
        region_hash="0" * 64 if class_name == "person" else None,
        redaction_log=[],
    )


def test_aggregate_counts_per_zone() -> None:
    agg = ZoneAggregator()
    dets = [
        _det("person", "zone_TL"),
        _det("person", "zone_TL"),
        _det("person", "zone_MC"),
        _det("cell phone", "zone_BR"),
    ]
    result = agg.aggregate(frame_id=0, detections=dets)
    assert result.zone_counts["zone_TL"] == 2
    assert result.zone_counts["zone_MC"] == 1
    assert result.zone_counts["zone_BR"] == 1
    assert result.person_count == 3


def test_all_zones_present_in_aggregate() -> None:
    agg = ZoneAggregator()
    result = agg.aggregate(frame_id=0, detections=[])
    for row in ZONE_LABELS:
        for label in row:
            assert label in result.zone_counts


def test_rolling_average_tracks_history() -> None:
    agg = ZoneAggregator(rolling_window=4)
    for _ in range(2):
        agg.aggregate(frame_id=0, detections=[_det("person", "zone_TL")])
    for _ in range(2):
        agg.aggregate(frame_id=0, detections=[])
    # 2 frames of 1, 2 frames of 0 → avg 0.5
    assert agg.rolling_average("zone_TL") == pytest.approx(0.5)


def test_active_zones_threshold() -> None:
    agg = ZoneAggregator(rolling_window=2)
    agg.aggregate(frame_id=0, detections=[_det("person", "zone_TL"), _det("person", "zone_MR")])
    agg.aggregate(frame_id=0, detections=[_det("person", "zone_TL"), _det("person", "zone_MR")])
    assert agg.active_zones(threshold=0.5) >= 2


def test_ppe_compliance_no_persons_is_100pct() -> None:
    agg = ZoneAggregator()
    agg.aggregate(frame_id=0, detections=[])
    assert agg.compute_ppe_compliance() == 1.0


def test_ppe_compliance_with_required_items_recognised() -> None:
    agg = ZoneAggregator()
    # One person + one hardhat in the same frame
    dets = [
        _det("person", "zone_MC"),
        _det("hardhat", "zone_MC"),
    ]
    agg.aggregate(frame_id=0, detections=dets)
    assert agg.compute_ppe_compliance() == 1.0


def test_ppe_compliance_drops_when_ppe_missing() -> None:
    agg = ZoneAggregator()
    # 3 persons, no PPE
    dets = [_det("person", "zone_MC") for _ in range(3)]
    agg.aggregate(frame_id=0, detections=dets)
    assert agg.compute_ppe_compliance() == 0.0


def test_hotspot_zones_top_k() -> None:
    agg = ZoneAggregator(rolling_window=2)
    agg.aggregate(
        frame_id=0,
        detections=[
            _det("person", "zone_TL"),
            _det("person", "zone_TL"),
            _det("person", "zone_TR"),
        ],
    )
    top = agg.hotspot_zones(top_k=2)
    assert top[0][0] == "zone_TL"
    assert top[0][1] >= top[1][1]


def test_reset_clears_state() -> None:
    agg = ZoneAggregator()
    agg.aggregate(frame_id=0, detections=[_det("person", "zone_TL")])
    agg.reset()
    assert agg.rolling_average("zone_TL") == 0.0
