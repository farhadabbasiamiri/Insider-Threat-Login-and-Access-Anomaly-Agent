from datetime import date

import pandas as pd
import pytest

from src.config import SPLIT_DATE
from src.features import FEATURE_COLUMNS, Baseline, user_day_features
from src.generate_data import generate
from src.ingest import LABEL_COLUMNS, SchemaError, validate


def _raw(rows):
    base = {"event_id": "E1", "timestamp": "2026-10-20T09:00:00-04:00", "user_id": "U001", "department": "HR",
            "event_type": "login", "system": "HR-LAPTOP-1", "source": "NET", "location": "Office-A",
            "result": "success", "privileged": "false", "scenario_id": "", "ground_truth": "normal"}
    return pd.DataFrame([{**base, **r} for r in rows])


def test_generator_is_deterministic():
    a, *_ = generate(100, 8)
    b, *_ = generate(100, 8)
    pd.testing.assert_frame_equal(a, b)


def test_generator_user_count_in_brief_range():
    events, users, _, _ = generate(100, 8)
    assert users.shape[0] == 100
    assert events["user_id"].nunique() == 100


def test_validation_drops_bad_rows():
    df = _raw([{}, {"event_id": "E1"}, {"event_id": "E2", "event_type": "teleport"},
               {"event_id": "E3", "timestamp": "not-a-time"}, {"event_id": "E4", "user_id": ""},
               {"event_id": "E5", "location": ""}])
    clean, report = validate(df)
    assert list(clean["event_id"]) == ["E1", "E5"]
    assert report.dropped == {"duplicate_or_empty_event_id": 1, "unknown_event_type": 1,
                              "invalid_timestamp": 1, "empty_user_id": 1}
    # Missing location stays visibly missing.
    assert clean.loc[clean.event_id == "E5", "location"].item() == "unknown"


def test_missing_column_raises():
    with pytest.raises(SchemaError):
        validate(_raw([{}]).drop(columns=["result"]))


def test_labels_never_used_as_features(pipeline):
    for col in LABEL_COLUMNS:
        assert col not in FEATURE_COLUMNS
        assert col not in pipeline.features.columns


def test_baseline_excludes_evaluation_days(pipeline):
    # U010's injected admin server appears only in the evaluation window, so it must not be "known".
    assert "ADMIN-SERVER-9" not in pipeline.baselines["U010"].known_systems
    assert pipeline.features["day"].min() >= SPLIT_DATE


def test_failure_rate_unknown_without_logins():
    day = _raw([{"event_type": "remote_access", "result": "not_applicable"}])
    clean, _ = validate(day)
    values, _ = user_day_features(clean, Baseline("U001", active_days=10, usual_hours={9}))
    assert pd.isna(values["failure_rate"])


def test_fail_then_success_sequence_detected():
    rows = [{"event_id": f"F{i}", "result": "failure", "timestamp": f"2026-10-20T02:0{i}:00-04:00"} for i in range(4)]
    rows.append({"event_id": "S1", "timestamp": "2026-10-20T02:06:00-04:00"})
    clean, _ = validate(_raw(rows))
    values, evidence = user_day_features(clean, Baseline("U001", active_days=10, usual_hours={9}))
    assert values["failed_logins"] == 4 and values["fail_then_success"] == 1
    assert evidence["fail_then_success"][-1] == "S1"
    assert values["off_hours_logins"] == 1
