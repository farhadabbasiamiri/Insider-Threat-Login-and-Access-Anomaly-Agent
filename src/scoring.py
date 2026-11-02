"""Transparent rule-based review-priority score.

The score ranks user-days for analyst attention. It is NOT a probability of
compromise or wrongdoing. Each point added is tied to a named rule and the
event IDs that triggered it.
"""

from __future__ import annotations

from src.config import (
    FAILED_BURST_MIN, FAILED_Z_FLOOR, FAILED_Z_MIN, HIGH_THRESHOLD, MEDIUM_THRESHOLD,
    MIN_BASELINE_DAYS, WEIGHTS,
)
from src.features import Baseline

RULE_TEXT = {
    "off_hours_login": "Successful login outside this account's usual hours",
    "new_system": "Access to a system not seen in this account's baseline",
    "failed_login_burst": "Failed-login count well above this account's baseline",
    "failures_then_success": "Successful login within 30 minutes of 3+ failed attempts",
    "unusual_privileged_action": "Privileged action by an account with no privileged history",
    "new_location": "Location label not seen in this account's baseline",
}


def label_for(score: int, sufficient: bool) -> str:
    if not sufficient:
        return "insufficient_baseline"
    if score >= HIGH_THRESHOLD:
        return "high"
    if score >= MEDIUM_THRESHOLD:
        return "medium"
    return "low"


def score_user_day(features: dict, evidence: dict[str, list[str]], baseline: Baseline) -> dict:
    sufficient = baseline.active_days >= MIN_BASELINE_DAYS
    fired: list[tuple[str, list[str]]] = []

    if sufficient and features["off_hours_logins"] > 0:
        fired.append(("off_hours_login", evidence["off_hours_logins"]))
    if sufficient and features["new_systems"] > 0:
        fired.append(("new_system", evidence["new_systems"]))
    f = features["failed_logins"]
    if f >= FAILED_BURST_MIN or (f >= FAILED_Z_FLOOR and features["failed_z"] >= FAILED_Z_MIN):
        fired.append(("failed_login_burst", evidence["failed_logins"]))
    if features["fail_then_success"]:
        fired.append(("failures_then_success", evidence["fail_then_success"]))
    if features["privileged_actions"] > 0 and baseline.privileged_days == 0:
        fired.append(("unusual_privileged_action", evidence["privileged_actions"]))
    if sufficient and features["new_locations"] > 0:
        fired.append(("new_location", evidence["new_locations"]))

    score = min(100, sum(WEIGHTS[r] for r, _ in fired))
    reasons = [{"rule": r, "points": WEIGHTS[r], "description": RULE_TEXT[r], "evidence_event_ids": ids}
               for r, ids in fired]
    unknowns = []
    if not sufficient:
        unknowns.append(f"Only {baseline.active_days} baseline day(s); novelty rules were not applied")
    if evidence.get("missing_location"):
        unknowns.append(f"Location missing on {len(evidence['missing_location'])} event(s)")
    return {
        "risk_score": score,
        "risk_label": label_for(score, sufficient),
        "reasons": reasons,
        "evidence_event_ids": sorted({i for r in reasons for i in r["evidence_event_ids"]}),
        "sequence_fail_then_success": evidence.get("fail_then_success", []),
        "unknowns": unknowns,
    }
