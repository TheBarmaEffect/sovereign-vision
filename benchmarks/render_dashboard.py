"""Render a one-shot dashboard screenshot for the README / assets.

Runs the simulation pipeline for a configurable number of warm-up frames so
the dashboard has populated event logs, zone occupancy, and certificate
hashes; then writes assets/demo_screenshot.png.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from dashboard.app import DashboardContext, composite_frame, ingest
from demo.simulate_webcam import SyntheticCamera
from sovereign.certificate import CertificateGenerator
from sovereign.detector import SovereignDetector
from sovereign.firewall import ConstitutionalFirewall
from sovereign.metrics import MetricsRegistry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("assets/demo_screenshot.png"))
    parser.add_argument("--warmup-frames", type=int, default=60)
    args = parser.parse_args()

    fw = ConstitutionalFirewall()
    cert_gen = CertificateGenerator(session_id=fw.session_id)
    metrics = MetricsRegistry()
    detector = SovereignDetector(model_path=Path("models/yolo26m.npz"), firewall=fw)
    cam = SyntheticCamera()
    ctx = DashboardContext(firewall=fw, cert_gen=cert_gen, metrics=metrics, model_name="yolo26m")

    last_frame: np.ndarray | None = None
    for _ in range(args.warmup_frames):
        _, frame = cam.read()
        last_frame = frame
        result = detector.detect(frame)
        cert = cert_gen.generate_frame_cert(result, rules=list(fw.rules))
        from demo.run_demo import _peek_raw  # type: ignore[import-not-found]

        raw_view = _peek_raw(detector, frame)
        ingest(ctx, raw_view, result, cert)

    if last_frame is None:
        raise RuntimeError("no frame rendered")
    composite = composite_frame(ctx, last_frame)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(args.output), composite)
    print(f"wrote {args.output} ({composite.shape[1]}x{composite.shape[0]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
