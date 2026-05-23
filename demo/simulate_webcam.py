"""Synthetic webcam - used when no physical camera is detected.

Generates a smooth animated BGR frame stream with moving rectangles that
roughly correspond to the synthetic detections produced by the simulation
backend in `sovereign.detector`. The visualisation makes the demo work
100% of the time for judges who may run it on a machine without a camera.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Iterator

import numpy as np

DEFAULT_WIDTH: int = 1280
DEFAULT_HEIGHT: int = 720
DEFAULT_FPS: float = 30.0


@dataclass(slots=True)
class SyntheticFrame:
    """A frame plus the synthetic objects in it (for visualisation only)."""

    image: "np.ndarray"
    timestamp: float


class SyntheticCamera:
    """Drop-in replacement for cv2.VideoCapture in CI/no-camera environments."""

    def __init__(
        self,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        fps: float = DEFAULT_FPS,
    ) -> None:
        self._w = width
        self._h = height
        self._fps = fps
        self._tick: int = 0
        self._opened: bool = True

    def isOpened(self) -> bool:  # noqa: N802 - cv2 API
        return self._opened

    def read(self) -> tuple[bool, "np.ndarray"]:
        frame = self._render()
        self._tick += 1
        return True, frame

    def release(self) -> None:
        self._opened = False

    # -- internals -----------------------------------------------------------

    def _render(self) -> "np.ndarray":
        frame = np.zeros((self._h, self._w, 3), dtype=np.uint8)
        # gradient background to make it feel like a factory floor
        for y in range(self._h):
            shade = 18 + int(28 * (y / self._h))
            frame[y, :] = (shade, shade // 2, max(shade - 8, 0))

        t = self._tick
        # moving "person" silhouettes
        for i, color in enumerate(((0, 220, 250), (60, 200, 240), (40, 240, 220))):
            cx = int((self._w // 2) + (self._w // 3) * math.sin((t + i * 50) / 30.0))
            cy = int(self._h // 2 + 40 * math.cos((t + i * 90) / 20.0))
            x = max(20, cx - 40)
            y = max(20, cy - 100)
            _rect(frame, x, y, 80, 200, color)

        # occasional "phone" rectangle
        if t % 5 == 0:
            _rect(frame, int(self._w * 0.4), int(self._h * 0.55), 40, 60, (200, 200, 200))

        # rare "sensitive object"
        if t % 47 == 0:
            _rect(frame, int(self._w * 0.6), int(self._h * 0.45), 50, 30, (40, 40, 220))

        return frame


def stream(
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    fps: float = DEFAULT_FPS,
) -> Iterator[SyntheticFrame]:
    """Iterator wrapper around SyntheticCamera with timing control."""
    cam = SyntheticCamera(width=width, height=height, fps=fps)
    interval = 1.0 / max(fps, 1.0)
    while cam.isOpened():
        ok, frame = cam.read()
        if not ok:
            break
        yield SyntheticFrame(image=frame, timestamp=time.time())
        time.sleep(interval)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _rect(
    frame: "np.ndarray",
    x: int,
    y: int,
    w: int,
    h: int,
    color: tuple[int, int, int],
) -> None:
    x2 = min(frame.shape[1], x + w)
    y2 = min(frame.shape[0], y + h)
    x = max(0, x)
    y = max(0, y)
    if x2 <= x or y2 <= y:
        return
    frame[y:y2, x:x2] = color
