"""Render a clean architecture diagram for the README.

Uses matplotlib; outputs to assets/architecture.png.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt


def main() -> int:
    output = Path("assets/architecture.png")
    output.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(14, 6), dpi=160)
    fig.patch.set_facecolor("#0A0B0E")
    ax.set_facecolor("#0A0B0E")

    # Apple-inspired palette
    BLUE   = "#0A84FF"
    GREEN  = "#30D158"
    RED    = "#FF453A"
    AMBER  = "#FF9F0A"
    TEXT   = "#F5F7FA"
    SOFT   = "#98A1B0"
    BG_CARD = "#1C1F26"

    boxes = [
        ("Camera",                  0.04, 0.50, 0.13, 0.30, BLUE),
        ("YOLO26 MLX\n(Apple Silicon)", 0.22, 0.50, 0.17, 0.30, BLUE),
        ("Constitutional\nFirewall\n(SV-001..SV-007)", 0.46, 0.50, 0.20, 0.30, RED),
        ("Zone\nAggregator", 0.71, 0.65, 0.13, 0.20, GREEN),
        ("Merkle\nAudit Chain", 0.71, 0.35, 0.13, 0.20, GREEN),
        ("Compliance\nCertificate (JSON)", 0.87, 0.50, 0.11, 0.30, AMBER),
    ]
    for label, x, y, w, h, color in boxes:
        rect = mpatches.FancyBboxPatch(
            (x, y),
            w, h,
            boxstyle="round,pad=0.012,rounding_size=0.018",
            linewidth=1.5,
            edgecolor=color,
            facecolor=BG_CARD,
        )
        ax.add_patch(rect)
        ax.text(
            x + w / 2,
            y + h / 2,
            label,
            ha="center",
            va="center",
            color=TEXT,
            fontsize=12,
            fontweight="semibold",
        )

    # Arrows connecting boxes
    def arrow(x1, y1, x2, y2, color):
        ax.annotate(
            "",
            xy=(x2, y2),
            xytext=(x1, y1),
            arrowprops=dict(
                arrowstyle="->",
                color=color,
                lw=1.6,
                shrinkA=2,
                shrinkB=2,
            ),
        )

    arrow(0.17, 0.65, 0.22, 0.65, BLUE)
    arrow(0.39, 0.65, 0.46, 0.65, BLUE)
    arrow(0.66, 0.70, 0.71, 0.75, GREEN)
    arrow(0.66, 0.60, 0.71, 0.45, GREEN)
    arrow(0.84, 0.75, 0.87, 0.65, AMBER)
    arrow(0.84, 0.45, 0.87, 0.65, AMBER)

    # Annotations
    ax.text(
        0.46 + 0.10, 0.92,
        "raw detections (PII)  NEVER leave this stage",
        ha="center", va="center", color=RED, fontsize=10, style="italic",
    )
    ax.text(
        0.04, 0.16,
        "Camera frame",
        color=SOFT, fontsize=9,
    )
    ax.text(
        0.87, 0.16,
        "Audit-verifiable\naggregate-only output",
        color=GREEN, fontsize=9,
    )

    # Title strip
    ax.text(
        0.5, 1.02,
        "Sovereign Vision  ·  Constitutional Firewall data flow",
        ha="center", va="bottom",
        color=TEXT, fontsize=15, fontweight="bold",
    )
    ax.text(
        0.5, -0.05,
        "on-device  ·  zero cloud  ·  GDPR Articles 4, 9, 22, 89  ·  HIPAA Safe Harbor  ·  CCPA",
        ha="center", va="top",
        color=SOFT, fontsize=10,
    )

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(output, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
