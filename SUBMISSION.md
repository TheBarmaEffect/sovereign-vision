# Submission - webAI YOLO26 MLX Build Challenge 2026

**Track:** Enterprise
**Team:** Karthik Barma (solo)
**Project:** Sovereign Vision
**Repo:** https://github.com/TheBarmaEffect/sovereign-vision
**PyPI:** https://pypi.org/project/sovereign-vision/
**Homebrew tap:** https://github.com/TheBarmaEffect/sovereign-vision-tap
**Built during:** May 22-23, 2026 (inside the May 18-24 challenge window)

---

## One-paragraph summary

Sovereign Vision is the first on-device enterprise computer-vision system
that is GDPR-compliant by design, not by policy. It intercepts every
YOLO26 MLX inference and enforces a seven-rule constitutional firewall in
flight: every person bounding box is redacted, every face region is
SHA-256 hashed with a per-session salt, every track ID is dropped to
None, every aggregate output gets calibrated differential-privacy noise
(epsilon = 1.0), and sensitive object classes get escalated without
recording who held them. Each frame issues a self-attested compliance
certificate that chains into a Merkle tree, and the session root can be
anchored to a DigiCert RFC 3161 trusted timestamp so a regulator three
years from now can verify exactly when the session happened. Shipped to
PyPI, a public Homebrew tap, a Chrome extension, an iOS SwiftUI app
scaffold, a macOS menu-bar app, an OBS virtual-camera output, and a
FastAPI REST server. Runs at ~55 FPS on yolo26m on Apple Silicon.
84 tests passing, including 12 constitutional zero-PII proofs.

---

## Map to the 6 judging criteria

### 1. Use of YOLO26 MLX / on-device execution - 20 points

YOLO26 MLX is the **inference layer** of the system and the **only reason
the constitutional firewall works at all**. Here is the architecture
constraint:

> If inference happened in the cloud, raw PII would leave the device
> the moment the camera captured a frame. Any "anonymisation" performed
> by the cloud is therefore liability laundering, not compliance.
> On-device MLX inference is what makes the constitutional firewall a
> privacy guarantee instead of a privacy theatre.

Where to verify:

- [`sovereign/detector.py`](sovereign/detector.py) - `SovereignDetector`
  wraps YOLO26 MLX as the sole inference path. The `detect()` method
  loads `yolo26m.npz` via the official `yolo26mlx.YOLO` API exactly as
  documented in `thewebAI/yolo-mlx`.
- [`sovereign/hardware.py`](sovereign/hardware.py) - detects the M-series
  chip, GPU cores, Neural Engine cores, MLX runtime version, and Metal
  framework presence. Every compliance certificate includes this
  hardware fingerprint so a regulator can verify on-device execution
  after the fact.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) - section 1 explains
  why on-device is the privacy contract, not a performance bonus.
- Tested at **~55 FPS on yolo26m** on Apple M5 Pro (author's deployment
  hardware). Variants yolo26n (170 FPS) through yolo26x (24 FPS) all
  work through the same `SovereignDetector`.

### 2. Demo quality / shipping completeness - 20 points

Sovereign Vision is not a one-script demo. It is a shipped product.

- **PyPI** - `pip install sovereign-vision` works for anyone, anywhere,
  right now. Verified end-to-end on a fresh venv.
- **Homebrew tap** - `brew tap TheBarmaEffect/sovereign-vision-tap && brew install sovereign-vision`
  also live.
- **Ten install channels** total: PyPI, Homebrew, Chrome extension,
  iOS app scaffold, macOS menu-bar app, OBS virtual camera, REST API
  server, GitHub Action, Docker, one-line installer.
- **3-panel premium OpenCV dashboard** rendered with Apple SF Pro fonts
  and the macOS system colour palette (see `assets/demo_screenshot.png`).
- **84 tests** including 12 constitutional zero-PII proofs and
  Hypothesis property tests across 1,000+ randomised frames.
  Run: `pytest tests/ -v`.
- **`sovereign doctor`** command runs environment diagnostics
  (Apple Silicon detected, MLX runtime, Metal, all dependencies).
- **`sovereign init`** is a setup wizard for first-time users.
- **Graceful fallbacks** - if no camera is attached, a deterministic
  synthetic backend kicks in so judges can run the demo on any Mac with
  no hardware setup.

### 3. Impact / usefulness - 20 points

This solves a real, current, frequently-cited blocker for enterprise CV.

- **Manufacturing**: factory-floor PPE compliance under OSHA without
  individual surveillance.
  See [`docs/ENTERPRISE_USE_CASES.md`](docs/ENTERPRISE_USE_CASES.md)
  section 1.
- **Retail**: foot-traffic analytics under CCPA/CPRA without face
  recognition or re-ID.
  See [`docs/ENTERPRISE_USE_CASES.md`](docs/ENTERPRISE_USE_CASES.md)
  section 2.
- **Healthcare**: hospital zone monitoring under HIPAA Safe Harbor.
  See [`docs/ENTERPRISE_USE_CASES.md`](docs/ENTERPRISE_USE_CASES.md)
  section 3.
- **Target user**: enterprise CTOs and compliance officers who have
  ever heard "legal says no" to a CV deployment. The constitutional
  layer is exactly the artifact their legal team needs to say yes.
- **ROI argument** for each scenario is in the use-cases doc with
  specific dollar figures.

### 4. Technical execution - 15 points

- **Type-level privacy guarantee**: the `SovereignDetector.detect()`
  return type is `FirewallResult`, not `list[RawDetection]`. There is
  no API surface that returns raw bbox coordinates. The audited
  side-channel `detect_with_raw_preview()` is opt-in for dashboard
  visualisation only and is documented as such.
- **Cryptographic audit chain**: each frame certificate is hashed with
  SHA-256, chained to the previous frame, and a Merkle root is computed
  at session end. See `sovereign/audit_chain.py`.
- **RFC 3161 trusted timestamping**: the session Merkle root can be
  anchored to a DigiCert public TSA. See `sovereign/notary.py`.
- **Differential privacy**: SV-007 adds calibrated Laplace noise to
  every aggregate before it leaves the firewall. Composes correctly
  under sequential queries. See `sovereign/dp.py`.
- **Multi-camera consensus**: M-of-N firewalls must agree before an
  ESCALATED status is raised. See `sovereign/consensus.py`.
- **Performance**: < 0.5 ms firewall overhead per frame on M5 Pro
  (measured via `MetricsRegistry`).
- **Loophole hardening**: the redactor's fallback path used to encode
  bbox coordinates into the hash input - that was a PII-in-the-hash-
  domain leak. Fixed in v1.1 by replacing the fallback with OS entropy.

### 5. Creativity / originality - 15 points

The Constitutional Firewall idea is **novel**. Existing approaches:

| Existing approach | Why it fails |
|---|---|
| Face-blur SDKs | Person bbox + track ID still leak |
| Cloud anonymisation | PII touches a server before being anonymised |
| Differential privacy bolted on output | The individual identification has already happened upstream |
| Privacy policies | Not enforced by code |

Sovereign Vision's contribution is a **runtime constitutional verifier**
on the inference path itself, modelled directly on the Glass Box Framework
research (Northeastern, Khoury College). Every detection is checked
against an immutable rule set, and every check produces an auditable
event. The result is a Merkle-anchored, self-attested, RFC-3161-anchored
compliance receipt that a regulator can verify three years from now.

No competing YOLO26 build implements this. This is the only entry that
turns YOLO26 MLX into a regulator-friendly artifact.

### 6. Presentation / storytelling - 10 points

- **README** opens with the legal problem in three sentences, gives
  the solution in three more, and offers a 10-second install path
  before any technical content.
- **Word choice was deliberately tightened in v1.1**: "CERTIFIED" was
  replaced with "CLEAR" because no third party certified the frame -
  the firewall self-attests, and the audit chain makes the attestation
  third-party verifiable. See `docs/ARCHITECTURE.md` section 8.
- **Three docs** for three audiences: `docs/ARCHITECTURE.md` for
  engineers, `docs/CONSTITUTIONAL_RULES.md` for compliance leads,
  `docs/ENTERPRISE_USE_CASES.md` for buyers.
- **Threat model** (`docs/THREAT_MODEL.md`) addresses 8 attack vectors
  honestly, including the ones the constitution does not cover.
- **Compliance score** is computed per session (0 to 100) so a CISO
  can read it in five seconds.

---

## What to run if you have 60 seconds

```bash
pip install sovereign-vision
sovereign demo
```

A 3-panel dashboard appears. Left panel shows what YOLO would emit
(person regions tinted red, tagged "PII"). Centre panel shows the
firewall log scrolling with rules firing. Right panel shows the
enterprise output: zone heat map, PPE compliance, latest certificate
hash, GDPR/CCPA/HIPAA badges, and the live Apple Silicon hardware
fingerprint.

Press Q to quit. A session compliance certificate is written to
`certificates/` with the Merkle audit chain anchor.

## What to run if you have five minutes

```bash
git clone https://github.com/TheBarmaEffect/sovereign-vision
cd sovereign-vision
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
pytest tests/ -v             # 84 tests, including 12 constitutional zero-PII proofs
sovereign demo                # full dashboard
sovereign benchmark           # FPS + latency report
sovereign verify certificates/session_*.json     # third-party verify the audit chain
```

---

## Honesty notes

- **AI assistance**: per challenge rules, AI assistants are encouraged.
  I used Claude as a pair-programming assistant during the May 22-23
  build window. All code, design decisions, architecture choices, and
  research connection (Glass Box Framework) are mine. All commits are
  authored under `Karthik Barma <karthik@thebarmaeffect.dev>`. Solo
  team.
- **Pre-existing scaffolding**: none. First commit was May 22, 2026.
  The Glass Box Framework research that motivates the constitutional
  approach pre-dates the challenge, but no Glass Box code was reused -
  Sovereign Vision is a fresh practical instantiation.
- **PyPI token reused**: was used once for the v1.3.0 upload and has
  since been revoked. Future releases will use a project-scoped token.
- **CI workflow file** (`.github/workflows/ci.yml`) is committed locally
  but not pushed because the OAuth token I used to set up `gh` lacked
  the workflow scope. To publish: `gh auth refresh -s workflow && git push`.

---

## Contact

Karthik Barma
MS Artificial Intelligence, Northeastern University, Khoury College of Computer Sciences
GitHub: [@TheBarmaEffect](https://github.com/TheBarmaEffect)
Email: karthik@thebarmaeffect.dev
