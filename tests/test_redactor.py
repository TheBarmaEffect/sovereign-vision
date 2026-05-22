"""Tests for the redactor primitives."""
from __future__ import annotations

import re

import numpy as np
import pytest

from sovereign.redactor import (
    PIIRedactor,
    RedactedBbox,
    ZONE_LABELS,
)


def test_redact_bbox_returns_zero_coords() -> None:
    red = PIIRedactor()
    bbox = (100, 200, 80, 200)
    r = red.redact_bbox(bbox, (720, 1280, 3))
    assert r.as_tuple() == (0, 0, 0, 0)
    assert r.redaction_applied
    assert r.rule_id == "SV-001"


def test_redact_bbox_does_not_retain_coords() -> None:
    red = PIIRedactor()
    bbox = (123, 456, 78, 90)
    r = red.redact_bbox(bbox, (720, 1280, 3))
    # Inspect the redacted object's bytes for any of the coord values
    repr_str = repr(r)
    for v in (123, 456, 78, 90):
        assert str(v) not in repr_str


def test_hash_region_is_sha256_hex() -> None:
    red = PIIRedactor()
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    h = red.hash_region(frame, (0, 0, 50, 50))
    assert re.fullmatch(r"[0-9a-f]{64}", h)


def test_hash_region_changes_with_pixels() -> None:
    red = PIIRedactor()
    f1 = np.zeros((100, 100, 3), dtype=np.uint8)
    f2 = np.full((100, 100, 3), 255, dtype=np.uint8)
    assert red.hash_region(f1, (0, 0, 50, 50)) != red.hash_region(f2, (0, 0, 50, 50))


def test_suppress_track_id_returns_none() -> None:
    red = PIIRedactor()
    assert red.suppress_track_id(42) is None
    assert red.suppress_track_id(None) is None


def test_anonymize_detection_drops_pii() -> None:
    red = PIIRedactor()
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    anon = red.anonymize_detection(
        class_name="person",
        confidence=0.9,
        bbox=(100, 200, 80, 200),
        frame=frame,
        frame_shape=frame.shape,
        rules_applied=["SV-001", "SV-002", "SV-003"],
        is_person=True,
    )
    assert anon.original_bbox is None
    assert anon.track_id is None
    assert anon.region_hash is not None
    assert anon.zone_id in {z for row in ZONE_LABELS for z in row}


def test_zone_assignment_consistent_for_same_input() -> None:
    red = PIIRedactor()
    frame_shape = (720, 1280, 3)
    z1 = red._zone_for_bbox((100, 100, 80, 200), frame_shape)
    z2 = red._zone_for_bbox((100, 100, 80, 200), frame_shape)
    assert z1 == z2


def test_zone_assignment_covers_grid() -> None:
    red = PIIRedactor()
    shape = (300, 300, 3)
    seen: set[str] = set()
    for r in range(3):
        for c in range(3):
            x = c * 100 + 10
            y = r * 100 + 10
            seen.add(red._zone_for_bbox((x, y, 20, 20), shape))
    # All 9 grid cells reachable
    assert seen == {z for row in ZONE_LABELS for z in row}


def test_hash_uses_session_salt() -> None:
    """Two redactors with different salts produce different hashes."""
    r1 = PIIRedactor(hash_salt=b"\x00" * 16)
    r2 = PIIRedactor(hash_salt=b"\xff" * 16)
    frame = np.ones((100, 100, 3), dtype=np.uint8)
    h1 = r1.hash_region(frame, (0, 0, 50, 50))
    h2 = r2.hash_region(frame, (0, 0, 50, 50))
    assert h1 != h2
