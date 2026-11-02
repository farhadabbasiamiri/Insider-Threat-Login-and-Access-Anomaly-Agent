"""Per-user baselines and per-user-per-day features.

Baselines use only events strictly before SPLIT_DATE (chronological split), so
an evaluation day can never leak into the history it is compared against.
Label columns (scenario_id, ground_truth) are never read here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from src.config import HOUR_TOLERANCE, SIGMA_FLOOR, SPLIT_DATE

FEATURE_COLUMNS = [
    "logins", "failed_logins", "failure_rate", "failed_z", "off_hours_logins", "new_systems",
    "new_locations", "privileged_actions", "distinct_systems", "remote_access", "fail_then_success",
]


@dataclass
class Baseline:
    user_id: str
    active_days: int
    usual_hours: set[int] = field(default_factory=set)
    known_systems: set[str] = field(default_factory=set)
    known_locations: set[str] = field(default_factory=set)
    failed_mean: float = 0.0
    failed_std: float = 0.0
    privileged_days: int = 0

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "baseline_active_days": self.active_days,
            "usual_login_hours": sorted(self.usual_hours),
            "known_systems": sorted(self.known_systems),
            "known_locations": sorted(self.known_locations),
            "failed_logins_per_day_mean": round(self.failed_mean, 2),
            "failed_logins_per_day_std": round(self.failed_std, 2),
            "baseline_days_with_privileged_actions": self.privileged_days,
        }


def _expand_hours(hours: set[int], tol: int) -> set[int]:
    return {(h + d) % 24 for h in hours for d in range(-tol, tol + 1)}


def build_baselines(events: pd.DataFrame, split: date = SPLIT_DATE) -> dict[str, Baseline]:
    hist = events[events["day"] < split]
    baselines: dict[str, Baseline] = {}
    all_users = events["user_id"].unique()
    for user_id in all_users:
        h = hist[hist["user_id"] == user_id]
        logins = h[h["event_type"] == "login"]
        active = sorted(h["day"].unique())
        fails = logins[logins["result"] == "failure"].groupby("day").size().reindex(active, fill_value=0)
        baselines[user_id] = Baseline(
            user_id=user_id,
            active_days=len(active),
            usual_hours=_expand_hours(set(logins.loc[logins["result"] == "success", "hour"]), HOUR_TOLERANCE),
            known_systems=set(h.loc[h["event_type"] != "login", "system"]) | set(logins["system"]),
            known_locations=set(h["location"]) - {"unknown"},
            failed_mean=float(fails.mean()) if len(fails) else 0.0,
            failed_std=float(fails.std(ddof=0)) if len(fails) else 0.0,
            privileged_days=int(h.loc[h["privileged"], "day"].nunique()),
        )
    return baselines


def _ids(frame: pd.DataFrame) -> list[str]:
    return frame["event_id"].tolist()


def user_day_features(day_events: pd.DataFrame, baseline: Baseline) -> tuple[dict, dict[str, list[str]]]:
    """Feature values for one user-day plus the event IDs that support each feature."""
    logins = day_events[day_events["event_type"] == "login"]
    failed = logins[logins["result"] == "failure"]
    success = logins[logins["result"] == "success"]
    access = day_events[day_events["event_type"] != "login"]
    attempts = len(failed) + len(success)

    off_hours = success[~success["hour"].isin(baseline.usual_hours)] if baseline.usual_hours else success.iloc[0:0]
    new_sys = access[~access["system"].isin(baseline.known_systems)]
    located = day_events[day_events["location"] != "unknown"]
    new_loc = located[~located["location"].isin(baseline.known_locations)] if baseline.known_locations else located.iloc[0:0]
    priv = day_events[day_events["privileged"]]

    # A success that follows 3+ failures within 30 minutes.
    fts_ids: list[str] = []
    for _, s in success.iterrows():
        prior = failed[(failed["timestamp"] <= s["timestamp"]) &
                       (failed["timestamp"] >= s["timestamp"] - pd.Timedelta(minutes=30))]
        if len(prior) >= 3:
            fts_ids = _ids(prior) + [s["event_id"]]
            break

    sigma = max(baseline.failed_std, SIGMA_FLOOR)
    values = {
        "logins": attempts,
        "failed_logins": len(failed),
        "failure_rate": round(len(failed) / attempts, 3) if attempts else np.nan,  # unknown with no attempts
        "failed_z": round((len(failed) - baseline.failed_mean) / sigma, 2),
        "off_hours_logins": len(off_hours),
        "new_systems": new_sys["system"].nunique(),
        "new_locations": new_loc["location"].nunique(),
        "privileged_actions": len(priv),
        "distinct_systems": access["system"].nunique(),
        "remote_access": int((day_events["event_type"] == "remote_access").sum()),
        "fail_then_success": int(bool(fts_ids)),
    }
    evidence = {
        "failed_logins": _ids(failed),
        "off_hours_logins": _ids(off_hours),
        "new_systems": _ids(new_sys),
        "new_locations": _ids(new_loc),
        "privileged_actions": _ids(priv),
        "fail_then_success": fts_ids,
        "missing_location": _ids(day_events[day_events["location"] == "unknown"]),
    }
    return values, evidence


def build_feature_table(events: pd.DataFrame, baselines: dict[str, Baseline],
                        split: date = SPLIT_DATE) -> tuple[pd.DataFrame, dict[tuple[str, date], dict]]:
    """One row per (user, evaluation day) and an evidence map keyed by the same pair."""
    current = events[events["day"] >= split]
    rows, evidence_map = [], {}
    for (user_id, day), grp in current.groupby(["user_id", "day"], sort=True):
        b = baselines[user_id]
        values, evidence = user_day_features(grp, b)
        rows.append({"user_id": user_id, "department": grp["department"].iloc[0], "day": day,
                     "baseline_active_days": b.active_days, **values})
        evidence_map[(user_id, day)] = evidence
    return pd.DataFrame(rows), evidence_map
