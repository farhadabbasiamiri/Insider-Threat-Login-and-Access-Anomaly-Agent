# Presentation notes (7 slides, 7–10 minutes)

| # | Slide | Talking points | Show |
|---|---|---|---|
| 1 | Problem & user | Compromised accounts and risky insider activity hide in normal-looking logins. SOC analysts need *explainable* evidence, not black-box alerts. | One-sentence scope; "anomaly ≠ guilt" |
| 2 | Dataset | 100 synthetic accounts, 28 days, ~12.6k events, 14-day baseline / 14-day evaluation split, 7 injected scenarios incl. one benign and one deliberately hard. Why not LANL: no department or location fields. | `docs/data_card.md` table |
| 3 | Architecture | Data → validation → baselines → user-day features → rules + Isolation Forest → read-only tools → Ollama agent → validator → Gradio → human. | `docs/architecture.md` diagram |
| 4 | AI / RAG / agent | Rule score with event IDs. TF-IDF policy RAG with citations. The agent picks among 4 allowlisted tools. The validator rejects invented IDs and names and accusatory wording. | Tool trace JSON from the UI |
| 5 | Live demo | U010 walkthrough, then SCN-06 approved maintenance, then a review decision. Backup: screenshots + Offline summary if Ollama fails. | `app.py` |
| 6 | Results & limits | Rules P/R/F1 on dev and held-out seeds vs Isolation Forest. SCN-07 misses. SCN-06 false positives. Agent case pass rate and latency. | `docs/evaluation.md`, `docs/agent_evaluation.md` |
| 7 | Value & next steps | Faster triage with verifiable evidence. Next: multi-day accumulation, system sensitivity weights, peer groups, change-record-aware scoring, bigger/real-schema datasets (CERT), stronger local model. | — |

## 60-second pitch

> We built an investigation assistant for SOC analysts that highlights unusual login and access activity. We
> generated synthetic logs for 100 accounts, learned each account's normal hours, systems, locations and
> failure rates from two weeks of history, and injected seven known scenarios. Transparent rules score each
> user-day and link every point to event IDs. Isolation Forest gives a comparison. A local LLM agent calls
> read-only tools for the evidence, timeline, change records and policy passages, and writes neutral notes
> with questions for the analyst. A validator blocks any report that cites something the tools never returned.
> The analyst makes the call. Nothing is enforced automatically.

## Backup plan

- Ollama slow or down: use **Offline summary (no LLM)** and say it is a deterministic template.
- UI fails: show `docs/agent_evaluation.md` and the screenshots.
- Warm up the model before presenting (run one investigation) to avoid cold-start latency.
