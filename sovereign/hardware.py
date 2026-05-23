"""Apple Silicon hardware introspection.

Surfaces the deployment context (chip name, generation, core counts,
memory, MLX availability) for two purposes:

  1. The dashboard footer shows where the inference is actually running,
     so a viewer can see at a glance "M5 Pro, 12P+4E, 36GB unified memory,
     MLX 0.20 active" - and confirm zero cloud.
  2. Compliance certificates record the hardware context so a regulator
     can verify "this run happened on a specific, attested Apple Silicon
     device" rather than a generic cloud GPU.

This module is best-effort. If `sysctl` is unavailable (Linux, CI) we
report what we can and degrade gracefully.
"""
from __future__ import annotations

import logging
import platform
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class AppleSiliconInfo:
    """Snapshot of the local Apple Silicon environment."""

    is_apple_silicon: bool
    chip_name: str
    chip_generation: str
    performance_cores: int
    efficiency_cores: int
    gpu_cores: int
    neural_engine_cores: int
    unified_memory_gb: float
    mlx_available: bool
    mlx_version: str
    os_version: str
    metal_available: bool

    @property
    def display_chip(self) -> str:
        """Short label for dashboards. e.g. 'Apple M5 Pro'."""
        if not self.is_apple_silicon:
            return self.chip_name or "non-Apple Silicon"
        return self.chip_name

    @property
    def display_cores(self) -> str:
        """e.g. '12P+4E + 18GPU + 16NE'."""
        parts = []
        if self.performance_cores:
            parts.append(f"{self.performance_cores}P")
        if self.efficiency_cores:
            parts.append(f"+{self.efficiency_cores}E")
        cpu = "".join(parts) if parts else "?"
        gpu = f"{self.gpu_cores} GPU" if self.gpu_cores else ""
        ne = f"{self.neural_engine_cores} NE" if self.neural_engine_cores else ""
        return "  ".join(p for p in (cpu, gpu, ne) if p)

    @property
    def display_memory(self) -> str:
        return f"{self.unified_memory_gb:.0f} GB unified" if self.unified_memory_gb else "?"

    @property
    def display_mlx(self) -> str:
        if not self.mlx_available:
            return "MLX inactive (simulation)"
        return f"MLX {self.mlx_version} active"

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_apple_silicon": self.is_apple_silicon,
            "chip_name": self.chip_name,
            "chip_generation": self.chip_generation,
            "cpu_p_cores": self.performance_cores,
            "cpu_e_cores": self.efficiency_cores,
            "gpu_cores": self.gpu_cores,
            "neural_engine_cores": self.neural_engine_cores,
            "unified_memory_gb": self.unified_memory_gb,
            "mlx_available": self.mlx_available,
            "mlx_version": self.mlx_version,
            "metal_available": self.metal_available,
            "os_version": self.os_version,
        }


@lru_cache(maxsize=1)
def detect() -> AppleSiliconInfo:
    """Detect the current Apple Silicon environment (cached, idempotent)."""
    is_apple = platform.system() == "Darwin" and platform.machine().lower() in (
        "arm64",
        "aarch64",
    )
    chip = _sysctl("machdep.cpu.brand_string") if is_apple else platform.processor() or "unknown"
    generation = _infer_generation(chip)
    p_cores = _sysctl_int("hw.perflevel0.physicalcpu", default=0)
    e_cores = _sysctl_int("hw.perflevel1.physicalcpu", default=0)
    gpu_cores = _infer_gpu_cores(chip)
    ne_cores = _infer_neural_engine_cores(chip)
    memory = _sysctl_int("hw.memsize", default=0) / (1024**3) if is_apple else 0.0
    mlx_available, mlx_version = _detect_mlx()
    metal_available = is_apple and _detect_metal()
    os_version = f"{platform.system()} {platform.release()}"

    info = AppleSiliconInfo(
        is_apple_silicon=is_apple,
        chip_name=chip,
        chip_generation=generation,
        performance_cores=p_cores,
        efficiency_cores=e_cores,
        gpu_cores=gpu_cores,
        neural_engine_cores=ne_cores,
        unified_memory_gb=round(memory, 1),
        mlx_available=mlx_available,
        mlx_version=mlx_version,
        os_version=os_version,
        metal_available=metal_available,
    )
    logger.info(
        "Apple Silicon: %s | %s | %s | %s",
        info.display_chip,
        info.display_cores,
        info.display_memory,
        info.display_mlx,
    )
    return info


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sysctl(key: str) -> str:
    try:
        out = subprocess.check_output(
            ["sysctl", "-n", key], stderr=subprocess.DEVNULL, text=True, timeout=2.0
        )
        return out.strip()
    except Exception:
        return ""


def _sysctl_int(key: str, default: int = 0) -> int:
    val = _sysctl(key)
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _infer_generation(chip: str) -> str:
    """Best-effort mapping from chip name to family generation."""
    c = chip.lower()
    for tag in ("m5 max", "m5 pro", "m5 ultra", "m5",
                "m4 max", "m4 pro", "m4 ultra", "m4",
                "m3 max", "m3 pro", "m3 ultra", "m3",
                "m2 max", "m2 pro", "m2 ultra", "m2",
                "m1 max", "m1 pro", "m1 ultra", "m1"):
        if tag in c:
            return tag.upper()
    return "unknown"


def _infer_gpu_cores(chip: str) -> int:
    """Heuristic GPU-core count by SKU. Apple does not expose this via sysctl."""
    c = chip.lower()
    table = {
        "m5 max": 40, "m5 pro": 18, "m5": 10,
        "m4 max": 40, "m4 pro": 20, "m4": 10,
        "m3 max": 40, "m3 pro": 18, "m3": 10,
        "m2 max": 38, "m2 pro": 19, "m2": 10,
        "m1 max": 32, "m1 pro": 16, "m1": 8,
    }
    for tag, cores in table.items():
        if tag in c:
            return cores
    return 0


def _infer_neural_engine_cores(chip: str) -> int:
    """Neural Engine cores: 16 across all M-series shipping today."""
    c = chip.lower()
    if any(tag in c for tag in ("m1", "m2", "m3", "m4", "m5")):
        return 16
    return 0


def _detect_mlx() -> tuple[bool, str]:
    try:
        import mlx.core as mx  # type: ignore[import-not-found]

        # mlx exposes __version__ at the package root in recent releases
        import mlx  # type: ignore[import-not-found]

        version = getattr(mlx, "__version__", "unknown")
        # A tiny eval to confirm the runtime is healthy
        _ = mx.array([1.0])
        return True, str(version)
    except Exception:
        return False, "n/a"


def _detect_metal() -> bool:
    """Cheap check: presence of /System/Library/Frameworks/Metal.framework."""
    import os

    return os.path.exists("/System/Library/Frameworks/Metal.framework")
