"""Agent tests with a scripted fake LLM, so they run without Ollama."""

import json

from src.agent import ToolBox, investigate, offline_summary, validate_report
from src.policy_retrieval import PolicyIndex

DAY = "2026-10-29"


def scn03_day(pipeline):
    r = pipeline.scenarios.query("scenario_id == 'SCN-03' and user_id == 'U010'").iloc[0]
    return r.day


class FakeClient:
    """Plays back a fixed sequence of assistant messages."""

    model = "fake"

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def available(self):
        return True, "fake"

    def chat(self, messages, tools=None, fmt=None):
        self.calls += 1
        item = self.script.pop(0)
        return item(messages) if callable(item) else item


def tool_msg(name, **args):
    return {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": name, "arguments": args}}]}


def good_report(evidence_ids, citations):
    return {"role": "assistant", "content": json.dumps({
        "finding": "Unusual sign-in sequence", "summary": "Possible anomaly on ADMIN-SERVER-9 for review.",
        "evidence_event_ids": evidence_ids, "reasons": ["off-hours login"], "policy_citations": citations,
        "change_record_ids": [], "unknowns": ["shift schedule"],
        "analyst_questions": ["Was overnight access approved?"], "recommended_next_steps": ["Confirm with owner"]})}


def test_toolbox_rejects_unknown_tool_and_bad_user(pipeline, policy):
    tb = ToolBox(pipeline, policy)
    assert "not allowed" in tb.call("disable_account", {"user_id": "U010"})["error"]
    assert "Unknown user_id" in tb.call("get_user_timeline", {"user_id": "U999", "date": DAY})["error"]
    assert "Invalid date" in tb.call("get_user_timeline", {"user_id": "U010", "date": "yesterday"})["error"]
    assert all(not t["ok"] for t in tb.trace)


def test_validator_rejects_invented_event_id_and_names(pipeline, policy):
    day = scn03_day(pipeline)
    tb = ToolBox(pipeline, policy)
    tb.call("get_anomaly_evidence", {"user_id": "U010", "date": day})
    report = json.loads(good_report(["E999999"], [])["content"])
    report["summary"] = "Accessed FIN-SERVER-9."
    v = validate_report(report, tb)
    assert not v["passed"]
    assert any("E999999" in i for i in v["issues"])
    assert any("FIN-SERVER-9" in i for i in v["issues"])


def test_validator_rejects_accusatory_language(pipeline, policy):
    day = scn03_day(pipeline)
    tb = ToolBox(pipeline, policy)
    ev = tb.call("get_anomaly_evidence", {"user_id": "U010", "date": day})
    report = json.loads(good_report(ev["reasons"][0]["evidence_event_ids"], [])["content"])
    report["summary"] = "U010 is a malicious insider and must be fired."
    v = validate_report(report, tb)
    assert not v["passed"] and any("unsafe" in i for i in v["issues"])
    report["summary"] = "Possible anomaly, not a confirmed incident."
    assert validate_report(report, tb)["passed"]
    report["summary"] = "This is a confirmed incident."
    assert not validate_report(report, tb)["passed"]


def test_agent_loop_end_to_end_with_fake_llm(pipeline, policy):
    day = scn03_day(pipeline)
    ids = pipeline.details[("U010", __import__("datetime").date.fromisoformat(day))]["evidence_event_ids"]
    client = FakeClient([
        tool_msg("get_anomaly_evidence", user_id="U010", date=day),
        tool_msg("get_user_timeline", user_id="U010", date=day),
        tool_msg("get_change_records", user_id="U010", date=day),
        tool_msg("search_access_policy", query="privileged action outside working hours"),
        {"role": "assistant", "content": "READY"},
        lambda msgs: good_report(ids[:3], ["SYNTHETIC_POLICY.md#SP-3.1"]),
    ])
    res = investigate(pipeline, policy, "U010", day, client=client)
    assert res["status"] == "ok", res.get("validation")
    assert [t["tool"] for t in res["tool_trace"]] == ["get_anomaly_evidence", "get_user_timeline",
                                                      "get_change_records", "search_access_policy"]
    r = res["report"]
    assert r["risk_priority"] == 100  # authoritative score comes from the detector
    assert r["requires_human_review"] is True and r["approved_action_taken"] is False


def test_agent_repairs_once_then_reports_failure(pipeline, policy):
    day = scn03_day(pipeline)
    client = FakeClient([
        tool_msg("get_anomaly_evidence", user_id="U010", date=day),
        tool_msg("search_access_policy", query="failed sign-in"),
        tool_msg("get_user_timeline", user_id="U010", date=day),
        tool_msg("get_change_records", user_id="U010", date=day),
        {"role": "assistant", "content": "READY"},
        good_report(["E000000"], []),
        good_report(["E000000"], []),
    ])
    res = investigate(pipeline, policy, "U010", day, client=client)
    assert res["status"] == "failed_validation" and res["repair_attempted"]


def test_invalid_user_rejected_before_llm(pipeline, policy):
    client = FakeClient([])
    res = investigate(pipeline, policy, "U999", DAY, client=client)
    assert res["status"] == "rejected_input" and client.calls == 0


def test_llm_unavailable_is_reported_honestly(pipeline, policy):
    class Down(FakeClient):
        def available(self):
            return False, "Ollama not reachable"

    res = investigate(pipeline, policy, "U010", DAY, client=Down([]))
    assert res["status"] == "llm_unavailable" and "report" not in res


def test_offline_summary_is_labelled_and_valid(pipeline, policy):
    res = offline_summary(pipeline, policy, "U010", scn03_day(pipeline))
    assert "no LLM" in res["mode"]
    assert res["validation"]["passed"], res["validation"]


def test_offline_summary_valid_when_no_rule_fires(pipeline, policy):
    row = pipeline.findings[pipeline.findings.risk_score == 0].iloc[0]
    res = offline_summary(pipeline, policy, row.user_id, str(row.day))
    assert res["report"]["evidence_event_ids"] == []
    assert res["validation"]["passed"], res["validation"]


def test_approved_change_record_is_found(pipeline, policy):
    r = pipeline.scenarios.query("scenario_id == 'SCN-06'").iloc[0]
    out = ToolBox(pipeline, policy).call("get_change_records", {"user_id": r.user_id, "date": r.day})
    assert out["records"] and out["records"][0]["systems"] == "BACKUP-01"
