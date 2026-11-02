# Evaluation

All results come from synthetic data and are reproducible with the commands below. They describe this
demo, not real-world performance.

```powershell
.\.venv\Scripts\python -m src.evaluate --holdout-seed 99   # -> docs/evaluation_results.md, outputs/metrics.json
.\.venv\Scripts\python -m src.run_agent_cases              # -> docs/agent_evaluation.md (real Ollama model)
.\.venv\Scripts\python -m pytest -q                        # unit + guardrail tests (fake LLM)
```

## 1. Detector (user-day level)

**Positive:** an evaluation-window user-day containing an `injected_risk` event. **Negative:** everything else,
including the 3 `benign_unusual` SCN-06 days. Labels are joined after detection and are never features.

| Dataset | Method | TP | FP | FN | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|---:|---:|
| dev (seed 8) | Rules (score ≥ 40) | 14 | 4 | 2 | 0.778 | 0.875 | 0.824 |
| dev (seed 8) | Isolation Forest | 8 | 22 | 8 | 0.267 | 0.500 | 0.348 |
| held-out (seed 99) | Rules (score ≥ 40) | 14 | 3 | 2 | 0.824 | 0.875 | 0.848 |
| held-out (seed 99) | Isolation Forest | 9 | 20 | 7 | 0.310 | 0.562 | 0.400 |

Full tables, per-scenario breakdown and the false-positive list are in [evaluation_results.md](evaluation_results.md).

### Error analysis

- **False negatives (2/2 on both seeds): SCN-07 low-and-slow.** One access to an admin system during normal
  hours earns only `new_system` (25 points), which is below the threshold. This is the expected weakness of
  single-day thresholds. Possible fixes: multi-day accumulation, or system sensitivity weights (admin
  systems count more).
- **False positives: SCN-06 approved maintenance (3/3 flagged).** The score does not use change records.
  The agent's `get_change_records` tool surfaces the approval. We chose to keep the score context-free and let
  the analyst see the context, rather than silently lowering scores.
- **Natural FP (seed 8): U023.** Four failed logins plus a slightly early login. A plausible benign cause is a
  forgotten password.
- **Isolation Forest vs rules.** IF catches multi-signal outliers (SCN-02 and SCN-03 all found). It misses
  single-signal novelty such as SCN-04 privileged actions (0/3), because the "new system" and "privileged"
  counts are 0/1 features that are common among admins. IF also flags many busy-but-normal admin days. Rules
  are more precise here and easier to explain, so IF is shown as a secondary signal only.
- **Development bias.** The `failures_then_success` rule was added after the first run missed SCN-02. The
  held-out seed confirms the rule set is not tuned to seed-8 randomness, but scenario *designs* are shared.

## 2. Agent end-to-end (real LLM)

**Latest run: 10/10 prepared cases passed with `qwen2.5-coder:7b`; latency 14–27 s per case.** Two cases
(T05, T10) needed the one-shot repair step, so the first draft failed validation and the corrected draft passed.
This shows the validator is doing real work. Small-model output varies between runs, so re-run before presenting.

See [agent_evaluation.md](agent_evaluation.md) for the per-case table: status, number of tool calls, whether a
repair was needed, latency, and which checks passed. A case passes only if the agent called all four tools,
the report passed evidence and safety validation, and the case-specific expectation held (for example,
SCN-06 must cite the change record).

## 3. Explanation quality rubric (project brief)

Score each agent report from 0 to 2 on each criterion during the team review and record the results in this table.

| Case | Clear | Evidence-based | Actionable | Safe | Reviewer |
|---|---|---|---|---|---|
| T07 U010 | | | | | |
| T05 SCN-06 | | | | | |
| … | | | | | |

The automated validator already enforces part of **Evidence-based** (only real IDs, citations and names) and
part of **Safe** (no accusatory or enforcement language). The other criteria need human judgement.
