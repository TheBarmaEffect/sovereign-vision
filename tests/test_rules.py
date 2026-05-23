"""Tests for the constitutional rule data model."""
from __future__ import annotations

import json

import pytest

from sovereign.rules import (
    DEFAULT_RULES,
    PERSON_LIKE_CLASSES,
    SENSITIVE_OBJECT_CLASSES,
    ConstitutionalRule,
    RuleAction,
    RuleSeverity,
    applicable_rules,
    validate_rule_set,
)


def test_default_rule_count() -> None:
    assert len(DEFAULT_RULES) == 7


def test_all_default_rule_ids_present() -> None:
    ids = {r.rule_id for r in DEFAULT_RULES}
    assert ids == {f"SV-00{i}" for i in range(1, 8)}


def test_rule_immutability() -> None:
    rule = DEFAULT_RULES[0]
    with pytest.raises(Exception):
        rule.name = "tampered"  # type: ignore[misc]


def test_rule_to_dict_round_trip() -> None:
    rule = DEFAULT_RULES[0]
    payload = rule.to_dict()
    encoded = json.dumps(payload)
    assert "SV-001" in encoded
    assert "GDPR" in encoded


def test_validate_rule_set_rejects_duplicates() -> None:
    rules = list(DEFAULT_RULES) + [DEFAULT_RULES[0]]
    with pytest.raises(ValueError, match="Duplicate rule_id"):
        validate_rule_set(rules)


def test_applicable_rules_sorted_by_severity() -> None:
    rules = applicable_rules(DEFAULT_RULES, "person")
    priorities = [r.severity.priority for r in rules]
    assert priorities == sorted(priorities)


def test_person_rules_include_critical() -> None:
    rules = applicable_rules(DEFAULT_RULES, "person")
    severities = {r.severity for r in rules}
    assert RuleSeverity.CRITICAL in severities


def test_wildcard_rule_applies_to_all_classes() -> None:
    aggregate_rule = next(r for r in DEFAULT_RULES if r.rule_id == "SV-004")
    assert aggregate_rule.applies("person")
    assert aggregate_rule.applies("car")
    assert aggregate_rule.applies("anything")


def test_sensitive_class_constants() -> None:
    assert "knife" in SENSITIVE_OBJECT_CLASSES
    assert "person" in PERSON_LIKE_CLASSES


def test_confidence_floor_only_on_block_rule() -> None:
    floor_rule = next(r for r in DEFAULT_RULES if r.rule_id == "SV-005")
    assert floor_rule.confidence_floor == 0.75
    assert floor_rule.action == RuleAction.BLOCK


def test_legal_basis_populated_for_every_rule() -> None:
    for rule in DEFAULT_RULES:
        assert rule.legal_basis
        assert len(rule.legal_basis) >= 10  # arbitrary but non-empty
