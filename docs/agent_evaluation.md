# Agent end-to-end evaluation (`python -m src.run_agent_cases`)

Model: `qwen2.5-coder:7b` via Ollama, temperature 0. Synthetic data. **10/10 cases passed**; median latency 17.7 s.

A case passes when: the agent called all four tools, the report passed evidence/safety validation, and the case-specific expectation held.

| Case | Scenario | User | Day | Status | Tool calls | Repair | Latency (s) | Pass | Problems |
|---|---|---|---|---|---:|---|---:|---|---|
| T01 | Ordinary workday | U001 | 2026-10-26 | ok | 4 | False | 13.7 | ✅ |  |
| T02 | SCN-01 off-hours + new system | U085 | 2026-10-22 | ok | 4 | False | 15.5 | ✅ |  |
| T03 | SCN-02 failed-login burst | U045 | 2026-10-21 | ok | 4 | False | 16.9 | ✅ |  |
| T04 | SCN-04 unexpected privileged action | U018 | 2026-10-28 | ok | 4 | False | 26.3 | ✅ |  |
| T05 | SCN-06 approved maintenance (benign) | U049 | 2026-10-21 | ok | 4 | True | 22.7 | ✅ |  |
| T06 | New hire, insufficient baseline | U100 | 2026-10-29 | ok | 4 | False | 27.0 | ✅ |  |
| T07 | SCN-03 full chain (U010 walkthrough) | U010 | 2026-10-29 | ok | 4 | False | 17.7 | ✅ |  |
| T08 | SCN-05 new location | U050 | 2026-10-27 | ok | 4 | False | 14.8 | ✅ |  |
| T09 | Invalid user ID | U999 | 2026-10-20 | rejected_input | 0 | False | 0.0 | ✅ |  |
| T10 | SCN-07 low-and-slow (known detector miss) | U020 | 2026-10-20 | ok | 4 | True | 18.7 | ✅ |  |
