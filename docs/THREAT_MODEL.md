# Sovereign Vision - Threat Model

This document captures the adversarial assumptions Sovereign Vision was
designed against, the mitigations in place, and the threats that are
explicitly out of scope. If you are deploying this in a regulated
environment, read this before going to production.

---

## 1. Adversary classes

We consider four adversaries:

| ID | Adversary | Capability |
|---|---|---|
| **A1** | Curious operator | Has shell access to the host. Wants to identify a specific person from the certificate stream. |
| **A2** | Compromised application | A non-firewall process on the same host has been compromised and can read process memory. |
| **A3** | Internal compliance auditor | Receives the session certificate after the run. Tries to identify an individual from the certificate. |
| **A4** | External regulator / lawyer | Subpoenas the certificate archive. Tries to disprove a claim about the session. |

We do NOT defend against:

- Adversaries with physical access to the camera at capture time (they can see the person directly).
- Nation-state side-channel attacks against the silicon (out of scope).
- Operators who replace the rule set before a session starts (they will fail audit verification, but the certificate is honest about which rules ran).

---

## 2. Asset inventory

| Asset | Sensitivity | Storage |
|---|---|---|
| Camera frame buffer | PII | RAM only, life of a single inference call |
| Raw bounding boxes | PII | RAM only, dropped at end of `_detect_with_raw` |
| Face region pixels | Special category PII (GDPR Art 9) | RAM only, consumed by hasher |
| Track IDs | Quasi-identifier | NEVER materialise as output |
| Frame certificate (JSON) | Aggregate-only, AGGREGATE-DP-noisy | Disk (`certificates/`) |
| Session certificate (JSON) | Aggregate-only + Merkle anchor | Disk (`certificates/`) |
| Audit chain Merkle root | Public-safe | Suitable for external notarisation |
| Session salt | Secret | RAM only, never persisted |

---

## 3. STRIDE walkthrough

### Spoofing
- **Threat**: an adversary tries to issue a fake compliance certificate.
- **Mitigation**: every certificate includes an integrity hash computed
  over its payload with sorted keys. The hash is bound to the audit
  chain link, which is bound to the prior link via SHA-256. A fake
  certificate would have to be inserted into the chain mid-stream, which
  the verifier detects at the next `audit_chain.verify()`.

### Tampering
- **Threat**: someone edits a frame certificate after the fact.
- **Mitigation**: editing any field changes its integrity hash. The
  integrity hash is part of the inputs to the next link's hash. The
  Merkle root at session end no longer matches. `sovereign verify` will
  report `FAILED: integrity hash mismatch`.

### Repudiation
- **Threat**: a deployer denies that a specific certificate came from
  Sovereign Vision.
- **Mitigation**: the session certificate records the hardware
  fingerprint (chip name, generation, core counts, MLX version) at the
  time of issuance. This is not non-repudiation in the legal sense, but
  it raises the cost of a false-denial significantly.

### Information disclosure
- **Threat (A1)**: operator reads the frame certificate hoping to find
  bbox coordinates of a specific individual.
  - **Mitigation**: the `pii_guarantee` block declares
    `individual_bboxes_stored: false`; the master test
    `test_zero_pii_guarantee_100_frames` is an executable proof of the
    claim. No coordinates ever enter the certificate payload.
- **Threat (A2)**: compromised co-process reads firewall memory.
  - **Mitigation**: raw bboxes are local to `_detect_with_raw`. The
    region pixel buffer is consumed by SHA-256 and goes out of scope. We
    cannot prevent a privileged adversary from snapshotting RAM during
    a frame, but we minimise the window: bbox lifetime is microseconds.
- **Threat (A3)**: auditor tries to re-identify by triangulating zone
  counts against a known schedule.
  - **Mitigation**: SV-007 applies (epsilon=1.0)-DP Laplace noise to
    every zone count, formally bounding the success probability under
    composition. The session certificate records cumulative epsilon.

### Denial of service
- **Threat**: adversary crashes the firewall to bypass it.
- **Mitigation**: the firewall has no public "skip" path. If it crashes,
  `SovereignDetector.detect` raises and no output is produced for that
  frame. There is no graceful degradation that emits raw detections.

### Elevation of privilege
- **Threat**: adversary loads a custom rule set that disables redaction.
- **Mitigation**: the rule set in force is recorded by ID and severity
  in every certificate. A regulator can see which rules were active. A
  "neutered" rule set is still self-attested but fails external review.

---

## 4. The audited side channel

The dashboard's left panel displays raw bounding boxes for the demo. To
prevent a double-inference path (predicting twice for the same frame),
this is implemented as the `SovereignDetector.detect_with_raw_preview()`
method, which:

  1. Runs `predict()` exactly once.
  2. Returns both the firewall result and a defensive copy of the raw
     detection list.
  3. Is explicitly documented as DEMO ONLY.

In production deployments, run `python demo/run_demo.py --production`.
This suppresses the left panel and refuses to call the side channel.
This is enforced by a flag on the call site, not by code in the side
channel itself (the side channel could not safely refuse without
introducing a different bypass path).

---

## 5. Out of scope

The following are not Sovereign Vision's responsibility, but are
relevant to a full deployment.

- **Camera link encryption**: the camera-to-host transport is the
  operator's responsibility. We recommend USB or wired Ethernet.
- **Disk encryption**: certificates on disk are aggregate-only and
  DP-noisy, so they have low residual risk, but for defense in depth
  enable FileVault on the host.
- **Retention policy**: certificates persist until manually deleted. A
  production deployment should have a documented retention window and
  delete certificates older than that window.
- **Operator authentication**: anyone with shell access can re-run the
  pipeline. Use macOS account separation if multiple operators share
  the host.

---

## 6. Deployment checklist

Before deploying Sovereign Vision in a regulated environment, confirm:

- [ ] `python demo/run_demo.py --production` is used (not the demo mode)
- [ ] FileVault enabled on the host
- [ ] Operator account has a strong password
- [ ] `certificates/` directory has a retention policy
- [ ] Merkle root from the session certificate is forwarded to an
      external timestamping or notary service (e.g. RFC 3161)
- [ ] `pytest tests/test_firewall.py -m constitutional` passes on the
      exact build deployed
- [ ] The constitution document (`docs/CONSTITUTIONAL_RULES.md`) is
      reviewed and approved by your legal team
- [ ] The deployed model file (`.npz`) hash is recorded
- [ ] Camera feed does not bypass the host (no parallel recording)

---

## 7. Reporting a vulnerability

If you find a privacy bug, please open a private GitHub security advisory
at [github.com/TheBarmaEffect/sovereign-vision/security](https://github.com/TheBarmaEffect/sovereign-vision/security)
or email karthik@thebarmaeffect.dev directly. We will respond within
72 hours.

Privacy infrastructure should be inspectable. If you find a hole, the
expectation is that we close it together.
