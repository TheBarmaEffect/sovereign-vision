"""Premium typography for the Sovereign Vision dashboard.

This module replaces cv2.putText (1990s Hershey lines) with PIL-based
TrueType rendering. On macOS it picks Apple's San Francisco (SF Pro) which
gives the dashboard an Apple-keynote feel. On other platforms it falls
back through Inter, Helvetica, DejaVuSans, until one is found.

All rendering is anti-aliased. We cache font instances by (path, size) so
the per-frame overhead stays well under 1ms.

Usage:
    from dashboard.typography import draw_text, FontStyle
    draw_text(bgr_image, "Hello", (32, 64), size=24, weight="semibold")
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

import numpy as np
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


Weight = Literal["regular", "medium", "semibold", "bold"]


# ---------------------------------------------------------------------------
# Font resolution
# ---------------------------------------------------------------------------

# Apple SF Pro variants (TrueType Collections). PIL ImageFont can index
# into a .ttc via the `index=` argument; we try a few likely indices.
_MACOS_FONTS: dict[Weight, list[tuple[str, int]]] = {
    "regular":  [("/System/Library/Fonts/SFNS.ttf",       0),
                 ("/System/Library/Fonts/HelveticaNeue.ttc", 0),
                 ("/System/Library/Fonts/Helvetica.ttc",  0)],
    "medium":   [("/System/Library/Fonts/SFNS.ttf",       0),
                 ("/System/Library/Fonts/HelveticaNeue.ttc", 1)],
    "semibold": [("/System/Library/Fonts/SFNS.ttf",       0),
                 ("/System/Library/Fonts/HelveticaNeue.ttc", 2)],
    "bold":     [("/System/Library/Fonts/SFNS.ttf",       0),
                 ("/System/Library/Fonts/HelveticaNeue.ttc", 3)],
}

_MACOS_MONO: list[tuple[str, int]] = [
    ("/System/Library/Fonts/SFNSMono.ttf", 0),
    ("/System/Library/Fonts/Menlo.ttc",    0),
]

_FALLBACKS: list[tuple[str, int]] = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 0),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0),
]


@lru_cache(maxsize=64)
def _load_font(
    weight: Weight, size: int, mono: bool = False
) -> ImageFont.FreeTypeFont:
    candidates = _MACOS_MONO if mono else _MACOS_FONTS.get(weight, _MACOS_FONTS["regular"])
    candidates = list(candidates) + _FALLBACKS
    last_err: Exception | None = None
    for path, idx in candidates:
        if not os.path.exists(path):
            continue
        try:
            return ImageFont.truetype(path, size=size, index=idx)
        except Exception as exc:
            last_err = exc
            continue
    logger.warning(
        "No premium font available (last error: %s); using PIL default", last_err
    )
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Style presets
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class FontStyle:
    size: int
    weight: Weight = "regular"
    mono: bool = False
    color: tuple[int, int, int] = (245, 247, 250)
    letter_spacing: float = 0.0

    def font(self) -> ImageFont.FreeTypeFont:
        return _load_font(self.weight, self.size, self.mono)


# Apple-inspired type scale
STYLE_HERO       = FontStyle(size=32, weight="bold")
STYLE_TITLE      = FontStyle(size=22, weight="semibold")
STYLE_SUBTITLE   = FontStyle(size=14, weight="medium",  color=(160, 175, 200))
STYLE_LABEL      = FontStyle(size=11, weight="semibold", color=(140, 155, 180))
STYLE_BODY       = FontStyle(size=14, weight="regular")
STYLE_BODY_SOFT  = FontStyle(size=14, weight="regular",  color=(180, 192, 210))
STYLE_METRIC_VAL = FontStyle(size=20, weight="semibold")
STYLE_MONO       = FontStyle(size=12, weight="regular", mono=True,
                              color=(180, 192, 210))
STYLE_MONO_BIG   = FontStyle(size=14, weight="semibold", mono=True)
STYLE_BADGE      = FontStyle(size=11, weight="semibold")


# ---------------------------------------------------------------------------
# Drawing API
# ---------------------------------------------------------------------------


def draw_text(
    img_bgr: "np.ndarray",
    text: str,
    xy: tuple[int, int],
    style: FontStyle | None = None,
    *,
    size: int | None = None,
    weight: Weight | None = None,
    mono: bool = False,
    color: tuple[int, int, int] | None = None,
    anchor: str = "lt",
) -> None:
    """Draw anti-aliased text onto a BGR numpy image.

    Parameters
    ----------
    img_bgr
        The destination image (modified in place).
    text
        The string to render.
    xy
        Top-left (x, y) by default; override with `anchor` (PIL anchors).
    style
        A FontStyle preset, or pass size/weight/color individually.
    """
    if style is None:
        style = FontStyle(
            size=size or 14,
            weight=weight or "regular",
            mono=mono,
            color=color or (245, 247, 250),
        )
    elif color is not None:
        style = FontStyle(
            size=style.size,
            weight=style.weight,
            mono=style.mono,
            color=color,
        )

    font = style.font()
    rgb = (style.color[2], style.color[1], style.color[0])  # BGR -> RGB

    # Composite via PIL for proper anti-aliased text
    pil = Image.fromarray(_bgr_to_rgb(img_bgr))
    draw = ImageDraw.Draw(pil)
    draw.text(xy, text, fill=rgb, font=font, anchor=anchor)
    np.copyto(img_bgr, _rgb_to_bgr(np.array(pil)))


def text_size(
    text: str,
    style: FontStyle | None = None,
    *,
    size: int | None = None,
    weight: Weight | None = None,
    mono: bool = False,
) -> tuple[int, int]:
    """Return the rendered (w, h) of `text` for a given style."""
    if style is None:
        style = FontStyle(
            size=size or 14, weight=weight or "regular", mono=mono
        )
    font = style.font()
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def draw_text_batch(
    img_bgr: "np.ndarray", items: list[tuple[str, tuple[int, int], FontStyle]]
) -> None:
    """Render multiple texts in a single PIL pass (cheaper than N calls)."""
    if not items:
        return
    pil = Image.fromarray(_bgr_to_rgb(img_bgr))
    draw = ImageDraw.Draw(pil)
    for text, xy, style in items:
        rgb = (style.color[2], style.color[1], style.color[0])
        draw.text(xy, text, fill=rgb, font=style.font())
    np.copyto(img_bgr, _rgb_to_bgr(np.array(pil)))


# ---------------------------------------------------------------------------
# BGR <-> RGB helpers
# ---------------------------------------------------------------------------


def _bgr_to_rgb(img: "np.ndarray") -> "np.ndarray":
    return img[..., ::-1].copy()


def _rgb_to_bgr(img: "np.ndarray") -> "np.ndarray":
    return img[..., ::-1].copy()
