// Constitution.swift
//
// Mirror of the Python SV-001..SV-007 constitution, in pure Swift so the
// iOS app can render the rule set offline.
//
// Source of truth: sovereign/rules.py in the parent repository.

import Foundation

public enum RuleAction: String, Codable {
    case redact   = "REDACT"
    case hash     = "HASH"
    case aggregate = "AGGREGATE"
    case block    = "BLOCK"
    case escalate = "ESCALATE"
}

public enum RuleSeverity: String, Codable {
    case critical = "CRITICAL"
    case high     = "HIGH"
    case medium   = "MEDIUM"
}

public struct ConstitutionalRule: Codable, Hashable, Identifiable {
    public var id: String { ruleID }
    public let ruleID: String
    public let name: String
    public let description: String
    public let action: RuleAction
    public let severity: RuleSeverity
    public let legalBasis: String

    enum CodingKeys: String, CodingKey {
        case ruleID = "rule_id"
        case name, description, action, severity
        case legalBasis = "legal_basis"
    }
}

public enum Constitution {
    public static let defaultRules: [ConstitutionalRule] = [
        ConstitutionalRule(
            ruleID: "SV-001",
            name: "Person Coordinate Redaction",
            description: "Raw bounding-box coordinates for detected persons are redacted before any output is generated.",
            action: .redact,
            severity: .critical,
            legalBasis: "GDPR Article 4(1) - Personal Data Definition"
        ),
        ConstitutionalRule(
            ruleID: "SV-002",
            name: "Face Region Cryptographic Hash",
            description: "Any detected face region is SHA-256 hashed. The hash cannot be reversed to reconstruct identity.",
            action: .hash,
            severity: .critical,
            legalBasis: "GDPR Article 9 - Biometric Data"
        ),
        ConstitutionalRule(
            ruleID: "SV-003",
            name: "Individual Track ID Suppression",
            description: "Per-frame track IDs that could enable cross-frame individual identification are never assigned or stored.",
            action: .block,
            severity: .critical,
            legalBasis: "GDPR Recital 30 - Online Identifiers"
        ),
        ConstitutionalRule(
            ruleID: "SV-004",
            name: "Zone Aggregate Only Output",
            description: "All person-related outputs are converted to zone aggregate counts before leaving the pipeline.",
            action: .aggregate,
            severity: .high,
            legalBasis: "GDPR Article 89 - Anonymisation Principle"
        ),
        ConstitutionalRule(
            ruleID: "SV-005",
            name: "Confidence Floor Enforcement",
            description: "Low-confidence person detections are suppressed entirely rather than passed as uncertain PII.",
            action: .block,
            severity: .high,
            legalBasis: "GDPR Article 22 - Automated Decision-Making"
        ),
        ConstitutionalRule(
            ruleID: "SV-006",
            name: "Sensitive Object Class Escalation",
            description: "Sensitive object classes trigger an escalation flag without recording who was holding the object.",
            action: .escalate,
            severity: .medium,
            legalBasis: "Enterprise Safety Protocol"
        ),
        ConstitutionalRule(
            ruleID: "SV-007",
            name: "Differential Privacy on Aggregates",
            description: "Calibrated Laplace noise added to per-zone counts (epsilon=1.0 default, sensitivity=1).",
            action: .aggregate,
            severity: .high,
            legalBasis: "GDPR Article 25 + NIST SP 800-188"
        ),
    ]
}
