"""Constitutional zero-PII proofs.

These tests are the executable form of Sovereign Vision's guarantees. If
any of them fail, the system has violated its constitution and the
deployment MUST be halted.

Marked with `@pytest.mark.constitutional` so a CI pipeline can run them
independently of the rest of the suite as a release gate.
"""
from __future__ import annotations

import json
import re

import numpy as np
import pytest

from sovereign.firewall import ConstitutionalFirewall, RawDetection
from sovereign.redactor import AnonDetection

pytestmark = pytest.mark.constitutional


# ---------------------------------------------------------------------------
# Zero-PII invariants
# ---------------------------------------------------------------------------


def test_person_bbox_never_in_output(firewall, sample_detections, synthetic_frame) -> None:
    """SV-001: person bounding boxes never appear in any output."""
    result = firewall.process_frame(sample_detections, frame=synthetic_frame)
    for d in result.certified_detections:
        if d.class_name == "person":
            assert d.original_bbox is None, "person bbox MUST be redacted"

    # Also check the JSON serialisation — PII can't leak via to_dict either
    payload = result.to_dict()
    encoded = json.dumps(payload)
    # The synthesised person bbox (100, 200, 80, 200) must not be present
    assert "100,200,80,200" not in encoded.replace(" ", "")
    # No bbox-like coordinate triples for persons
    for d in payload["certified_detections"]:
        if d["class_name"] == "person":
            assert d["original_bbox"] is None
            assert d["track_id"] is None


def test_face_hash_is_irreversible(firewall, sample_detections, synthetic_frame) -> None:
    """SV-002: face hash is SHA-256 hex (irreversible by cryptographic property).

    We can't directly test irreversibility — that's the SHA-256 contract. Instead
    we test the observable invariants:
      - hex format with exactly 64 lowercase chars (256 bits)
      - same region → same hash (deterministic)
      - different region → different hash (collision-resistant for distinct input)
    """
    result = firewall.process_frame(sample_detections, frame=synthetic_frame)
    person_hashes: list[str] = []
    for d in result.certified_detections:
        if d.class_name == "person":
            assert d.region_hash is not None
            assert re.fullmatch(r"[0-9a-f]{64}", d.region_hash), "must be SHA-256 hex"
            person_hashes.append(d.region_hash)

    # Distinct person regions → distinct hashes (sanity check on collision resistance)
    assert len(set(person_hashes)) == len(person_hashes) or len(person_hashes) <= 1


def test_track_id_always_none_for_persons(firewall, sample_detections, synthetic_frame) -> None:
    """SV-003: track IDs are dropped to None for all persons."""
    result = firewall.process_frame(sample_detections, frame=synthetic_frame)
    for d in result.certified_detections:
        assert d.track_id is None


def test_low_confidence_blocked(firewall, synthetic_frame) -> None:
    """SV-005: persons below the 0.75 confidence floor are dropped entirely."""
    dets = [
        RawDetection("person", 0.40, (100, 100, 80, 200)),
        RawDetection("person", 0.65, (200, 100, 80, 200)),
        RawDetection("person", 0.95, (300, 100, 80, 200)),
    ]
    result = firewall.process_frame(dets, frame=synthetic_frame)
    surviving = [d for d in result.certified_detections if d.class_name == "person"]
    assert len(surviving) == 1, "only the high-confidence person should pass"


def test_certificate_integrity_hash_changes_on_edit(synthetic_frame) -> None:
    """Tampering with any cert field must invalidate the integrity hash."""
    from sovereign.certificate import CertificateGenerator, _integrity_hash

    fw = ConstitutionalFirewall()
    gen = CertificateGenerator(session_id=fw.session_id)
    dets = [RawDetection("person", 0.92, (100, 200, 80, 200))]
    result = fw.process_frame(dets, frame=synthetic_frame)
    cert = gen.generate_frame_cert(result, rules=list(fw.rules))

    payload = json.loads(json.dumps(cert.payload))
    original = _integrity_hash(payload)
    assert original == cert.integrity_hash

    # Tamper: change person count
    payload["aggregate_output"]["total_persons_detected"] = 999
    tampered = _integrity_hash(payload)
    assert tampered != original


def test_audit_chain_verifies(synthetic_frame, sample_detections) -> None:
    """A fresh audit chain must verify after multi-frame ingestion."""
    from sovereign.certificate import CertificateGenerator

    fw = ConstitutionalFirewall()
    gen = CertificateGenerator(session_id=fw.session_id)
    for _ in range(20):
        result = fw.process_frame(sample_detections, frame=synthetic_frame)
        gen.generate_frame_cert(result, rules=list(fw.rules))

    assert gen.audit_chain.verify()
    anchor = gen.audit_chain.seal()
    assert anchor.chain_length == 20
    assert anchor.merkle_root != "0" * 64


def test_audit_chain_detects_tampering() -> None:
    """If we mutate a chain entry, verification must fail."""
    from sovereign.audit_chain import AuditChain

    chain = AuditChain("test")
    for i in range(5):
        chain.append(i, {"frame_id": i, "stub": True})
    assert chain.verify()

    # Tamper: replace one entry's certificate_hash directly
    chain._entries[2].certificate_hash = "deadbeef" * 8  # type: ignore[attr-defined]
    assert not chain.verify()


# ---------------------------------------------------------------------------
# Master constitutional proof
# ---------------------------------------------------------------------------


def test_zero_pii_guarantee_100_frames() -> None:
    """The single master test: 100 frames, scan EVERY byte of EVERY cert
    for any of the PII fingerprints. The system must produce zero hits.
    """
    from sovereign.certificate import CertificateGenerator

    fw = ConstitutionalFirewall()
    gen = CertificateGenerator(session_id=fw.session_id)

    rng = np.random.default_rng(7)
    forbidden_coords: list[tuple[int, int, int, int]] = []
    forbidden_track_ids: list[int] = []

    for frame_id in range(100):
        frame = rng.integers(0, 255, size=(720, 1280, 3), dtype=np.uint8)
        dets: list[RawDetection] = []
        for _ in range(rng.integers(0, 5)):
            x = int(rng.integers(0, 1100))
            y = int(rng.integers(0, 500))
            w = int(rng.integers(40, 200))
            h = int(rng.integers(60, 240))
            track = int(rng.integers(1, 10_000))
            forbidden_coords.append((x, y, w, h))
            forbidden_track_ids.append(track)
            dets.append(
                RawDetection(
                    class_name="person",
                    confidence=float(rng.uniform(0.6, 0.99)),
                    bbox=(x, y, w, h),
                    track_id=track,
                )
            )
        result = fw.process_frame(dets, frame=frame)
        cert = gen.generate_frame_cert(result, rules=list(fw.rules))
        payload = json.dumps(cert.to_dict())

        # Test: no bbox tuple from any person detection appears literally
        # anywhere in the payload string.
        for x, y, w, h in forbidden_coords:
            assert f"{x}, {y}" not in payload, f"PII leak: bbox tuple {x},{y} in cert"
            assert f"\"{x}\"" not in payload, f"PII leak: x-coord {x} in cert"
        # Test: no track id appears in the payload
        for tid in forbidden_track_ids:
            assert f"\"track_id\": {tid}" not in payload, f"PII leak: track_id {tid}"

    # And the audit chain still verifies after all that
    assert gen.audit_chain.verify()


# ---------------------------------------------------------------------------
# Process-level invariants
# ---------------------------------------------------------------------------


def test_constitutional_status_escalates_on_sensitive_class(synthetic_frame) -> None:
    fw = ConstitutionalFirewall()
    dets = [RawDetection("knife", 0.85, (300, 200, 50, 30))]
    result = fw.process_frame(dets, frame=synthetic_frame)
    assert result.constitutional_status == "ESCALATED"


def test_processing_latency_recorded(synthetic_frame, sample_detections) -> None:
    fw = ConstitutionalFirewall()
    result = fw.process_frame(sample_detections, frame=synthetic_frame)
    assert result.processing_latency_ms >= 0.0
    assert result.processing_latency_ms < 5000.0  # sanity bound


def test_frame_counter_increments(synthetic_frame, sample_detections) -> None:
    fw = ConstitutionalFirewall()
    r0 = fw.process_frame(sample_detections, frame=synthetic_frame)
    r1 = fw.process_frame(sample_detections, frame=synthetic_frame)
    assert r0.frame_id + 1 == r1.frame_id


def test_session_id_stable(synthetic_frame, sample_detections) -> None:
    fw = ConstitutionalFirewall()
    sid = fw.session_id
    fw.process_frame(sample_detections, frame=synthetic_frame)
    fw.process_frame(sample_detections, frame=synthetic_frame)
    assert fw.session_id == sid
