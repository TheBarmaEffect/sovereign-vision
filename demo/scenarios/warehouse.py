"""Warehouse — zone monitoring and forklift-proximity scenario.

Warehouse logistics wants:
  - Occupancy by zone for OSHA forklift safety distance
  - Sensitive-object escalation (knives, sharp tools)
  - Equipment-in-zone tracking without tracking people

Sovereign Vision provides aggregate proximity events without ever
identifying who triggered them.
"""
from __future__ import annotations

from demo.scenarios import Scenario


def scenario() -> Scenario:
    return Scenario(
        name="warehouse",
        title="Warehouse — Zone Monitoring & Equipment Proximity",
        description=(
            "Aggregate proximity events between people and equipment in a "
            "logistics environment. Used for OSHA forklift safety auditing "
            "without identifying any individual worker."
        ),
        zone_labels=[
            "Dock 1",
            "Dock 2",
            "Picking Aisle A",
            "Picking Aisle B",
            "Forklift Lane",
            "High-Rack Storage",
            "Staging",
            "Receiving",
            "Charging Area",
        ],
        ppe_required=["hardhat", "vest"],
        escalation_classes=["knife", "scissors"],
        compliance_note=(
            "OSHA 29 CFR 1910.178 (powered industrial trucks). "
            "Sovereign Vision provides anonymised proximity evidence that "
            "satisfies OSHA recordkeeping without GDPR/CCPA exposure."
        ),
        extra={
            "forklift_lane_alert_when_person_present": True,
        },
    )
