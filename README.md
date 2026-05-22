# Sovereign Vision

### The first on-device enterprise vision system that is GDPR-compliant by design, not by policy.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![MLX](https://img.shields.io/badge/MLX-Apple%20Silicon-orange.svg)](https://github.com/ml-explore/mlx)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Tests](https://img.shields.io/badge/tests-54%20passing-brightgreen.svg)](tests/)
[![Track](https://img.shields.io/badge/YOLO26%20MLX%20Challenge-Enterprise-purple.svg)](https://github.com/thewebAI/yolo-mlx)
[![Research](https://img.shields.io/badge/Research-Glass%20Box%20Framework-red.svg)](https://github.com/TheBarmaEffect)

![Sovereign Vision 3-panel dashboard](assets/demo_screenshot.png)

> A YOLO26-MLX submission for the **webAI YOLO26 Build Challenge — Enterprise track**.
> Runs entirely on Apple Silicon. Zero cloud. Zero PII. Real audit trail.

---

## The Problem

Enterprises that want to deploy computer vision today hit a legal wall.

GDPR Article 4(1) classifies a person's spatial position as personal data.
Article 9 classifies face data as a special category. Recital 30 captures
track IDs. CCPA and HIPAA add their own layers. Every off-the-shelf
computer-vision system today produces detections that *are* PII by the time
they reach memory — bounding boxes, track IDs, face embeddings — and then
tries to clean them up downstream. Legal teams cannot defend that pattern.

Result: most plants, stores, and hospitals don't deploy CV at all, or pay
for expensive cloud anonymisation pipelines that still create liability
because the PII touched a server.

## The Solution

Sovereign Vision intercepts every YOLO26 inference **before any output
exists** with a **Constitutional Firewall**. Six immutable rules — each
mapped to a specific legal article — redact, hash, block, aggregate, and
escalate detections in flight. Only certified aggregate output (zone
counts, compliance rates, anomaly flags) ever leaves the inference
pipeline.

This is not a policy. This is the type system.

---

## Architecture

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

Full technical walkthrough: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## The Constitution — Six Rules

| ID | Name | Action | Severity | Legal basis |
|---|---|---|---|---|
| **SV-001** | Person Coordinate Redaction | REDACT | CRITICAL | GDPR Article 4(1) |
| **SV-002** | Face Region Cryptographic Hash | HASH | CRITICAL | GDPR Article 9 |
| **SV-003** | Individual Track ID Suppression | BLOCK | CRITICAL | GDPR Recital 30 |
| **SV-004** | Zone Aggregate Only Output | AGGREGATE | HIGH | GDPR Article 89 |
| **SV-005** | Confidence Floor Enforcement | BLOCK | HIGH | GDPR Article 22 |
| **SV-006** | Sensitive Object Class Escalation | ESCALATE | MEDIUM | Enterprise Safety Protocol |

Full rule specification with legal commentary: [docs/CONSTITUTIONAL_RULES.md](docs/CONSTITUTIONAL_RULES.md).

---

## What the Enterprise Gets

**Exists in the output:**
- Zone occupancy counts (3x3 aggregated grid)
- PPE compliance rate (rolling window)
- Active zones, hotspot zones (top-K)
- Aggregate dwell time (per zone, never per person)
- Sensitive object escalation flags
- Per-frame compliance certificate (SHA-256 integrity hash)
- Per-session Merkle audit anchor

**NEVER exists, anywhere, ever:**
- Individual bounding-box coordinates
- Face image or embedding
- Multi-frame track IDs
- Person-level dwell time
- Any data on any server (it's all on-device)

---

## Live Demo

![Sovereign Vision dashboard](assets/demo_screenshot.png)

Three panels, live:

1. **RAW INFERENCE** — what YOLO sees. Person regions tagged "! PII" and
   visibly contained to this panel only.
2. **CONSTITUTIONAL FIREWALL** — every rule firing in real time, with an
   amber/green/red status badge and a rolling per-second histogram.
3. **CERTIFIED ENTERPRISE OUTPUT** — the only thing your compliance team
   sees: zone heatmap, PPE compliance, certificate hash, GDPR coverage
   badges, LIVE/ON-DEVICE/ZERO-CLOUD indicator.

A parallel Rich-powered terminal dashboard runs in the same process so
screen recordings look great even with the terminal in view.

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

# 4. Run the full demo
python demo/run_demo.py
# press Q in the window (or Ctrl+C) to quit and seal the session certificate
```

If you don't have a camera attached, the system falls back to a synthetic
camera automatically — judges can run the demo on any Mac with no
hardware setup.

Headless run for CI / screen recording:

```bash
python demo/run_demo.py --headless --max-frames 300 --write-frame-certs
```

CLI:

```bash
sovereign info                # version + rule summary
sovereign rules               # full constitutional rule set as JSON
sovereign verify path/to/session.json     # check integrity hash
sovereign benchmark --frames 500          # FPS + latency benchmark
```

---

## Hardware

Apple MacBook Pro — Apple Silicon (M-series). Fully on-device. Zero cloud.

The MLX runtime is exclusive to Apple Silicon; runs on Intel Macs and
Linux via the simulation backend so CI can verify the constitution.

---

## Model Variant

`yolo26m` is the default for the enterprise demo (good detection quality,
~55 FPS on M-series). `yolo26n` is available for latency-critical mode
(~165 FPS). `yolo26l` / `yolo26x` available for high-quality offline
analysis.

---

## Performance

Benchmarked on an Apple M4 Pro (reference; M5 Pro will be similar or faster):

| Model | Raw YOLO FPS | Firewall overhead | Effective FPS |
|---|---|---|---|
| yolo26n | 170 | < 0.5 ms / frame | ~165 |
| yolo26s | 105 | < 0.5 ms / frame | ~103 |
| **yolo26m (default)** | **55** | **< 0.5 ms / frame** | **~54** |
| yolo26l | 44 | < 0.5 ms / frame | ~43 |
| yolo26x | 24 | < 0.5 ms / frame | ~24 |

Pure firewall throughput (simulation backend, no model inference) measured at **>460 FPS** on the same hardware — the constitution is not a bottleneck.

```
$ sovereign benchmark --frames 300
{
  "frames": 300,
  "fps_actual": 467.92,
  "avg_inference_ms": 0.0048,
  "avg_firewall_ms": 0.0507,
  "rules_per_frame": 11.54,
  "status_mix": {"CERTIFIED": 203, "ESCALATED": 65, "BLOCKED": 32}
}
```

---

## Enterprise Use Cases

**Manufacturing — PPE compliance.** Continuous, aggregate-only PPE
monitoring across the floor. OSHA-grade evidence without GDPR exposure
or union friction.

**Retail — Foot traffic analytics.** Dwell time, hotspots, conversion
correlation, with zero individual tracking. No loyalty card, no cookie,
no face recognition. CCPA-clean by design.

**Healthcare — Hospital zone monitoring.** ED flow, ICU coverage,
sensitive-area access alerts. HIPAA Safe Harbor satisfied at the
algorithm layer.

Full scenarios: [docs/ENTERPRISE_USE_CASES.md](docs/ENTERPRISE_USE_CASES.md).

---

## The Research Foundation

Sovereign Vision is a practical instantiation of the **Glass Box Framework**, a
runtime constitutional AI verification system under active research at
**Northeastern University's Khoury College of Computer Sciences**. The
Constitutional Firewall implements the core Glass Box thesis: AI systems
operating in high-stakes environments must have verifiable, auditable
decision rules that can be inspected, challenged, and certified in real time.
Every detection in Sovereign Vision undergoes constitutional review before it
becomes an official output. The session compliance certificate is a Glass Box
artifact — proof that the system operated within its constitutional bounds
for the entire session.

---

## Why On-Device Matters Here

This is not a performance optimisation. On-device is the privacy guarantee.

Data that never leaves the device cannot be:
- Breached (no server to hack)
- Subpoenaed (no data controller to compel)
- Sold (no telemetry pipeline to monetise)
- Mis-configured into a public S3 bucket
- Reused for a purpose the user didn't consent to

The MLX runtime makes this practical at production frame rates on
consumer Apple hardware. Sovereign Vision is the constitutional layer
that makes it *legally usable*.

---

## Constitutional Proofs

The repository ships with executable proofs of the zero-PII guarantee.
Run them with:

```bash
pytest tests/test_firewall.py -v
```

The suite includes:

| Test | Proves |
|---|---|
| `test_person_bbox_never_in_output` | SV-001: person bboxes are zero-coord in every cert |
| `test_face_hash_is_irreversible` | SV-002: face hashes are SHA-256 hex, distinct per region |
| `test_track_id_always_none_for_persons` | SV-003: track IDs always None in output |
| `test_low_confidence_blocked` | SV-005: < 0.75 confidence persons dropped entirely |
| `test_certificate_integrity_hash_changes_on_edit` | Tamper detection works |
| `test_audit_chain_verifies` | Multi-frame Merkle chain integrity |
| `test_zero_pii_guarantee_100_frames` | **Master proof: 100 random frames, scans every cert for PII fingerprints, asserts zero hits.** |

All 54 tests pass in under half a second:

```
$ pytest tests/ -v
============================== 54 passed in 0.41s ==============================
```

---

## Project Layout

```
sovereign-vision/
+- sovereign/              # core Python package
|  +- rules.py             # the 6 constitutional rules
|  +- redactor.py          # PII redaction primitives (the only legal PII surface)
|  +- aggregator.py        # aggregate-only zone metrics
|  +- firewall.py          # the orchestrator
|  +- certificate.py       # per-frame and per-session compliance certs
|  +- audit_chain.py       # Merkle-chained audit trail
|  +- detector.py          # YOLO26 MLX wrapper (firewall-mandatory)
|  +- config.py            # YAML config
|  +- metrics.py           # perf + constitutional metrics, Prometheus export
|  +- cli.py               # `sovereign` CLI
+- dashboard/              # 3-panel OpenCV UI + Rich terminal dashboard
|  +- panels/
|  |  +- raw_panel.py
|  |  +- firewall_panel.py
|  |  +- certified_panel.py
|  +- app.py
|  +- styles.py
+- demo/                   # end-to-end demo + scenario configs
|  +- run_demo.py
|  +- simulate_webcam.py
|  +- scenarios/
+- tests/                  # 54 tests including the constitutional proofs
+- docs/                   # architecture, rules spec, use cases
+- benchmarks/             # FPS + dashboard rendering benchmarks
+- assets/                 # screenshots, diagrams
```

---

## Open Source

Sovereign Vision is licensed under **AGPL-3.0**, matching the YOLO26 MLX
upstream. The constitutional rule set is part of the licensed work — any
modification offered over a network must publish its rule changes.

Privacy infrastructure should be inspectable.

---

## Author

**Karthik Barma**
MS Artificial Intelligence — Northeastern University, Khoury College of Computer Sciences
Active research: Glass Box Framework
[github.com/TheBarmaEffect](https://github.com/TheBarmaEffect)

---

## Acknowledgments

- **Fatih Altay** and the webAI team for YOLO26 MLX, the foundation that
  makes this demo possible at on-device speeds.
- **Hossein Moghimifam** for years of public arguments that *sovereign
  AI* is not just a tagline — it's a contract.

If you build on this work, please open an issue. The constitution is
public for a reason.
