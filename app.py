"""Group 8B — Login & Access Anomaly Investigation dashboard (Gradio).

Run:  python app.py   then open http://127.0.0.1:7860
"""

from __future__ import annotations

import json
from datetime import date, datetime

import gradio as gr
import pandas as pd

from src.agent import OllamaClient, investigate, offline_summary
from src.config import OUTPUT_DIR
from src.detector import default_pipeline
from src.policy_retrieval import PolicyIndex
from src.timeline import get_user_timeline

P = default_pipeline()
POLICY = PolicyIndex()
REVIEWS = OUTPUT_DIR / "reviews.jsonl"
ALL = "All"
RISK_CHOICES = ["Flagged (medium + high)", ALL, "high", "medium", "low", "insufficient_baseline", "Isolation Forest outliers"]
TABLE_COLS = ["user_id", "department", "day", "risk_score", "risk_label", "reasons", "if_outlier", "if_decision",
              "failed_logins", "off_hours_logins", "new_systems", "new_locations", "privileged_actions"]
REVIEW_CHOICES = ["Pending review", "Reviewed - no further action", "Needs more context", "Escalate to analyst lead"]

DISCLAIMER = ("**Synthetic data only.** A high score means *review priority*, not proof of wrongdoing. "
              "Logs show account activity, not who used the account. Nothing here changes any account.")


def filter_findings(dept: str, user: str, risk: str) -> pd.DataFrame:
    f = P.findings
    if dept != ALL:
        f = f[f["department"] == dept]
    if user != ALL:
        f = f[f["user_id"] == user]
    if risk == "Flagged (medium + high)":
        f = f[f["risk_label"].isin(["medium", "high"])]
    elif risk == "Isolation Forest outliers":
        f = f[f["if_outlier"]]
    elif risk != ALL:
        f = f[f["risk_label"] == risk]
    out = f[TABLE_COLS].copy()
    out["day"] = out["day"].astype(str)
    return out.reset_index(drop=True)


def summary_md(table: pd.DataFrame) -> str:
    f = P.findings
    return (f"**{len(table)}** user-days shown  ·  high: **{(f.risk_label == 'high').sum()}**  ·  "
            f"medium: **{(f.risk_label == 'medium').sum()}**  ·  insufficient baseline: "
            f"**{(f.risk_label == 'insufficient_baseline').sum()}**  ·  IF outliers: **{int(f.if_outlier.sum())}**  "
            f"(evaluation window, {f['user_id'].nunique()} accounts)")


def refresh(dept, user, risk):
    t = filter_findings(dept, user, risk)
    return t, summary_md(t), t


def on_select(table: pd.DataFrame, evt: gr.SelectData):
    row = table.iloc[evt.index[0]]
    return row["user_id"], row["day"]


def explain(user_id: str, day_s: str):
    if not user_id or not day_s:
        return "Select a row in the findings table.", pd.DataFrame()
    day = date.fromisoformat(day_s)
    d = P.details.get((user_id, day))
    if d is None:
        return f"No evaluation-window activity for {user_id} on {day_s}.", pd.DataFrame()
    b = P.baselines[user_id].to_dict()
    lines = [f"### {user_id} — {day_s}", f"**Review priority:** {d['risk_score']}/100 (`{d['risk_label']}`)", ""]
    if d["reasons"]:
        lines.append("| Rule | Points | Why | Event IDs |\n|---|---:|---|---|")
        lines += [f"| `{r['rule']}` | +{r['points']} | {r['description']} | {', '.join(r['evidence_event_ids'])} |"
                  for r in d["reasons"]]
    else:
        lines.append("_No rule triggered._")
    row = P.findings[(P.findings.user_id == user_id) & (P.findings.day == day)].iloc[0]
    lines += ["", f"**Isolation Forest:** decision {row.if_decision:+.3f} "
                  f"({'outlier' if row.if_outlier else 'inlier'}; lower = more unusual)",
              "", f"**Baseline ({b['baseline_active_days']} active days before the split):** "
                  f"systems {', '.join(b['known_systems']) or '—'}; locations {', '.join(b['known_locations']) or '—'}; "
                  f"failed logins/day {b['failed_logins_per_day_mean']} ± {b['failed_logins_per_day_std']}; "
                  f"privileged days {b['baseline_days_with_privileged_actions']}"]
    if d["unknowns"]:
        lines += ["", "**Unknowns:** " + "; ".join(d["unknowns"])]
    tl = get_user_timeline(P.events, user_id, day, flagged_ids=set(d["evidence_event_ids"]))
    return "\n".join(lines), tl


def report_md(result: dict) -> str:
    head = f"**Mode:** `{result.get('mode')}`  ·  **Status:** `{result.get('status')}`"
    if result.get("latency_s") is not None:
        head += f"  ·  {result['latency_s']} s"
    if "report" not in result:
        return f"{head}\n\n⚠️ {result.get('error', 'No report produced.')}"
    r, v = result["report"], result["validation"]
    check = "✅ Passed evidence & safety checks" if v["passed"] else "❌ **Failed validation — do not rely on this report.**"
    bullets = lambda xs: "\n".join(f"- {x}" for x in xs) or "- none"
    return f"""{head}

{check}{''.join(f"<br>• {i}" for i in v['issues'])}

### {r.get('finding', '')}
**Status:** possible anomaly requiring analyst review (not a confirmed incident)
**Review priority:** {r.get('risk_priority')}/100 (`{r.get('risk_label')}`)

{r.get('summary', '')}

**Evidence event IDs:** {', '.join(r.get('evidence_event_ids', [])) or 'none'}

**Reasons**
{bullets(r.get('reasons', []))}

**Policy references:** {', '.join(r.get('policy_citations', [])) or 'No matching policy evidence found.'}
**Change records:** {', '.join(r.get('change_record_ids', [])) or 'none found'}

**Unknowns**
{bullets(r.get('unknowns', []))}

**Questions for the analyst**
{bullets(r.get('analyst_questions', []))}

**Suggested next steps (analyst decides)**
{bullets(r.get('recommended_next_steps', []))}

🧑‍💼 **Human checkpoint:** requires_human_review = `{r.get('requires_human_review')}`, approved_action_taken = `{r.get('approved_action_taken')}`
"""


def run_agent(user_id, day_s):
    if not user_id or not day_s:
        return "Select a user-day first.", [], {}
    res = investigate(P, POLICY, user_id, day_s)
    return report_md(res), res.get("tool_trace", []), res.get("report", res)


def run_offline(user_id, day_s):
    if not user_id or not day_s:
        return "Select a user-day first.", [], {}
    res = offline_summary(P, POLICY, user_id, day_s)
    return ("> ℹ️ Deterministic template — **no LLM was used**. Tools were called in a fixed order.\n\n"
            + report_md(res)), res.get("tool_trace", []), res.get("report", res)


def review_history(user_id, day_s) -> pd.DataFrame:
    if not REVIEWS.exists():
        return pd.DataFrame(columns=["at", "reviewer", "decision", "notes"])
    rows = [json.loads(line) for line in REVIEWS.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [r for r in rows if r["user_id"] == user_id and r["day"] == day_s]
    return pd.DataFrame(rows, columns=["at", "reviewer", "decision", "notes"])


def save_review(user_id, day_s, decision, reviewer, notes):
    if not user_id or not day_s:
        return "Select a user-day first.", review_history(user_id, day_s)
    OUTPUT_DIR.mkdir(exist_ok=True)
    rec = {"at": datetime.now().isoformat(timespec="seconds"), "user_id": user_id, "day": day_s,
           "decision": decision, "reviewer": (reviewer or "analyst").strip()[:40], "notes": (notes or "")[:1000]}
    with open(REVIEWS, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    return (f"Saved **{decision}** for {user_id} {day_s}. This records the analyst's decision only; "
            "no account or permission was changed."), review_history(user_id, day_s)


def build() -> gr.Blocks:
    depts = [ALL] + sorted(P.findings["department"].unique())
    users = [ALL] + sorted(P.findings["user_id"].unique())
    days = sorted(str(d) for d in P.findings["day"].unique())
    ok, llm_info = OllamaClient().available()

    with gr.Blocks(title="Group 8B — Login & Access Anomaly Agent") as demo:
        gr.Markdown("# Group 8B · Login & Access Anomaly Investigation\n" + DISCLAIMER)
        gr.Markdown(f"LLM: {'🟢' if ok else '🔴'} {llm_info}  ·  Data: {P.report.rows_kept:,} events "
                    f"({P.report.rows_read - P.report.rows_kept} rejected by validation, "
                    f"{P.report.missing_location} with missing location)")

        with gr.Row():
            dept = gr.Dropdown(depts, value=ALL, label="Department")
            user = gr.Dropdown(users, value=ALL, label="User")
            risk = gr.Dropdown(RISK_CHOICES, value=RISK_CHOICES[0], label="Risk")
        summary = gr.Markdown()
        table_state = gr.State()
        table = gr.Dataframe(label="User-day findings (click a row)", interactive=False, wrap=True, max_height=360)

        with gr.Row():
            sel_user = gr.Dropdown(users[1:], label="Selected user")
            sel_day = gr.Dropdown(days, label="Selected day")
            show_btn = gr.Button("Show evidence", variant="secondary")

        with gr.Row():
            with gr.Column(scale=1):
                explanation = gr.Markdown("Select a row in the findings table.")
            with gr.Column(scale=1):
                timeline = gr.Dataframe(label="Timeline (flagged = supports a triggered rule)",
                                        interactive=False, max_height=360)

        gr.Markdown("## AI investigation notes")
        with gr.Row():
            agent_btn = gr.Button("Investigate with AI agent (Ollama)", variant="primary")
            offline_btn = gr.Button("Offline summary (no LLM)")
        notes = gr.Markdown()
        with gr.Accordion("Agent tool calls and raw JSON", open=False):
            trace = gr.JSON(label="Tool trace")
            raw = gr.JSON(label="Structured report")

        gr.Markdown("## Human review checkpoint")
        with gr.Row():
            decision = gr.Radio(REVIEW_CHOICES, value=REVIEW_CHOICES[0], label="Analyst decision")
            reviewer = gr.Textbox(label="Reviewer (synthetic name)", value="analyst-1")
        review_notes = gr.Textbox(label="Notes", lines=2)
        save_btn = gr.Button("Save review decision")
        review_msg = gr.Markdown()
        history = gr.Dataframe(label="Review history for this user-day", interactive=False)

        for c in (dept, user, risk):
            c.change(refresh, [dept, user, risk], [table, summary, table_state])
        demo.load(refresh, [dept, user, risk], [table, summary, table_state])
        table.select(on_select, [table_state], [sel_user, sel_day]).then(
            explain, [sel_user, sel_day], [explanation, timeline]).then(
            review_history, [sel_user, sel_day], [history])
        show_btn.click(explain, [sel_user, sel_day], [explanation, timeline]).then(
            review_history, [sel_user, sel_day], [history])
        agent_btn.click(run_agent, [sel_user, sel_day], [notes, trace, raw])
        offline_btn.click(run_offline, [sel_user, sel_day], [notes, trace, raw])
        save_btn.click(save_review, [sel_user, sel_day, decision, reviewer, review_notes], [review_msg, history])
    return demo


if __name__ == "__main__":
    build().launch(server_name="127.0.0.1", server_port=7860)
