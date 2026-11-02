from datetime import date

from src.features import Baseline
from src.scoring import score_user_day

FEATURES = {"off_hours_logins": 1, "new_systems": 1, "failed_logins": 6, "failed_z": 9.0, "fail_then_success": 1,
            "privileged_actions": 1, "new_locations": 0}
EVIDENCE = {"off_hours_logins": ["E3"], "new_systems": ["E4"], "failed_logins": ["E1", "E2"],
            "fail_then_success": ["E1", "E2", "E3"], "privileged_actions": ["E5"], "new_locations": [],
            "missing_location": []}


def test_walkthrough_case_scores_high_with_evidence():
    d = score_user_day(FEATURES, EVIDENCE, Baseline("U010", active_days=10))
    assert d["risk_score"] == 100 and d["risk_label"] == "high"
    assert {r["rule"] for r in d["reasons"]} == {"off_hours_login", "new_system", "failed_login_burst",
                                                 "failures_then_success", "unusual_privileged_action"}
    assert d["evidence_event_ids"] == ["E1", "E2", "E3", "E4", "E5"]


def test_admin_privileged_action_is_not_unusual():
    f = {**FEATURES, "off_hours_logins": 0, "new_systems": 0, "failed_logins": 0, "fail_then_success": 0}
    d = score_user_day(f, EVIDENCE, Baseline("U004", active_days=10, privileged_days=8))
    assert d["risk_score"] == 0 and d["risk_label"] == "low"


def test_new_account_gets_insufficient_baseline_not_high_risk():
    d = score_user_day({**FEATURES, "failed_logins": 0, "fail_then_success": 0, "privileged_actions": 0},
                       EVIDENCE, Baseline("U100", active_days=0))
    assert d["risk_label"] == "insufficient_baseline"
    assert d["risk_score"] == 0
    assert any("baseline" in u for u in d["unknowns"])


def test_known_scenarios_flagged_in_pipeline(pipeline):
    m = pipeline.scenarios
    for scn in ["SCN-01", "SCN-02", "SCN-03", "SCN-04"]:
        for r in m[m.scenario_id == scn].itertuples():
            d = pipeline.details[(r.user_id, date.fromisoformat(r.day))]
            assert d["risk_label"] in {"medium", "high"}, (scn, r.user_id, d)


def test_new_hires_marked_insufficient(pipeline):
    labels = pipeline.findings[pipeline.findings.user_id.isin(["U099", "U100"])]["risk_label"]
    assert set(labels) == {"insufficient_baseline"}
