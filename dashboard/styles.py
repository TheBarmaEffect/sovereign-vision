"""Sovereign Vision dashboard design system.

A small, deliberate palette inspired by macOS Sonoma + Apple Human Interface
Guidelines. All colors are BGR tuples (OpenCV's native order).

This module owns:
  - Layout constants (panel sizes, paddings)
  - Color palette
  - Spacing tokens
  - Easing helpers for animations
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Window layout
# ---------------------------------------------------------------------------

PANEL_WIDTH: int = 640
PANEL_HEIGHT: int = 720
WINDOW_WIDTH: int = PANEL_WIDTH * 3
WINDOW_HEIGHT: int = PANEL_HEIGHT
HEADER_HEIGHT: int = 72
FOOTER_HEIGHT: int = 40

PADDING_X: int = 20
PADDING_Y: int = 16
RADIUS_CARD: int = 10
RADIUS_BADGE: int = 6


# ---------------------------------------------------------------------------
# Color palette (BGR for OpenCV)
# ---------------------------------------------------------------------------

# Backgrounds
BG_DEEP        = (14, 11, 10)      # near black, base of every panel
BG_PANEL       = (24, 21, 18)      # panel base
BG_HEADER      = (30, 26, 22)      # header strip
BG_CARD        = (37, 32, 28)      # surface card
BG_CARD_ALT    = (47, 42, 36)      # raised card
BG_GLASS       = (60, 52, 45)      # subtle highlight strip

# Borders & dividers
BORDER_SOFT    = (45, 39, 33)
BORDER_HARD    = (72, 62, 52)
BORDER_FOCUS   = (255, 122,  0)    # Apple system blue (BGR of #007AFF)

# Apple System colors (BGR)
APPLE_BLUE     = (255, 122,   0)   # #007AFF
APPLE_GREEN    = ( 88, 209,  48)   # #30D158
APPLE_AMBER    = ( 10, 159, 255)   # #FF9F0A
APPLE_RED      = ( 58,  69, 255)   # #FF453A
APPLE_PURPLE   = (199,  82, 191)   # #BF5AF2
APPLE_INDIGO   = (245, 121,  88)   # #5856D6

# Status semantics
STATUS_CLEAR     = APPLE_GREEN
STATUS_ESCALATED = APPLE_AMBER
STATUS_BLOCKED   = APPLE_RED
ACCENT           = APPLE_BLUE
PII_WARN         = APPLE_RED

# Text
TEXT_PRIMARY   = (245, 247, 250)   # near white
TEXT_SECONDARY = (175, 187, 205)
TEXT_TERTIARY  = (130, 145, 165)
TEXT_DIM       = (95, 108, 128)

# Heatmap stops for zone occupancy (BGR)
HEATMAP_STOPS: tuple[tuple[int, int, int], ...] = (
    (32, 29, 25),       # empty
    (90, 60, 40),       # 1
    (140, 90, 50),      # 2
    (200, 130, 30),     # 3
    (250, 180, 60),     # 4
    (255, 210, 100),    # 5+ hotspot
)


# ---------------------------------------------------------------------------
# Legacy aliases (some panels still reference these names)
# ---------------------------------------------------------------------------

BG_PANEL_ALT   = BG_HEADER
BORDER_PRIMARY = BORDER_FOCUS
BORDER_DIVIDER = BORDER_SOFT
COLOR_CERTIFIED = APPLE_GREEN   # color name only; user-facing strings now say "CLEAR"
COLOR_ESCALATED = APPLE_AMBER
COLOR_BLOCKED   = APPLE_RED
COLOR_ACCENT    = APPLE_BLUE
COLOR_PII_WARN  = APPLE_RED
TEXT_MUTED      = TEXT_TERTIARY

# Legacy cv2 font defaults (kept for any non-converted call sites)
FONT_PRIMARY = 0                # cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE_HEADER     = 0.7
FONT_SCALE_SUBHEADER  = 0.45
FONT_SCALE_BODY       = 0.5
FONT_SCALE_SMALL      = 0.4
FONT_THICKNESS_HEADER = 2
FONT_THICKNESS_BODY   = 1


# ---------------------------------------------------------------------------
# Animation
# ---------------------------------------------------------------------------

PULSE_PERIOD_FRAMES: int = 30
PII_PULSE_INTENSITY: float = 0.22
RULE_LOG_MAX_VISIBLE: int = 12
RULE_LOG_FADE_FRAMES: int = 90


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def with_alpha(color: tuple[int, int, int], alpha: float) -> tuple[int, int, int]:
    """Multiply a BGR tuple by `alpha` in [0, 1] (used for fading)."""
    a = max(0.0, min(1.0, alpha))
    return (int(color[0] * a), int(color[1] * a), int(color[2] * a))
