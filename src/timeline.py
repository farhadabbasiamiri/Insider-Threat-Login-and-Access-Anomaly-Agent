"""Time-ordered event timeline for one account. Sequence is shown, not causation."""

from __future__ import annotations

from datetime import date

import pandas as pd

TIMELINE_COLUMNS = ["event_id", "time", "event_type", "result", "system", "source", "location", "privileged"]


def get_user_timeline(events: pd.DataFrame, user_id: str, day: date | None = None,
                      flagged_ids: set[str] | None = None, limit: int = 200) -> pd.DataFrame:
    rows = events[events["user_id"] == user_id]
    if day is not None:
        rows = rows[rows["day"] == day]
    rows = rows.sort_values("timestamp").head(limit)
    out = pd.DataFrame({
        "event_id": rows["event_id"],
        "time": rows["timestamp"].dt.strftime("%Y-%m-%d %H:%M"),
        "event_type": rows["event_type"],
        "result": rows["result"],
        "system": rows["system"],
        "source": rows["source"],
        "location": rows["location"],
        "privileged": rows["privileged"],
    })
    if flagged_ids is not None:
        out["flagged"] = out["event_id"].isin(flagged_ids)
    return out.reset_index(drop=True)
