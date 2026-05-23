"""Rule-pack registry.

Pre-built constitutional rule packs for specific industries. A pack is
a YAML file under ``packs/`` that declares additional rules to be
layered on top of the default SV-001..SV-007 constitution.

Usage:

    from sovereign.packs import load_pack, list_packs
    from sovereign.firewall import ConstitutionalFirewall

    rules = load_pack("hipaa")    # default rules + HIPAA pack
    fw = ConstitutionalFirewall(rules=rules)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sovereign.rules import (
    DEFAULT_RULES,
    ConstitutionalRule,
    RuleAction,
    RuleSeverity,
)

logger = logging.getLogger(__name__)

_PACKS_DIR = Path(__file__).parent.parent / "packs"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_packs() -> list[str]:
    """Return the names of every installed pack."""
    if not _PACKS_DIR.exists():
        return []
    return sorted(p.stem for p in _PACKS_DIR.glob("*.yaml"))


def pack_metadata(name: str) -> dict[str, Any]:
    """Return the `pack:` block of a pack without loading its rules."""
    data = _load_yaml(name)
    return dict(data.get("pack") or {})


def load_pack(
    name: str,
    base: tuple[ConstitutionalRule, ...] = DEFAULT_RULES,
) -> tuple[ConstitutionalRule, ...]:
    """Return the default rules plus the rules in `name`'s pack.

    Pack rules are appended to the base; their severity ordering kicks
    in at firewall evaluation time.
    """
    data = _load_yaml(name)
    rules = list(base)
    for raw in data.get("rules") or []:
        rules.append(_make_rule(raw))
    return tuple(rules)


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _load_yaml(name: str) -> dict[str, Any]:
    path = _PACKS_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Pack not found: {name}")
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "PyYAML is required to load rule packs. `pip install PyYAML`."
        ) from exc
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Pack YAML root must be a mapping: {name}")
    return data


def _make_rule(raw: dict[str, Any]) -> ConstitutionalRule:
    return ConstitutionalRule(
        rule_id=str(raw["rule_id"]),
        name=str(raw["name"]),
        description=str(raw["description"]),
        applies_to=tuple(raw.get("applies_to") or ("*",)),
        action=RuleAction(str(raw["action"]).upper()),
        severity=RuleSeverity(str(raw["severity"]).upper()),
        legal_basis=str(raw["legal_basis"]),
        confidence_floor=raw.get("confidence_floor"),
        aggregation_window=raw.get("aggregation_window"),
        metadata=tuple((k, str(v)) for k, v in (raw.get("metadata") or {}).items()),
    )
