"""Tests for the certificate generator + session sealing."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from sovereign.certificate import CertificateGenerator
from sovereign.firewall import ConstitutionalFirewall, RawDetection


@pytest.fixture()
def populated_session(tmp_path):
    fw = ConstitutionalFirewall()
    gen = CertificateGenerator(
        session_id=fw.session_id,
        output_dir=tmp_path,
        write_frame_certs=True,
    )
    rng = np.random.default_rng(1)
    frame = rng.integers(0, 255, size=(720, 1280, 3), dtype=np.uint8)
    for _ in range(10):
        dets = [
            RawDetection("person", 0.9, (100, 200, 80, 200)),
            RawDetection("cell phone", 0.8, (400, 300, 40, 60)),
        ]
        result = fw.process_frame(dets, frame=frame)
        gen.generate_frame_cert(result, rules=list(fw.rules))
    return gen, tmp_path


def test_frame_cert_has_required_fields(populated_session) -> None:
    gen, tmp = populated_session
    files = sorted(tmp.glob("frame_*.json"))
    assert len(files) == 10
    payload = json.loads(files[0].read_text())
    for key in (
        "cert_version",
        "cert_type",
        "session_id",
        "frame_id",
        "timestamp_utc",
        "timestamp_ns",
        "constitutional_status",
        "rules_applied",
        "aggregate_output",
        "pii_guarantee",
        "performance",
        "integrity_hash",
        "chain_link_hash",
    ):
        assert key in payload, f"missing {key}"


def test_pii_guarantee_all_false_negatives(populated_session) -> None:
    gen, tmp = populated_session
    for path in tmp.glob("frame_*.json"):
        payload = json.loads(path.read_text())
        guarantee = payload["pii_guarantee"]
        assert guarantee["individual_bboxes_stored"] is False
        assert guarantee["face_data_stored"] is False
        assert guarantee["track_ids_stored"] is False
        assert guarantee["data_transmitted_off_device"] is False


def test_session_cert_seals_chain(populated_session) -> None:
    gen, tmp = populated_session
    cert = gen.generate_session_cert()
    assert cert.total_frames == 10
    assert cert.anchor.chain_length == 10
    assert cert.anchor.merkle_root and cert.anchor.merkle_root != "0" * 64
    # session_*.json should now exist on disk
    files = list(tmp.glob("session_*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text())
    assert payload["cert_type"] == "session"
    assert payload["audit_chain"]["merkle_root"] == cert.anchor.merkle_root


def test_integrity_hash_stable(populated_session) -> None:
    """The integrity hash should be deterministic given the same input."""
    from sovereign.certificate import _integrity_hash

    payload = {"a": 1, "b": [1, 2, 3], "c": {"x": "y"}}
    h1 = _integrity_hash(payload)
    h2 = _integrity_hash(payload)
    assert h1 == h2

    # And order-insensitive
    reordered = {"c": {"x": "y"}, "a": 1, "b": [1, 2, 3]}
    h3 = _integrity_hash(reordered)
    assert h1 == h3


def test_rule_count_summary_in_session_cert(populated_session) -> None:
    gen, _ = populated_session
    cert = gen.generate_session_cert()
    assert sum(cert.rules_triggered.values()) > 0
    assert "SV-001" in cert.rules_triggered
