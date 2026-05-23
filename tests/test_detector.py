"""Tests for SovereignDetector that close real loopholes.

These prove the architectural claims that the README makes about
SovereignDetector: that `detect()` returns no raw detections, that the
audited side channel is the only legal way to get a raw-preview list,
and that the detector does not retain raw detections between calls.
"""
from __future__ import annotations

import gc
from pathlib import Path

import numpy as np
import pytest

from sovereign.detector import SovereignDetector
from sovereign.firewall import ConstitutionalFirewall, FirewallResult, RawDetection


@pytest.fixture()
def detector() -> SovereignDetector:
    fw = ConstitutionalFirewall()
    return SovereignDetector(model_path=Path("models/yolo26m.npz"), firewall=fw)


def _frame() -> np.ndarray:
    rng = np.random.default_rng(0)
    return rng.integers(0, 255, size=(720, 1280, 3), dtype=np.uint8)


def test_detect_returns_firewall_result_only(detector) -> None:
    result = detector.detect(_frame())
    assert isinstance(result, FirewallResult)


def test_detect_does_not_expose_raw_detections_on_returned_object(detector) -> None:
    result = detector.detect(_frame())
    # No attribute on the result object should be a list of RawDetection
    for name in dir(result):
        if name.startswith("_"):
            continue
        value = getattr(result, name, None)
        if isinstance(value, list) and value and isinstance(value[0], RawDetection):
            pytest.fail(f"Detector leaked raw detections via FirewallResult.{name}")


def test_audited_side_channel_returns_raw_preview(detector) -> None:
    result, raw = detector.detect_with_raw_preview(_frame())
    assert isinstance(result, FirewallResult)
    assert isinstance(raw, list)
    assert all(isinstance(d, RawDetection) for d in raw)


def test_audited_side_channel_does_not_double_invoke_predict(detector) -> None:
    """The side channel must use the same predict() call as the firewall."""
    calls = {"n": 0}
    original = detector._model.predict  # type: ignore[attr-defined]

    def counting_predict(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    detector._model.predict = counting_predict  # type: ignore[attr-defined]
    detector.detect_with_raw_preview(_frame())
    assert calls["n"] == 1, "side channel must call predict() exactly once"


def test_detector_does_not_retain_raw_between_calls(detector) -> None:
    """After detect() returns, no RawDetection should survive on the
    detector instance. We GC-walk to find any references."""
    detector.detect(_frame())
    gc.collect()

    referrers_found: list[object] = []
    # Walk all live RawDetection instances and check none is referenced by
    # the detector or its model. (We tolerate references from this test's
    # local scope.)
    candidates = [o for o in gc.get_objects() if isinstance(o, RawDetection)]
    for cand in candidates:
        for ref in gc.get_referrers(cand):
            if ref is detector or ref is detector._model:  # type: ignore[attr-defined]
                referrers_found.append(ref)
    assert not referrers_found, "raw detections were retained on detector"


def test_repeat_calls_produce_independent_results(detector) -> None:
    r1 = detector.detect(_frame())
    r2 = detector.detect(_frame())
    assert r1.frame_id != r2.frame_id


def test_average_inference_ms_is_nonnegative(detector) -> None:
    detector.detect(_frame())
    assert detector.average_inference_ms >= 0.0


def test_firewall_session_id_matches(detector) -> None:
    result = detector.detect(_frame())
    assert result.session_id == detector.firewall.session_id


def test_simulation_backend_uses_simulation_when_no_model() -> None:
    """If the model file does not exist, detector must fall back to the
    SimulationModel gracefully (no hard error). This protects the demo
    on a fresh checkout without weights."""
    fw = ConstitutionalFirewall()
    det = SovereignDetector(
        model_path=Path("does/not/exist/yolo26m.npz"), firewall=fw
    )
    # Should not raise
    result = det.detect(_frame())
    assert isinstance(result, FirewallResult)
