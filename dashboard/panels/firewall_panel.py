"""Panel 2 - Constitutional Firewall (center).

Premium, Apple-grade rendering of the live rule event log. The center panel
is the visual centerpiece of the demo: it shows the firewall doing its work
in real time. Each rule event is rendered as a card with a status dot, a
rule id pill, the action taken, and a pass/applied state.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Iterable

import cv2
import numpy as np

from dashboard import gfx
from dashboard import styles as S
from dashboard.typography import (
    STYLE_BODY,
    STYLE_BODY_SOFT,
    STYLE_HERO,
    STYLE_LABEL,
    STYLE_MONO,
    STYLE_SUBTITLE,
    STYLE_TITLE,
    draw_text,
)
from sovereign.firewall import FirewallResult, RuleEvent

PANEL_TITLE = "CONSTITUTIONAL FIREWALL"
PANEL_SUBTITLE = "Glass Box runtime verification  ·  on-device"


class FirewallPanelState:
    """Rolling rule log + per-second trigger histogram."""

    def __init__(self, max_visible: int = S.RULE_LOG_MAX_VISIBLE) -> None:
        self.events: deque[tuple[float, RuleEvent]] = deque(maxlen=max_visible * 3)
        self.per_second_counts: deque[int] = deque(maxlen=30)
        self.this_second_count: int = 0
        self.last_second: int = -1
        self.total_rules_applied: int = 0
        self.last_status: str = "CLEAR"
        self.session_id: str = "-"

    def ingest(self, ts_seconds: float, result: FirewallResult) -> None:
        now_sec = int(ts_seconds)
        if now_sec != self.last_second:
            if self.last_second >= 0:
                self.per_second_counts.append(self.this_second_count)
            self.this_second_count = 0
            self.last_second = now_sec
        for ev in result.rules_fired:
            self.events.appendleft((ts_seconds, ev))
            self.total_rules_applied += 1
            self.this_second_count += 1
        self.last_status = result.constitutional_status
        self.session_id = result.session_id


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def render(state: FirewallPanelState) -> "np.ndarray":
    panel = _new_panel()
    _draw_header(panel)
    _draw_status_badge(panel, state.last_status, state.total_rules_applied)
    _draw_event_log(panel, state.events)
    _draw_histogram(panel, state.per_second_counts)
    _draw_footer(panel, state.session_id, state.total_rules_applied)
    _draw_panel_border(panel, S.APPLE_BLUE)
    return panel


# ---------------------------------------------------------------------------
# Sections
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
    cv2.line(panel, (0, S.HEADER_HEIGHT), (S.PANEL_WIDTH, S.HEADER_HEIGHT),
             S.APPLE_BLUE, 2)
    cv2.circle(panel, (S.PADDING_X + 6, 36), 6, S.APPLE_BLUE, -1)
    draw_text(panel, PANEL_TITLE, (S.PADDING_X + 24, 18), STYLE_TITLE)
    draw_text(panel, PANEL_SUBTITLE, (S.PADDING_X + 24, 46),
              STYLE_SUBTITLE, color=(140, 155, 180))


def _draw_panel_border(panel: "np.ndarray", color: tuple[int, int, int]) -> None:
    cv2.rectangle(panel, (0, 0), (S.PANEL_WIDTH - 1, S.PANEL_HEIGHT - 1), color, 1)


def _draw_status_badge(panel: "np.ndarray", status: str, total: int) -> None:
    color = {
        "CLEAR":     S.APPLE_GREEN,
        "ESCALATED": S.APPLE_AMBER,
        "BLOCKED":   S.APPLE_RED,
    }.get(status, S.APPLE_GREEN)

    x0 = S.PADDING_X
    y0 = S.HEADER_HEIGHT + 14
    x1 = S.PANEL_WIDTH - S.PADDING_X
    y1 = y0 + 84

    gfx.soft_glow(panel, (x0, y0, x1, y1), color, blur_radius=12, intensity=0.25)
    gfx.rounded_rect(panel, (x0, y0, x1, y1), radius=S.RADIUS_CARD,
                     fill=S.BG_CARD, outline=color, outline_width=1)

    cv2.circle(panel, (x0 + 24, y0 + 32), 6, color, -1)
    draw_text(panel, status, (x0 + 40, y0 + 14), STYLE_HERO, color=color)

    sub = f"{total} rules applied this session   ·   zero PII passed"
    draw_text(panel, sub, (x0 + 24, y0 + 56), STYLE_BODY_SOFT)


def _draw_event_log(
    panel: "np.ndarray", events: Iterable[tuple[float, RuleEvent]]
) -> None:
    x0 = S.PADDING_X
    y = S.HEADER_HEIGHT + 114
    draw_text(panel, "LIVE RULE EVENTS", (x0, y), STYLE_LABEL)
    y += 22

    row_h = 30
    max_rows = S.RULE_LOG_MAX_VISIBLE
    for i, (ts, ev) in enumerate(list(events)[:max_rows]):
        _draw_event_row(panel, x0, S.PANEL_WIDTH - S.PADDING_X,
                        y + i * row_h, ts, ev, fade=i / max(max_rows, 1))


def _draw_event_row(
    panel: "np.ndarray",
    x0: int,
    x1: int,
    y: int,
    ts: float,
    ev: RuleEvent,
    fade: float,
) -> None:
    fade_factor = max(0.45, 1.0 - 0.5 * fade)
    color = {
        "REDACT":    S.APPLE_GREEN,
        "HASH":      S.APPLE_GREEN,
        "AGGREGATE": S.APPLE_GREEN,
        "BLOCK":     S.APPLE_RED if ev.blocked else S.APPLE_GREEN,
        "ESCALATE":  S.APPLE_AMBER,
    }.get(ev.action, S.TEXT_PRIMARY)
    color = S.with_alpha(color, fade_factor)
    text_color = S.with_alpha(S.TEXT_PRIMARY, fade_factor)
    soft_color = S.with_alpha(S.TEXT_SECONDARY, fade_factor)

    gfx.rounded_rect(panel, (x0, y, x1, y + 26), radius=6,
                     fill=S.BG_CARD, alpha=fade_factor * 0.85)

    ts_str = datetime.fromtimestamp(ts).strftime("%H:%M:%S.%f")[:-3]

    draw_text(panel, ts_str, (x0 + 10, y + 6), STYLE_MONO, color=soft_color)
    draw_text(panel, ev.rule_id, (x0 + 100, y + 5), STYLE_BODY, color=color)
    draw_text(panel, ev.rule_name[:30], (x0 + 158, y + 6), STYLE_BODY,
              color=text_color)
    draw_text(panel, ev.action, (x1 - 170, y + 6), STYLE_BODY, color=color)
    draw_text(panel, "blocked" if ev.blocked else "applied",
              (x1 - 80, y + 6), STYLE_BODY, color=color)


def _draw_histogram(panel: "np.ndarray", counts: Iterable[int]) -> None:
    base_y = S.PANEL_HEIGHT - S.FOOTER_HEIGHT - 80
    x0 = S.PADDING_X
    draw_text(panel, "RULES TRIGGERED PER SECOND", (x0, base_y),
              STYLE_LABEL)
    base_y += 18
    bars = list(counts)
    if not bars:
        return
    width = S.PANEL_WIDTH - 2 * S.PADDING_X
    bar_w = max(2, (width - len(bars)) // max(len(bars), 1))
    max_v = max(bars + [1])
    for i, v in enumerate(bars):
        bh = int(50 * v / max_v)
        x = x0 + i * (bar_w + 1)
        gfx.rounded_rect(
            panel,
            (x, base_y + 50 - bh, x + bar_w, base_y + 50),
            radius=2,
            fill=S.APPLE_BLUE,
            alpha=0.85,
        )


def _draw_footer(panel: "np.ndarray", session_id: str, total: int) -> None:
    y0 = S.PANEL_HEIGHT - S.FOOTER_HEIGHT
    cv2.rectangle(panel, (0, y0), (S.PANEL_WIDTH, S.PANEL_HEIGHT), S.BG_HEADER, -1)
    cv2.line(panel, (0, y0), (S.PANEL_WIDTH, y0), S.BORDER_SOFT, 1)
    sid = session_id[:8] if session_id and session_id != "-" else "-"
    text = f"session {sid}   ·   {total} rules applied"
    draw_text(panel, text, (S.PADDING_X, y0 + 12), STYLE_MONO,
              color=S.TEXT_SECONDARY)
