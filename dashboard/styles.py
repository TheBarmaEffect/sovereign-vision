"""Dashboard styling: colors, fonts, layout constants.

We deliberately use OpenCV BGR tuples here (since OpenCV is the rendering
backend). Hex codes are documented next to each constant for designer
review.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Window layout
# ---------------------------------------------------------------------------

PANEL_WIDTH: int = 640
PANEL_HEIGHT: int = 720
WINDOW_WIDTH: int = PANEL_WIDTH * 3  # 1920
WINDOW_HEIGHT: int = PANEL_HEIGHT  # 720
HEADER_HEIGHT: int = 64
FOOTER_HEIGHT: int = 32


# ---------------------------------------------------------------------------
# Color palette — BGR for OpenCV
# ---------------------------------------------------------------------------

# Backgrounds
BG_PANEL = (15, 10, 10)          # #0A0A0F near-black
BG_PANEL_ALT = (24, 18, 18)      # slightly lighter
BG_CARD = (40, 30, 25)           # dark slate
BG_HEADER = (45, 30, 20)         # panel header strip

# Borders / dividers
BORDER_PRIMARY = (95, 58, 30)    # #1E3A5F dark blue
BORDER_DIVIDER = (60, 45, 30)

# Text
TEXT_PRIMARY = (253, 244, 232)   # #E8F4FD near white
TEXT_SECONDARY = (211, 179, 127) # #7FB3D3 muted blue
TEXT_MUTED = (150, 130, 100)

# Status colors
COLOR_CERTIFIED = (170, 212, 0)  # #00D4AA mint green
COLOR_ESCALATED = (71, 179, 255) # #FFB347 amber
COLOR_BLOCKED = (87, 71, 255)    # #FF4757 red
COLOR_ACCENT = (255, 153, 0)     # #0099FF webAI blue
COLOR_PII_WARN = (60, 60, 255)   # warning red overlay

# Heat-map gradient for zone occupancy (low → high)
HEATMAP_STOPS: tuple[tuple[int, int, int], ...] = (
    (40, 30, 25),     # empty zone
    (120, 70, 30),    # 1 person
    (180, 110, 30),   # 2 persons
    (210, 140, 30),   # 3+
    (250, 170, 50),   # hotspot
)


# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------

FONT_PRIMARY = 0           # cv2.FONT_HERSHEY_SIMPLEX
FONT_MONO = 5              # cv2.FONT_HERSHEY_TRIPLEX as approximation
FONT_SCALE_HEADER = 0.7
FONT_SCALE_SUBHEADER = 0.45
FONT_SCALE_BODY = 0.5
FONT_SCALE_SMALL = 0.4
FONT_THICKNESS_HEADER = 2
FONT_THICKNESS_BODY = 1


# ---------------------------------------------------------------------------
# Animation
# ---------------------------------------------------------------------------

PULSE_PERIOD_FRAMES: int = 30
PII_PULSE_INTENSITY: float = 0.25
RULE_LOG_MAX_VISIBLE: int = 12
RULE_LOG_FADE_FRAMES: int = 90
