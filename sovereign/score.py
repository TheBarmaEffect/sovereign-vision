"""Compliance score computation.

Turns a session's run-time metrics into a single 0-100 score that a
compliance officer can read at a glance. The score is intentionally
opinionated: it favours runs where every critical rule fired at least
once, the status mix is dominated by CLEAR, the DP epsilon budget was
respected, and the audit chain verifies.

The scoring formula is documented in docs/COMPLIANCE_SCORE.md (the
math is open so it can be challenged).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


CRITICAL_RULE_IDS: tuple[str, ...] = ("SV-001", "SV-002", "SV-003")
HIGH_RULE_IDS: tuple[str, ...] = ("SV-004", "SV-005", "SV-007")
MEDIUM_RULE_IDS: tuple[str, ...] = ("SV-006",)


@dataclass(slots=True, frozen=True)
class ComplianceScore:
    """A reproducible 0-100 score with a human-readable breakdown."""

    score: int
    grade: str
    rule_coverage_score: int
    status_mix_score: int
    audit_integrity_score: int
    dp_budget_score: int
    redaction_density_score: int
    breakdown: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "score": self.score,
            "grade": self.grade,
            "rule_coverage_score": self.rule_coverage_score,
            "status_mix_score": self.status_mix_score,
            "audit_integrity_score": self.audit_integrity_score,
            "dp_budget_score": self.dp_budget_score,
            "redaction_density_score": self.redaction_density_score,
            "breakdown": dict(self.breakdown),
        }


def compute(
    rules_triggered: dict[str, int],
    total_frames: int,
    status_counts: dict[str, int],
    redactions: int,
    audit_chain_verified: bool,
    dp_cumulative_epsilon: float,
    dp_max_recommended_epsilon: float | None = None,
) -> ComplianceScore:
    """Compute compliance score.

    The DP budget ceiling scales with frame count: each per-frame
    aggregate is one query at eps=1.0, so a session running N frames is
    allowed up to ~N epsilon under naive composition. We use 1.5 * N as
    the recommended ceiling, giving 33% headroom before we start
    penalising. Override by passing `dp_max_recommended_epsilon`
    explicitly.
    """
    if dp_max_recommended_epsilon is None:
        dp_max_recommended_epsilon = max(10.0, total_frames * 1.5)
    """Compute a compliance score for a session."""
    rc = _rule_coverage(rules_triggered)
    sm = _status_mix(status_counts, total_frames)
    ai = 25 if audit_chain_verified else 0
    dp = _dp_budget(dp_cumulative_epsilon, dp_max_recommended_epsilon)
    rd = _redaction_density(redactions, total_frames)

    total = rc + sm + ai + dp + rd
    score = max(0, min(100, total))
    grade = _grade(score)

    breakdown = {
        "rule_coverage": _explain_rule_coverage(rules_triggered),
        "status_mix": _explain_status_mix(status_counts, total_frames),
        "audit_integrity": "PASS" if audit_chain_verified else "FAIL: chain did not verify",
        "dp_budget": _explain_dp_budget(dp_cumulative_epsilon, dp_max_recommended_epsilon),
        "redaction_density": _explain_redaction_density(redactions, total_frames),
    }

    return ComplianceScore(
        score=score,
        grade=grade,
        rule_coverage_score=rc,
        status_mix_score=sm,
        audit_integrity_score=ai,
        dp_budget_score=dp,
        redaction_density_score=rd,
        breakdown=breakdown,
    )


# ---------------------------------------------------------------------------
# Sub-scores (sum to 100)
# ---------------------------------------------------------------------------


def _rule_coverage(rules: dict[str, int]) -> int:
    """30 pts. Every critical rule must have fired at least once."""
    crit_hits = sum(1 for r in CRITICAL_RULE_IDS if rules.get(r, 0) > 0)
    high_hits = sum(1 for r in HIGH_RULE_IDS if rules.get(r, 0) > 0)
    crit_score = int(20 * crit_hits / max(len(CRITICAL_RULE_IDS), 1))
    high_score = int(10 * high_hits / max(len(HIGH_RULE_IDS), 1))
    return crit_score + high_score


def _status_mix(counts: dict[str, int], total_frames: int) -> int:
    """25 pts. CLEAR frames dominate; BLOCKED frames are heavily penalised."""
    if total_frames <= 0:
        return 0
    clear = counts.get("CLEAR", 0)
    escalated = counts.get("ESCALATED", 0)
    blocked = counts.get("BLOCKED", 0)
    clear_ratio = clear / total_frames
    blocked_ratio = blocked / total_frames
    return max(0, min(25, int(25 * clear_ratio - 25 * blocked_ratio)))


def _dp_budget(spent: float, recommended_max: float) -> int:
    """10 pts. Below recommended max is full marks; over is rapid decay."""
    if spent <= recommended_max:
        return 10
    over = spent - recommended_max
    return max(0, 10 - int(over))


def _redaction_density(redactions: int, frames: int) -> int:
    """10 pts. Some redactions expected; zero means no PII detected (also OK)."""
    if frames <= 0:
        return 10
    per_frame = redactions / frames
    if per_frame == 0:
        return 8  # not zero (we want to see SOMETHING)
    if per_frame > 50:
        return 5  # unusually high; may indicate over-triggering
    return 10


# ---------------------------------------------------------------------------
# Explanations
# ---------------------------------------------------------------------------


def _explain_rule_coverage(rules: dict[str, int]) -> str:
    hit_crit = [r for r in CRITICAL_RULE_IDS if rules.get(r, 0) > 0]
    miss_crit = [r for r in CRITICAL_RULE_IDS if rules.get(r, 0) == 0]
    if not miss_crit:
        return f"all critical rules fired: {hit_crit}"
    return f"critical rules silent: {miss_crit}"


def _explain_status_mix(counts: dict[str, int], total: int) -> str:
    if total == 0:
        return "no frames processed"
    parts = [f"{k}={v}" for k, v in counts.items() if v > 0]
    return ", ".join(parts) if parts else "no statuses recorded"


def _explain_dp_budget(spent: float, recommended: float) -> str:
    pct = (spent / recommended * 100) if recommended else 0
    return f"{spent:.2f} of {recommended:.0f} recommended ({pct:.0f}%)"


def _explain_redaction_density(redactions: int, frames: int) -> str:
    if frames <= 0:
        return "no frames processed"
    return f"{redactions} redactions across {frames} frames ({redactions / frames:.2f}/frame)"


def _grade(score: int) -> str:
    if score >= 95:
        return "A+"
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"
