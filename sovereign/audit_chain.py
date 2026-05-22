"""Merkle-chained audit trail for compliance certificates.

Each frame certificate is hashed and chained to the previous one, so any
tamper with a historical certificate breaks the chain. The session anchor
(final hash) can be exported, time-stamped, or anchored in an external
notary service if regulatory needs require it.

This is what makes the certificate evidence rather than reporting.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

GENESIS_HASH: str = "0" * 64


@dataclass(slots=True)
class AuditChainEntry:
    """One link in the audit chain."""

    index: int
    frame_id: int
    certificate_hash: str
    prev_hash: str
    link_hash: str
    timestamp_ns: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "frame_id": self.frame_id,
            "certificate_hash": self.certificate_hash,
            "prev_hash": self.prev_hash,
            "link_hash": self.link_hash,
            "timestamp_ns": self.timestamp_ns,
        }


@dataclass(slots=True)
class AuditChainAnchor:
    """The session-end anchor that proves the entire chain is intact."""

    session_id: str
    chain_length: int
    genesis_hash: str
    head_hash: str
    merkle_root: str
    sealed_at_ns: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "chain_length": self.chain_length,
            "genesis_hash": self.genesis_hash,
            "head_hash": self.head_hash,
            "merkle_root": self.merkle_root,
            "sealed_at_ns": self.sealed_at_ns,
        }


class AuditChain:
    """An append-only, tamper-evident chain of certificate hashes."""

    def __init__(self, session_id: str) -> None:
        self._session_id = session_id
        self._entries: list[AuditChainEntry] = []
        self._head_hash: str = GENESIS_HASH
        logger.debug("AuditChain initialised for session %s", session_id)

    def append(self, frame_id: int, certificate: dict[str, Any]) -> AuditChainEntry:
        """Append a frame certificate to the chain and return the new link."""
        cert_hash = _stable_sha256(certificate)
        prev_hash = self._head_hash
        link_hash = hashlib.sha256(
            (prev_hash + cert_hash + str(frame_id)).encode("utf-8")
        ).hexdigest()
        entry = AuditChainEntry(
            index=len(self._entries),
            frame_id=frame_id,
            certificate_hash=cert_hash,
            prev_hash=prev_hash,
            link_hash=link_hash,
            timestamp_ns=time.time_ns(),
        )
        self._entries.append(entry)
        self._head_hash = link_hash
        return entry

    def verify(self) -> bool:
        """Re-derive every link hash and confirm the chain has not been edited."""
        prev = GENESIS_HASH
        for entry in self._entries:
            expected = hashlib.sha256(
                (prev + entry.certificate_hash + str(entry.frame_id)).encode("utf-8")
            ).hexdigest()
            if expected != entry.link_hash or prev != entry.prev_hash:
                return False
            prev = entry.link_hash
        return prev == self._head_hash

    def seal(self) -> AuditChainAnchor:
        """Compute a Merkle root over all link hashes and return the anchor."""
        merkle_root = _merkle_root([e.link_hash for e in self._entries])
        anchor = AuditChainAnchor(
            session_id=self._session_id,
            chain_length=len(self._entries),
            genesis_hash=GENESIS_HASH,
            head_hash=self._head_hash,
            merkle_root=merkle_root,
            sealed_at_ns=time.time_ns(),
        )
        logger.info(
            "AuditChain sealed: session=%s length=%d merkle_root=%s",
            self._session_id,
            anchor.chain_length,
            merkle_root[:16],
        )
        return anchor

    # -- accessors -----------------------------------------------------------

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def head_hash(self) -> str:
        return self._head_hash

    @property
    def length(self) -> int:
        return len(self._entries)

    def entries(self) -> list[AuditChainEntry]:
        return list(self._entries)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _stable_sha256(payload: dict[str, Any]) -> str:
    """SHA-256 of a JSON-serialised payload with sorted keys.

    Sorting keys ensures the hash is deterministic regardless of dict order,
    so we can re-derive certificate hashes during verification.
    """
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _merkle_root(hashes: list[str]) -> str:
    """Compute a binary Merkle root over the input hashes."""
    if not hashes:
        return GENESIS_HASH
    layer = list(hashes)
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        layer = [
            hashlib.sha256((layer[i] + layer[i + 1]).encode("utf-8")).hexdigest()
            for i in range(0, len(layer), 2)
        ]
    return layer[0]
