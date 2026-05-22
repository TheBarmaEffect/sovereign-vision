"""Sovereign Vision — main demo entry point.

Single command to start the full system:

    python demo/run_demo.py

What it does:
  1. Detects Apple Silicon and prints a friendly warning if not present.
  2. Looks for the requested YOLO26 MLX model file; falls back gracefully
     to the simulation backend if missing.
  3. Tries to open the default webcam; falls back to the synthetic camera.
  4. Initialises the Constitutional Firewall with the 6 default rules.
  5. Runs the 3-panel OpenCV dashboard.
  6. Runs the Rich terminal dashboard on a daemon thread.
  7. Writes per-frame certificates (optional) and a session certificate.
  8. On Q (or Ctrl+C), gracefully seals the audit chain.
"""
from __future__ import annotations

import argparse
import logging
import platform
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger("sovereign-vision")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    _configure_logging(args.verbose)

    _check_apple_silicon()

    # Lazy imports so `python demo/run_demo.py --help` works without cv2.
    from sovereign.certificate import CertificateGenerator
    from sovereign.config import SovereignConfig
    from sovereign.firewall import ConstitutionalFirewall
    from sovereign.metrics import MetricsRegistry

    cfg = SovereignConfig.load(args.config) if args.config else SovereignConfig()
    if args.scenario:
        cfg.scenario.name = args.scenario

    output_dir = Path(args.output_dir or cfg.session.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    firewall = ConstitutionalFirewall()
    cert_gen = CertificateGenerator(
        session_id=firewall.session_id,
        output_dir=output_dir,
        write_frame_certs=args.write_frame_certs,
    )
    metrics = MetricsRegistry()

    _print_startup_banner(cfg, firewall.session_id, args)

    rc = _run_loop(
        firewall=firewall,
        cert_gen=cert_gen,
        metrics=metrics,
        scenario_name=cfg.scenario.name,
        model_path=Path(cfg.detector.model_path),
        camera_index=args.camera,
        headless=args.headless,
        max_frames=args.max_frames,
    )

    session_cert = cert_gen.generate_session_cert()
    print()
    print("Session sealed.")
    print(f"  session_id : {session_cert.session_id}")
    print(f"  frames     : {session_cert.total_frames}")
    print(f"  duration   : {session_cert.duration_seconds:.2f}s")
    print(f"  rules fired: {sum(session_cert.rules_triggered.values())}")
    print(f"  merkle root: {session_cert.anchor.merkle_root}")
    print(f"  output dir : {output_dir}")
    return rc


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


@dataclass
class _Quitter:
    quit: bool = False


def _run_loop(
    firewall,
    cert_gen,
    metrics,
    scenario_name: str,
    model_path: Path,
    camera_index: int,
    headless: bool,
    max_frames: int | None,
) -> int:
    """Read frames → run detector → ingest into dashboard → write certs."""
    quitter = _Quitter()
    _install_signal_handlers(quitter)

    # 1) load the detector (real YOLO if available, else simulation)
    from sovereign.detector import SovereignDetector

    detector = SovereignDetector(model_path=model_path, firewall=firewall)

    # 2) open camera (or fall back to synthetic)
    cap, model_name = _open_camera(camera_index, headless, model_path)

    # 3) optionally set up the OpenCV window + Rich dashboard
    composite_frame = ingest = TerminalDashboard = None  # type: ignore[assignment]
    window_title = "Sovereign Vision — Constitutional Firewall (live)"
    if not headless:
        try:
            import cv2

            from dashboard.app import (
                DashboardContext,
                TerminalDashboard,
                composite_frame,
                ingest,
            )

            ctx = DashboardContext(
                firewall=firewall,
                cert_gen=cert_gen,
                metrics=metrics,
                model_name=model_name,
            )
            terminal = TerminalDashboard(ctx)
            terminal.start()
            cv2.namedWindow(window_title, cv2.WINDOW_NORMAL)
        except ImportError as exc:
            logger.warning("OpenCV/Rich unavailable (%s) — running headless", exc)
            headless = True
    else:
        ctx = None
        terminal = None

    # 4) frame loop
    frame_count = 0
    try:
        while not quitter.quit:
            if max_frames is not None and frame_count >= max_frames:
                break

            ok, frame = _read_frame(cap)
            if not ok or frame is None:
                logger.warning("camera read failed at frame %d", frame_count)
                time.sleep(0.05)
                continue

            result = detector.detect(frame)
            cert = cert_gen.generate_frame_cert(result, rules=list(firewall.rules))

            if not headless and ctx is not None:
                # We deliberately rebuild the raw detection list here purely
                # for visualisation. The official pipeline already ran above.
                raw_for_view = _peek_raw(detector, frame)
                ingest(ctx, raw_for_view, result, cert)  # type: ignore[misc]
                composite = composite_frame(ctx, frame)  # type: ignore[misc]
                import cv2  # already imported above; harmless

                cv2.imshow(window_title, composite)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    quitter.quit = True

            frame_count += 1
    except KeyboardInterrupt:
        quitter.quit = True
    finally:
        try:
            cap.release()
        except Exception:
            pass
        if not headless:
            try:
                import cv2

                cv2.destroyAllWindows()
            except Exception:
                pass
            if terminal is not None:
                terminal.stop()  # type: ignore[union-attr]

    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_args(argv: Optional[list[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="sovereign-vision",
        description="Sovereign Vision — Constitutional Firewall for on-device CV.",
    )
    parser.add_argument("--config", type=Path, default=None, help="YAML config path")
    parser.add_argument(
        "--scenario",
        type=str,
        default=None,
        choices=("factory_floor", "retail_floor", "warehouse"),
        help="Demo scenario to load.",
    )
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default 0)")
    parser.add_argument("--headless", action="store_true", help="Disable OpenCV window")
    parser.add_argument(
        "--max-frames",
        dest="max_frames",
        type=int,
        default=None,
        help="Quit after N frames (useful for CI / recording short demos)",
    )
    parser.add_argument(
        "--output-dir",
        dest="output_dir",
        type=Path,
        default=None,
        help="Where to write compliance certificates",
    )
    parser.add_argument(
        "--write-frame-certs",
        dest="write_frame_certs",
        action="store_true",
        help="Persist a JSON certificate per frame (default off — session cert only)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args(argv)


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )


def _check_apple_silicon() -> None:
    machine = platform.machine()
    if machine.lower() not in ("arm64", "aarch64"):
        logger.warning(
            "Running on %s — not Apple Silicon. MLX acceleration is disabled.",
            machine,
        )


def _print_startup_banner(cfg, session_id: str, args: argparse.Namespace) -> None:
    print("=" * 72)
    print(" SOVEREIGN VISION v1.0  —  On-device Constitutional Computer Vision")
    print("=" * 72)
    print(f"  Model         : {cfg.detector.model_path}")
    print(f"  Scenario      : {cfg.scenario.name}")
    print(f"  Session ID    : {session_id}")
    print(f"  Output dir    : {cfg.session.output_dir}")
    print(f"  Rules loaded  : 6 (SV-001..SV-006)")
    print(f"  Headless mode : {bool(args.headless)}")
    print()
    print("  Constitution :  CRITICAL=3   HIGH=2   MEDIUM=1")
    print("  Press Q (in the window) to quit and seal the session certificate.")
    print("=" * 72)


def _install_signal_handlers(quitter: _Quitter) -> None:
    def handler(signum, frame):  # noqa: ARG001
        quitter.quit = True

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)


def _open_camera(
    camera_index: int, headless: bool, model_path: Path
) -> tuple[object, str]:
    """Try the real camera; fall back to the synthetic one."""
    from demo.simulate_webcam import SyntheticCamera

    try:
        import cv2

        cap = cv2.VideoCapture(camera_index)
        if cap is not None and cap.isOpened():
            return cap, model_path.stem or "yolo26"
        logger.info("No physical camera at index %d — using synthetic feed.", camera_index)
    except ImportError:
        logger.info("OpenCV not installed — using synthetic feed.")

    return SyntheticCamera(), model_path.stem or "yolo26"


def _read_frame(cap):
    try:
        ok, frame = cap.read()
        return ok, frame
    except Exception as exc:
        logger.error("camera read raised: %s", exc)
        return False, None


def _peek_raw(detector, frame):
    """Best-effort visualisation helper — pulls a raw detection list from
    the underlying model for the left panel only. This list is dropped at
    the end of the render frame; it is not persisted anywhere.
    """
    model = getattr(detector, "_model", None)
    if model is None:
        return []
    predict = getattr(model, "predict", None)
    if predict is None:
        return []
    try:
        raw = predict(frame, conf=0.25)
        from sovereign.detector import _yolo_results_to_raw

        if isinstance(raw, list) and raw and not hasattr(raw[0], "boxes"):
            return raw  # SimulationModel already returns RawDetection
        return _yolo_results_to_raw(raw)
    except Exception:
        return []


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(main())
