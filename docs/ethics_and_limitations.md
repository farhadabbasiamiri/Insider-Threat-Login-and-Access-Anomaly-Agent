# Ethics, privacy and limitations

## Safeguards built into the MVP

1. **Synthetic data only.** No real people, accounts, logs or company policies. The policy file is marked fictional.
2. **Local LLM.** Ollama runs on the analyst's machine, so no log data is sent to a cloud AI service.
3. **Data minimization.** The agent sees one account-day: aggregate features, ≤ 60 events and retrieved policy text.
4. **Read-only tools.** No tool can disable an account, change permissions or notify anyone.
5. **Neutral language enforced.** The validator rejects reports that call someone malicious or guilty, claim a confirmed attack, or demand enforcement.
6. **Evidence grounding.** Event IDs, citations, change IDs and system names must come from tool results.
7. **Human checkpoint.** Every report has `requires_human_review: true`. The review button only writes a local note to `outputs/reviews.jsonl`.
8. **Honest failure modes.** If Ollama is down, the UI says so. The offline summary is labelled "no LLM" and is never presented as an agent.
9. **Prompt injection.** Policy passages with instruction-like text are dropped at indexing time. Tool results are framed as data in the system prompt.
10. **No secrets.** None are needed. `.env` is git-ignored.

## Known limitations

- **Synthetic ≠ real.** Routine behaviour is regular and scenarios are simple, so precision and recall here will not transfer to an enterprise.
- **Same authors for attacks and detector.** The held-out seed changes randomness, not attacker behaviour.
- **Known misses.** SCN-07 (one quiet access to an admin system) scores 25 and is missed by design. Low-and-slow misuse needs longer windows or peer-group comparison.
- **False positives.** Approved maintenance (SCN-06) is flagged by rules. The agent can surface the change record, but the score does not use it.
- **Account ≠ person.** Logs show what an account did, not who was at the keyboard.
- **Small LLM.** `qwen2.5-coder:7b` sometimes skips tools or invents names. The nudge, validator and repair step reduce this but do not remove it.
- **Fixed timezone and calendar-day grouping.** Night-shift activity that crosses midnight is split across two user-days.
- **Isolation Forest** is fitted unsupervised on the evaluation window with a fixed contamination of 3%. Its score is relative, not a risk probability.

## Appropriate use

This is a classroom prototype for triage support. It must not be used to monitor real people, make HR
decisions, or take automated security actions.
