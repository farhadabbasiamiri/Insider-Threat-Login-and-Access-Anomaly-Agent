"""End-to-end agent evaluation on prepared cases using the REAL local Ollama model.

Usage:  python -m src.run_agent_cases      (writes docs/agent_evaluation.md)
"""

from __future__ import annotations

import json

import pandas as pd

from src.agent import REQUIRED_TOOLS, OllamaClient, investigate
from src.config import DATA_DIR, OUTPUT_DIR, ROOT
from src.detector import default_pipeline
from src.policy_retrieval import PolicyIndex


def prepared_cases(p) -> list[dict]:
    m = pd.read_csv(DATA_DIR / "scenario_manifest.csv", dtype=str)
    first = lambda scn: m[m.scenario_id == scn].iloc[0]
    f = p.findings
    normal = f[(f.risk_score == 0) & (f.risk_label == "low") & (f.user_id == "U001")].iloc[0]
    newhire = f[f.risk_label == "insufficient_baseline"].iloc[0]
    cases = [
        ("T01", "Ordinary workday", normal.user_id, str(normal.day), {"label": "low"}),
        ("T02", "SCN-01 off-hours + new system", first("SCN-01").user_id, first("SCN-01").day, {"flagged": True}),
        ("T03", "SCN-02 failed-login burst", first("SCN-02").user_id, first("SCN-02").day, {"flagged": True}),
        ("T04", "SCN-04 unexpected privileged action", first("SCN-04").user_id, first("SCN-04").day, {"flagged": True}),
        ("T05", "SCN-06 approved maintenance (benign)", first("SCN-06").user_id, first("SCN-06").day,
         {"change_record_cited": True}),
        ("T06", "New hire, insufficient baseline", newhire.user_id, str(newhire.day), {"label": "insufficient_baseline"}),
        ("T07", "SCN-03 full chain (U010 walkthrough)", "U010", m[(m.scenario_id == "SCN-03") & (m.user_id == "U010")].day.iloc[0],
         {"label": "high"}),
        ("T08", "SCN-05 new location", first("SCN-05").user_id, first("SCN-05").day, {"flagged": True}),
        ("T09", "Invalid user ID", "U999", "2026-10-20", {"status": "rejected_input"}),
        ("T10", "SCN-07 low-and-slow (known detector miss)", first("SCN-07").user_id, first("SCN-07").day, {"label": "low"}),
    ]
    return [dict(zip(["id", "name", "user_id", "day", "expect"], c)) for c in cases]


def check(case: dict, res: dict) -> list[str]:
    exp, problems = case["expect"], []
    if exp.get("status"):
        return [] if res["status"] == exp["status"] else [f"status {res['status']} != {exp['status']}"]
    if res["status"] != "ok":
        problems.append(f"status {res['status']}: {res.get('validation', {}).get('issues') or res.get('error')}")
    r = res.get("report", {})
    if "label" in exp and r.get("risk_label") != exp["label"]:
        problems.append(f"label {r.get('risk_label')} != {exp['label']}")
    if exp.get("flagged") and r.get("risk_label") not in ("medium", "high"):
        problems.append(f"not flagged ({r.get('risk_label')})")
    if exp.get("change_record_cited") and not r.get("change_record_ids"):
        problems.append("approved change record not cited")
    missing = set(REQUIRED_TOOLS) - {t["tool"] for t in res.get("tool_trace", []) if t["ok"]}
    if missing:
        problems.append(f"tools not called: {sorted(missing)}")
    return problems


def main() -> None:
    p, policy, client = default_pipeline(), PolicyIndex(), OllamaClient()
    ok, info = client.available()
    if not ok:
        raise SystemExit(f"Cannot run real-agent evaluation: {info}")
    rows, raw = [], []
    for case in prepared_cases(p):
        res = investigate(p, policy, case["user_id"], case["day"], client=client)
        problems = check(case, res)
        rows.append({**{k: case[k] for k in ("id", "name", "user_id", "day")}, "status": res["status"],
                     "tools": len(res.get("tool_trace", [])), "repair": res.get("repair_attempted", False),
                     "latency_s": res.get("latency_s", 0), "pass": not problems, "problems": "; ".join(problems)})
        raw.append({"case": case, "result": res})
        print(f"{case['id']} {'PASS' if not problems else 'FAIL'} {res['status']} {res.get('latency_s')}s {problems}")

    df = pd.DataFrame(rows)
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "agent_cases.json").write_text(json.dumps(raw, indent=1, default=str))
    md = [f"# Agent end-to-end evaluation (`python -m src.run_agent_cases`)", "",
          f"Model: `{client.model}` via Ollama, temperature 0. Synthetic data. "
          f"**{int(df['pass'].sum())}/{len(df)} cases passed**; median latency "
          f"{df.loc[df.latency_s > 0, 'latency_s'].median():.1f} s.", "",
          "A case passes when: the agent called all four tools, the report passed evidence/safety validation, "
          "and the case-specific expectation held.", "",
          "| Case | Scenario | User | Day | Status | Tool calls | Repair | Latency (s) | Pass | Problems |",
          "|---|---|---|---|---|---:|---|---:|---|---|"]
    md += [f"| {r.id} | {r['name']} | {r.user_id} | {r.day} | {r.status} | {r.tools} | {r.repair} | {r.latency_s} | "
           f"{'✅' if r['pass'] else '❌'} | {r.problems} |" for _, r in df.iterrows()]
    (ROOT / "docs" / "agent_evaluation.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"{int(df['pass'].sum())}/{len(df)} cases passed -> docs/agent_evaluation.md")


if __name__ == "__main__":
    main()
