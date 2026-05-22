"""Sovereign Vision — on-device enterprise computer vision with a Constitutional Firewall.

This package implements the Glass Box Framework for computer vision: every raw
YOLO26 detection is intercepted by a constitutional rule set before it can ever
become an output. PII is redacted at the point of inference, not after.

Public API
----------
ConstitutionalRule, RuleAction, RuleSeverity
    Rule data model.
DEFAULT_RULES
    The six default rules that ship with Sovereign Vision (SV-001..SV-006).
PIIRedactor
    The redaction engine. Performs bbox redaction, region hashing, track-id
    suppression, and detection anonymisation.
ConstitutionalFirewall
    The orchestrator. Takes raw detections, runs all applicable rules, and
    emits a FirewallResult that contains only certified aggregate output.
SovereignDetector
    Thin wrapper around YOLO26 MLX that pipes inferences directly into the
    firewall. The raw model output never escapes this class.
CertificateGenerator
    Emits per-frame and per-session compliance certificates with an integrity
    hash and an optional Merkle audit chain anchor.
ZoneAggregator
    Aggregate-only metrics: zone occupancy, rolling averages, PPE compliance,
    dwell-time estimates.
AuditChain
    Append-only Merkle chain of frame certificates. Tamper-evident.
SovereignConfig
    Type-safe YAML/dict configuration for runtime customisation.

Research connection
-------------------
This package is a practical instantiation of the Glass Box Framework, a
runtime constitutional AI verification system under active research at
Northeastern University's Khoury College of Computer Sciences.
"""
from __future__ import annotations

from sovereign.aggregator import ZoneAggregator
from sovereign.audit_chain import AuditChain, AuditChainAnchor
from sovereign.certificate import CertificateGenerator, FrameCertificate, SessionCertificate
from sovereign.config import SovereignConfig
from sovereign.detector import SovereignDetector
from sovereign.firewall import ConstitutionalFirewall, FirewallResult, RuleEvent
from sovereign.redactor import AnonDetection, PIIRedactor, RedactedBbox
from sovereign.rules import (
    DEFAULT_RULES,
    ConstitutionalRule,
    RuleAction,
    RuleSeverity,
)

__version__ = "1.0.0"
__author__ = "Karthik Barma"
__license__ = "AGPL-3.0"

__all__ = [
    "AnonDetection",
    "AuditChain",
    "AuditChainAnchor",
    "CertificateGenerator",
    "ConstitutionalFirewall",
    "ConstitutionalRule",
    "DEFAULT_RULES",
    "FirewallResult",
    "FrameCertificate",
    "PIIRedactor",
    "RedactedBbox",
    "RuleAction",
    "RuleEvent",
    "RuleSeverity",
    "SessionCertificate",
    "SovereignConfig",
    "SovereignDetector",
    "ZoneAggregator",
    "__version__",
]
