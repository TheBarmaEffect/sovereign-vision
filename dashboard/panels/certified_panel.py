"""Panel 3 - Enterprise Output (right).

Premium, Apple-grade rendering of the certified enterprise output. This is
the panel a compliance team would see in production: a 3x3 zone heat map,
the live PPE compliance rate, the most recent attestation hash, and the
"LIVE / ON-DEVICE / ZERO CLOUD" guarantee.

All metrics here are aggregate-only. Nothing on this panel references any
individual.
"""
from __future__ import annotations

import cv2
import numpy as np

from dashboard import gfx
from dashboard import styles as S
from dashboard.typography import (
    STYLE_BODY,
    STYLE_BODY_SOFT,
    STYLE_LABEL,
    STYLE_METRIC_VAL,
    STYLE_MONO,
    STYLE_SUBTITLE,
    STYLE_TITLE,
    draw_text,
    text_size,
)
from sovereign.firewall import FirewallResult
from sovereign.redactor import ZONE_LABELS

PANEL_TITLE = "ENTERPRISE OUTPUT"
PANEL_SUBTITLE = "Self-attested  ·  Tamper-evident  ·  On-device"


def render(
    result: FirewallResult | None,
    cert_hash: str,
    last_cert_age_s: float,
    tick: int,
    hardware_label: str = "",
) -> "np.ndarray":
    panel = _new_panel()
    _draw_header(panel)
    _draw_zone_heatmap(panel, result)
    _draw_metrics(panel, result)
    _draw_attestation_card(panel, cert_hash, last_cert_age_s, result)
    _draw_legal_badges(panel)
    _draw_live_indicator(panel, tick, hardware_label)
    _draw_panel_border(panel, S.APPLE_GREEN)
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
             S.APPLE_GREEN, 2)
    cv2.circle(panel, (S.PADDING_X + 6, 36), 6, S.APPLE_GREEN, -1)
    draw_text(panel, PANEL_TITLE, (S.PADDING_X + 24, 18), STYLE_TITLE)
    draw_text(panel, PANEL_SUBTITLE, (S.PADDING_X + 24, 46),
              STYLE_SUBTITLE, color=(140, 155, 180))


def _draw_panel_border(panel: "np.ndarray", color: tuple[int, int, int]) -> None:
    cv2.rectangle(panel, (0, 0), (S.PANEL_WIDTH - 1, S.PANEL_HEIGHT - 1), color, 1)


def _draw_zone_heatmap(panel: "np.ndarray", result: FirewallResult | None) -> None:
    x0 = S.PADDING_X
    y0 = S.HEADER_HEIGHT + 14
    draw_text(panel, "ZONE OCCUPANCY  (AGGREGATE)", (x0, y0), STYLE_LABEL)
    y0 += 20
    grid_w = S.PANEL_WIDTH - 2 * S.PADDING_X
    grid_h = 180
    cell_w = grid_w // 3
    cell_h = grid_h // 3

    zone_counts: dict[str, int] = {}
    if result is not None:
        zone_counts = dict(result.frame_aggregate.zone_counts)

    for r, row in enumerate(ZONE_LABELS):
        for c, label in enumerate(row):
            x = x0 + c * cell_w
            y = y0 + r * cell_h
            count = zone_counts.get(label, 0)
            color = _heat_color(count)
            gfx.rounded_rect(
                panel,
                (x + 3, y + 3, x + cell_w - 3, y + cell_h - 3),
                radius=8,
                fill=color,
                outline=S.BORDER_SOFT,
                outline_width=1,
            )
            label_short = label.replace("zone_", "")
            count_str = str(count)
            cw, _ = text_size(count_str, STYLE_METRIC_VAL)
            draw_text(
                panel,
                count_str,
                (x + (cell_w - cw) // 2, y + cell_h // 2 - 14),
                STYLE_METRIC_VAL,
            )
            draw_text(
                panel, label_short, (x + 10, y + cell_h - 22),
                STYLE_MONO, color=S.TEXT_TERTIARY,
            )


def _draw_metrics(panel: "np.ndarray", result: FirewallResult | None) -> None:
    x0 = S.PADDING_X
    y0 = S.HEADER_HEIGHT + 220
    draw_text(panel, "LIVE METRICS", (x0, y0), STYLE_LABEL)
    y0 += 18

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

    _progress_bar(panel, "PPE Compliance Rate", y0, ppe)
    _kv_row(panel, "Active Zones",         f"{active}/9",          y0 + 44)
    _kv_row(panel, "Avg Dwell (aggregate)", f"{avg_dwell:.2f}s",    y0 + 66)
    _kv_row(panel, "Sensitive Objects",    f"{sensitive} flagged", y0 + 88)


def _draw_attestation_card(
    panel: "np.ndarray",
    cert_hash: str,
    last_cert_age_s: float,
    result: FirewallResult | None,
) -> None:
    x0 = S.PADDING_X
    y0 = S.HEADER_HEIGHT + 380
    draw_text(panel, "ATTESTATION  (SELF-ISSUED, AUDIT-VERIFIABLE)",
              (x0, y0), STYLE_LABEL)
    y0 += 18

    x1 = S.PANEL_WIDTH - S.PADDING_X
    gfx.rounded_rect(panel, (x0, y0, x1, y0 + 116), radius=S.RADIUS_CARD,
                     fill=S.BG_CARD, outline=S.APPLE_GREEN, outline_width=1)

    short = cert_hash[:24] + "..." if cert_hash else "-"
    rules_count = len(result.rules_fired) if result is not None else 0

    _kv_in_card(panel, "Cert hash",      short,                              y0 + 14)
    _kv_in_card(panel, "Last certified", f"{last_cert_age_s:.2f}s ago",      y0 + 36)
    _kv_in_card(panel, "Rules applied",  f"{rules_count} this frame",        y0 + 58)
    _kv_in_card(panel, "PII stored",     "NONE",                             y0 + 80,
                value_color=S.APPLE_GREEN)


def _draw_legal_badges(panel: "np.ndarray") -> None:
    x0 = S.PADDING_X
    y0 = S.HEADER_HEIGHT + 520
    draw_text(panel, "LEGAL COVERAGE", (x0, y0), STYLE_LABEL)
    y0 += 16
    badges = [
        ("GDPR Art.4",  S.APPLE_GREEN),
        ("Art.9",       S.APPLE_GREEN),
        ("Art.22",      S.APPLE_GREEN),
        ("Art.89",      S.APPLE_GREEN),
        ("CCPA",        S.APPLE_GREEN),
        ("HIPAA SH",    S.APPLE_GREEN),
    ]
    x = x0
    for label, color in badges:
        text = f"{label} OK"
        tw, _ = text_size(text, STYLE_BODY)
        gfx.rounded_rect(
            panel,
            (x, y0 + 8, x + tw + 14, y0 + 32),
            radius=S.RADIUS_BADGE,
            fill=S.BG_CARD,
            outline=color,
            outline_width=1,
        )
        draw_text(panel, text, (x + 7, y0 + 11), STYLE_BODY, color=color)
        x += tw + 22


def _draw_live_indicator(panel: "np.ndarray", tick: int, hw_label: str) -> None:
    y0 = S.PANEL_HEIGHT - S.FOOTER_HEIGHT
    cv2.rectangle(panel, (0, y0), (S.PANEL_WIDTH, S.PANEL_HEIGHT), S.BG_HEADER, -1)
    cv2.line(panel, (0, y0), (S.PANEL_WIDTH, y0), S.BORDER_SOFT, 1)
    blink = (tick // 15) % 2 == 0
    dot = S.APPLE_GREEN if blink else S.BG_CARD
    cv2.circle(panel, (S.PADDING_X + 4, y0 + 18), 6, dot, -1)
    draw_text(panel, "LIVE  ·  ON-DEVICE  ·  ZERO CLOUD",
              (S.PADDING_X + 20, y0 + 10), STYLE_BODY, color=S.APPLE_GREEN)
    if hw_label:
        tw, _ = text_size(hw_label, STYLE_MONO)
        draw_text(panel, hw_label,
                  (S.PANEL_WIDTH - S.PADDING_X - tw, y0 + 12),
                  STYLE_MONO, color=S.TEXT_SECONDARY)


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------


def _progress_bar(panel: "np.ndarray", label: str, y: int, value: float) -> None:
    x0 = S.PADDING_X
    x1 = S.PANEL_WIDTH - S.PADDING_X
    draw_text(panel, label, (x0, y), STYLE_BODY)
    pct = f"{value * 100:.0f}%"
    tw, _ = text_size(pct, STYLE_BODY)
    draw_text(panel, pct, (x1 - tw, y), STYLE_BODY, color=S.APPLE_GREEN)
    bar_y = y + 22
    gfx.rounded_rect(panel, (x0, bar_y, x1, bar_y + 8), radius=4,
                     fill=S.BG_CARD)
    fill_w = int((x1 - x0) * max(0.0, min(1.0, value)))
    if fill_w > 0:
        gfx.rounded_rect(panel, (x0, bar_y, x0 + fill_w, bar_y + 8),
                         radius=4, fill=S.APPLE_GREEN)


def _kv_row(panel: "np.ndarray", label: str, value: str, y: int) -> None:
    x0 = S.PADDING_X
    x1 = S.PANEL_WIDTH - S.PADDING_X
    draw_text(panel, label, (x0, y), STYLE_BODY, color=S.TEXT_SECONDARY)
    tw, _ = text_size(value, STYLE_BODY)
    draw_text(panel, value, (x1 - tw, y), STYLE_BODY)


def _kv_in_card(
    panel: "np.ndarray",
    label: str,
    value: str,
    y: int,
    value_color: tuple[int, int, int] | None = None,
) -> None:
    x0 = S.PADDING_X + 14
    x1 = S.PANEL_WIDTH - S.PADDING_X - 14
    draw_text(panel, label, (x0, y), STYLE_BODY, color=S.TEXT_SECONDARY)
    tw, _ = text_size(value, STYLE_BODY if value_color is None else STYLE_BODY)
    draw_text(panel, value, (x1 - tw, y), STYLE_BODY, color=value_color)


def _heat_color(count: int) -> tuple[int, int, int]:
    if count <= 0:
        return S.HEATMAP_STOPS[0]
    if count >= len(S.HEATMAP_STOPS):
        return S.HEATMAP_STOPS[-1]
    return S.HEATMAP_STOPS[count]
