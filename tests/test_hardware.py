"""Tests for the Apple Silicon introspection module."""
from __future__ import annotations

from sovereign.hardware import AppleSiliconInfo, detect


def test_detect_returns_apple_silicon_info() -> None:
    info = detect()
    assert isinstance(info, AppleSiliconInfo)


def test_detect_is_cached() -> None:
    a = detect()
    b = detect()
    assert a is b


def test_to_dict_round_trip_keys() -> None:
    info = detect()
    d = info.to_dict()
    for key in (
        "is_apple_silicon",
        "chip_name",
        "chip_generation",
        "cpu_p_cores",
        "cpu_e_cores",
        "gpu_cores",
        "neural_engine_cores",
        "unified_memory_gb",
        "mlx_available",
        "mlx_version",
        "metal_available",
        "os_version",
    ):
        assert key in d


def test_display_strings_are_strings() -> None:
    info = detect()
    for s in (info.display_chip, info.display_cores,
              info.display_memory, info.display_mlx):
        assert isinstance(s, str)
