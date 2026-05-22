"""Panel 1 — Raw Inference (left).

Shows the camera feed with raw YOLO bounding boxes. Person boxes are
overlaid with a translucent red "⚠ PII" tag to make clear that this data
exists ONLY in this panel and is never persisted.

This panel takes a list of `RawDetection` directly (the firewall hands us
a copy for visualisation only — the official pipeline still runs through
`process_frame`). The visualisation copy is dropped at the end of every
render frame.
"""
from __future__ import annotations

import math
from typing import Any, Iterable

import cv2
import numpy as np

from dashboard import styles as S
from sovereign.firewall import RawDetection

PANEL_TITLE = "RAW INFERENCE"
PANEL_SUBTITLE = "Pre-firewall - contains PII"


def render(
    frame: "np.ndarray",
    raw_detections: Iterable[RawDetection],
    fps: float,
    model_name: str,
    total_detections: int,
    tick: int,
) -> "np.ndarray":
    """Render the raw-inference panel.

    Parameters
    ----------
    frame
        BGR numpy image (the original camera frame).
    raw_detections
        Raw detection iterable. Drawn for *visualisation only*. Never stored.
    fps
        Current FPS.
    model_name
        e.g. "yolo26m".
    total_detections
        Cumulative count of raw detections this session.
    tick
        Frame counter for the pulse animation.
    """
    panel = _new_panel()
    body = _draw_header(panel)
    feed = _fit_frame(frame, body.shape[1], body.shape[0] - S.FOOTER_HEIGHT)
    _blit(body, feed, 0, 0)

    pulse = _pulse(tick)
    for det in raw_detections:
        _draw_detection(body, det, pulse)

    _draw_footer(body, fps, model_name, total_detections)
    _draw_panel_border(panel, S.COLOR_BLOCKED)
    return panel


# ---------------------------------------------------------------------------
# Panel chrome
# ---------------------------------------------------------------------------


def _new_panel() -> "np.ndarray":
    panel = np.zeros((S.PANEL_HEIGHT, S.PANEL_WIDTH, 3), dtype=np.uint8)
    panel[:] = S.BG_PANEL
    return panel


def _draw_header(panel: "np.ndarray") -> "np.ndarray":
    cv2.rectangle(
        panel, (0, 0), (S.PANEL_WIDTH, S.HEADER_HEIGHT), S.BG_HEADER, -1
    )
    cv2.line(
        panel,
        (0, S.HEADER_HEIGHT),
        (S.PANEL_WIDTH, S.HEADER_HEIGHT),
        S.COLOR_BLOCKED,
        2,
    )
    cv2.putText(
        panel,
        f"!  {PANEL_TITLE}",
        (16, 30),
        S.FONT_PRIMARY,
        S.FONT_SCALE_HEADER,
        S.TEXT_PRIMARY,
        S.FONT_THICKNESS_HEADER,
    )
    cv2.putText(
        panel,
        PANEL_SUBTITLE,
        (16, 54),
        S.FONT_PRIMARY,
        S.FONT_SCALE_SUBHEADER,
        S.TEXT_SECONDARY,
        1,
    )
    return panel[S.HEADER_HEIGHT :]


def _draw_panel_border(panel: "np.ndarray", color: tuple[int, int, int]) -> None:
    cv2.rectangle(panel, (0, 0), (S.PANEL_WIDTH - 1, S.PANEL_HEIGHT - 1), color, 1)


def _draw_footer(
    body: "np.ndarray",
    fps: float,
    model_name: str,
    total_detections: int,
) -> None:
    y = body.shape[0] - S.FOOTER_HEIGHT + 22
    cv2.rectangle(
        body,
        (0, body.shape[0] - S.FOOTER_HEIGHT),
        (body.shape[1], body.shape[0]),
        S.BG_PANEL_ALT,
        -1,
    )
    text = f"{model_name}  |  {fps:5.1f} FPS  |  total raw dets: {total_detections}"
    cv2.putText(body, text, (12, y), S.FONT_PRIMARY, S.FONT_SCALE_BODY, S.TEXT_SECONDARY, 1)
    cv2.putText(
        body,
        "This data never leaves this panel",
        (body.shape[1] - 280, y),
        S.FONT_PRIMARY,
        S.FONT_SCALE_SMALL,
        S.COLOR_BLOCKED,
        1,
    )


# ---------------------------------------------------------------------------
# Detection rendering
# ---------------------------------------------------------------------------


def _draw_detection(body: "np.ndarray", det: RawDetection, pulse: float) -> None:
    x, y, w, h = (int(v) for v in det.bbox)
    color = S.COLOR_BLOCKED if det.class_name == "person" else S.TEXT_PRIMARY
    thickness = 2 if det.class_name == "person" else 1
    cv2.rectangle(body, (x, y), (x + w, y + h), color, thickness)

    if det.class_name == "person":
        # translucent red wash + pulse on person regions
        roi = body[max(0, y) : y + h, max(0, x) : x + w]
        if roi.size:
            alpha = S.PII_PULSE_INTENSITY * pulse
            overlay = np.full_like(roi, S.COLOR_BLOCKED)
            blended = (roi.astype(np.float32) * (1 - alpha) + overlay.astype(np.float32) * alpha)
            body[max(0, y) : y + h, max(0, x) : x + w] = blended.astype(np.uint8)
        tag = "! PII"
    else:
        tag = det.class_name

    label = f"{tag}  {det.confidence:.2f}"
    _draw_label(body, label, x, y, color)


def _draw_label(body: "np.ndarray", text: str, x: int, y: int, color: tuple[int, int, int]) -> None:
    (tw, th), _ = cv2.getTextSize(text, S.FONT_PRIMARY, S.FONT_SCALE_SMALL, 1)
    pad = 4
    y0 = max(th + pad * 2, y - 6)
    cv2.rectangle(
        body, (x, y0 - th - pad * 2), (x + tw + pad * 2, y0), color, -1
    )
    cv2.putText(
        body,
        text,
        (x + pad, y0 - pad),
        S.FONT_PRIMARY,
        S.FONT_SCALE_SMALL,
        (0, 0, 0),
        1,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fit_frame(frame: "np.ndarray", w: int, h: int) -> "np.ndarray":
    fh, fw = frame.shape[:2]
    scale = min(w / fw, h / fh)
    nw, nh = int(fw * scale), int(fh * scale)
    resized = cv2.resize(frame, (nw, nh))
    canvas = np.zeros((h, w, 3), dtype=np.uint8)
    canvas[:] = S.BG_PANEL
    off_x = (w - nw) // 2
    off_y = (h - nh) // 2
    canvas[off_y : off_y + nh, off_x : off_x + nw] = resized
    return canvas


def _blit(dst: "np.ndarray", src: "np.ndarray", x: int, y: int) -> None:
    h, w = src.shape[:2]
    dst[y : y + h, x : x + w] = src


def _pulse(tick: int) -> float:
    """0..1 sinusoidal pulse with PULSE_PERIOD_FRAMES period."""
    return 0.5 * (1.0 + math.sin(2 * math.pi * tick / S.PULSE_PERIOD_FRAMES))
