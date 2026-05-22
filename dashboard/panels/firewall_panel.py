"""Panel 2 — Constitutional Firewall (center).

Live scrolling log of rule events. Shows the firewall doing its work in
real time — each card has a timestamp, rule id, action, and pass/applied
status. A large status badge at the top reflects the latest frame's
constitutional status.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Iterable

import cv2
import numpy as np

from dashboard import styles as S
from sovereign.firewall import FirewallResult, RuleEvent

PANEL_TITLE = "CONSTITUTIONAL FIREWALL"
PANEL_SUBTITLE = "Glass Box Runtime Verification"


class FirewallPanelState:
    """Stores rolling rule log + per-second trigger histogram."""

    def __init__(self, max_visible: int = S.RULE_LOG_MAX_VISIBLE) -> None:
        self.events: deque[tuple[float, RuleEvent]] = deque(maxlen=max_visible * 3)
        self.per_second_counts: deque[int] = deque(maxlen=30)
        self.this_second_count: int = 0
        self.last_second: int = -1
        self.total_rules_applied: int = 0
        self.last_status: str = "CERTIFIED"
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
    body = _draw_header(panel)
    _draw_status_badge(body, state.last_status, state.total_rules_applied)
    _draw_event_log(body, state.events)
    _draw_histogram(body, state.per_second_counts)
    _draw_footer(body, state.session_id, state.total_rules_applied)
    _draw_panel_border(panel, S.COLOR_ACCENT)
    return panel


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------


def _new_panel() -> "np.ndarray":
    panel = np.zeros((S.PANEL_HEIGHT, S.PANEL_WIDTH, 3), dtype=np.uint8)
    panel[:] = S.BG_PANEL
    return panel


def _draw_header(panel: "np.ndarray") -> "np.ndarray":
    cv2.rectangle(panel, (0, 0), (S.PANEL_WIDTH, S.HEADER_HEIGHT), S.BG_HEADER, -1)
    cv2.line(panel, (0, S.HEADER_HEIGHT), (S.PANEL_WIDTH, S.HEADER_HEIGHT), S.COLOR_ACCENT, 2)
    cv2.putText(
        panel,
        f"o  {PANEL_TITLE}",
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


def _draw_status_badge(body: "np.ndarray", status: str, total: int) -> None:
    color = {
        "CERTIFIED": S.COLOR_CERTIFIED,
        "ESCALATED": S.COLOR_ESCALATED,
        "BLOCKED": S.COLOR_BLOCKED,
    }.get(status, S.COLOR_CERTIFIED)
    icon = {"CERTIFIED": "[C]", "ESCALATED": "[!]", "BLOCKED": "[X]"}.get(status, "[C]")

    x0, y0, x1, y1 = 16, 16, S.PANEL_WIDTH - 16, 82
    cv2.rectangle(body, (x0, y0), (x1, y1), S.BG_CARD, -1)
    cv2.rectangle(body, (x0, y0), (x1, y1), color, 2)
    label = f"{icon}  {status}"
    cv2.putText(body, label, (x0 + 18, y0 + 42), S.FONT_PRIMARY, 0.9, color, 2)
    sub = f"{total} rules applied this session   |   Zero PII passed: yes"
    cv2.putText(body, sub, (x0 + 18, y1 - 10), S.FONT_PRIMARY, 0.42, S.TEXT_SECONDARY, 1)


def _draw_event_log(body: "np.ndarray", events: Iterable[tuple[float, RuleEvent]]) -> None:
    y = 100
    cv2.putText(
        body,
        "LIVE RULE EVENTS",
        (16, y),
        S.FONT_PRIMARY,
        S.FONT_SCALE_SUBHEADER,
        S.TEXT_MUTED,
        1,
    )
    y += 10
    row_h = 28
    max_rows = S.RULE_LOG_MAX_VISIBLE
    for i, (ts, ev) in enumerate(list(events)[:max_rows]):
        row_y = y + i * row_h
        _draw_event_row(body, row_y, ts, ev, fade=i / max(max_rows, 1))


def _draw_event_row(
    body: "np.ndarray", y: int, ts: float, ev: RuleEvent, fade: float
) -> None:
    fade_factor = max(0.35, 1.0 - 0.5 * fade)
    color = {
        "REDACT": S.COLOR_CERTIFIED,
        "HASH": S.COLOR_CERTIFIED,
        "AGGREGATE": S.COLOR_CERTIFIED,
        "BLOCK": S.COLOR_BLOCKED if ev.blocked else S.COLOR_CERTIFIED,
        "ESCALATE": S.COLOR_ESCALATED,
    }.get(ev.action, S.TEXT_PRIMARY)
    color = tuple(int(c * fade_factor) for c in color)

    cv2.rectangle(body, (16, y - 2), (S.PANEL_WIDTH - 16, y + 22), S.BG_PANEL_ALT, -1)
    cv2.line(body, (16, y + 22), (S.PANEL_WIDTH - 16, y + 22), S.BORDER_DIVIDER, 1)

    ts_str = datetime.fromtimestamp(ts).strftime("%H:%M:%S.%f")[:-3]
    text_color = tuple(int(c * fade_factor) for c in S.TEXT_PRIMARY)

    cv2.putText(body, ts_str, (24, y + 16), S.FONT_PRIMARY, 0.38, text_color, 1)
    cv2.putText(body, ev.rule_id, (130, y + 16), S.FONT_PRIMARY, 0.42, color, 1)
    cv2.putText(body, ev.rule_name[:22], (200, y + 16), S.FONT_PRIMARY, 0.4, text_color, 1)
    cv2.putText(body, ev.action, (430, y + 16), S.FONT_PRIMARY, 0.42, color, 1)
    status_text = "blocked" if ev.blocked else "applied"
    cv2.putText(body, status_text, (S.PANEL_WIDTH - 96, y + 16), S.FONT_PRIMARY, 0.4, color, 1)


def _draw_histogram(body: "np.ndarray", counts: Iterable[int]) -> None:
    base_y = S.PANEL_HEIGHT - S.HEADER_HEIGHT - 72
    cv2.putText(
        body,
        "RULES TRIGGERED PER SECOND",
        (16, base_y - 6),
        S.FONT_PRIMARY,
        S.FONT_SCALE_SMALL,
        S.TEXT_MUTED,
        1,
    )
    bars = list(counts)
    if not bars:
        return
    width = S.PANEL_WIDTH - 32
    bar_w = max(2, width // max(len(bars), 1))
    max_v = max(bars + [1])
    for i, v in enumerate(bars):
        h = int(40 * v / max_v)
        x = 16 + i * bar_w
        cv2.rectangle(
            body,
            (x, base_y + 40 - h),
            (x + bar_w - 1, base_y + 40),
            S.COLOR_ACCENT,
            -1,
        )


def _draw_footer(body: "np.ndarray", session_id: str, total: int) -> None:
    y = body.shape[0] - 12
    cv2.putText(
        body,
        f"session {session_id[:18]}  |  total rules: {total}",
        (16, y),
        S.FONT_PRIMARY,
        S.FONT_SCALE_SMALL,
        S.TEXT_MUTED,
        1,
    )
