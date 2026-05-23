"""Lightweight 2D primitives the panels use: rounded rects, gradients, glow.

OpenCV does not give us rounded rectangles or smooth gradients natively;
PIL does, and the cost is one PIL composite per primitive (~0.3ms). All
primitives operate on BGR numpy arrays in place.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def rounded_rect(
    img_bgr: "np.ndarray",
    xy: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, int, int] | None = None,
    outline: tuple[int, int, int] | None = None,
    outline_width: int = 1,
    alpha: float = 1.0,
) -> None:
    """Draw a rounded rectangle into img_bgr in place."""
    x0, y0, x1, y1 = xy
    if x1 <= x0 or y1 <= y0:
        return
    w, h = x1 - x0, y1 - y0
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    rgba_fill = _rgba(fill, alpha) if fill is not None else None
    rgba_out = _rgba(outline, 1.0) if outline is not None else None
    draw.rounded_rectangle(
        (0, 0, w - 1, h - 1),
        radius=radius,
        fill=rgba_fill,
        outline=rgba_out,
        width=outline_width if rgba_out else 0,
    )
    _blend(img_bgr, overlay, x0, y0)


def vertical_gradient(
    img_bgr: "np.ndarray",
    xy: tuple[int, int, int, int],
    top_color: tuple[int, int, int],
    bot_color: tuple[int, int, int],
) -> None:
    """Vertical linear gradient inside the given rect."""
    x0, y0, x1, y1 = xy
    h = max(1, y1 - y0)
    for i in range(h):
        t = i / max(h - 1, 1)
        c = (
            int(top_color[0] * (1 - t) + bot_color[0] * t),
            int(top_color[1] * (1 - t) + bot_color[1] * t),
            int(top_color[2] * (1 - t) + bot_color[2] * t),
        )
        img_bgr[y0 + i, x0:x1] = c


def soft_glow(
    img_bgr: "np.ndarray",
    xy: tuple[int, int, int, int],
    color: tuple[int, int, int],
    blur_radius: int = 12,
    intensity: float = 0.5,
) -> None:
    """Halo a region with a soft glow of the given color."""
    x0, y0, x1, y1 = xy
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        return
    pad = blur_radius * 2
    overlay = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle(
        (pad, pad, pad + w - 1, pad + h - 1),
        radius=10,
        fill=_rgba(color, intensity),
    )
    overlay = overlay.filter(ImageFilter.GaussianBlur(blur_radius))
    _blend(img_bgr, overlay, x0 - pad, y0 - pad)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _rgba(bgr: tuple[int, int, int] | None, alpha: float) -> tuple[int, int, int, int] | None:
    if bgr is None:
        return None
    return (bgr[2], bgr[1], bgr[0], int(max(0.0, min(1.0, alpha)) * 255))


def _blend(img_bgr: "np.ndarray", overlay: Image.Image, x: int, y: int) -> None:
    h_full, w_full = img_bgr.shape[:2]
    w, h = overlay.size
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(w_full, x + w)
    y1 = min(h_full, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    src_x0 = x0 - x
    src_y0 = y0 - y
    src_x1 = src_x0 + (x1 - x0)
    src_y1 = src_y0 + (y1 - y0)
    sub = overlay.crop((src_x0, src_y0, src_x1, src_y1))
    region_rgb = img_bgr[y0:y1, x0:x1, ::-1].copy()
    base = Image.fromarray(region_rgb).convert("RGBA")
    base.alpha_composite(sub)
    img_bgr[y0:y1, x0:x1] = np.array(base.convert("RGB"))[..., ::-1]
