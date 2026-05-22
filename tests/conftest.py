"""Pytest fixtures shared by the Sovereign Vision test suite."""
from __future__ import annotations

import sys
from pathlib import Path

# Make the package importable when running pytest from a fresh checkout
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import numpy as np  # noqa: E402
import pytest  # noqa: E402

from sovereign.firewall import ConstitutionalFirewall, RawDetection  # noqa: E402


@pytest.fixture()
def firewall() -> ConstitutionalFirewall:
    return ConstitutionalFirewall()


@pytest.fixture()
def synthetic_frame() -> np.ndarray:
    rng = np.random.default_rng(42)
    return rng.integers(0, 255, size=(720, 1280, 3), dtype=np.uint8)


@pytest.fixture()
def sample_detections() -> list[RawDetection]:
    return [
        RawDetection("person", 0.92, (100, 200, 80, 200), track_id=7),
        RawDetection("person", 0.55, (300, 200, 80, 200), track_id=9),
        RawDetection("cell phone", 0.81, (400, 350, 40, 60)),
        RawDetection("knife", 0.79, (500, 250, 50, 30)),
    ]
