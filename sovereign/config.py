"""Type-safe YAML configuration for Sovereign Vision.

Enterprise deployments need configurable rule severities, custom sensitive
classes, custom zone labels, scenario-specific PPE requirements, etc. This
module loads a YAML file into a strongly-typed `SovereignConfig` so that
the firewall remains the source of truth for what's enforced.

Example YAML:

    session:
      name: "factory-line-3"
      output_dir: "./certificates"
    detector:
      model_path: "models/yolo26m.npz"
      conf_threshold: 0.25
    aggregator:
      rolling_window: 30
      ppe_window: 10
    rules:
      confidence_floor: 0.75
      aggregation_window: 5
      sensitive_classes:
        - knife
        - gun
        - cell phone
    scenario:
      name: "factory_floor"
      ppe_required: ["hardhat", "vest", "goggles"]
      zones:
        - "Entry"
        - "Assembly Line A"
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sub-configs
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class SessionConfig:
    name: str = "sovereign-vision-session"
    output_dir: str = "./certificates"
    write_frame_certs: bool = False


@dataclass(slots=True)
class DetectorConfig:
    model_path: str = "models/yolo26m.npz"
    conf_threshold: float = 0.25
    device: str = "mlx"


@dataclass(slots=True)
class AggregatorConfig:
    rolling_window: int = 30
    ppe_window: int = 10


@dataclass(slots=True)
class RulesConfig:
    confidence_floor: float = 0.75
    aggregation_window: int = 5
    sensitive_classes: list[str] = field(
        default_factory=lambda: ["knife", "gun", "cell phone", "laptop"]
    )


@dataclass(slots=True)
class ScenarioConfig:
    name: str = "default"
    ppe_required: list[str] = field(default_factory=list)
    zones: list[str] = field(default_factory=list)
    escalation_rules: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DashboardConfig:
    enable_opencv: bool = True
    enable_terminal: bool = True
    window_width: int = 1920
    window_height: int = 720


# ---------------------------------------------------------------------------
# Root config
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class SovereignConfig:
    """Root configuration object."""

    session: SessionConfig = field(default_factory=SessionConfig)
    detector: DetectorConfig = field(default_factory=DetectorConfig)
    aggregator: AggregatorConfig = field(default_factory=AggregatorConfig)
    rules: RulesConfig = field(default_factory=RulesConfig)
    scenario: ScenarioConfig = field(default_factory=ScenarioConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)

    # -- loaders -------------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path | None = None) -> "SovereignConfig":
        """Load from YAML or return defaults if path is None / missing."""
        if path is None:
            return cls()
        p = Path(path)
        if not p.exists():
            logger.warning("Config %s not found - using defaults", p)
            return cls()
        return cls.from_dict(_load_yaml(p))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SovereignConfig":
        return cls(
            session=SessionConfig(**(data.get("session") or {})),
            detector=DetectorConfig(**(data.get("detector") or {})),
            aggregator=AggregatorConfig(**(data.get("aggregator") or {})),
            rules=RulesConfig(**(data.get("rules") or {})),
            scenario=ScenarioConfig(**(data.get("scenario") or {})),
            dashboard=DashboardConfig(**(data.get("dashboard") or {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "PyYAML is required to load YAML configs. `pip install PyYAML`."
        ) from exc
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config root must be a mapping; got {type(data).__name__}")
    return data
