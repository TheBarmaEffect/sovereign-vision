"""Factory floor - PPE compliance monitoring scenario.

The factory wants to know:
  - Are workers wearing required PPE?
  - Is anyone in the hazmat zone alone or in pairs > 2?
  - How does PPE compliance trend through the shift?

Sovereign Vision answers every question without ever storing who was where.
"""
from __future__ import annotations

from demo.scenarios import Scenario


def scenario() -> Scenario:
    return Scenario(
        name="factory_floor",
        title="Factory Floor - PPE Compliance Monitoring",
        description=(
            "Real-time enforcement of PPE requirements on an active "
            "manufacturing line. Workers' identities are never recorded, "
            "but every compliance event is provably logged for OSHA audits."
        ),
        zone_labels=[
            "Entry",
            "Assembly Line A",
            "Assembly Line B",
            "QA Station",
            "Hazmat Zone",
            "Tool Crib",
            "Break Area",
            "Loading Bay",
            "Exit Corridor",
        ],
        ppe_required=["hardhat", "vest", "goggles"],
        escalation_classes=["knife", "gun"],
        compliance_note=(
            "OSHA 29 CFR 1910.132 (PPE), 1910.134 (respiratory protection). "
            "Sovereign Vision certificates are GDPR Article 89 anonymisation-"
            "compliant evidence suitable for OSHA recordkeeping."
        ),
        extra={
            "hazmat_zone_max_occupancy": 2,
            "compliance_threshold": 0.80,
            "alert_on_breach": True,
        },
    )
