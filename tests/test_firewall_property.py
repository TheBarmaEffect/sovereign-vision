"""Property-based tests using Hypothesis.

These randomise input across thousands of trials to find edge cases that
hand-written examples miss. Marked `constitutional` so a CI release gate
can run them with longer deadlines.
"""
from __future__ import annotations

import json

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from sovereign.firewall import ConstitutionalFirewall, RawDetection


pytestmark = pytest.mark.constitutional


_PERSON_CLASS = st.just("person")
_NONPERSON_CLASS = st.sampled_from(
    ["cell phone", "laptop", "knife", "car", "chair", "cup"]
)
_CLASS = st.one_of(_PERSON_CLASS, _NONPERSON_CLASS)

_CONFIDENCE = st.floats(min_value=0.0, max_value=1.0,
                        allow_nan=False, allow_infinity=False)
_COORD = st.integers(min_value=0, max_value=1200)
_SIZE = st.integers(min_value=10, max_value=400)
_TRACK = st.integers(min_value=1, max_value=10_000_000)


@st.composite
def _detection(draw) -> RawDetection:
    cls = draw(_CLASS)
    conf = draw(_CONFIDENCE)
    x = draw(_COORD)
    y = draw(_COORD)
    w = draw(_SIZE)
    h = draw(_SIZE)
    track = draw(_TRACK)
    return RawDetection(class_name=cls, confidence=conf, bbox=(x, y, w, h),
                        track_id=track)


@given(dets=st.lists(_detection(), min_size=0, max_size=8))
@settings(max_examples=200, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_no_track_id_in_output(dets: list[RawDetection]) -> None:
    fw = ConstitutionalFirewall()
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    result = fw.process_frame(dets, frame=frame)
    payload = json.dumps(result.to_dict())
    for det in dets:
        if det.track_id is not None:
            # Match the JSON key form exactly so we don't false-positive
            # against natural occurrences of the number inside hashes.
            assert f'"track_id": {det.track_id}' not in payload


@given(dets=st.lists(_detection(), min_size=0, max_size=8))
@settings(max_examples=200, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_status_is_well_formed(dets: list[RawDetection]) -> None:
    fw = ConstitutionalFirewall()
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    result = fw.process_frame(dets, frame=frame)
    assert result.constitutional_status in ("CLEAR", "ESCALATED", "BLOCKED")


@given(dets=st.lists(_detection(), min_size=0, max_size=4))
@settings(max_examples=100, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_zone_counts_non_negative(dets: list[RawDetection]) -> None:
    """SV-007 DP noise can produce negative values pre-clamp; SV-007's
    clamp must guarantee non-negativity in the output."""
    fw = ConstitutionalFirewall()
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    result = fw.process_frame(dets, frame=frame)
    for zone, count in result.frame_aggregate.zone_counts.items():
        assert count >= 0, f"zone {zone} count {count} < 0"
