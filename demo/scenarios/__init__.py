"""Enterprise demo scenarios - factory floor, retail, warehouse."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(slots=True)
class Scenario:
    """A demo scenario configuration."""

    name: str
    title: str
    description: str
    zone_labels: list[str] = field(default_factory=list)
    ppe_required: list[str] = field(default_factory=list)
    escalation_classes: list[str] = field(default_factory=list)
    compliance_note: str = ""
    extra: dict[str, object] = field(default_factory=dict)


def load_scenario(name: str) -> Scenario:
    """Load a scenario by name. Defaults to factory_floor."""
    from demo.scenarios import factory_floor, retail_floor, warehouse

    registry: dict[str, Callable[[], Scenario]] = {
        "factory_floor": factory_floor.scenario,
        "retail_floor": retail_floor.scenario,
        "warehouse": warehouse.scenario,
    }
    builder = registry.get(name, factory_floor.scenario)
    return builder()


def list_scenarios() -> list[str]:
    return ["factory_floor", "retail_floor", "warehouse"]
