<div align="center">

# Sovereign Vision

### The first on-device enterprise vision system that is GDPR-compliant by design, not by policy.

![Sovereign Vision dashboard](assets/demo_screenshot.png)

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![MLX](https://img.shields.io/badge/MLX-Apple%20Silicon-FF9F0A.svg)](https://github.com/ml-explore/mlx)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-0A84FF.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Tests](https://img.shields.io/badge/tests-77%20passing-30D158.svg)](tests/)
[![Constitution](https://img.shields.io/badge/constitution-SV--001..SV--007-FF453A.svg)](docs/CONSTITUTIONAL_RULES.md)
[![Apple Silicon](https://img.shields.io/badge/Apple%20Silicon-M-series-000000.svg)](https://www.apple.com/mac/)
[![Track](https://img.shields.io/badge/YOLO26%20MLX%20Challenge-Enterprise-BF5AF2.svg)](https://github.com/thewebAI/yolo-mlx)
[![Research](https://img.shields.io/badge/Research-Glass%20Box%20Framework-30D158.svg)](https://github.com/TheBarmaEffect)

**Built by [Karthik Barma](https://github.com/TheBarmaEffect)**
MS Artificial Intelligence  ·  Northeastern University, Khoury College of Computer Sciences
Research: Glass Box Framework  ·  Runtime constitutional AI verification

</div>

---

## The Problem

Enterprises that want to deploy computer vision today hit a legal wall.

GDPR Article 4(1) classifies a person's spatial position as personal data.
Article 9 covers face data as a special category. Recital 30 covers track
IDs. CCPA and HIPAA add their own layers. Every off-the-shelf CV system
on the market today produces detections that are PII the moment they
reach memory: bounding boxes, track IDs, face embeddings. Then it tries
to clean them up downstream. Legal teams cannot defend that pattern.

Result: most plants, stores, and hospitals do not deploy CV at all, or
pay for expensive cloud anonymisation pipelines that still create
liability because the PII touched a server.

## The Solution

Sovereign Vision intercepts every YOLO26 inference **before any output
exists** with a **Constitutional Firewall**. Seven immutable rules,
each mapped to a specific legal article, redact, hash, block, aggregate,
escalate, and noise detections in flight. Only aggregate output, with
calibrated differential-privacy noise on per-zone counts, ever leaves
the inference pipeline.

This is not a policy. This is the type system.

---

## Architecture

![Architecture diagram](assets/architecture.png)

Full technical walkthrough: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
Adversary model: [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md).

---

## The Constitution: Seven Rules

| ID | Name | Action | Severity | Legal basis |
|---|---|---|---|---|
| **SV-001** | Person Coordinate Redaction | REDACT | CRITICAL | GDPR Article 4(1) |
| **SV-002** | Face Region Cryptographic Hash | HASH | CRITICAL | GDPR Article 9 |
| **SV-003** | Individual Track ID Suppression | BLOCK | CRITICAL | GDPR Recital 30 |
| **SV-004** | Zone Aggregate Only Output | AGGREGATE | HIGH | GDPR Article 89 |
| **SV-005** | Confidence Floor Enforcement | BLOCK | HIGH | GDPR Article 22 |
| **SV-006** | Sensitive Object Class Escalation | ESCALATE | MEDIUM | Enterprise Safety Protocol |
| **SV-007** | Differential Privacy on Aggregates | AGGREGATE | HIGH | GDPR Article 25 + NIST SP 800-188 |

Full rule specification with legal commentary: [docs/CONSTITUTIONAL_RULES.md](docs/CONSTITUTIONAL_RULES.md).

---

## Word choice matters

Sovereign Vision is careful about who said what.

- **"Compliance certificate"** = a JSON file the system itself issues. It
  is *self-attested*, not third-party-certified. The integrity hash and
  Merkle audit anchor are what make the claim *verifiable by a third
  party after the fact*.
- **Frame status `CLEAR`** = the frame passed every constitutional rule
  in force. We deliberately do not use `CERTIFIED` (loaded language).
- **`ESCALATED`** = a sensitive-class rule fired. The frame still passes,
  but a flag is recorded.
- **`BLOCKED`** = a critical rule rejected one or more detections in this
  frame. No partial PII leaked.
- **"Audit-verifiable"** = a third party can re-derive the integrity
  hash and Merkle chain to detect tampering. They are not endorsing the
  rule set; they are confirming the rule set was applied without
  modification.

---

## What the Enterprise Gets

**Exists in the output:**
- Zone occupancy counts (3x3 aggregated grid, with SV-007 DP noise)
- PPE compliance rate (rolling window)
- Active zones, hotspot zones (top-K)
- Aggregate dwell time (per zone, never per person)
- Sensitive object escalation flags
- Per-frame compliance certificate (SHA-256 integrity hash)
- Per-session Merkle audit anchor
- Hardware fingerprint (chip, MLX version, OS) in the session cert

**NEVER exists, anywhere, ever:**
- Individual bounding-box coordinates
- Face image or embedding
- Multi-frame track IDs
- Person-level dwell time
- Any data on any server (it is all on-device)

---

## Built for Apple Silicon

Sovereign Vision runs natively on Apple Silicon (M1 through M5) via
[MLX](https://github.com/ml-explore/mlx). The dashboard surfaces the
exact hardware fingerprint on every render, and the session certificate
records it for the audit trail:

```
Apple M5 Pro  ·  5P+10E  ·  18 GPU  ·  16 Neural Engine  ·  24 GB unified
```

- Inference runs on the GPU + Neural Engine through MLX (zero CUDA, zero TensorFlow)
- The Constitutional Firewall runs on the performance cores (sub-millisecond per frame)
- All certificates are written to the host SSD; no telemetry, no cloud, no fallback path

There is a non-Apple-Silicon simulation backend used for CI on Linux and
Intel Macs. It cannot be used in production - the `--production` flag
of `run_demo.py` refuses to start when MLX is unavailable.

---

## Live Demo

![Sovereign Vision dashboard](assets/demo_screenshot.png)

Three panels, live:

1. **RAW INFERENCE** (left). What YOLO26 sees, with person regions
   visibly tagged "PII". This panel is suppressed entirely in
   `--production` mode.
2. **CONSTITUTIONAL FIREWALL** (center). The seven rules firing in real
   time. Each event card carries a timestamp, rule id, action, and
   status. Status badge at the top reflects the latest frame.
3. **ENTERPRISE OUTPUT** (right). What a compliance team actually sees:
   3x3 zone heat map (with DP noise), PPE compliance, latest cert hash,
   legal coverage badges, and the LIVE / ON-DEVICE / ZERO CLOUD
   indicator with the live hardware fingerprint.

A parallel Rich-powered terminal dashboard runs in the same process so
screen recordings look great even with the terminal in view.

A standalone **HTML certificate viewer** at [`tools/cert_viewer.html`](tools/cert_viewer.html)
lets anyone drop a `session_*.json` into a browser to re-verify the
integrity hash and Merkle chain offline. No server, no upload.

---

## How to Run

```bash
# 1. Clone Sovereign Vision and the YOLO26 MLX base model
git clone https://github.com/TheBarmaEffect/sovereign-vision.git
cd sovereign-vision
git clone https://github.com/thewebAI/yolo-mlx.git    # base model repo

# 2. Set up the venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ./yolo-mlx
pip install -e ./yolo-mlx[convert]

# 3. Pull and convert YOLO26 weights to MLX
cd yolo-mlx
bash scripts/download_yolo26_models.sh
yolo26 converters convert models/yolo26m.pt -o ../models/yolo26m.npz --verify
cd ..

# 4. Run the live demo (presenter mode, all three panels)
python demo/run_demo.py

# 5. Or production mode (left panel suppressed, no raw-preview side channel)
python demo/run_demo.py --production

# Press Q in the window to quit and seal the session certificate.
```

If no camera is attached, the system falls back to a synthetic feed
automatically. Judges can run the demo on any Mac with no hardware setup.

CLI:

```bash
sovereign info                                     # version + rule summary
sovereign rules                                    # full constitution as JSON
sovereign verify certificates/session_*.json       # check integrity hash
sovereign benchmark --frames 500                   # FPS + latency benchmark
```

---

## Performance

Benchmarked on Apple M5 Pro (the author's deployment hardware) and M4 Pro
(reference; numbers are similar):

| Model | Raw YOLO FPS | Firewall overhead | Effective FPS |
|---|---|---|---|
| yolo26n | 170 | < 0.5 ms / frame | ~165 |
| yolo26s | 105 | < 0.5 ms / frame | ~103 |
| **yolo26m (default)** | **55** | **< 0.5 ms / frame** | **~54** |
| yolo26l | 44 | < 0.5 ms / frame | ~43 |
| yolo26x | 24 | < 0.5 ms / frame | ~24 |

Pure firewall throughput on the simulation backend (the constitution by
itself, no real model): **>460 FPS**. The constitution is not a
bottleneck.

```
$ sovereign benchmark --frames 300
{
  "frames": 300,
  "fps_actual": 467.92,
  "avg_inference_ms": 0.0048,
  "avg_firewall_ms": 0.0507,
  "rules_per_frame": 11.54,
  "status_mix": {"CLEAR": 203, "ESCALATED": 65, "BLOCKED": 32}
}
```

---

## Enterprise Use Cases

**Manufacturing - PPE compliance.** Continuous, aggregate-only PPE
monitoring across the floor. OSHA-grade evidence without GDPR exposure
or union friction.

**Retail - Foot traffic analytics.** Dwell time, hotspots, conversion
correlation, with zero individual tracking. No loyalty card, no cookie,
no face recognition. CCPA-clean by design.

**Healthcare - Hospital zone monitoring.** ED flow, ICU coverage,
sensitive-area access alerts. HIPAA Safe Harbor satisfied at the
algorithm layer.

Full scenarios: [docs/ENTERPRISE_USE_CASES.md](docs/ENTERPRISE_USE_CASES.md).

---

## The Research Foundation

Sovereign Vision is a practical instantiation of the **Glass Box
Framework**, a runtime constitutional AI verification system under
active research at **Northeastern University's Khoury College of
Computer Sciences**. The Constitutional Firewall implements the core
Glass Box thesis: AI systems operating in high-stakes environments must
have verifiable, auditable decision rules that can be inspected,
challenged, and certified in real time. Every detection in Sovereign
Vision undergoes constitutional review before it becomes an official
output. The session compliance certificate is a Glass Box artifact:
proof that the system operated within its constitutional bounds for the
entire session.

---

## Why On-Device Matters Here

This is not a performance optimisation. On-device is the privacy
guarantee.

Data that never leaves the device cannot be:
- Breached (no server to hack)
- Subpoenaed (no data controller to compel)
- Sold (no telemetry pipeline to monetise)
- Mis-configured into a public S3 bucket
- Reused for a purpose the data subject did not consent to

MLX makes this practical at production frame rates on consumer Apple
hardware. Sovereign Vision is the constitutional layer that makes it
*legally usable*.

---

## Constitutional Proofs

The repository ships with executable proofs of the zero-PII guarantee.

```bash
pytest tests/test_firewall.py tests/test_firewall_property.py -v
```

Key proofs:

| Test | Proves |
|---|---|
| `test_person_bbox_never_in_output` | SV-001: person bboxes are zero-coord in every cert |
| `test_face_hash_is_irreversible` | SV-002: face hashes are SHA-256 hex, distinct per region |
| `test_track_id_always_none_for_persons` | SV-003: track IDs always None in output |
| `test_low_confidence_blocked` | SV-005: < 0.75 confidence persons dropped entirely |
| `test_certificate_integrity_hash_changes_on_edit` | Tamper detection works |
| `test_audit_chain_verifies` | Multi-frame Merkle chain integrity |
| `test_audited_side_channel_does_not_double_invoke_predict` | Audited raw-preview is single-shot |
| `test_detector_does_not_retain_raw_between_calls` | Detector holds no raw refs |
| `test_property_no_track_id_in_output` | Hypothesis: 200 random inputs, no track id leaks |
| `test_property_zone_counts_non_negative` | Hypothesis: DP-noised counts always >= 0 |
| `test_zero_pii_guarantee_100_frames` | **Master proof: 100 random frames, scans every cert byte for PII fingerprints.** |

All 77 tests pass in under one second:

```
$ pytest tests/ -v
============================== 77 passed in 0.90s ==============================
```

To run just the constitutional release-gate proofs:
```bash
pytest tests/ -m constitutional -v
```

---

## Project Layout

```
sovereign-vision/
+- sovereign/                 # core Python package
|  +- rules.py                # the 7 constitutional rules
|  +- redactor.py             # the only legal surface for PII
|  +- aggregator.py           # aggregate-only zone metrics
|  +- firewall.py             # the orchestrator
|  +- certificate.py          # self-attested compliance certificates
|  +- audit_chain.py          # tamper-evident Merkle chain
|  +- detector.py             # YOLO26 MLX wrapper (firewall-mandatory)
|  +- dp.py                   # SV-007 Laplace mechanism
|  +- hardware.py             # Apple Silicon introspection
|  +- config.py               # YAML config
|  +- metrics.py              # perf + constitutional metrics
|  +- cli.py                  # `sovereign` CLI
+- dashboard/                 # 3-panel OpenCV UI + Rich terminal dashboard
|  +- typography.py           # PIL/SF Pro premium text rendering
|  +- gfx.py                  # rounded rects, gradients, soft glow
|  +- styles.py               # Apple-inspired palette
|  +- panels/
|     +- raw_panel.py
|     +- firewall_panel.py
|     +- certified_panel.py
|  +- app.py
+- demo/                      # end-to-end demo + scenario configs
+- tests/                     # 77 tests including constitutional proofs + hypothesis
+- docs/
|  +- ARCHITECTURE.md
|  +- CONSTITUTIONAL_RULES.md
|  +- ENTERPRISE_USE_CASES.md
|  +- THREAT_MODEL.md
+- benchmarks/                # FPS, dashboard render, architecture diagram
+- tools/                     # cert_viewer.html browser-side verifier
+- configs/                   # YAML scenario configs
+- assets/                    # screenshots, architecture diagram
```

---

## Open Source

Sovereign Vision is licensed under **AGPL-3.0**, matching the YOLO26 MLX
upstream. The constitutional rule set is part of the licensed work: any
modification offered over a network must publish its rule changes.

Privacy infrastructure should be inspectable.

---

## About the Author

**Karthik Barma** ·  MS Artificial Intelligence  ·  Northeastern University, Khoury College of Computer Sciences

I build runtime-verifiable AI systems for high-stakes environments. My
research thesis - the **Glass Box Framework** - argues that production
AI in regulated industries needs constitutional layers that can be
inspected and audited in real time, not just policy documents. Sovereign
Vision is one practical instantiation of that framework, applied to
computer vision on Apple Silicon.

If you are building enterprise AI in a regulated industry (finance,
healthcare, manufacturing, retail, public sector) and want to talk
about constitutional verification, runtime audit, or the privacy
guarantees of on-device inference, please reach out.

- GitHub: [@TheBarmaEffect](https://github.com/TheBarmaEffect)
- This project: [github.com/TheBarmaEffect/sovereign-vision](https://github.com/TheBarmaEffect/sovereign-vision)

---

## Acknowledgments

- **Fatih Altay** and the webAI team for YOLO26 MLX, the foundation that
  makes this demo possible at on-device speeds.
- **Hossein Moghimifam** for years of public arguments that *sovereign
  AI* is not just a tagline, it is a contract.

If you build on this work, open an issue. The constitution is public for
a reason.
