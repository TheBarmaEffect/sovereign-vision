"""Constitutional Firewall — the orchestrator.

The firewall takes raw YOLO detections and runs them through the constitutional
rule set BEFORE any output is produced. The output of `process_frame` is the
only legal payload that may leave the inference pipeline.

This is the centrepiece of Sovereign Vision. If you read one file in this
codebase, read this one.
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterable

from sovereign.aggregator import FrameAggregate, ZoneAggregator
from sovereign.redactor import AnonDetection, PIIRedactor
from sovereign.rules import (
    DEFAULT_RULES,
    PERSON_LIKE_CLASSES,
    SENSITIVE_OBJECT_CLASSES,
    ConstitutionalRule,
    RuleAction,
    applicable_rules,
    validate_rule_set,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class RuleEvent:
    """One rule firing on one detection in one frame."""

    rule_id: str
    rule_name: str
    action: str
    severity: str
    legal_basis: str
    applied_to_class: str
    timestamp_ns: int
    blocked: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "action": self.action,
            "severity": self.severity,
            "legal_basis": self.legal_basis,
            "applied_to_class": self.applied_to_class,
            "timestamp_ns": int(self.timestamp_ns),
            "blocked": bool(self.blocked),
        }


@dataclass(slots=True)
class FirewallResult:
    """Everything the firewall is willing to admit happened in a frame."""

    frame_id: int
    session_id: str
    certified_detections: list[AnonDetection]
    rules_fired: list[RuleEvent]
    frame_aggregate: FrameAggregate
    constitutional_status: str  # CERTIFIED | ESCALATED | BLOCKED
    processing_latency_ms: float
    inference_latency_ms: float = 0.0
    redactions_performed: int = 0
    ppe_compliance_rate: float = 1.0
    active_zones: int = 0
    hotspot_zones: list[tuple[str, float]] = field(default_factory=list)
    dwell_time_estimate: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_id": self.frame_id,
            "session_id": self.session_id,
            "certified_detections": [d.to_dict() for d in self.certified_detections],
            "rules_fired": [r.to_dict() for r in self.rules_fired],
            "frame_aggregate": self.frame_aggregate.to_dict(),
            "constitutional_status": self.constitutional_status,
            "processing_latency_ms": round(self.processing_latency_ms, 3),
            "inference_latency_ms": round(self.inference_latency_ms, 3),
            "redactions_performed": self.redactions_performed,
            "ppe_compliance_rate": round(self.ppe_compliance_rate, 4),
            "active_zones": self.active_zones,
            "hotspot_zones": [(z, round(s, 4)) for z, s in self.hotspot_zones],
            "dwell_time_estimate": {k: round(v, 3) for k, v in self.dwell_time_estimate.items()},
        }


@dataclass(slots=True)
class RawDetection:
    """The input to the firewall — what YOLO would normally produce.

    The firewall is the *only* code in the system that should ever see raw
    detections. Once `process_frame` returns, the caller should discard the
    raw detections that were passed in.
    """

    class_name: str
    confidence: float
    bbox: tuple[float, float, float, float]  # x, y, w, h
    track_id: int | None = None


# ---------------------------------------------------------------------------
# Firewall
# ---------------------------------------------------------------------------


class ConstitutionalFirewall:
    """The orchestrator. Take raw detections, return only certified output."""

    def __init__(
        self,
        rules: Iterable[ConstitutionalRule] | None = None,
        redactor: PIIRedactor | None = None,
        aggregator: ZoneAggregator | None = None,
        sensitive_classes: Iterable[str] | None = None,
        session_id: str | None = None,
    ) -> None:
        self._rules: tuple[ConstitutionalRule, ...] = tuple(rules) if rules else DEFAULT_RULES
        validate_rule_set(self._rules)
        self._redactor = redactor or PIIRedactor()
        self._aggregator = aggregator or ZoneAggregator()
        self._sensitive_classes: tuple[str, ...] = (
            tuple(sensitive_classes) if sensitive_classes else SENSITIVE_OBJECT_CLASSES
        )
        self._session_id = session_id or str(uuid.uuid4())
        self._frame_counter: int = 0
        self._total_rules_fired: int = 0
        self._total_redactions: int = 0

        logger.info(
            "ConstitutionalFirewall ready: session=%s rules=%s",
            self._session_id,
            [r.rule_id for r in self._rules],
        )

    # -- per-frame processing -----------------------------------------------

    def process_frame(
        self,
        raw_detections: Iterable[RawDetection | dict[str, Any]],
        frame: Any | None = None,
        frame_shape: tuple[int, int, int] | tuple[int, int] | None = None,
        inference_latency_ms: float = 0.0,
    ) -> FirewallResult:
        """Filter `raw_detections` through the constitutional rule set."""
        start_ns = time.perf_counter_ns()
        frame_id = self._frame_counter
        self._frame_counter += 1

        shape = frame_shape or _infer_shape(frame)
        events: list[RuleEvent] = []
        certified: list[AnonDetection] = []
        escalated = False

        for raw in raw_detections:
            det = _coerce_detection(raw)

            # 1) collect rules that apply to this class
            triggered = applicable_rules(self._rules, det.class_name)
            blocked = False
            applied_ids: list[str] = []

            for rule in triggered:
                if rule.action == RuleAction.BLOCK:
                    # Confidence floor → drop the detection entirely
                    if rule.confidence_floor is not None:
                        if det.confidence < rule.confidence_floor:
                            blocked = True
                            events.append(_make_event(rule, det.class_name, blocked=True))
                            self._total_rules_fired += 1
                            break
                        # else: rule applies but passes — no event recorded
                        continue
                    # Track-ID suppression: always fires for persons
                    self._redactor.suppress_track_id(det.track_id, rule_id=rule.rule_id)
                    applied_ids.append(rule.rule_id)
                    events.append(_make_event(rule, det.class_name))
                    self._total_rules_fired += 1
                    continue

                if rule.action == RuleAction.ESCALATE:
                    if det.class_name in self._sensitive_classes:
                        escalated = True
                        applied_ids.append(rule.rule_id)
                        events.append(_make_event(rule, det.class_name))
                        self._total_rules_fired += 1
                    continue

                if rule.action in (RuleAction.REDACT, RuleAction.HASH, RuleAction.AGGREGATE):
                    applied_ids.append(rule.rule_id)
                    events.append(_make_event(rule, det.class_name))
                    self._total_rules_fired += 1
                    continue

            if blocked:
                continue

            is_person = det.class_name in PERSON_LIKE_CLASSES
            anon = self._redactor.anonymize_detection(
                class_name=det.class_name,
                confidence=det.confidence,
                bbox=det.bbox,
                frame=frame,
                frame_shape=shape,
                rules_applied=applied_ids,
                is_person=is_person,
            )
            certified.append(anon)

        # 2) aggregate
        agg = self._aggregator.aggregate(
            frame_id=frame_id,
            detections=certified,
            sensitive_classes=self._sensitive_classes,
        )

        # 3) finalise
        latency_ms = (time.perf_counter_ns() - start_ns) / 1e6
        status = "BLOCKED" if not certified and any(e.blocked for e in events) else (
            "ESCALATED" if escalated else "CERTIFIED"
        )
        self._total_redactions = self._redactor.redactions_performed

        return FirewallResult(
            frame_id=frame_id,
            session_id=self._session_id,
            certified_detections=certified,
            rules_fired=events,
            frame_aggregate=agg,
            constitutional_status=status,
            processing_latency_ms=latency_ms,
            inference_latency_ms=inference_latency_ms,
            redactions_performed=self._total_redactions,
            ppe_compliance_rate=self._aggregator.compute_ppe_compliance(),
            active_zones=self._aggregator.active_zones(),
            hotspot_zones=self._aggregator.hotspot_zones(),
            dwell_time_estimate=self._aggregator.compute_dwell_time_estimate(),
        )

    # -- accessors -----------------------------------------------------------

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def rules(self) -> tuple[ConstitutionalRule, ...]:
        return self._rules

    @property
    def aggregator(self) -> ZoneAggregator:
        return self._aggregator

    @property
    def redactor(self) -> PIIRedactor:
        return self._redactor

    @property
    def total_rules_fired(self) -> int:
        return self._total_rules_fired

    @property
    def frame_counter(self) -> int:
        return self._frame_counter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(
    rule: ConstitutionalRule,
    class_name: str,
    blocked: bool = False,
) -> RuleEvent:
    return RuleEvent(
        rule_id=rule.rule_id,
        rule_name=rule.name,
        action=rule.action.value,
        severity=rule.severity.value,
        legal_basis=rule.legal_basis,
        applied_to_class=class_name,
        timestamp_ns=time.time_ns(),
        blocked=blocked,
    )


def _coerce_detection(raw: RawDetection | dict[str, Any]) -> RawDetection:
    """Accept either a RawDetection or a dict from a model wrapper."""
    if isinstance(raw, RawDetection):
        return raw
    return RawDetection(
        class_name=str(raw["class_name"]),
        confidence=float(raw["confidence"]),
        bbox=tuple(raw["bbox"]),  # type: ignore[arg-type]
        track_id=raw.get("track_id"),
    )


def _infer_shape(frame: Any | None) -> tuple[int, int, int] | tuple[int, int]:
    if frame is None:
        return (720, 1280, 3)
    try:
        return tuple(frame.shape)  # type: ignore[return-value]
    except AttributeError:
        return (720, 1280, 3)
