"""Sovereign Vision virtual camera output.

Streams certified, PII-redacted frames to a macOS / Windows virtual
camera device (via pyvirtualcam, which bridges to OBS Virtual Camera on
macOS).

Once running, any other app on your Mac that takes a webcam input
(Zoom, FaceTime, Google Meet, Loom, etc.) can select "OBS Virtual
Camera" and receive ONLY the Sovereign Vision certified stream. The
firewall sits between the raw camera and the meeting app.

Setup (one time):
    1. Install OBS Studio (https://obsproject.com).
    2. Open OBS once, then quit; OBS installs its Virtual Camera driver.
    3. pip install pyvirtualcam

Run:
    python tools/virtualcam.py

What the certified stream looks like:
    - Raw frame, but with every person bbox filled with a solid neutral
      gray rectangle (no faces, no clothing, no identifying detail).
    - A persistent watermark in the corner: "SV CERTIFIED · session ID
      prefix · live cert hash".
    - The compliance status (CLEAR / ESCALATED / BLOCKED) tinted into
      the watermark badge.

A bystander watching your Zoom call sees: zone occupancy as gray
silhouettes plus an attestation strip, never a face.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger("sovereign.virtualcam")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--width",  type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--fps",    type=int, default=30)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        import pyvirtualcam  # type: ignore[import-not-found]
    except ImportError:
        logger.error(
            "pyvirtualcam not installed. Run: pip install pyvirtualcam"
        )
        return 1

    # Sovereign Vision pieces
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from sovereign.certificate import CertificateGenerator
    from sovereign.detector import SovereignDetector
    from sovereign.firewall import ConstitutionalFirewall

    fw = ConstitutionalFirewall()
    cert_gen = CertificateGenerator(session_id=fw.session_id)
    detector = SovereignDetector(model_path=Path("models/yolo26m.npz"),
                                 firewall=fw)

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        logger.error("Could not open camera %d", args.camera)
        return 2

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    cap.set(cv2.CAP_PROP_FPS,          args.fps)

    logger.info("Sovereign Vision virtual camera starting on %dx%d @ %d FPS",
                args.width, args.height, args.fps)

    with pyvirtualcam.Camera(width=args.width, height=args.height,
                              fps=args.fps, fmt=pyvirtualcam.PixelFormat.BGR) as cam:
        logger.info("Virtual cam device: %s", cam.device)
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    time.sleep(0.01)
                    continue

                result, raw_view = detector.detect_with_raw_preview(frame)
                cert = cert_gen.generate_frame_cert(result, rules=list(fw.rules))

                # Black out every person region (this is the certified output).
                certified = _redact_persons(frame, raw_view)
                _draw_watermark(certified, cert, result.constitutional_status,
                                 fw.session_id)

                cam.send(certified)
                cam.sleep_until_next_frame()
        except KeyboardInterrupt:
            pass
        finally:
            cap.release()

    return 0


# ---------------------------------------------------------------------------
# Visual treatment
# ---------------------------------------------------------------------------


def _redact_persons(frame: np.ndarray, raw_detections) -> np.ndarray:
    out = frame.copy()
    for det in raw_detections:
        if det.class_name != "person":
            continue
        x, y, w, h = (int(v) for v in det.bbox)
        x = max(0, x)
        y = max(0, y)
        x2 = min(out.shape[1], x + w)
        y2 = min(out.shape[0], y + h)
        if x2 <= x or y2 <= y:
            continue
        out[y:y2, x:x2] = (60, 60, 65)
    return out


def _draw_watermark(img: np.ndarray, cert, status: str, session_id: str) -> None:
    h, w = img.shape[:2]
    pad = 14
    strip_h = 44
    cv2.rectangle(img, (0, 0), (w, strip_h), (15, 12, 10), -1)

    dot_color = {
        "CLEAR":     (88, 209, 48),
        "ESCALATED": (10, 159, 255),
        "BLOCKED":   (58, 69, 255),
    }.get(status, (245, 247, 250))
    cv2.circle(img, (pad + 6, strip_h // 2), 6, dot_color, -1)

    label = (
        f"SV CERTIFIED  |  session {session_id[:8]}  |  "
        f"cert {cert.integrity_hash[:12]}...  |  {status}"
    )
    cv2.putText(img, label, (pad + 20, strip_h - 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, (240, 240, 240), 1)


if __name__ == "__main__":
    raise SystemExit(main())
