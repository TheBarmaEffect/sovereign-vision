"""Generate a designed compliance PDF from a session_*.json.

Usage:
    python tools/report_pdf.py certificates/session_*.json -o report.pdf

The PDF includes:
  - Cover page (status, score, session id, duration)
  - Constitutional rule trigger table
  - Compliance score breakdown
  - Audit chain anchor + integrity hash
  - Hardware fingerprint (Apple Silicon attestation)
  - Author footer

Uses matplotlib for layout (no new heavyweight dep needed; matplotlib is
already in requirements).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


BG       = "#0A0B0E"
PANEL    = "#16181D"
CARD     = "#1C1F26"
BORDER   = "#2A2E37"
TEXT     = "#F5F7FA"
SOFT     = "#98A1B0"
DIM      = "#6F7888"
GREEN    = "#30D158"
BLUE     = "#0A84FF"
AMBER    = "#FF9F0A"
RED      = "#FF453A"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cert", type=Path, help="session_*.json")
    parser.add_argument("-o", "--output", type=Path, default=Path("report.pdf"))
    args = parser.parse_args()

    if not args.cert.exists():
        print(f"ERROR: {args.cert} not found")
        return 2
    data = json.loads(args.cert.read_text())

    with PdfPages(args.output) as pdf:
        _cover_page(pdf, data)
        _rules_page(pdf, data)
        _score_page(pdf, data)
        _hardware_page(pdf, data)
    print(f"wrote {args.output}")
    return 0


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


def _cover_page(pdf: PdfPages, data: dict) -> None:
    fig = _new_page()
    ax = fig.gca()
    status = data.get("overall_status", "-")
    status_color = {
        "CLEAR": GREEN, "ESCALATED": AMBER, "BLOCKED": RED,
        "TAMPERED": RED,
    }.get(status, TEXT)

    ax.text(0.5, 0.85, "Sovereign Vision",
            ha="center", color=TEXT, fontsize=32, fontweight="bold")
    ax.text(0.5, 0.79, "Compliance Certificate",
            ha="center", color=SOFT, fontsize=14)

    # Status badge
    ax.add_patch(mpatches.FancyBboxPatch(
        (0.18, 0.55), 0.64, 0.16,
        boxstyle="round,pad=0.012,rounding_size=0.025",
        linewidth=1.5, edgecolor=status_color, facecolor=CARD,
    ))
    ax.text(0.5, 0.66, status, ha="center", color=status_color,
            fontsize=36, fontweight="bold")
    ax.text(0.5, 0.59, "Self-attested  ·  Audit-verifiable  ·  On-device",
            ha="center", color=SOFT, fontsize=11)

    score = (data.get("compliance_score") or {}).get("score", "-")
    grade = (data.get("compliance_score") or {}).get("grade", "-")
    ax.text(0.5, 0.46, f"{score} / 100",
            ha="center", color=GREEN, fontsize=42, fontweight="bold")
    ax.text(0.5, 0.40, f"Compliance grade {grade}",
            ha="center", color=SOFT, fontsize=12)

    # Stat strip
    rows = [
        ("Session",   (data.get("session_id") or "-")[:16] + "..."),
        ("Started",   data.get("started_utc", "-")),
        ("Ended",     data.get("ended_utc", "-")),
        ("Duration",  f'{data.get("duration_seconds", 0):.2f}s'),
        ("Frames",    str(data.get("total_frames", "-"))),
        ("Persons",   str(data.get("total_persons_counted", "-"))),
    ]
    y = 0.30
    for k, v in rows:
        ax.text(0.18, y, k, color=SOFT, fontsize=10)
        ax.text(0.50, y, str(v), color=TEXT, fontsize=10)
        y -= 0.026

    _footer(ax)
    pdf.savefig(fig, facecolor=BG)
    plt.close(fig)


def _rules_page(pdf: PdfPages, data: dict) -> None:
    fig = _new_page()
    ax = fig.gca()
    ax.text(0.08, 0.92, "Constitutional rules triggered",
            color=TEXT, fontsize=18, fontweight="bold")
    ax.text(0.08, 0.88, "Counts of each rule that fired during the session.",
            color=SOFT, fontsize=10)

    rules_triggered = data.get("rules_triggered") or {}
    y = 0.80
    headers = [("Rule", 0.10), ("Triggers", 0.65)]
    for label, x in headers:
        ax.text(x, y, label, color=DIM, fontsize=9, fontweight="bold")
    y -= 0.02
    ax.hlines(y, 0.08, 0.92, colors=BORDER, linewidth=0.5)
    y -= 0.015

    for rid, n in sorted(rules_triggered.items()):
        if y < 0.08:
            break
        ax.text(0.10, y, rid, color=TEXT, fontsize=10, family="monospace")
        ax.text(0.65, y, str(n), color=GREEN, fontsize=10)
        y -= 0.022

    _footer(ax)
    pdf.savefig(fig, facecolor=BG)
    plt.close(fig)


def _score_page(pdf: PdfPages, data: dict) -> None:
    score = data.get("compliance_score") or {}
    fig = _new_page()
    ax = fig.gca()
    ax.text(0.08, 0.92, "Compliance score breakdown",
            color=TEXT, fontsize=18, fontweight="bold")
    ax.text(0.08, 0.88, "Sub-scores summing to 100. See docs/COMPLIANCE_SCORE.md.",
            color=SOFT, fontsize=10)

    rows = [
        ("Rule coverage",          score.get("rule_coverage_score", 0), 30),
        ("Status mix",             score.get("status_mix_score", 0),     25),
        ("Audit integrity",        score.get("audit_integrity_score", 0), 25),
        ("DP budget respect",      score.get("dp_budget_score", 0),       10),
        ("Redaction density",      score.get("redaction_density_score", 0), 10),
    ]
    y = 0.78
    for name, value, ceiling in rows:
        # Bar
        ax.add_patch(mpatches.FancyBboxPatch(
            (0.08, y - 0.005), 0.84, 0.020,
            boxstyle="round,pad=0,rounding_size=0.008",
            linewidth=0, facecolor=CARD,
        ))
        bar_w = 0.84 * (value / max(ceiling, 1))
        ax.add_patch(mpatches.FancyBboxPatch(
            (0.08, y - 0.005), bar_w, 0.020,
            boxstyle="round,pad=0,rounding_size=0.008",
            linewidth=0, facecolor=GREEN,
        ))
        ax.text(0.08, y + 0.020, name, color=TEXT, fontsize=10)
        ax.text(0.84, y + 0.020, f"{value}/{ceiling}", color=GREEN, fontsize=10,
                ha="left")
        y -= 0.078

    bd = score.get("breakdown") or {}
    y -= 0.02
    ax.text(0.08, y, "Reasoning", color=DIM, fontsize=10, fontweight="bold")
    y -= 0.025
    for k, v in bd.items():
        if y < 0.12:
            break
        ax.text(0.08, y, f"{k}: {v}", color=SOFT, fontsize=8)
        y -= 0.022

    _footer(ax)
    pdf.savefig(fig, facecolor=BG)
    plt.close(fig)


def _hardware_page(pdf: PdfPages, data: dict) -> None:
    hw = data.get("hardware") or {}
    chain = data.get("audit_chain") or {}
    fig = _new_page()
    ax = fig.gca()
    ax.text(0.08, 0.92, "Attestation context",
            color=TEXT, fontsize=18, fontweight="bold")
    ax.text(0.08, 0.88,
            "The hardware and audit anchor that this certificate was issued under.",
            color=SOFT, fontsize=10)

    # Hardware card
    ax.add_patch(mpatches.FancyBboxPatch(
        (0.08, 0.62), 0.84, 0.18,
        boxstyle="round,pad=0,rounding_size=0.02",
        linewidth=1, edgecolor=BORDER, facecolor=CARD,
    ))
    ax.text(0.10, 0.76, "Hardware", color=DIM, fontsize=10, fontweight="bold")
    y = 0.72
    for k, v in [
        ("Chip",            hw.get("chip_name", "-")),
        ("Generation",      hw.get("chip_generation", "-")),
        ("Cores",           f"{hw.get('cpu_p_cores', '-')}P + {hw.get('cpu_e_cores', '-')}E"),
        ("GPU cores",       hw.get("gpu_cores", "-")),
        ("Neural Engine",   hw.get("neural_engine_cores", "-")),
        ("Unified memory",  f'{hw.get("unified_memory_gb", "-")} GB'),
        ("MLX",             hw.get("mlx_version", "-")),
    ]:
        ax.text(0.12, y, k, color=SOFT, fontsize=9)
        ax.text(0.42, y, str(v), color=TEXT, fontsize=9, family="monospace")
        y -= 0.017

    # Audit chain card
    ax.add_patch(mpatches.FancyBboxPatch(
        (0.08, 0.30), 0.84, 0.28,
        boxstyle="round,pad=0,rounding_size=0.02",
        linewidth=1, edgecolor=BORDER, facecolor=CARD,
    ))
    ax.text(0.10, 0.54, "Audit chain anchor", color=DIM, fontsize=10, fontweight="bold")
    y = 0.50
    for k, v in [
        ("Chain length", str(chain.get("chain_length", "-"))),
        ("Genesis hash", (chain.get("genesis_hash") or "-")[:32] + "..."),
        ("Head hash",    (chain.get("head_hash") or "-")[:32] + "..."),
        ("Merkle root",  (chain.get("merkle_root") or "-")[:32] + "..."),
        ("Cert integrity", (data.get("integrity_hash") or "-")[:32] + "..."),
    ]:
        ax.text(0.12, y, k, color=SOFT, fontsize=9)
        ax.text(0.42, y, str(v), color=TEXT, fontsize=8, family="monospace")
        y -= 0.040

    _footer(ax)
    pdf.savefig(fig, facecolor=BG)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _new_page() -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8.5, 11), dpi=160)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_axis_off()
    return fig


def _footer(ax) -> None:
    ax.text(
        0.5, 0.04,
        "Sovereign Vision  ·  Built by Karthik Barma  ·  github.com/TheBarmaEffect",
        ha="center", color=DIM, fontsize=8,
    )


if __name__ == "__main__":
    raise SystemExit(main())
