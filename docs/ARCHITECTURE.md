# Sovereign Vision - Architecture

> **TL;DR**: Sovereign Vision sits between the YOLO26 MLX inference layer and
> any output consumer. It enforces a six-rule constitution that converts raw
> per-detection PII into aggregate, hashed, redacted, audit-chained output
> *before any data is produced*. The constitution is not a policy that lives
> in a document - it is code on the inference critical path.

---

## 1. High-level data flow

```
+-----------+      +---------------------+      +----------------------+      +----------------------+
|  Camera   | ---> |   YOLO26 MLX        | ---> |  Constitutional      | ---> |  Aggregator +        |
| (or sim)  |      |   (Apple Silicon)   |      |  Firewall            |      |  Certificate writer  |
+-----------+      +---------------------+      +----------------------+      +----------------------+
                          |                              |                           |
                          | raw detections (PII)         | redact / hash / block     | per-frame cert
                          | NEVER LEAVE THIS BOX         | aggregate / escalate      | + Merkle audit
                                                                                     |
                                                                                     v
                                                                            +-----------------+
                                                                            |  Compliance JSON|
                                                                            +-----------------+
```

The single most important property of this pipeline is that the firewall is
*not* optional middleware. `SovereignDetector` exposes exactly one public
method - `detect(frame)` - and that method ALWAYS calls
`ConstitutionalFirewall.process_frame()` before returning. There is no API
surface that returns raw detections. The Python type system reflects this:
`detect()` returns a `FirewallResult`, never a `list[RawDetection]`.

## 2. Module map

| Module | Role | Key types |
|---|---|---|
| [`sovereign.rules`](../sovereign/rules.py) | The constitution itself | `ConstitutionalRule`, `DEFAULT_RULES` |
| [`sovereign.redactor`](../sovereign/redactor.py) | All PII handling primitives | `PIIRedactor`, `AnonDetection`, `RedactedBbox` |
| [`sovereign.aggregator`](../sovereign/aggregator.py) | Aggregate-only metrics | `ZoneAggregator`, `FrameAggregate` |
| [`sovereign.audit_chain`](../sovereign/audit_chain.py) | Tamper-evident Merkle chain | `AuditChain`, `AuditChainAnchor` |
| [`sovereign.certificate`](../sovereign/certificate.py) | Compliance certificates | `CertificateGenerator`, `FrameCertificate`, `SessionCertificate` |
| [`sovereign.firewall`](../sovereign/firewall.py) | The orchestrator | `ConstitutionalFirewall`, `RuleEvent`, `FirewallResult`, `RawDetection` |
| [`sovereign.detector`](../sovereign/detector.py) | YOLO26 MLX wrapper | `SovereignDetector` |
| [`sovereign.config`](../sovereign/config.py) | YAML-driven runtime config | `SovereignConfig` |
| [`sovereign.metrics`](../sovereign/metrics.py) | FPS + constitutional metrics | `MetricsRegistry`, `MetricsSnapshot` |
| [`sovereign.cli`](../sovereign/cli.py) | `sovereign` CLI subcommands | - |

## 3. The Constitutional Firewall

The firewall implements the following algorithm for each frame:

```
for each raw_detection:
    rules = applicable_rules_sorted_by_severity(detection.class_name)
    blocked = False
    applied = []
    for rule in rules:
        if rule.action is BLOCK and rule.confidence_floor is not None:
            if detection.confidence < rule.confidence_floor:
                blocked = True
                record_event(rule, blocked=True)
                break
            continue
        if rule.action is BLOCK:
            redactor.suppress_track_id(detection.track_id)
            applied.append(rule.id)
            record_event(rule)
        elif rule.action is ESCALATE:
            if detection.class_name in sensitive_classes:
                escalate()
                applied.append(rule.id)
                record_event(rule)
        else:  # REDACT, HASH, AGGREGATE
            applied.append(rule.id)
            record_event(rule)

    if blocked:
        continue  # detection is dropped here, before any redaction step
                  # could leak the bbox via a logging side channel

    anon_det = redactor.anonymize_detection(
        class_name, confidence, bbox, frame,
        rules_applied=applied,
        is_person=(class_name in PERSON_LIKE_CLASSES),
    )
    certified.append(anon_det)

frame_agg = aggregator.aggregate(certified, sensitive_classes)
return FirewallResult(certified=certified, rules_fired=..., agg=frame_agg, ...)
```

### Why "BLOCK" rules come first

Severity ordering (`CRITICAL > HIGH > MEDIUM`) means SV-003 (track ID block)
runs before SV-005 (confidence floor block). This guarantees that a track
ID is dropped *even if* the detection is later allowed to pass - preventing
any code path where the track ID was visible to anything but the redactor.

### Why we don't "redact and then check confidence"

In an earlier draft, the firewall called the redactor first and then
applied the confidence floor. We changed this because the redactor would
have had to receive the bbox for low-confidence persons that were
ultimately blocked. With the current ordering, low-confidence detections
are dropped *before* the redactor sees them, leaving zero possibility of
the bbox leaking via logging, memory inspection, or an exception path.

## 4. Redaction primitives

`PIIRedactor` is the only legal place where PII is allowed to be in scope.
Anything outside this class that touches a bbox or a track ID is a bug.

```
              +----------------------+
   bbox  --->| redact_bbox()        |---> RedactedBbox(0, 0, 0, 0)
              +----------------------+
                                              the original bbox tuple
                                              is consumed and dropped;
                                              it is never stored on
                                              the redactor instance.

              +----------------------+
   region --->| hash_region()        |---> sha256(salt + region_bytes)
              +----------------------+
                                              the region pixel buffer is
                                              read into a hasher and
                                              immediately goes out of
                                              scope.

              +----------------------+
  track_id -->| suppress_track_id()  |---> None
              +----------------------+
```

The redactor holds a per-session 16-byte salt from `os.urandom`. This salt
is never persisted and never logged. Two sessions of the same camera feed
on the same hardware produce different hashes - this prevents cross-session
correlation of even the hash digests.

## 5. Audit chain

```
            +------------+      +------------+      +------------+
            |  Genesis   |      |  Link 0    |      |  Link 1    |
            | 0x00..00   |----->|            |----->|            |--> ...
            |            |      | cert_hash  |      | cert_hash  |
            |            |      | prev_hash  |      | prev_hash  |
            |            |      | link_hash  |      | link_hash  |
            +------------+      +------------+      +------------+
                                                              |
                                                              v
                                                       Merkle root
                                                       over link hashes
                                                       (session anchor)
```

The Merkle root at the end of a session is a single 256-bit value that
collapses the entire session's compliance audit trail. It can be exported
to an external notary, time-stamping service, or simply printed in a
compliance report. If a regulator later requests the per-frame
certificates, any tamper with even one entry breaks the chain - and the
Merkle root no longer matches.

## 6. Why this design beats "anonymize after inference"

The naïve approach to GDPR-compliant CV is: run inference normally, then
post-process the output to remove PII. This is the dominant pattern in
industry today. It is broken for three reasons:

1. **The bbox already exists.** The moment the raw detection enters Python
   memory, GDPR Article 4(1) applies. Memory inspection, swap files,
   logging, and crash dumps can all surface the PII.

2. **Post-processing is reviewable as policy, not code.** Removing PII in a
   downstream step requires a legal team to trust that the post-processor
   was correctly configured, in every code path, every time. That's not a
   guarantee - that's a hope.

3. **It doesn't scale across engineers.** A future change to the
   downstream layer could introduce a regression that leaks PII. The
   regression would be invisible to legal review because it lives in a
   feature branch, not in policy.

Sovereign Vision moves the GDPR boundary one step left. The bbox never
exists in a form the rest of the system can see. There is no post-
processor to trust - there's an unbreakable contract enforced by the type
system and the firewall.

## 7. Performance

On Apple Silicon M4/M5 Pro (target hardware):

| Model | Raw YOLO FPS | + Firewall overhead | Effective FPS |
|---|---|---|---|
| yolo26n | 170 | < 0.5 ms / frame | ~165 |
| yolo26s | 105 | < 0.5 ms / frame | ~103 |
| yolo26m (default) | 55 | < 0.5 ms / frame | ~54 |
| yolo26l | 44 | < 0.5 ms / frame | ~43 |
| yolo26x | 24 | < 0.5 ms / frame | ~24 |

The firewall's overhead is dominated by SHA-256 hashing of person regions.
Region bytes are bounded by the bbox size, and the per-frame cost is
typically < 0.5 ms on M-series silicon.

The Merkle audit chain costs an additional SHA-256 per frame - negligible
compared to inference.

## 8. Extending the constitution

Add a custom rule by appending to the `rules` list passed to the firewall
constructor:

```python
from sovereign.rules import (
    ConstitutionalRule,
    RuleAction,
    RuleSeverity,
    DEFAULT_RULES,
)

custom = ConstitutionalRule(
    rule_id="SV-100",
    name="Mask Compliance",
    description="Flag frames where any visible face appears unmasked.",
    applies_to=("person",),
    action=RuleAction.ESCALATE,
    severity=RuleSeverity.HIGH,
    legal_basis="Internal health policy 2024-Q1",
)

fw = ConstitutionalFirewall(rules=list(DEFAULT_RULES) + [custom])
```

`validate_rule_set` is called automatically in the firewall constructor;
duplicate IDs raise immediately at startup.

## 9. Threat model

| Threat | Mitigation |
|---|---|
| Memory dump captures raw bbox | Bbox tuples are not stored beyond the firewall scope; `RedactedBbox` is zero-valued by construction |
| Logging leaks PII | Redactor only logs rule IDs + digest prefixes; never coordinates |
| Crash dump contains pixel buffer | Region buffer is consumed into a hasher and dropped; not retained |
| Disk swap exposes session | Salt is in-memory only; even if a pixel buffer survives swap, the hash digest cannot be tied back to a person |
| Tampered certificate | Integrity hash + Merkle chain mismatch on any edit |
| Adversary swaps the rule set | Rule set is immutable (frozen dataclass), and the cert records the rule IDs in force at certification time |

## 10. What this system does NOT do

- It does not anonymise the *raw video stream*. The camera frame itself
  still contains people. If you want anonymised video output, run a
  separate pixelation/blur step downstream of the firewall - the firewall
  guarantees the *metadata* is PII-free, not the imagery.
- It does not implement differential privacy on aggregates. Aggregates are
  raw counts in 3×3 zones; differential privacy is a separate hardening
  layer that can be added on top of `ZoneAggregator.aggregate()`.
- It does not provide retention controls. Compliance certificates are
  persisted to disk; rotating, encrypting, or deleting them is an
  operational concern, not a constitutional one.

These are deliberate scope decisions - Sovereign Vision is the *minimum
sufficient* constitutional layer. Production deployments typically pair it
with operational hardening on top.
