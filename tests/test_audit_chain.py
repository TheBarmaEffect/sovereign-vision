"""Tests for the Merkle audit chain."""
from __future__ import annotations

import pytest

from sovereign.audit_chain import GENESIS_HASH, AuditChain


def test_genesis_state() -> None:
    chain = AuditChain("s")
    assert chain.head_hash == GENESIS_HASH
    assert chain.length == 0


def test_append_increments_length_and_changes_head() -> None:
    chain = AuditChain("s")
    h0 = chain.head_hash
    chain.append(0, {"frame_id": 0})
    assert chain.length == 1
    assert chain.head_hash != h0


def test_verify_intact_chain() -> None:
    chain = AuditChain("s")
    for i in range(50):
        chain.append(i, {"frame_id": i, "payload": "ok"})
    assert chain.verify()


def test_verify_detects_certificate_tamper() -> None:
    chain = AuditChain("s")
    for i in range(10):
        chain.append(i, {"frame_id": i})
    chain._entries[3].certificate_hash = "ff" * 32  # type: ignore[attr-defined]
    assert not chain.verify()


def test_verify_detects_prev_hash_tamper() -> None:
    chain = AuditChain("s")
    for i in range(10):
        chain.append(i, {"frame_id": i})
    chain._entries[5].prev_hash = "00" * 32  # type: ignore[attr-defined]
    assert not chain.verify()


def test_seal_produces_merkle_root() -> None:
    chain = AuditChain("s")
    for i in range(8):
        chain.append(i, {"frame_id": i})
    anchor = chain.seal()
    assert anchor.merkle_root != GENESIS_HASH
    assert anchor.chain_length == 8


def test_seal_empty_chain_returns_genesis_root() -> None:
    anchor = AuditChain("s").seal()
    assert anchor.merkle_root == GENESIS_HASH


def test_two_chains_with_same_input_match() -> None:
    """Deterministic chains: same inputs → same merkle root."""
    c1 = AuditChain("s1")
    c2 = AuditChain("s2")
    payloads = [{"frame_id": i, "value": i * 2} for i in range(12)]
    for i, p in enumerate(payloads):
        c1.append(i, p)
        c2.append(i, p)
    a1, a2 = c1.seal(), c2.seal()
    assert a1.merkle_root == a2.merkle_root
