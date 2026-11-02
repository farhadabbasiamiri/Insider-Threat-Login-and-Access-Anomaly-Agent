# Prepared test scenarios

| ID | Scenario | Expected behaviour | Covered by |
|---|---|---|---|
| T01 | Ordinary workday | Low priority, no accusation | `run_agent_cases` T01 |
| T02 | SCN-01 late login + new admin system | Flagged with event IDs | `test_known_scenarios_flagged_in_pipeline`, T02 |
| T03 | SCN-02 failed-login burst then success | Flagged; sequence shown | same, T03 |
| T04 | SCN-04 unexpected privileged action | Flagged; privileged-access policy retrieved | same, T04 |
| T05 | SCN-06 approved overnight maintenance | Flagged by rules (FP), agent cites change record | `test_approved_change_record_is_found`, T05 |
| T06 | New hire | `insufficient_baseline`, not high risk | `test_new_hires_marked_insufficient`, T06 |
| T07 | Missing location | Shown as `unknown`, never counted as new | `test_validation_drops_bad_rows` |
| T08 | Policy retrieval finds nothing / poisoned policy | "No matching policy evidence found"; poisoned passage dropped | `test_policy_retrieval.py` |
| T09 | Invalid user / unknown tool | Rejected before LLM; tool call refused | `test_invalid_user_rejected_before_llm`, `test_toolbox_rejects_unknown_tool_and_bad_user`, T09 |
| T10 | LLM invents an event ID or system name | Validator fails the report; one repair; ❌ in UI | `test_validator_rejects_invented_event_id_and_names`, `test_agent_repairs_once_then_reports_failure` |
| T11 | LLM unavailable | `llm_unavailable` status; no fake report | `test_llm_unavailable_is_reported_honestly` |
| T12 | Accusatory wording | Validator fails it; negated "not a confirmed incident" is allowed | `test_validator_rejects_accusatory_language` |
