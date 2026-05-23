"""Differential privacy primitives for SV-007.

Adds calibrated Laplace noise to aggregate count queries with sensitivity 1,
giving an (epsilon)-DP mechanism per query. The default epsilon=1.0 is a
common production setting that provides strong privacy with practical
utility for occupancy aggregates.

References:
    Dwork, McSherry, Nissim, Smith. "Calibrating Noise to Sensitivity in
    Private Data Analysis." (2006).
    NIST SP 800-188 "De-Identifying Government Datasets" (2023).
"""
from __future__ import annotations

import math
import secrets
from dataclasses import dataclass


DEFAULT_EPSILON: float = 1.0
DEFAULT_SENSITIVITY: float = 1.0


@dataclass(slots=True, frozen=True)
class DPConfig:
    """Parameters for the SV-007 Laplace mechanism."""

    epsilon: float = DEFAULT_EPSILON
    sensitivity: float = DEFAULT_SENSITIVITY
    clamp_non_negative: bool = True

    @property
    def scale(self) -> float:
        """Laplace scale parameter b = sensitivity / epsilon."""
        return self.sensitivity / max(self.epsilon, 1e-9)


def laplace_noise(scale: float) -> float:
    """Sample Laplace(0, scale) using crypto-quality randomness.

    Uses `secrets.SystemRandom` rather than `random.random()` so the
    noise cannot be predicted by an adversary with access to a non-DP
    PRNG seed.
    """
    rng = secrets.SystemRandom()
    u = rng.random() - 0.5
    # F^{-1}(u) for Laplace(0, b): -b * sign(u) * ln(1 - 2|u|)
    if u == 0:
        return 0.0
    sign = 1.0 if u > 0 else -1.0
    return -scale * sign * math.log(1.0 - 2.0 * abs(u))


def noisy_count(count: int, cfg: DPConfig = DPConfig()) -> int:
    """Apply Laplace noise to an integer count and (optionally) clamp to >= 0."""
    raw = count + laplace_noise(cfg.scale)
    if cfg.clamp_non_negative and raw < 0:
        return 0
    return int(round(raw))


def noisy_dict(
    counts: dict[str, int], cfg: DPConfig = DPConfig()
) -> dict[str, int]:
    """Apply DP noise to every value in a dict of counts (per-zone aggregates)."""
    return {k: noisy_count(v, cfg) for k, v in counts.items()}


def composition_epsilon(per_query_epsilon: float, num_queries: int) -> float:
    """Naive sequential composition: total epsilon = k * per-query epsilon.

    Used to report the *cumulative* privacy budget consumed by a session.
    Conservative (advanced composition gives tighter bounds for large k).
    """
    return per_query_epsilon * num_queries
