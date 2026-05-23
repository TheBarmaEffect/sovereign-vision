# Sovereign Vision - The Constitution

This document is the complete legal specification of the six rules that
ship with Sovereign Vision. Each rule has a stable ID, a legal basis, an
enforcement action, and a severity. The full set is loaded into the
firewall on every session and recorded in every compliance certificate.

| ID | Name | Action | Severity | Legal basis |
|---|---|---|---|---|
| SV-001 | Person Coordinate Redaction | REDACT | CRITICAL | GDPR Article 4(1) |
| SV-002 | Face Region Cryptographic Hash | HASH | CRITICAL | GDPR Article 9 |
| SV-003 | Individual Track ID Suppression | BLOCK | CRITICAL | GDPR Recital 30 |
| SV-004 | Zone Aggregate Only Output | AGGREGATE | HIGH | GDPR Article 89 |
| SV-005 | Confidence Floor Enforcement | BLOCK | HIGH | GDPR Article 22 |
| SV-006 | Sensitive Object Class Escalation | ESCALATE | MEDIUM | Enterprise Safety Protocol |

---

## SV-001 - Person Coordinate Redaction

> **Action**: REDACT &nbsp;·&nbsp; **Severity**: CRITICAL

**Legal basis.** GDPR Article 4(1) defines personal data as *"any
information relating to an identified or identifiable natural person"*.
The European Data Protection Board has consistently held that the spatial
position of a person inside a monitored space constitutes personal data
when combined with the time of observation, because it permits
identification by triangulation with other contextual data (entry logs,
roster, shift schedules, etc).

**What this rule does.** Every detection classified as `person` has its
bounding-box coordinates redacted before any output is produced. The
`RedactedBbox` returned by the redactor is zero-valued by construction;
the original bbox is never stored on any object that outlives the
function call.

**Why this is non-negotiable.** A raw bbox plus a timestamp plus a known
floor plan equals identification. Treating raw bboxes as "just metadata"
is the single most common GDPR failure mode in deployed CV systems.

---

## SV-002 - Face Region Cryptographic Hash

> **Action**: HASH &nbsp;·&nbsp; **Severity**: CRITICAL

**Legal basis.** GDPR Article 9(1) classifies biometric data as a special
category requiring an explicit lawful basis. *Article 4(14)* defines
biometric data as *"personal data resulting from specific technical
processing relating to the physical, physiological or behavioural
characteristics of a natural person which allow or confirm the unique
identification of that natural person, such as facial images"*. Storing
or transmitting a face image is almost always a compliance failure.

**What this rule does.** When the firewall sees a `person` detection, it
extracts the bbox region from the frame, runs the pixel bytes through
SHA-256 with a per-session salt, and stores only the resulting 256-bit
hex digest. The region buffer is consumed by the hasher and immediately
goes out of scope.

**Why a salt.** Without a salt, two sessions on the same hardware could
produce identical hashes for the same person, giving a deterministic
cross-session identifier. The per-session salt breaks that linkage. The
salt is in-memory only - never persisted, never logged.

---

## SV-003 - Individual Track ID Suppression

> **Action**: BLOCK &nbsp;·&nbsp; **Severity**: CRITICAL

**Legal basis.** GDPR Recital 30 explicitly addresses online identifiers
including *"cookies, IP addresses, RFID tags... which may leave traces
which, in particular when combined with unique identifiers, can be used
to create profiles of the natural persons and identify them"*. A
multi-frame track ID is an analogous identifier in the visual domain.

**What this rule does.** Any track ID that the underlying tracker would
otherwise assign is dropped to `None` by the redactor's
`suppress_track_id()` method. Persons are counted within a frame; they
are not tracked across frames.

**Why this is critical.** Track IDs enable behavioural profiling - dwell
time per individual, path through a store, time spent at a shelf - which
all become personal data under GDPR the moment they can be reattached to
an identifiable person (e.g. through CCTV review or floor staff
recognition). Aggregate dwell time computed over anonymous occupancy
counts is fine; per-individual dwell time is not.

---

## SV-004 - Zone Aggregate Only Output

> **Action**: AGGREGATE &nbsp;·&nbsp; **Severity**: HIGH

**Legal basis.** GDPR Article 89 establishes the principle of
anonymisation through aggregation. Once data is aggregated to the point
where individual identification is impossible "by reasonable means", it
is no longer personal data under the regulation.

**What this rule does.** All person-related outputs are converted to zone
aggregate counts before leaving the pipeline. Zones are a coarse 3×3
spatial grid (configurable). The default aggregation window is 5 frames,
preventing the special case of single-frame identification when only one
person is in the scene.

**Note on the wildcard.** SV-004 has `applies_to=("*",)` - it fires for
every detection class, not just persons. This is deliberate: aggregating
sensitive objects (knives, phones) by zone is also a useful enterprise
signal, and the wildcard ensures uniform aggregate-only handling.

---

## SV-005 - Confidence Floor Enforcement

> **Action**: BLOCK &nbsp;·&nbsp; **Severity**: HIGH

**Legal basis.** GDPR Article 22 grants individuals *"the right not to be
subject to a decision based solely on automated processing... which
produces legal effects concerning him or her or similarly significantly
affects him or her"*. An uncertain detection that nonetheless triggers a
compliance event is exactly such a decision.

**What this rule does.** Person detections below the configured
confidence floor (default 0.75) are dropped entirely. They are not
counted in zone occupancy, not used in PPE compliance, not surfaced to
any downstream consumer.

**Design philosophy.** Uncertain identification is worse than no
identification. A low-confidence "person" detection that's actually a
mannequin or a coat rack should never lower the PPE compliance rate.
Sovereign Vision prefers a few false negatives over any false positives.

---

## SV-006 - Sensitive Object Class Escalation

> **Action**: ESCALATE &nbsp;·&nbsp; **Severity**: MEDIUM

**Legal basis.** Internal enterprise safety protocols (OSHA 1910, FAA
Part 139, hospital security). Not a GDPR rule per se - this is a safety
rule that benefits *from* GDPR compliance because it lets safety officers
inspect aggregate events without legal exposure.

**What this rule does.** Detections in the configurable sensitive class
list (default: `knife`, `gun`, `scissors`, `cell phone`, `laptop`) flag
the frame as ESCALATED and record an event in the compliance certificate.
Crucially, the firewall does NOT record who was holding the object or
where they were beyond zone granularity. The escalation is on the *event*,
not the *person*.

---

## Adding custom rules

The constitution is extensible. Define a `ConstitutionalRule` and pass it
to the firewall:

```python
from sovereign.rules import ConstitutionalRule, RuleAction, RuleSeverity, DEFAULT_RULES
from sovereign.firewall import ConstitutionalFirewall

my_rule = ConstitutionalRule(
    rule_id="SV-100",
    name="Loading dock occupancy alert",
    description="Flag when the loading dock zone has > 3 persons simultaneously.",
    applies_to=("person",),
    action=RuleAction.ESCALATE,
    severity=RuleSeverity.MEDIUM,
    legal_basis="OSHA 1910.178 forklift safety",
)

fw = ConstitutionalFirewall(rules=list(DEFAULT_RULES) + [my_rule])
```

`ConstitutionalRule` is `frozen=True`. To change a rule's enforcement,
build a new instance and rebuild the firewall - the running instance
cannot be mutated. This is by design: the rule set in force at
certification time is what the certificate records.

## Reviewing the constitution

Every compliance certificate lists the rule IDs that were in force when
the frame was certified. To re-derive the rules used for a historical
certificate:

```bash
sovereign rules            # print the default constitution
sovereign verify cert.json # verify a session's integrity hash
```

If a regulator asks "what was the system allowed to do on May 22?",
the answer is in the session certificate. There is no second source of
truth.
