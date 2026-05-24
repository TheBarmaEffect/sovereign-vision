"""Render the 60-second submission demo video, frame by frame.

Pure numpy + PIL composition. No screen recording, no audio, no human
intervention. Output is `assets/demo_60s.mp4`, H.264, 1920x720, 30 fps,
under 30 MB so LinkedIn / X / YouTube all accept it directly.

Storyboard
----------
  0.0 -  3.5 s  Hero title card    (Sovereign Vision)
  3.5 -  8.5 s  The problem
  8.5 - 13.5 s  The solution
 13.5 - 50.0 s  Live dashboard     (37 s of constitutional firewall)
 50.0 - 55.0 s  Stats + numbers
 55.0 - 60.0 s  Install + outro
"""
from __future__ import annotations

import math
import uuid
from pathlib import Path

import cv2
import numpy as np

from dashboard import gfx
from dashboard import styles as S
from dashboard.app import DashboardContext, composite_frame, ingest
from dashboard.typography import (
    STYLE_BODY,
    STYLE_BODY_SOFT,
    STYLE_HERO,
    STYLE_LABEL,
    STYLE_MONO,
    STYLE_MONO_BIG,
    STYLE_SUBTITLE,
    STYLE_TITLE,
    FontStyle,
    draw_text,
    text_size,
)
from sovereign.certificate import CertificateGenerator
from sovereign.detector import SovereignDetector
from sovereign.firewall import ConstitutionalFirewall
from sovereign.metrics import MetricsRegistry

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WIDTH = 1920
HEIGHT = 720
FPS = 30
OUTPUT = Path("assets/demo_60s.mp4")

STYLE_GIANT = FontStyle(size=72, weight="bold")
STYLE_BIG = FontStyle(size=40, weight="semibold")
STYLE_MED = FontStyle(size=24, weight="medium", color=S.TEXT_SECONDARY)
STYLE_TAGLINE = FontStyle(size=22, weight="regular", color=S.TEXT_SECONDARY)
STYLE_KICKER = FontStyle(size=14, weight="semibold", color=S.APPLE_BLUE,
                          letter_spacing=2.0)


# ---------------------------------------------------------------------------
# Canvas helpers
# ---------------------------------------------------------------------------


def _blank() -> np.ndarray:
    img = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    gfx.vertical_gradient(img, (0, 0, WIDTH, HEIGHT),
                          top_color=(8, 7, 6), bot_color=S.BG_PANEL)
    return img


def _center_x(text: str, style: FontStyle) -> int:
    tw, _ = text_size(text, style)
    return (WIDTH - tw) // 2


def _apply_alpha(frame: np.ndarray, alpha: float) -> np.ndarray:
    a = max(0.0, min(1.0, alpha))
    if a >= 0.999:
        return frame
    return (frame.astype(np.float32) * a).astype(np.uint8)


def _emit_with_fade(
    writer: cv2.VideoWriter,
    img: np.ndarray,
    duration_frames: int,
    fade_in: int = 12,
    fade_out: int = 12,
) -> None:
    """Write a static image with smooth fade in / hold / fade out."""
    for i in range(duration_frames):
        if i < fade_in:
            alpha = (i + 1) / fade_in
        elif i >= duration_frames - fade_out:
            alpha = max(0.0, (duration_frames - i) / fade_out)
        else:
            alpha = 1.0
        writer.write(_apply_alpha(img, alpha))


# ---------------------------------------------------------------------------
# Act 1: hero title
# ---------------------------------------------------------------------------


def _hero_card(tick: int = 0) -> np.ndarray:
    img = _blank()
    # subtle glow behind the title
    gfx.soft_glow(img, (480, 230, 1440, 350), S.APPLE_BLUE,
                  blur_radius=60, intensity=0.18)

    draw_text(img, "SOVEREIGN VISION", (_center_x("SOVEREIGN VISION", STYLE_KICKER), 200),
              STYLE_KICKER)
    title = "Compliant by design,"
    title2 = "not by policy."
    draw_text(img, title, (_center_x(title, STYLE_GIANT), 240), STYLE_GIANT)
    draw_text(img, title2, (_center_x(title2, STYLE_GIANT), 330), STYLE_GIANT,
              color=S.APPLE_GREEN)

    sub = "The first on-device enterprise vision system whose privacy is enforced by code."
    draw_text(img, sub, (_center_x(sub, STYLE_MED), 470), STYLE_MED)

    foot = "Karthik Barma   ·   webAI YOLO26 MLX Build Challenge   ·   Enterprise track"
    draw_text(img, foot, (_center_x(foot, STYLE_MONO), 640), STYLE_MONO,
              color=S.TEXT_TERTIARY)
    return img


# ---------------------------------------------------------------------------
# Acts 2 + 3: problem and solution cards
# ---------------------------------------------------------------------------


def _kicker_card(kicker: str, line1: str, line2: str, body: str,
                 accent: tuple[int, int, int]) -> np.ndarray:
    img = _blank()
    gfx.soft_glow(img, (480, 200, 1440, 480), accent,
                  blur_radius=60, intensity=0.12)
    draw_text(img, kicker, (_center_x(kicker, STYLE_KICKER), 170),
              STYLE_KICKER, color=accent)
    draw_text(img, line1, (_center_x(line1, STYLE_BIG), 230), STYLE_BIG)
    draw_text(img, line2, (_center_x(line2, STYLE_BIG), 285), STYLE_BIG,
              color=accent)

    # Body wrapped manually (PIL doesn't word-wrap for us)
    style_body = FontStyle(size=20, weight="regular", color=S.TEXT_SECONDARY)
    lines = body.split("\n")
    y = 400
    for ln in lines:
        draw_text(img, ln, (_center_x(ln, style_body), y), style_body)
        y += 36
    return img


def _problem_card() -> np.ndarray:
    return _kicker_card(
        kicker="THE PROBLEM",
        line1="Every YOLO detection is PII",
        line2="the moment a camera sees a person.",
        accent=S.APPLE_RED,
        body=(
            "GDPR Article 4: spatial location is personal data.\n"
            "Article 9: face data is a special category.\n"
            "Recital 30: track IDs are online identifiers.\n"
            "Most factories, stores, and hospitals never deploy CV at all."
        ),
    )


def _solution_card() -> np.ndarray:
    return _kicker_card(
        kicker="THE SOLUTION",
        line1="A constitutional firewall",
        line2="on the inference path itself.",
        accent=S.APPLE_GREEN,
        body=(
            "Seven cryptographically-audited rules redact, hash, block,"
            " aggregate, and add\n"
            "differential-privacy noise to every detection before any output exists.\n"
            "Each frame issues a self-attested, Merkle-anchored compliance certificate."
        ),
    )


# ---------------------------------------------------------------------------
# Act 4: live dashboard
# ---------------------------------------------------------------------------


def _camera_frame(tick: int) -> np.ndarray:
    """A subtly animated synthetic camera frame so the left panel has texture."""
    h, w = 720, 1280
    img = np.zeros((h, w, 3), dtype=np.uint8)
    # warm charcoal gradient
    gfx.vertical_gradient(img, (0, 0, w, h),
                          top_color=(22, 18, 14), bot_color=(40, 32, 26))
    # subtle grid (factory-floor feel)
    for x in range(0, w, 80):
        cv2.line(img, (x, 0), (x, h), (32, 26, 22), 1)
    for y in range(0, h, 80):
        cv2.line(img, (0, y), (w, y), (32, 26, 22), 1)
    # camera HUD
    cv2.rectangle(img, (18, 18), (210, 56), (8, 7, 6), -1)
    cv2.circle(img, (40, 38), 6, S.APPLE_RED, -1)
    return img


def _emit_dashboard(writer: cv2.VideoWriter, duration_frames: int) -> None:
    firewall = ConstitutionalFirewall(session_id=str(uuid.uuid4()))
    cert_gen = CertificateGenerator(session_id=firewall.session_id)
    metrics = MetricsRegistry()
    ctx = DashboardContext(
        firewall=firewall,
        cert_gen=cert_gen,
        metrics=metrics,
        model_name="yolo26m",
        hardware_label="Apple M5 Pro  ·  18 GPU  ·  16 NE  ·  MLX",
    )
    detector = SovereignDetector(model_path=Path("models/yolo26m.npz"),
                                  firewall=firewall)

    # Brief 12-frame fade-in so the cut from card 3 is smooth.
    for i in range(duration_frames):
        cam = _camera_frame(i)
        result, raw_view = detector.detect_with_raw_preview(cam)
        cert = cert_gen.generate_frame_cert(result, rules=list(firewall.rules))
        ingest(ctx, raw_view, result, cert)
        composite = composite_frame(ctx, cam)
        ctx.tick += 1

        if i < 12:
            alpha = (i + 1) / 12
        elif i >= duration_frames - 12:
            alpha = max(0.0, (duration_frames - i) / 12)
        else:
            alpha = 1.0
        writer.write(_apply_alpha(composite, alpha))


# ---------------------------------------------------------------------------
# Act 5: stats card
# ---------------------------------------------------------------------------


def _stats_card() -> np.ndarray:
    img = _blank()
    draw_text(img, "BY THE NUMBERS",
              (_center_x("BY THE NUMBERS", STYLE_KICKER), 110), STYLE_KICKER)

    metrics = [
        ("7",       "Constitutional rules"),
        ("84",      "Tests passing"),
        ("55",      "FPS on yolo26m"),
        ("0",       "PII bytes ever stored"),
        ("0",       "Bytes sent to the cloud"),
        ("RFC 3161","Trusted timestamp"),
    ]
    cell_w = 580
    cell_h = 140
    cols = 3
    rows = 2
    grid_w = cols * cell_w + (cols - 1) * 20
    grid_h = rows * cell_h + (rows - 1) * 20
    grid_x = (WIDTH - grid_w) // 2
    grid_y = 180

    style_val = FontStyle(size=56, weight="bold")
    style_lbl = FontStyle(size=18, weight="medium", color=S.TEXT_SECONDARY)

    for idx, (val, lbl) in enumerate(metrics):
        r, c = divmod(idx, cols)
        x = grid_x + c * (cell_w + 20)
        y = grid_y + r * (cell_h + 20)
        gfx.rounded_rect(img, (x, y, x + cell_w, y + cell_h), radius=14,
                         fill=S.BG_CARD, outline=S.BORDER_SOFT, outline_width=1)
        vw, _ = text_size(val, style_val)
        draw_text(img, val, (x + (cell_w - vw) // 2, y + 24), style_val,
                  color=S.APPLE_GREEN)
        lw, _ = text_size(lbl, style_lbl)
        draw_text(img, lbl, (x + (cell_w - lw) // 2, y + 92), style_lbl)
    return img


# ---------------------------------------------------------------------------
# Act 6: install + outro
# ---------------------------------------------------------------------------


def _outro_card() -> np.ndarray:
    img = _blank()
    gfx.soft_glow(img, (480, 130, 1440, 300), S.APPLE_BLUE,
                  blur_radius=60, intensity=0.18)

    draw_text(img, "INSTALL NOW",
              (_center_x("INSTALL NOW", STYLE_KICKER), 120), STYLE_KICKER)

    pip_line = "pip install sovereign-vision"
    brew_line = "brew tap TheBarmaEffect/sovereign-vision-tap"
    brew_line2 = "brew install sovereign-vision"

    style_cmd = FontStyle(size=32, weight="semibold", mono=True,
                           color=S.APPLE_GREEN)

    draw_text(img, pip_line, (_center_x(pip_line, style_cmd), 180), style_cmd)
    draw_text(img, brew_line, (_center_x(brew_line, style_cmd), 240), style_cmd)
    draw_text(img, brew_line2, (_center_x(brew_line2, style_cmd), 290), style_cmd)

    link = "github.com/TheBarmaEffect/sovereign-vision"
    draw_text(img, link, (_center_x(link, STYLE_MONO_BIG), 420),
              STYLE_MONO_BIG, color=S.APPLE_BLUE)

    sub = "Source code  ·  Threat model  ·  Audit chain spec  ·  10 install channels"
    draw_text(img, sub, (_center_x(sub, STYLE_MED), 470), STYLE_MED)

    foot1 = "Karthik Barma   ·   MS Artificial Intelligence"
    foot2 = "Northeastern University, Khoury College of Computer Sciences"
    foot3 = "Glass Box Framework  ·  Runtime constitutional AI verification"
    draw_text(img, foot1, (_center_x(foot1, STYLE_MED), 560), STYLE_MED)
    draw_text(img, foot2, (_center_x(foot2, STYLE_MED), 595), STYLE_MED)
    draw_text(img, foot3, (_center_x(foot3, STYLE_MONO), 640), STYLE_MONO,
              color=S.TEXT_TERTIARY)
    return img


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    # Render every frame to PNG first, then assemble with ffmpeg.
    # This bypasses the cv2.VideoWriter quirk where avc1 silently rejects
    # frames after a few hundred writes on some macOS builds.
    frames_dir = Path("/tmp/sovereign_frames")
    if frames_dir.exists():
        import shutil
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True)
    writer = _PngWriter(frames_dir)

    print(f"Rendering frames to {frames_dir} ...")

    # Act 1: hero  (3.5s = 105 frames)
    _emit_with_fade(writer, _hero_card(), duration_frames=105,
                    fade_in=20, fade_out=12)
    # Act 2: problem  (5.0s = 150 frames)
    _emit_with_fade(writer, _problem_card(), duration_frames=150,
                    fade_in=12, fade_out=12)
    # Act 3: solution  (5.0s = 150 frames)
    _emit_with_fade(writer, _solution_card(), duration_frames=150,
                    fade_in=12, fade_out=12)
    # Act 4: live dashboard  (36.5s = 1095 frames)
    _emit_dashboard(writer, duration_frames=1095)
    # Act 5: stats  (5.0s = 150 frames)
    _emit_with_fade(writer, _stats_card(), duration_frames=150,
                    fade_in=12, fade_out=12)
    # Act 6: outro  (5.0s = 150 frames)
    _emit_with_fade(writer, _outro_card(), duration_frames=150,
                    fade_in=12, fade_out=20)

    n = writer.frame_count
    print(f"Wrote {n} PNG frames. Encoding with ffmpeg...")

    # Encode with ffmpeg directly to H.264 yuv420p (LinkedIn / X / YouTube safe).
    import subprocess
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", str(frames_dir / "f_%05d.png"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "medium",
        "-crf", "20",
        "-movflags", "+faststart",
        str(OUTPUT),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("ffmpeg failed:")
        print(res.stderr[-2000:])
        return 1

    import os
    size_mb = os.path.getsize(OUTPUT) / 1024 / 1024
    print(f"Done. {OUTPUT}  ({size_mb:.1f} MB)")
    return 0


class _PngWriter:
    """Tiny adapter so the existing render code can keep calling writer.write()."""

    def __init__(self, out_dir: Path) -> None:
        self._dir = out_dir
        self._count = 0

    def write(self, frame: np.ndarray) -> None:
        # Ensure contiguous uint8 BGR for cv2.imwrite
        if frame.dtype != np.uint8:
            frame = frame.astype(np.uint8)
        if not frame.flags["C_CONTIGUOUS"]:
            frame = np.ascontiguousarray(frame)
        if frame.shape[0] != HEIGHT or frame.shape[1] != WIDTH:
            frame = cv2.resize(frame, (WIDTH, HEIGHT))
        path = self._dir / f"f_{self._count:05d}.png"
        cv2.imwrite(str(path), frame)
        self._count += 1

    def isOpened(self) -> bool:  # noqa: N802 (cv2 interface)
        return True

    def release(self) -> None:
        pass

    @property
    def frame_count(self) -> int:
        return self._count


if __name__ == "__main__":
    raise SystemExit(main())
