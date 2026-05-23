"""Webhook system for ESCALATED frames.

When the firewall produces a frame with status ESCALATED, the webhook
subscriber fires a POST to a configurable URL with the certificate
payload. The webhook explicitly does NOT include any raw bbox or person
imagery; only the same audit-grade aggregate certificate that's already
written to disk.

The webhook fires on a daemon thread so the inference loop is never
blocked by a slow consumer.

Usage:
    from sovereign.webhooks import WebhookSubscriber
    sub = WebhookSubscriber(url="https://your-siem/alerts",
                            hmac_secret=b"shared-secret")
    sub.start()

    # in your frame loop:
    sub.maybe_fire(firewall_result, cert)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import queue
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class WebhookConfig:
    url: str
    hmac_secret: bytes | None = None
    timeout_seconds: float = 5.0
    only_on: tuple[str, ...] = ("ESCALATED", "BLOCKED")
    max_queue: int = 100


class WebhookSubscriber:
    """Background webhook dispatcher with HMAC-signed payloads."""

    def __init__(
        self,
        url: str,
        hmac_secret: bytes | None = None,
        timeout_seconds: float = 5.0,
        only_on: tuple[str, ...] = ("ESCALATED", "BLOCKED"),
    ) -> None:
        self._cfg = WebhookConfig(
            url=url,
            hmac_secret=hmac_secret,
            timeout_seconds=timeout_seconds,
            only_on=only_on,
        )
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=self._cfg.max_queue)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._delivered: int = 0
        self._failed: int = 0
        self._dropped: int = 0

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="sovereign-webhook"
        )
        self._thread.start()
        logger.info("WebhookSubscriber started for %s (on %s)",
                    self._cfg.url, self._cfg.only_on)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def maybe_fire(self, firewall_result: Any, cert: Any | None = None) -> bool:
        """Enqueue a webhook event if the result's status is in `only_on`."""
        status = getattr(firewall_result, "constitutional_status", None)
        if status not in self._cfg.only_on:
            return False

        payload = {
            "type": "sovereign.firewall.event",
            "schema_version": "1.0",
            "ts_ns": time.time_ns(),
            "session_id": getattr(firewall_result, "session_id", None),
            "frame_id": getattr(firewall_result, "frame_id", None),
            "status": status,
            "rules_fired": [ev.rule_id for ev in getattr(firewall_result, "rules_fired", [])],
            "aggregate": getattr(
                getattr(firewall_result, "frame_aggregate", None),
                "to_dict",
                lambda: {},
            )(),
            "integrity_hash": getattr(cert, "integrity_hash", None) if cert else None,
        }
        try:
            self._queue.put_nowait(payload)
            return True
        except queue.Full:
            self._dropped += 1
            logger.warning("webhook queue full; dropping event")
            return False

    # -- stats ---------------------------------------------------------------

    @property
    def delivered(self) -> int:
        return self._delivered

    @property
    def failed(self) -> int:
        return self._failed

    @property
    def dropped(self) -> int:
        return self._dropped

    # -- internals -----------------------------------------------------------

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                payload = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self._deliver(payload)
                self._delivered += 1
            except Exception as exc:
                self._failed += 1
                logger.warning("webhook delivery failed: %s", exc)

    def _deliver(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        req = urllib.request.Request(
            self._cfg.url,
            data=body,
            method="POST",
            headers={"content-type": "application/json"},
        )
        if self._cfg.hmac_secret:
            mac = hmac.new(self._cfg.hmac_secret, body, hashlib.sha256).hexdigest()
            req.add_header("x-sovereign-signature", f"sha256={mac}")
        with urllib.request.urlopen(req, timeout=self._cfg.timeout_seconds):
            pass
