"""Panel 3 — Certified Enterprise Output (right).

Shows the data your compliance team actually sees:
  - 3x3 zone heat map (aggregate occupancy)
  - PPE compliance rate
  - Active zones / dwell time
  - Sensitive objects flagged
  - Latest certificate hash + audit chain info
  - GDPR coverage badges
  - LIVE / ON-DEVICE / ZERO CLOUD indicator
"""
from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from dashboard import styles as S
from sovereign.firewall import FirewallResult
from sovereign.redactor import ZONE_LABELS

PANEL_TITLE = "CERTIFIED ENTERPRISE OUTPUT"
PANEL_SUBTITLE = "What your compliance team actually sees"


def render(
    result: FirewallResult | None,
    cert_hash: str,
    last_cert_age_s: float,
    tick: int,
) -> "np.ndarray":
    panel = _new_panel()
    body = _draw_header(panel)
    _draw_zone_heatmap(body, result)
    _draw_metrics(body, result)
    _draw_certificate_card(body, cert_hash, last_cert_age_s, result)
    _draw_legal_badges(body)
    _draw_live_indicator(body, tick)
    _draw_panel_border(panel, S.COLOR_CERTIFIED)
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
    cv2.line(panel, (0, S.HEADER_HEIGHT), (S.PANEL_WIDTH, S.HEADER_HEIGHT), S.COLOR_CERTIFIED, 2)
    cv2.putText(
        panel,
        f"+  {PANEL_TITLE}",
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


def _draw_zone_heatmap(body: "np.ndarray", result: FirewallResult | None) -> None:
    y0 = 12
    cv2.putText(
        body,
        "ZONE OCCUPANCY (AGGREGATE)",
        (16, y0 + 8),
        S.FONT_PRIMARY,
        S.FONT_SCALE_SUBHEADER,
        S.TEXT_MUTED,
        1,
    )
    grid_x, grid_y, grid_w, grid_h = 16, y0 + 18, S.PANEL_WIDTH - 32, 200
    cell_w = grid_w // 3
    cell_h = grid_h // 3

    zone_counts: dict[str, int] = {}
    if result is not None:
        zone_counts = dict(result.frame_aggregate.zone_counts)

    for r, row in enumerate(ZONE_LABELS):
        for c, label in enumerate(row):
            x = grid_x + c * cell_w
            y = grid_y + r * cell_h
            count = zone_counts.get(label, 0)
            color = _heat_color(count)
            cv2.rectangle(body, (x + 2, y + 2), (x + cell_w - 2, y + cell_h - 2), color, -1)
            cv2.rectangle(
                body,
                (x + 2, y + 2),
                (x + cell_w - 2, y + cell_h - 2),
                S.BORDER_DIVIDER,
                1,
            )
            cv2.putText(
                body,
                str(count),
                (x + cell_w // 2 - 6, y + cell_h // 2 + 8),
                S.FONT_PRIMARY,
                0.9,
                S.TEXT_PRIMARY,
                2,
            )
            cv2.putText(
                body,
                label.replace("zone_", ""),
                (x + 6, y + cell_h - 6),
                S.FONT_PRIMARY,
                S.FONT_SCALE_SMALL,
                S.TEXT_MUTED,
                1,
            )


def _draw_metrics(body: "np.ndarray", result: FirewallResult | None) -> None:
    y = 248
    cv2.putText(
        body,
        "LIVE METRICS",
        (16, y),
        S.FONT_PRIMARY,
        S.FONT_SCALE_SUBHEADER,
        S.TEXT_MUTED,
        1,
    )
    y += 8
    ppe = result.ppe_compliance_rate if result is not None else 1.0
    active = result.active_zones if result is not None else 0
    sensitive = (
        result.frame_aggregate.sensitive_objects_flagged if result is not None else 0
    )
    avg_dwell = (
        sum(result.dwell_time_estimate.values()) / max(len(result.dwell_time_estimate), 1)
        if result is not None and result.dwell_time_estimate
        else 0.0
    )

    _progress_bar(body, "PPE Compliance Rate", y + 20, ppe)
    _kv(body, "Active Zones", f"{active}/9", y + 60)
    _kv(body, "Avg Dwell (aggregate)", f"{avg_dwell:.2f}s", y + 80)
    _kv(body, "Sensitive Objects", f"{sensitive} flagged", y + 100)


def _draw_certificate_card(
    body: "np.ndarray",
    cert_hash: str,
    last_cert_age_s: float,
    result: FirewallResult | None,
) -> None:
    y = 388
    cv2.putText(
        body,
        "COMPLIANCE CERTIFICATE",
        (16, y),
        S.FONT_PRIMARY,
        S.FONT_SCALE_SUBHEADER,
        S.TEXT_MUTED,
        1,
    )
    y += 18
    cv2.rectangle(body, (16, y), (S.PANEL_WIDTH - 16, y + 110), S.BG_CARD, -1)
    cv2.rectangle(body, (16, y), (S.PANEL_WIDTH - 16, y + 110), S.COLOR_CERTIFIED, 1)

    short = cert_hash[:16] + "..." if cert_hash else "-"
    rules_count = len(result.rules_fired) if result is not None else 0

    _kv(body, "Cert hash", short, y + 24, label_w=110)
    _kv(body, "Last certified", f"{last_cert_age_s:.2f}s ago", y + 46, label_w=110)
    _kv(body, "Rules applied", f"{rules_count} this frame", y + 68, label_w=110)
    _kv(body, "PII stored", "NONE", y + 90, label_w=110, value_color=S.COLOR_CERTIFIED)


def _draw_legal_badges(body: "np.ndarray") -> None:
    y = 528
    cv2.putText(
        body,
        "LEGAL COVERAGE",
        (16, y),
        S.FONT_PRIMARY,
        S.FONT_SCALE_SUBHEADER,
        S.TEXT_MUTED,
        1,
    )
    badges = ["GDPR Art.4", "Art.9", "Art.22", "Art.89", "CCPA"]
    x = 16
    for label in badges:
        text = f"{label} OK"
        (tw, th), _ = cv2.getTextSize(text, S.FONT_PRIMARY, 0.42, 1)
        cv2.rectangle(
            body, (x, y + 8), (x + tw + 16, y + th + 24), S.BG_CARD, -1
        )
        cv2.rectangle(
            body, (x, y + 8), (x + tw + 16, y + th + 24), S.COLOR_CERTIFIED, 1
        )
        cv2.putText(
            body, text, (x + 8, y + th + 18), S.FONT_PRIMARY, 0.42, S.COLOR_CERTIFIED, 1
        )
        x += tw + 24


def _draw_live_indicator(body: "np.ndarray", tick: int) -> None:
    y = body.shape[0] - 18
    blink = (tick // 15) % 2 == 0
    dot_color = S.COLOR_CERTIFIED if blink else S.BG_CARD
    cv2.circle(body, (24, y - 4), 6, dot_color, -1)
    cv2.putText(
        body,
        "LIVE  |  ON DEVICE  |  ZERO CLOUD",
        (40, y),
        S.FONT_PRIMARY,
        S.FONT_SCALE_BODY,
        S.COLOR_CERTIFIED,
        1,
    )


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------


def _progress_bar(body: "np.ndarray", label: str, y: int, value: float) -> None:
    cv2.putText(body, label, (16, y), S.FONT_PRIMARY, S.FONT_SCALE_BODY, S.TEXT_PRIMARY, 1)
    pct_text = f"{value * 100:.0f}%"
    cv2.putText(
        body,
        pct_text,
        (S.PANEL_WIDTH - 60, y),
        S.FONT_PRIMARY,
        S.FONT_SCALE_BODY,
        S.COLOR_CERTIFIED,
        1,
    )
    bar_y = y + 10
    cv2.rectangle(body, (16, bar_y), (S.PANEL_WIDTH - 16, bar_y + 8), S.BG_CARD, -1)
    fill = int((S.PANEL_WIDTH - 32) * max(0.0, min(1.0, value)))
    cv2.rectangle(body, (16, bar_y), (16 + fill, bar_y + 8), S.COLOR_CERTIFIED, -1)


def _kv(
    body: "np.ndarray",
    label: str,
    value: str,
    y: int,
    label_w: int = 200,
    value_color: tuple[int, int, int] = S.TEXT_PRIMARY,
) -> None:
    cv2.putText(body, label, (24, y), S.FONT_PRIMARY, S.FONT_SCALE_BODY, S.TEXT_SECONDARY, 1)
    cv2.putText(
        body, value, (24 + label_w, y), S.FONT_PRIMARY, S.FONT_SCALE_BODY, value_color, 1
    )


def _heat_color(count: int) -> tuple[int, int, int]:
    """Map a zone count to a heat-map color stop."""
    if count <= 0:
        return S.HEATMAP_STOPS[0]
    if count >= len(S.HEATMAP_STOPS):
        return S.HEATMAP_STOPS[-1]
    return S.HEATMAP_STOPS[count]
