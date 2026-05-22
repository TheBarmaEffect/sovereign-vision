"""Constitutional Rule data model and the six default rules.

A ConstitutionalRule is an immutable specification of a privacy or safety
constraint that must hold for every detection passing through the firewall.
Rules are evaluated in priority order (CRITICAL first, MEDIUM last) and the
list of triggered rules forms the auditable trail in every compliance
certificate.

This file is the single source of truth for what Sovereign Vision guarantees.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

PERSON_LIKE_CLASSES: tuple[str, ...] = ("person",)
SENSITIVE_OBJECT_CLASSES: tuple[str, ...] = (
    "knife",
    "gun",
    "scissors",
    "cell phone",
    "laptop",
)
WILDCARD: str = "*"

DEFAULT_CONFIDENCE_FLOOR: float = 0.75
DEFAULT_AGGREGATION_WINDOW: int = 5


class RuleAction(str, Enum):
    """What the firewall does when a rule fires."""

    REDACT = "REDACT"
    HASH = "HASH"
    AGGREGATE = "AGGREGATE"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"


class RuleSeverity(str, Enum):
    """Order of evaluation; CRITICAL rules are applied first."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"

    @property
    def priority(self) -> int:
        return {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}[self.value]


# ---------------------------------------------------------------------------
# Rule data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConstitutionalRule:
    """An immutable constitutional rule.

    Frozen so a running system cannot mutate the constitution. To change
    rules, build a new firewall with a new rule list — this guarantees that
    the rules-applied list in every certificate matches the rules that were
    actually in force.
    """

    rule_id: str
    name: str
    description: str
    applies_to: tuple[str, ...]
    action: RuleAction
    severity: RuleSeverity
    legal_basis: str
    confidence_floor: float | None = None
    aggregation_window: int | None = None
    metadata: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def applies(self, class_name: str) -> bool:
        """True if this rule applies to a given detection class."""
        return WILDCARD in self.applies_to or class_name in self.applies_to

    def to_dict(self) -> dict[str, object]:
        """JSON-friendly representation for certificates."""
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "applies_to": list(self.applies_to),
            "action": self.action.value,
            "severity": self.severity.value,
            "legal_basis": self.legal_basis,
            "confidence_floor": self.confidence_floor,
            "aggregation_window": self.aggregation_window,
            "metadata": dict(self.metadata),
        }


# ---------------------------------------------------------------------------
# Default rules (SV-001..SV-006)
# ---------------------------------------------------------------------------

SV_001 = ConstitutionalRule(
    rule_id="SV-001",
    name="Person Coordinate Redaction",
    description=(
        "Raw bounding-box coordinates for detected persons are redacted "
        "before any output is generated. Spatial location of individuals "
        "is personal data under GDPR."
    ),
    applies_to=PERSON_LIKE_CLASSES,
    action=RuleAction.REDACT,
    severity=RuleSeverity.CRITICAL,
    legal_basis="GDPR Article 4(1) — Personal Data Definition",
)

SV_002 = ConstitutionalRule(
    rule_id="SV-002",
    name="Face Region Cryptographic Hash",
    description=(
        "Any detected face region is SHA-256 hashed. The hash cannot be "
        "reversed to reconstruct identity. No biometric data is stored or "
        "transmitted."
    ),
    applies_to=PERSON_LIKE_CLASSES,
    action=RuleAction.HASH,
    severity=RuleSeverity.CRITICAL,
    legal_basis="GDPR Article 9 — Biometric Data",
)

SV_003 = ConstitutionalRule(
    rule_id="SV-003",
    name="Individual Track ID Suppression",
    description=(
        "Per-frame track IDs that could enable cross-frame individual "
        "identification are never assigned or stored. Persons are counted, "
        "never tracked."
    ),
    applies_to=PERSON_LIKE_CLASSES,
    action=RuleAction.BLOCK,
    severity=RuleSeverity.CRITICAL,
    legal_basis="GDPR Recital 30 — Online Identifiers",
)

SV_004 = ConstitutionalRule(
    rule_id="SV-004",
    name="Zone Aggregate Only Output",
    description=(
        "All person-related outputs are converted to zone aggregate counts "
        "before leaving the pipeline. Aggregation window is enforced to "
        "prevent single-frame identification."
    ),
    applies_to=(WILDCARD,),
    action=RuleAction.AGGREGATE,
    severity=RuleSeverity.HIGH,
    legal_basis="GDPR Article 89 — Anonymisation Principle",
    aggregation_window=DEFAULT_AGGREGATION_WINDOW,
)

SV_005 = ConstitutionalRule(
    rule_id="SV-005",
    name="Confidence Floor Enforcement",
    description=(
        "Low-confidence person detections are suppressed entirely rather "
        "than passed as uncertain PII. Uncertain identification is worse "
        "than no identification."
    ),
    applies_to=PERSON_LIKE_CLASSES + ("face",),
    action=RuleAction.BLOCK,
    severity=RuleSeverity.HIGH,
    legal_basis="GDPR Article 22 — Automated Decision-Making",
    confidence_floor=DEFAULT_CONFIDENCE_FLOOR,
)

SV_006 = ConstitutionalRule(
    rule_id="SV-006",
    name="Sensitive Object Class Escalation",
    description=(
        "Sensitive object classes trigger an escalation flag in the "
        "compliance output without recording who was holding or near the "
        "object."
    ),
    applies_to=SENSITIVE_OBJECT_CLASSES,
    action=RuleAction.ESCALATE,
    severity=RuleSeverity.MEDIUM,
    legal_basis="Enterprise Safety Protocol",
)

DEFAULT_RULES: tuple[ConstitutionalRule, ...] = (
    SV_001,
    SV_002,
    SV_003,
    SV_004,
    SV_005,
    SV_006,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def applicable_rules(
    rules: Iterable[ConstitutionalRule],
    class_name: str,
) -> list[ConstitutionalRule]:
    """Return the rules that apply to a given detection class, sorted by severity."""
    out = [r for r in rules if r.applies(class_name)]
    out.sort(key=lambda r: r.severity.priority)
    return out


def validate_rule_set(rules: Iterable[ConstitutionalRule]) -> None:
    """Ensure no duplicate rule_ids exist in the given rule set.

    Raises ValueError if duplicates are found. This guards against silent
    misconfiguration when loading rules from YAML or a custom enterprise
    rule pack.
    """
    seen: set[str] = set()
    for rule in rules:
        if rule.rule_id in seen:
            raise ValueError(f"Duplicate rule_id in rule set: {rule.rule_id}")
        seen.add(rule.rule_id)
    logger.debug("Validated %d constitutional rules", len(seen))
