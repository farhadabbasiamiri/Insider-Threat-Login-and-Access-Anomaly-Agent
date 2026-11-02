"""Load and validate the login/access event CSV."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from src.config import DATA_DIR

REQUIRED_COLUMNS = [
    "event_id", "timestamp", "user_id", "department", "event_type", "system",
    "source", "location", "result", "privileged", "scenario_id", "ground_truth",
]
EVENT_TYPES = {"login", "remote_access", "privileged_action"}
RESULTS = {"success", "failure", "not_applicable"}
# Columns that exist only to grade the detector. They must never become model features.
LABEL_COLUMNS = ["scenario_id", "ground_truth"]


class SchemaError(ValueError):
    pass


@dataclass
class ValidationReport:
    rows_read: int = 0
    rows_kept: int = 0
    dropped: dict[str, int] = field(default_factory=dict)
    missing_location: int = 0

    def drop(self, reason: str, n: int) -> None:
        if n:
            self.dropped[reason] = self.dropped.get(reason, 0) + int(n)


def validate(df: pd.DataFrame) -> tuple[pd.DataFrame, ValidationReport]:
    """Return a cleaned copy plus a report of what was rejected and why."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise SchemaError(f"Missing required columns: {missing}")

    report = ValidationReport(rows_read=len(df))
    df = df.copy()
    for col in ["event_id", "user_id", "department", "event_type", "system", "source", "location", "result",
                "scenario_id", "ground_truth"]:
        df[col] = df[col].fillna("").astype(str).str.strip()
    df["event_type"] = df["event_type"].str.lower()
    df["result"] = df["result"].str.lower().replace("", "not_applicable")

    empty_user = df["user_id"] == ""
    report.drop("empty_user_id", empty_user.sum())
    df = df[~empty_user]

    dupes = df["event_id"].duplicated(keep="first") | (df["event_id"] == "")
    report.drop("duplicate_or_empty_event_id", dupes.sum())
    df = df[~dupes]

    bad_type = ~df["event_type"].isin(EVENT_TYPES)
    report.drop("unknown_event_type", bad_type.sum())
    df = df[~bad_type]

    bad_result = ~df["result"].isin(RESULTS)
    report.drop("unknown_result", bad_result.sum())
    df = df[~bad_result]

    ts = pd.to_datetime(df["timestamp"], errors="coerce", utc=True, format="ISO8601")
    bad_ts = ts.isna()
    report.drop("invalid_timestamp", bad_ts.sum())
    df = df[~bad_ts]
    # Keep wall-clock time in the logs' own fixed offset; "day" and "hour" are local concepts.
    # (The "Etc/GMT+4" zone name means UTC-04:00; POSIX inverts the sign.)
    df["timestamp"] = ts[~bad_ts].dt.tz_convert("Etc/GMT+4")

    df["privileged"] = df["privileged"].astype(str).str.lower().isin({"true", "1", "yes"})
    # Missing stays visibly missing: never silently treated as "normal".
    df["location"] = df["location"].replace("", "unknown")
    report.missing_location = int((df["location"] == "unknown").sum())

    df["day"] = df["timestamp"].dt.date
    df["hour"] = df["timestamp"].dt.hour
    df = df.sort_values(["timestamp", "event_id"]).reset_index(drop=True)
    report.rows_kept = len(df)
    return df, report


def load_events(path: Path | str | None = None) -> tuple[pd.DataFrame, ValidationReport]:
    path = Path(path) if path else DATA_DIR / "events.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run `python -m src.generate_data` first.")
    return validate(pd.read_csv(path, dtype=str, keep_default_na=False))


def load_change_records(path: Path | str | None = None) -> pd.DataFrame:
    path = Path(path) if path else DATA_DIR / "change_records.csv"
    return pd.read_csv(path, dtype=str) if path.exists() else pd.DataFrame(
        columns=["change_id", "user_id", "date", "window", "systems", "description", "approved_by"])
