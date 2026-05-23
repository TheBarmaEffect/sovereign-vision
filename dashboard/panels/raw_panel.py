"""Panel 1 - Raw Inference (left).

Premium, Apple-grade rendering. Shows the camera feed with raw YOLO bounding
boxes. Person regions are tinted red with a translucent "PII" tag to make
clear that this data exists ONLY in this panel and is never persisted.
"""
from __future__ import annotations

import math
from typing import Iterable

import cv2
import numpy as np

from dashboard import gfx
from dashboard import styles as S
from dashboard.typography import (
    STYLE_LABEL,
    STYLE_MONO,
    STYLE_SUBTITLE,
    STYLE_TITLE,
    draw_text,
    text_size,
)
from sovereign.firewall import RawDetection

PANEL_TITLE = "RAW INFERENCE"
PANEL_SUBTITLE = "Pre-firewall  ·  Contains PII"


def render(
    frame: "np.ndarray",
    raw_detections: Iterable[RawDetection],
    fps: float,
    model_name: str,
    total_detections: int,
    tick: int,
) -> "np.ndarray":
    panel = _new_panel()
    _draw_header(panel)
    body_top = S.HEADER_HEIGHT
    body_h = S.PANEL_HEIGHT - S.HEADER_HEIGHT - S.FOOTER_HEIGHT

    # Camera feed area
    feed = _fit_frame(frame, S.PANEL_WIDTH - 2 * S.PADDING_X, body_h - 2 * S.PADDING_Y)
    feed_x = S.PADDING_X
    feed_y = body_top + S.PADDING_Y
    fh, fw = feed.shape[:2]
    panel[feed_y : feed_y + fh, feed_x : feed_x + fw] = feed

    # Overlay detections (the feed has been resized; rescale bbox coords)
    scale_x = fw / max(frame.shape[1], 1)
    scale_y = fh / max(frame.shape[0], 1)
    pulse = _pulse(tick)
    for det in raw_detections:
        _draw_detection(panel, det, feed_x, feed_y, scale_x, scale_y, pulse)

    _draw_footer(panel, fps, model_name, total_detections)
    _draw_panel_border(panel, S.APPLE_RED)
    return panel


# ---------------------------------------------------------------------------
# Panel chrome
# ---------------------------------------------------------------------------


def _new_panel() -> "np.ndarray":
    panel = np.zeros((S.PANEL_HEIGHT, S.PANEL_WIDTH, 3), dtype=np.uint8)
    gfx.vertical_gradient(
        panel,
        (0, 0, S.PANEL_WIDTH, S.PANEL_HEIGHT),
        top_color=S.BG_DEEP,
        bot_color=S.BG_PANEL,
    )
    return panel


def _draw_header(panel: "np.ndarray") -> None:
    cv2.rectangle(panel, (0, 0), (S.PANEL_WIDTH, S.HEADER_HEIGHT), S.BG_HEADER, -1)
    cv2.line(
        panel,
        (0, S.HEADER_HEIGHT),
        (S.PANEL_WIDTH, S.HEADER_HEIGHT),
        S.APPLE_RED,
        2,
    )
    # Status dot
    cv2.circle(panel, (S.PADDING_X + 6, 36), 6, S.APPLE_RED, -1)
    draw_text(panel, PANEL_TITLE, (S.PADDING_X + 24, 18), STYLE_TITLE)
    draw_text(
        panel,
        PANEL_SUBTITLE,
        (S.PADDING_X + 24, 46),
        STYLE_SUBTITLE,
        color=(140, 155, 180),
    )


def _draw_panel_border(panel: "np.ndarray", color: tuple[int, int, int]) -> None:
    cv2.rectangle(panel, (0, 0), (S.PANEL_WIDTH - 1, S.PANEL_HEIGHT - 1), color, 1)


def _draw_footer(
    panel: "np.ndarray",
    fps: float,
    model_name: str,
    total_detections: int,
) -> None:
    y0 = S.PANEL_HEIGHT - S.FOOTER_HEIGHT
    cv2.rectangle(panel, (0, y0), (S.PANEL_WIDTH, S.PANEL_HEIGHT), S.BG_HEADER, -1)
    cv2.line(panel, (0, y0), (S.PANEL_WIDTH, y0), S.BORDER_SOFT, 1)

    left = f"{model_name}   ·   {fps:5.1f} FPS"
    draw_text(panel, left, (S.PADDING_X, y0 + 12), STYLE_MONO,
              color=S.TEXT_SECONDARY)

    right = "this data never leaves this panel"
    w, _ = text_size(right, STYLE_MONO)
    draw_text(panel, right,
              (S.PANEL_WIDTH - S.PADDING_X - w, y0 + 12), STYLE_MONO,
              color=S.APPLE_RED)


# ---------------------------------------------------------------------------
# Detection rendering
# ---------------------------------------------------------------------------


def _draw_detection(
    panel: "np.ndarray",
    det: RawDetection,
    ox: int,
    oy: int,
    sx: float,
    sy: float,
    pulse: float,
) -> None:
    x, y, w, h = det.bbox
    x = int(ox + x * sx)
    y = int(oy + y * sy)
    w = int(w * sx)
    h = int(h * sy)

    is_person = det.class_name == "person"
    color = S.APPLE_RED if is_person else S.TEXT_PRIMARY
    thickness = 2 if is_person else 1
    gfx.rounded_rect(panel, (x, y, x + w, y + h), radius=4,
                     outline=color, outline_width=thickness)

    if is_person:
        # Translucent red wash on person region with subtle pulse
        sub = panel[max(0, y) : y + h, max(0, x) : x + w]
        if sub.size:
            alpha = S.PII_PULSE_INTENSITY * (0.5 + 0.5 * pulse)
            overlay = np.full_like(sub, S.APPLE_RED)
            sub[:] = (sub.astype(np.float32) * (1 - alpha) +
                      overlay.astype(np.float32) * alpha).astype(np.uint8)
        tag = "PII"
    else:
        tag = det.class_name

    label = f"{tag}  {det.confidence:.2f}"
    _draw_label(panel, label, x, y, color)


def _draw_label(panel: "np.ndarray", text: str, x: int, y: int,
                color: tuple[int, int, int]) -> None:
    tw, th = text_size(text, STYLE_LABEL)
    pad = 6
    box_h = th + pad * 2
    y0 = max(box_h, y) - box_h
    gfx.rounded_rect(panel, (x, y0, x + tw + pad * 2, y0 + box_h),
                     radius=4, fill=color, alpha=0.95)
    draw_text(panel, text, (x + pad, y0 + pad), STYLE_LABEL,
              color=(20, 20, 20))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fit_frame(frame: "np.ndarray", w: int, h: int) -> "np.ndarray":
    fh, fw = frame.shape[:2]
    scale = min(w / fw, h / fh)
    nw, nh = max(1, int(fw * scale)), max(1, int(fh * scale))
    resized = cv2.resize(frame, (nw, nh))
    canvas = np.zeros((h, w, 3), dtype=np.uint8)
    canvas[:] = S.BG_DEEP
    off_x = (w - nw) // 2
    off_y = (h - nh) // 2
    canvas[off_y : off_y + nh, off_x : off_x + nw] = resized
    return canvas


def _pulse(tick: int) -> float:
    return 0.5 * (1.0 + math.sin(2 * math.pi * tick / S.PULSE_PERIOD_FRAMES))
