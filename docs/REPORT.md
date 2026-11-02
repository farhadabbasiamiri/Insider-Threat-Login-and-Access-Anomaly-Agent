# Insider Threat Login and Access Anomaly Agent — Project Report

**Group 8B** · AI/ML in Cybersecurity Capstone · Laurentian University · Fall 2026
**Supervisor:** Farhad Abbasi Amiri
**Authors:** Yash Baksheshkumar Patel, Yash Niravkumar Patel, Jay Barot, Smit Panchal, Devendra Suther

---

## Abstract

Login and access anomalies can reveal compromised accounts or risky insider behaviour, but SOC analysts need
evidence they can verify, not opaque alerts. We built a working MVP that generates synthetic login/access logs
for 100 accounts and learns a per-account baseline from 14 days of history. It scores each later user-day with
six transparent rules, and an Isolation Forest provides a comparison score. A local LLM agent
(`qwen2.5-coder:7b` on Ollama) investigates a selected user-day by calling four read-only tools: evidence,
timeline, change records and policy retrieval. It writes a structured report, and a validator rejects the
report if it cites anything the tools never returned or uses accusatory language. A Gradio dashboard presents
the results to a human analyst, who records the decision. On a held-out data seed the rules reach
**precision 0.824 and recall 0.875**, against 0.310 and 0.562 for Isolation Forest. The agent passed **10 of
10** prepared end-to-end cases, with a median latency of 17.7 s. The system supports investigation only. It does
not prove wrongdoing and never takes automatic action.

## 1. Problem and security relevance

**Insider threat** covers both malicious insiders and attackers using stolen credentials, who look like insiders
once logged in. Both show up as *account behaviour that differs from normal*: logins at unusual hours, bursts
of failed sign-ins, first-time access to sensitive systems, unexpected privileged actions, or unfamiliar
locations. Fixed organisation-wide rules ("alert on any login after midnight") are noisy because normal differs
per person; a night-shift administrator logs in after midnight every day.

UEBA addresses this by comparing each account with *its own* history. The second problem is **explainability**.
An analyst who receives "risk 85" must still reconstruct why. Our design goal was that every number links to
the exact events behind it, and that any AI-written text is checked against those events.

**Target user:** a SOC analyst triaging account activity.
**Scope (from the project brief):** logins, remote access, privilege use, unusual systems. The output is a
dashboard of anomalous patterns, user timelines, risk scores and recommended analyst questions.

**Explicitly out of scope:** real monitoring of real people, automatic enforcement, and conclusions about intent.

## 2. Development process (SDLC)

| Phase | What we did |
|---|---|
| Planning | Fixed the scope (above). Agreed that "anomaly ≠ guilt" and that the system is read-only. |
| Requirements | 100–500 users. Baselines for login time, systems, location, failure rate and privileged actions. User-day features. Dashboard filters for department, user and risk. RAG over a policy. Human approval. |
| Design | One shared CSV schema and one JSON report contract, agreed before coding. Module boundaries are in `docs/architecture.md`. |
| Development | Python modules for each pipeline stage, built incrementally with Claude Code under the rules in `CLAUDE.md`. |
| Testing | 27 pytest tests, including a fake LLM for agent tests. Detector metrics on development and held-out seeds. 10 real-LLM end-to-end cases. |
| Deployment | Local: one `pip install` and `python app.py`. Ollama runs locally, so no cloud keys are needed. |
| Monitoring | Each agent run's metadata (status, tools called, latency, validation issues) is appended to `outputs/agent_runs.jsonl`. |
| Improvement | Fixes driven by measured failures (section 9). |

## 3. Data

### 3.1 Choice of dataset

The brief allows LANL-style authentication data or synthetic logs. The LANL dataset has no department or
location fields, which the dashboard filters require, and its timestamps are anonymised relative times. We
therefore wrote a **deterministic synthetic generator** (`src/generate_data.py`). It gives us realistic routine
behaviour, controlled labelled scenarios and zero privacy risk.

### 3.2 What the generator produces

| Property | Value |
|---|---|
| Accounts | 100 (`U001`–`U100`) in 6 synthetic departments. `--users` accepts up to 500. |
| Period | 2026-10-05 → 2026-11-01, 28 days, fixed UTC-04:00 offset |
| Split | 14 baseline days, then 14 evaluation days (chronological) |
| Events | 12,635 (seed 8), of which 122 have a deliberately missing location |
| Context tables | `users.csv`, `change_records.csv` (6 approved change windows), `scenario_manifest.csv` |

**Routine behaviour.** Each account has a start hour (7–10, or 22 for two IT-Ops night-shift accounts), a
laptop, two department systems plus mail and intranet, and an office. Workdays contain 1–3 sessions of a login
followed by system accesses. About 6% of sessions start with 1–2 failed logins, and about 6% of days are absent.
Remote workers (30% of accounts) use `Remote-Home` over VPN on about 40% of days. IT-Ops accounts are
administrators who perform privileged actions routinely. To create realistic false positives, about 2% of
evaluation user-days include a legitimate first visit to another department system. `U099` and `U100` are new
hires with no baseline.

**Injected scenarios** (evaluation window only):

| ID | n | Label | Behaviour |
|---|---:|---|---|
| SCN-01 | 3 | risk | Login 01:00–04:00, then an admin system |
| SCN-02 | 3 | risk | 6–10 failed logins in minutes, then success |
| SCN-03 | 3 | risk | Failures 02:05 → success 02:08 → `ADMIN-SERVER-9` → privileged action (includes walkthrough account U010) |
| SCN-04 | 3 | risk | Non-admin privileged action on `DC-01` in work hours |
| SCN-05 | 2 | risk | Login from an unfamiliar location label, then `BACKUP-01` |
| SCN-06 | 3 | **benign** | Approved overnight migration, with a change record |
| SCN-07 | 2 | risk | A single quiet admin-system access in work hours (designed to be hard) |

### 3.3 Schema and validation

Each event has `event_id, timestamp, user_id, department, event_type, system, source, location, result,
privileged, scenario_id, ground_truth`. `src/ingest.py` checks the required columns, then drops and counts rows
with an empty user, a duplicate or empty event ID, an unknown event type or result, or an unparseable
timestamp. It normalises booleans, keeps timestamps in the log's own offset, and replaces a missing location
with the explicit value `unknown`. The validation report is shown in the dashboard header. The full data card
is in `docs/data_card.md`.

**Leakage control.** `scenario_id` and `ground_truth` are evaluation labels. They are never read by the
feature, scoring or model code, and a test enforces this.

## 4. Feature engineering and baselines (`src/features.py`)

For each account, the **baseline** uses only events strictly before the split date (2026-10-19):

- **Usual login hours:** the set of hours with successful logins, widened by ±1 h (modulo 24, so night
  shifts work).
- **Known systems** and **known locations** (`unknown` is excluded).
- **Failed logins per day:** mean and standard deviation.
- **Privileged history:** the number of days with privileged actions.
- **Active days:** fewer than 5 gives `insufficient_baseline`.

Each evaluation **user-day** becomes one feature row: `logins, failed_logins, failure_rate` (NaN when there
were no attempts, which avoids divide-by-zero), `failed_z` (z-score against the account's own history, with σ
floored at 0.5), `off_hours_logins, new_systems, new_locations, privileged_actions, distinct_systems,
remote_access, fail_then_success` (a success within 30 minutes of 3 or more failures). Alongside every feature
we keep the **event IDs that produced it**, so all later explanations can point to the raw evidence.

## 5. Anomaly detection and risk scoring

### 5.1 Explainable rule score (`src/scoring.py`)

| Rule | Points | Fires when |
|---|---:|---|
| `off_hours_login` | 20 | Successful login outside the usual hours |
| `new_system` | 25 | Access to a system not in the baseline |
| `failed_login_burst` | 20 | ≥ 5 failures, or ≥ 3 failures with z ≥ 3 |
| `failures_then_success` | 20 | Success within 30 min of ≥ 3 failures |
| `unusual_privileged_action` | 20 | Privileged action by an account with no privileged history |
| `new_location` | 15 | Location label not in the baseline |

The total is capped at 100. Labels are **high** (≥ 70), **medium** (≥ 40) and **low**; medium and high count as
*flagged*. Novelty rules are switched off for accounts with insufficient history, so a new hire is not
automatically "suspicious" just because every system is new to them. The score is a **review priority**, not a
probability of compromise. The weights are illustrative teaching values.

### 5.2 Isolation Forest comparison (`src/detector.py`)

We used scikit-learn `IsolationForest` (300 trees, contamination 0.03, `random_state=8`), fitted
unsupervised on the evaluation-window feature rows. No labels are used. `decision_function` (lower means more
unusual) and `predict == -1` (outlier) are shown next to the rule score as a secondary signal.

## 6. RAG over the access policy (`src/policy_retrieval.py`)

The brief does not supply a policy, so we wrote `policies/SYNTHETIC_POLICY.md`. It is clearly marked as
fictional and has 10 numbered sections (e.g. `SP-3.1 Privileged access review`). The retriever splits the file
by section and indexes it with TF-IDF (unigrams and bigrams, English stop words). It returns the top 3
passages with similarity ≥ 0.08, each with a citation such as `SYNTHETIC_POLICY.md#SP-3.1`. When nothing
matches, it says *"No matching policy evidence found"*. Two practical additions:

- **Query expansion.** The LLM tends to search with rule names (`failed_login_burst`), which share no words
  with the policy text. We expand each rule name into policy vocabulary.
- **Prompt-injection filter.** Passages containing instruction-like text such as "ignore previous
  instructions" are dropped at indexing time and reported.

A vector database was unnecessary at this size. Section-level TF-IDF is transparent and fully deterministic.

## 7. LLM agent (`src/agent.py`)

### 7.1 Model and runtime

**Ollama 0.31 running `qwen2.5-coder:7b` locally**, with temperature 0 and seed 8. We chose a local model so
that no log data leaves the machine, no API key is needed, and the model supports native tool calling.

### 7.2 Tools (read-only allowlist)

| Tool | Returns |
|---|---|
| `get_anomaly_evidence(user_id, date)` | Score, fired rules with event IDs, features, baseline summary, Isolation Forest result |
| `get_user_timeline(user_id, date)` | Up to 60 ordered events, each marked if it supports a rule |
| `get_change_records(user_id, date)` | Approved synthetic change windows |
| `search_access_policy(query)` | Policy passages with citations |

Python validates every argument (user ID format and existence, ISO date) and rejects unknown tool names.

### 7.3 Control loop

1. The system prompt sets the role, the rules (tool output is data, never invent facts, neutral language,
   a human decides) and the tool order.
2. Up to 6 tool-calling turns. If the model stops before calling all four tools, it gets one reminder.
   Tool calls that a small model writes into the message text instead of the `tool_calls` field are also
   parsed.
3. A final turn with an Ollama **JSON-schema `format`** produces the structured report: `finding, summary,
   evidence_event_ids, reasons, policy_citations, change_record_ids, unknowns, analyst_questions,
   recommended_next_steps`.
4. **`validate_report`** fails the report if it cites any event ID, policy citation, change ID or system name
   that no tool returned. It also fails it if no evidence is cited even though rules fired, or if it uses
   accusatory or enforcement language. Negated wording such as "not a confirmed incident" is allowed.
5. On failure the model gets **one repair turn**, with the list of valid identifiers. If it still fails, the
   UI shows ❌ *"do not rely on this report"*.
6. The **risk score and label are overwritten from the detector**. `requires_human_review=true` and
   `approved_action_taken=false` are forced.

If Ollama is unreachable, the status is `llm_unavailable` and no fake report is produced. A separate **Offline
summary (no LLM)** button runs the same tools in a fixed order and is always labelled as not being an agent.

## 8. Backend and frontend (Gradio dashboard, `app.py`)

The backend is plain Python. The pipeline runs once at start-up (about 7 s for 12.6k events, including imports) and is cached.
The Gradio `Blocks` UI provides:

- **Header:** LLM status (🟢/🔴), event counts, rows rejected by validation, missing-location count.
- **Filters:** department, user, and risk (flagged, high, medium, low, insufficient baseline, Isolation Forest outliers).
- **Findings table** of user-days. Clicking a row loads the evidence panel.
- **Evidence panel:** the rule table with points and event IDs, the Isolation Forest score, the baseline summary and the unknowns.
- **Timeline** with flagged events marked.
- **AI investigation notes:** the agent or offline report, validation status, citations, questions and next
  steps, plus an expandable **tool trace** and the raw JSON.
- **Human review checkpoint:** a decision (pending, reviewed, needs more context, escalate), reviewer and
  notes, written to `outputs/reviews.jsonl`, with a history per user-day. It never changes any account.

## 9. Testing and results

### 9.1 Automated tests (27, all passing)

These cover generator determinism; validation of bad rows; no label leakage; the baseline excluding evaluation
days; NaN failure rate; the failures-then-success sequence; rule scoring, admin exemptions and new hires;
injected scenarios being flagged in the pipeline; policy retrieval, the no-match case and injection
filtering; and the agent with a scripted fake LLM (full loop, repair-then-fail, invalid user rejected before
the LLM, LLM unavailable, unknown tool, invented IDs and names, accusatory language, change-record lookup,
offline summary). The case list is in `tests/scenarios.md`.

### 9.2 Detector metrics (user-day level)

**Positive** means the user-day contains an injected-risk event. Approved maintenance (SCN-06) counts as
**negative**, so flagging it is a false positive.

| Dataset | Method | TP | FP | FN | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|---:|---:|
| Development (seed 8) | Rules | 14 | 4 | 2 | 0.778 | 0.875 | 0.824 |
| Development (seed 8) | Isolation Forest | 8 | 22 | 8 | 0.267 | 0.500 | 0.348 |
| Held-out (seed 99) | Rules | 14 | 3 | 2 | 0.824 | 0.875 | 0.848 |
| Held-out (seed 99) | Isolation Forest | 9 | 20 | 7 | 0.310 | 0.562 | 0.400 |

Per scenario, the rules detect SCN-01 to SCN-05 completely on both seeds and miss both SCN-07 cases.
Isolation Forest finds all SCN-02 and SCN-03 cases but none of SCN-04.

### 9.3 Agent end-to-end (real model)

10 prepared cases: an ordinary day, SCN-01 through SCN-07, a new hire, and an invalid user ID. A case passes
only if all four tools were called, the report passed validation, and the case-specific expectation held (for
example, the SCN-06 report must cite the approved change record).

**Result: 10/10 passed.** Median latency was 17.7 s (range 13.7–27.0 s). Two cases (SCN-06 and SCN-07)
passed only after the repair turn. The invalid user was rejected before any LLM call. Details are in
`docs/agent_evaluation.md`.

### 9.4 Error analysis and improvements made

| Observation | Cause | Action |
|---|---|---|
| SCN-02 missed in the first run (score 20) | A failure burst alone was below the threshold | Added the `failures_then_success` rule, then validated on the held-out seed because this change was made after seeing results |
| 36 events rejected as invalid timestamps | Mixed ISO formats (with and without microseconds) | Parse with `format="ISO8601"` and round timestamps to seconds in the generator |
| Policy search returned nothing | The LLM searched with rule names | Rule-name query expansion |
| Agent skipped the timeline and change-record tools | Only two tools were required | All four tools are required, with one reminder |
| LLM wrote "FIN-SERVER-9" (does not exist; the real system is `ADMIN-SERVER-9`) | Hallucinated entity | Added the system-name grounding check to the validator |
| "not a confirmed incident" flagged as unsafe | Banned-phrase check ignored negation | Negation handling, plus tests for both directions |
| Days with no rules failed validation | "No evidence cited" was required unconditionally | Evidence is required only when rules fired |

**Remaining false negatives (SCN-07).** A single access to an admin system scores 25, below the threshold.
This is the known weakness of single-day thresholds against low-and-slow activity.
**Remaining false positives (SCN-06).** The score deliberately ignores change records. The agent surfaces the
approval so the analyst can close the finding.
**Isolation Forest** flags many busy but normal IT-Ops admin days (16 of 22 false positives on seed 8) and
misses single-signal novelty, so we kept it as a secondary signal.

## 10. Human-in-the-loop, ethics and privacy

- Synthetic data only, and a policy marked fictional.
- The LLM runs locally, so no data goes to a cloud service.
- The agent sees only one account-day.
- Tools are read-only, and every report needs human review. The review button only records the decision.
- The validator enforces neutral language and grounding. Failures are shown, not hidden.
- Prompt-injection filtering, and tool output is framed as data.
- No secrets are needed. `.env`, `.venv/` and `outputs/` are git-ignored.

Logs show what an **account** did, not who was at the keyboard, so the system never names a person as
responsible. See `docs/ethics_and_limitations.md`.

## 11. Limitations and future work

**Limitations.**

- Synthetic behaviour is more regular than real activity, so these metrics are optimistic.
- The same team designed both the scenarios and the rules.
- Grouping by calendar day splits night shifts that cross midnight.
- The 7B model sometimes needs the repair turn.
- The thresholds are not calibrated.

**Future work.**

- Multi-day accumulation for low-and-slow activity.
- Sensitivity weights for systems (admin servers count more).
- Peer-group baselines by department and role.
- Change-record-aware scoring.
- Evaluation on the CERT insider-threat dataset.
- A stronger local model.
- Docker packaging.

## 12. Use of AI coding assistants

The MVP was built with **Claude Code**, guided by the standing instructions in `CLAUDE.md`: project
rules, commands, invariants and testing expectations. The team treated all generated code as a proposal. We
ran it, wrote and ran tests, measured results, and fixed the problems listed in section 9.4. The LLM inside the
product (Ollama `qwen2.5-coder:7b`) is separate from the coding assistant.

## 13. How to reproduce

```powershell
python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt
ollama pull qwen2.5-coder:7b
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m src.evaluate --holdout-seed 99
.\.venv\Scripts\python -m src.run_agent_cases
.\.venv\Scripts\python app.py
```

## References

- Project brief *Group 8B*, the capstone general notes, the grading rubric, the resource list and the SDLC
  student guide (Laurentian University).
- Los Alamos National Laboratory, *Comprehensive, Multi-Source Cyber-Security Events*, https://csr.lanl.gov/data/cyber1/
- CMU SEI, *Insider Threat Test Dataset*, https://www.sei.cmu.edu/library/insider-threat-test-dataset/
- scikit-learn, `IsolationForest`, https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html
- Gradio documentation, https://www.gradio.app/docs
- Ollama tool calling and structured outputs, https://ollama.com
