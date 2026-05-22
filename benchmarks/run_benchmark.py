"""Synthetic benchmark for Sovereign Vision.

Runs N frames through the firewall using the simulation backend and reports
FPS, mean inference latency, mean firewall latency, and rule throughput.

Usage:
    python benchmarks/run_benchmark.py --frames 500
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from sovereign.certificate import CertificateGenerator
from sovereign.detector import SovereignDetector
from sovereign.firewall import ConstitutionalFirewall
from sovereign.metrics import MetricsRegistry


def run_benchmark(n_frames: int = 300, model_path: str = "models/yolo26m.npz") -> dict:
    fw = ConstitutionalFirewall()
    gen = CertificateGenerator(session_id=fw.session_id)
    metrics = MetricsRegistry()
    detector = SovereignDetector(model_path=Path(model_path), firewall=fw)

    rng = np.random.default_rng(0)
    start = time.perf_counter()
    for _ in range(n_frames):
        frame = rng.integers(0, 255, size=(720, 1280, 3), dtype=np.uint8)
        result = detector.detect(frame)
        gen.generate_frame_cert(result, rules=list(fw.rules))
        metrics.record(result)
    elapsed = time.perf_counter() - start

    snap = metrics.snapshot()
    return {
        "frames": n_frames,
        "wall_seconds": round(elapsed, 3),
        "fps_actual": round(n_frames / elapsed, 2) if elapsed > 0 else 0.0,
        "avg_inference_ms": snap.avg_inference_ms,
        "avg_firewall_ms": snap.avg_firewall_ms,
        "total_rules_fired": snap.total_rules_fired,
        "rules_per_frame": round(snap.total_rules_fired / n_frames, 2),
        "redactions": snap.total_redactions,
        "status_mix": {
            "CERTIFIED": snap.status_certified,
            "ESCALATED": snap.status_escalated,
            "BLOCKED": snap.status_blocked,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=300)
    parser.add_argument("--model", type=str, default="models/yolo26m.npz")
    args = parser.parse_args()
    print(json.dumps(run_benchmark(args.frames, args.model), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
