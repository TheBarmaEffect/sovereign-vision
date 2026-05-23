"""Retail floor - foot traffic analytics scenario.

Retailers want store analytics: dwell time, hotspot zones, entry/exit flow.
They want this WITHOUT loyalty cards, WITHOUT cookies, WITHOUT face recognition.
Sovereign Vision gives them all of it with provable anonymity.
"""
from __future__ import annotations

from demo.scenarios import Scenario


def scenario() -> Scenario:
    return Scenario(
        name="retail_floor",
        title="Retail Floor - Foot Traffic Analytics",
        description=(
            "Store-level dwell time, hotspot identification, and flow analytics "
            "without tracking any individual. No loyalty card, no cookies, no "
            "facial recognition required."
        ),
        zone_labels=[
            "Entrance",
            "Promotions",
            "Electronics",
            "Apparel",
            "Home Goods",
            "Grocery",
            "Checkout",
            "Customer Service",
            "Exit",
        ],
        ppe_required=[],
        escalation_classes=["knife", "gun"],
        compliance_note=(
            "CCPA / CPRA compliant by design - aggregate-only analytics. "
            "No 'personal information' as defined by Cal. Civ. Code §1798.140 "
            "is collected, processed, or stored."
        ),
        extra={
            "peak_hour_alert": True,
            "hotspot_top_k": 3,
            "dwell_time_aggregate_only": True,
        },
    )
