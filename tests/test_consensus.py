"""Tests for the multi-camera consensus coordinator."""
from __future__ import annotations

import pytest

from sovereign.aggregator import FrameAggregate
from sovereign.consensus import ConsensusCoordinator


class _FakeResult:
    def __init__(self, status: str, zones: dict[str, int] | None = None) -> None:
        self.constitutional_status = status
        self.frame_aggregate = FrameAggregate(frame_id=0, zone_counts=zones or {})


def test_init_validates() -> None:
    with pytest.raises(ValueError):
        ConsensusCoordinator([], quorum=1)
    with pytest.raises(ValueError):
        ConsensusCoordinator(["a", "b"], quorum=3)


def test_clear_when_all_agree() -> None:
    c = ConsensusCoordinator(["a", "b", "c"], quorum=2)
    c.submit("a", _FakeResult("CLEAR"))
    c.submit("b", _FakeResult("CLEAR"))
    c.submit("c", _FakeResult("CLEAR"))
    d = c.decide()
    assert d.status == "CLEAR"
    assert set(d.agreed_cameras) == {"a", "b", "c"}


def test_escalated_only_when_quorum_met() -> None:
    c = ConsensusCoordinator(["a", "b", "c"], quorum=2)
    c.submit("a", _FakeResult("ESCALATED"))
    c.submit("b", _FakeResult("CLEAR"))
    c.submit("c", _FakeResult("CLEAR"))
    d = c.decide()
    # Only 1 camera said ESCALATED; quorum is 2 → CLEAR wins (2 agree)
    assert d.status == "CLEAR"


def test_escalated_fires_at_quorum() -> None:
    c = ConsensusCoordinator(["a", "b", "c"], quorum=2)
    c.submit("a", _FakeResult("ESCALATED"))
    c.submit("b", _FakeResult("ESCALATED"))
    c.submit("c", _FakeResult("CLEAR"))
    d = c.decide()
    assert d.status == "ESCALATED"
    assert set(d.agreed_cameras) == {"a", "b"}


def test_blocked_takes_precedence_over_escalated() -> None:
    c = ConsensusCoordinator(["a", "b", "c", "d"], quorum=2)
    c.submit("a", _FakeResult("BLOCKED"))
    c.submit("b", _FakeResult("BLOCKED"))
    c.submit("c", _FakeResult("ESCALATED"))
    c.submit("d", _FakeResult("ESCALATED"))
    d = c.decide()
    assert d.status == "BLOCKED"


def test_zone_counts_sum_across_cameras() -> None:
    c = ConsensusCoordinator(["a", "b"], quorum=1)
    c.submit("a", _FakeResult("CLEAR", zones={"zone_TL": 1, "zone_MC": 2}))
    c.submit("b", _FakeResult("CLEAR", zones={"zone_TL": 3, "zone_BR": 1}))
    d = c.decide()
    assert d.total_zones["zone_TL"] == 4
    assert d.total_zones["zone_MC"] == 2
    assert d.total_zones["zone_BR"] == 1


def test_explanation_string_non_empty() -> None:
    c = ConsensusCoordinator(["a", "b"], quorum=1)
    c.submit("a", _FakeResult("CLEAR"))
    d = c.decide()
    assert d.explanation
