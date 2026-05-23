"""Tests for SV-007 differential privacy mechanism."""
from __future__ import annotations

import statistics

import pytest

from sovereign.dp import (
    DPConfig,
    composition_epsilon,
    laplace_noise,
    noisy_count,
    noisy_dict,
)


def test_default_epsilon_is_one() -> None:
    cfg = DPConfig()
    assert cfg.epsilon == 1.0
    assert cfg.sensitivity == 1.0
    assert cfg.scale == 1.0


def test_noisy_count_returns_int() -> None:
    n = noisy_count(5)
    assert isinstance(n, int)


def test_noisy_count_clamps_negative_by_default() -> None:
    # Run many trials; with epsilon=1, count=0, noise can go negative,
    # but the clamped result must always be >= 0.
    for _ in range(200):
        assert noisy_count(0) >= 0


def test_noisy_count_distribution_centered_near_true_value() -> None:
    """For high count and many trials, the mean should be near the true value."""
    true_value = 100
    samples = [noisy_count(true_value, DPConfig(epsilon=0.5)) for _ in range(2000)]
    mean = statistics.mean(samples)
    # The Laplace mean is the true value; sample mean should be within
    # a generous margin given the sample size and scale=2.
    assert abs(mean - true_value) < 1.0


def test_noisy_dict_preserves_keys() -> None:
    d = {"zone_TL": 1, "zone_MC": 4, "zone_BR": 0}
    out = noisy_dict(d)
    assert set(out.keys()) == set(d.keys())
    for v in out.values():
        assert isinstance(v, int)
        assert v >= 0


def test_composition_epsilon_naive() -> None:
    assert composition_epsilon(0.5, 4) == pytest.approx(2.0)


def test_laplace_noise_zero_mean() -> None:
    samples = [laplace_noise(1.0) for _ in range(5000)]
    mean = statistics.mean(samples)
    assert abs(mean) < 0.2  # generous given sample size
