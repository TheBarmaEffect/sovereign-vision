"""Sovereign Vision dashboard - main entry.

Composites the three panels into a single 1920x720 OpenCV window and runs a
parallel Rich terminal dashboard so screen recordings look great even when
the terminal is visible.

The main render loop is intentionally side-effect-free except for cv2 calls
and the certificate writes that happen inside the firewall pipeline.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Iterable

import cv2
import numpy as np

from dashboard import styles as S
from dashboard.panels import certified_panel, firewall_panel, raw_panel
from dashboard.panels.firewall_panel import FirewallPanelState
from sovereign.certificate import CertificateGenerator, FrameCertificate
from sovereign.firewall import ConstitutionalFirewall, FirewallResult, RawDetection
from sovereign.metrics import MetricsRegistry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


@dataclass
class DashboardContext:
    """Shared state for the OpenCV window and the Rich terminal."""

    firewall: ConstitutionalFirewall
    cert_gen: CertificateGenerator
    metrics: MetricsRegistry
    firewall_state: FirewallPanelState = field(default_factory=FirewallPanelState)
    last_result: FirewallResult | None = None
    last_cert: FrameCertificate | None = None
    last_cert_ns: int = 0
    tick: int = 0
    raw_detections_buffer: list[RawDetection] = field(default_factory=list)
    total_raw_detections: int = 0
    model_name: str = "yolo26m"
    hardware_label: str = ""
    quit_requested: bool = False


def composite_frame(
    ctx: DashboardContext,
    frame: "np.ndarray",
) -> "np.ndarray":
    """Render and stitch all three panels."""
    fps = ctx.metrics.snapshot().fps
    raw_panel_img = raw_panel.render(
        frame=frame,
        raw_detections=ctx.raw_detections_buffer,
        fps=fps,
        model_name=ctx.model_name,
        total_detections=ctx.total_raw_detections,
        tick=ctx.tick,
    )
    fw_panel_img = firewall_panel.render(ctx.firewall_state)

    cert_hash = ctx.last_cert.integrity_hash if ctx.last_cert is not None else ""
    age = (time.time_ns() - ctx.last_cert_ns) / 1e9 if ctx.last_cert_ns else 0.0
    cert_panel_img = certified_panel.render(
        result=ctx.last_result,
        cert_hash=cert_hash,
        last_cert_age_s=age,
        tick=ctx.tick,
        hardware_label=ctx.hardware_label,
    )

    window = np.concatenate([raw_panel_img, fw_panel_img, cert_panel_img], axis=1)
    window = _add_brand_strip(window, ctx)
    return window


def _add_brand_strip(window: "np.ndarray", ctx: "DashboardContext") -> "np.ndarray":
    """Add a 40px brand strip below the panels: author, repo, hardware."""
    from dashboard import gfx
    from dashboard import styles as S
    from dashboard.typography import STYLE_BODY, STYLE_MONO, draw_text, text_size

    h, w = window.shape[:2]
    strip_h = 44
    new = np.zeros((h + strip_h, w, 3), dtype=np.uint8)
    new[:h] = window
    gfx.vertical_gradient(new, (0, h, w, h + strip_h),
                          top_color=S.BG_HEADER, bot_color=S.BG_DEEP)

    # Left: author + research line
    left_text = "SOVEREIGN  VISION   ·   Karthik Barma   ·   github.com/TheBarmaEffect"
    draw_text(new, left_text, (S.PADDING_X, h + 14), STYLE_BODY,
              color=S.TEXT_PRIMARY)

    # Right: hardware fingerprint
    if ctx.hardware_label:
        hw = ctx.hardware_label
        tw, _ = text_size(hw, STYLE_MONO)
        draw_text(new, hw, (w - S.PADDING_X - tw, h + 16),
                  STYLE_MONO, color=S.TEXT_SECONDARY)
    return new


def ingest(
    ctx: DashboardContext,
    raw_detections: Iterable[RawDetection],
    result: FirewallResult,
    cert: FrameCertificate,
) -> None:
    """Plug a new firewall result + certificate into the dashboard state."""
    raw_list = list(raw_detections)
    ctx.raw_detections_buffer = raw_list
    ctx.total_raw_detections += len(raw_list)
    ctx.last_result = result
    ctx.last_cert = cert
    ctx.last_cert_ns = time.time_ns()
    ctx.tick += 1
    ctx.firewall_state.ingest(time.time(), result)
    ctx.metrics.record(result)


# ---------------------------------------------------------------------------
# Rich terminal dashboard
# ---------------------------------------------------------------------------


class TerminalDashboard:
    """Optional Rich dashboard running on a background thread.

    Renders a live table of recent rule events, a metrics panel, and the
    latest compliance certificate so judges see both the OpenCV window
    and a polished terminal view.
    """

    def __init__(self, ctx: DashboardContext, refresh_hz: float = 10.0) -> None:
        self._ctx = ctx
        self._refresh_hz = refresh_hz
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        try:
            import rich  # noqa: F401
        except ImportError:
            logger.warning("rich not installed - terminal dashboard disabled")
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="rich-dashboard")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def _run(self) -> None:  # pragma: no cover - terminal-only
        from rich.console import Console, Group
        from rich.layout import Layout
        from rich.live import Live
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        console = Console()
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=4),
        )
        layout["body"].split_row(
            Layout(name="events", ratio=2),
            Layout(name="metrics", ratio=1),
        )

        with Live(layout, console=console, refresh_per_second=self._refresh_hz, screen=False):
            while not self._stop_event.is_set():
                layout["header"].update(
                    Panel(
                        Text(
                            "SOVEREIGN VISION - Constitutional Firewall (live)",
                            style="bold cyan",
                        ),
                        border_style="cyan",
                    )
                )
                layout["events"].update(self._events_table())
                layout["metrics"].update(self._metrics_panel())
                layout["footer"].update(self._footer_panel())
                time.sleep(1.0 / self._refresh_hz)

    def _events_table(self):  # pragma: no cover
        from rich.table import Table

        table = Table(
            title="Live rule events",
            border_style="cyan",
            header_style="bold magenta",
            expand=True,
        )
        table.add_column("Time", width=12)
        table.add_column("Rule", width=8)
        table.add_column("Action", width=10)
        table.add_column("Class", width=14)
        table.add_column("Status")
        for ts, ev in list(self._ctx.firewall_state.events)[:20]:
            color = "green" if not ev.blocked else "red"
            status = "blocked" if ev.blocked else "applied"
            table.add_row(
                time.strftime("%H:%M:%S", time.localtime(ts)),
                ev.rule_id,
                ev.action,
                ev.applied_to_class,
                f"[{color}]{status}[/{color}]",
            )
        return table

    def _metrics_panel(self):  # pragma: no cover
        from rich.panel import Panel
        from rich.table import Table

        snap = self._ctx.metrics.snapshot()
        table = Table.grid(expand=True)
        table.add_column(style="cyan", width=18)
        table.add_column(style="white")
        table.add_row("FPS", f"{snap.fps:.1f}")
        table.add_row("Inference (ms)", f"{snap.avg_inference_ms:.2f}")
        table.add_row("Firewall (ms)", f"{snap.avg_firewall_ms:.2f}")
        table.add_row("Frames", str(snap.total_frames))
        table.add_row("Rules fired", str(snap.total_rules_fired))
        table.add_row("Redactions", str(snap.total_redactions))
        table.add_row("Certified", f"[green]{snap.status_clear}[/green]")
        table.add_row("Escalated", f"[yellow]{snap.status_escalated}[/yellow]")
        table.add_row("Blocked", f"[red]{snap.status_blocked}[/red]")
        return Panel(table, title="Metrics", border_style="green")

    def _footer_panel(self):  # pragma: no cover
        from rich.panel import Panel

        cert_short = (
            self._ctx.last_cert.integrity_hash[:32] + "..."
            if self._ctx.last_cert is not None
            else "-"
        )
        chain_short = (
            self._ctx.last_cert.chain_link_hash[:32] + "..."
            if self._ctx.last_cert is not None
            else "-"
        )
        body = (
            f"[bold]session:[/bold] {self._ctx.firewall.session_id}   "
            f"[bold]cert:[/bold] {cert_short}   "
            f"[bold]chain:[/bold] {chain_short}"
        )
        return Panel(body, border_style="cyan", title="Compliance certificate")
