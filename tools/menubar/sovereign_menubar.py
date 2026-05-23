"""Sovereign Vision menu bar app for macOS.

A tiny menu bar app written with rumps that polls the local Sovereign
Vision REST API and surfaces:

    sovereign-vision  CLEAR | 54 fps | M5 Pro

Click to open the live dashboard, copy the latest cert hash, open the
HTML cert viewer, or quit.

Install:
    pip install rumps
    python tools/menubar/sovereign_menubar.py

You will see a green/amber/red dot plus the status string in the macOS
menu bar.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    import rumps  # type: ignore[import-not-found]
except ImportError:
    print("rumps not installed. Run: pip install rumps")
    sys.exit(1)


API_BASE = "http://127.0.0.1:8765"
POLL_SECONDS = 2.0
DOT_GREEN  = "●"  # filled circle (we render coloured strings via emoji below)
ICON_FILE = Path(__file__).parent / "icon.png"


def _api(path: str) -> dict | None:
    try:
        with urllib.request.urlopen(f"{API_BASE}{path}", timeout=1.0) as resp:
            return json.load(resp)
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return None


class SovereignMenuBar(rumps.App):
    def __init__(self) -> None:
        super().__init__(
            "Sovereign Vision",
            title="⚬ Sovereign",   # neutral icon until first poll
            icon=str(ICON_FILE) if ICON_FILE.exists() else None,
            quit_button=None,
        )

        self.menu = [
            rumps.MenuItem("Status: -",          callback=None),
            rumps.MenuItem("FPS: -",             callback=None),
            rumps.MenuItem("Rules fired: -",     callback=None),
            rumps.MenuItem("Redactions: -",      callback=None),
            None,
            rumps.MenuItem("Open dashboard",     callback=self.open_dashboard),
            rumps.MenuItem("Open cert viewer",   callback=self.open_cert_viewer),
            rumps.MenuItem("Open replay viewer", callback=self.open_replay),
            rumps.MenuItem("Open API docs",      callback=self.open_api),
            None,
            rumps.MenuItem("Copy session ID",    callback=self.copy_session),
            rumps.MenuItem("Quit",               callback=rumps.quit_application),
        ]

        self._latest_session: str = ""

        # Background polling thread (rumps timers also work; threads keep it explicit)
        threading.Thread(target=self._poll_loop, daemon=True).start()

    # -- polling -------------------------------------------------------------

    def _poll_loop(self) -> None:
        while True:
            stats = _api("/stats")
            root = _api("/")
            self._render(stats, root)
            time.sleep(POLL_SECONDS)

    def _render(self, stats: dict | None, root: dict | None) -> None:
        if stats is None or root is None:
            self.title = "⚠ Sovereign (offline)"
            self.menu["Status: -"].title = "Status: API offline"
            self.menu["FPS: -"].title    = "FPS: -"
            return

        status = "CLEAR"
        sc = stats.get("status_clear", 0)
        esc = stats.get("status_escalated", 0)
        blk = stats.get("status_blocked", 0)
        if blk > 0:
            status = "BLOCKED"
        elif esc > 0:
            status = "ESCALATED"

        dot = {"CLEAR": "\U0001F7E2", "ESCALATED": "\U0001F7E1",
               "BLOCKED": "\U0001F534"}.get(status, "⚫")
        chip = (root.get("hardware") or {}).get("chip_name", "?")
        self.title = f"{dot} {chip.split()[-1]} | {stats.get('fps', 0):.0f}fps"

        self.menu["Status: -"].title     = f"Status: {status}"
        self.menu["FPS: -"].title        = f"FPS: {stats.get('fps', 0):.1f}"
        self.menu["Rules fired: -"].title = f"Rules fired: {stats.get('total_rules_fired', 0)}"
        self.menu["Redactions: -"].title = f"Redactions: {stats.get('total_redactions', 0)}"

        self._latest_session = (root.get("session_id") or "")

    # -- callbacks -----------------------------------------------------------

    def open_dashboard(self, _) -> None:
        subprocess.Popen(
            ["osascript", "-e",
             'tell application "Terminal" to do script "sovereign demo"'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    def open_cert_viewer(self, _) -> None:
        repo = Path(__file__).resolve().parents[2]
        path = repo / "tools" / "cert_viewer.html"
        subprocess.Popen(["open", str(path)])

    def open_replay(self, _) -> None:
        repo = Path(__file__).resolve().parents[2]
        path = repo / "tools" / "replay.html"
        subprocess.Popen(["open", str(path)])

    def open_api(self, _) -> None:
        subprocess.Popen(["open", f"{API_BASE}/docs"])

    def copy_session(self, _) -> None:
        if not self._latest_session:
            rumps.notification("Sovereign Vision", "", "no session id yet")
            return
        try:
            subprocess.run(
                ["pbcopy"], input=self._latest_session.encode("utf-8"),
                check=True,
            )
            rumps.notification("Sovereign Vision", "Copied",
                               self._latest_session)
        except Exception as exc:
            rumps.notification("Sovereign Vision", "Copy failed", str(exc))


if __name__ == "__main__":
    SovereignMenuBar().run()
