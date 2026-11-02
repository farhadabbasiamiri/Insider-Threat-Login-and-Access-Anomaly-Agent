# Data card — Group 8B synthetic login/access logs

| Item | Value |
|---|---|
| Generator | `src/generate_data.py` (pure Python, `random.Random(seed)`) |
| Default seed | 8 (held-out evaluation seed: 99) |
| Accounts | 100 synthetic accounts `U001`–`U100` across 6 synthetic departments (the brief allows 100–500; `--users` up to 500) |
| Time range | 2026-10-05 → 2026-11-01 (28 days), fixed UTC-04:00 offset |
| Split | Baseline: 2026-10-05 → 10-18 (14 days). Evaluation: 2026-10-19 → 11-01 (14 days). Chronological; no look-ahead. |
| Size | ~12,600 events (seed 8) |
| Real data | **None.** No real people, organizations, IPs or logs. Names like `ADMIN-SERVER-9` are invented. |
| License / use | Created by the team for coursework; free to share. |

## Files (`data/synthetic/`)

| File | Contents |
|---|---|
| `events.csv` | One row per event (schema below) |
| `users.csv` | Account metadata: department, admin role, night shift, remote worker, first active day |
| `change_records.csv` | Synthetic approved change windows (used by the agent as context, not by the detector) |
| `scenario_manifest.csv` | Which scenario was injected for which account-day (for evaluation only) |

## `events.csv` schema

| Column | Type | Meaning |
|---|---|---|
| `event_id` | string | Unique, `E` + 6 digits, assigned in time order |
| `timestamp` | ISO 8601 with offset | When the event happened |
| `user_id` | string | Synthetic account |
| `department` | string | Synthetic department label |
| `event_type` | `login` / `remote_access` / `privileged_action` | Kind of event |
| `system` | string | Destination device/server |
| `source` | string | Network origin label (e.g. `VPN-01`, `OFFICE-A-NET`) |
| `location` | string | **Synthetic** location label; ~1% intentionally blank → shown as `unknown` |
| `result` | `success` / `failure` / `not_applicable` | Login outcome |
| `privileged` | bool | Elevated-rights action |
| `scenario_id` | string | Injected scenario (blank for routine) — **label, never a feature** |
| `ground_truth` | `normal` / `injected_risk` / `benign_unusual` | **Label, never a feature** |

## How routine behaviour is generated

- Each account has a start hour (7–10, or 22 for two IT-Ops night-shift accounts), a laptop, 2 department systems plus `MAIL-01`/`INTRANET-01`, and an office.
- Workdays: 1–3 sessions, each a login followed by 1–3 accesses to home systems. ~6% of sessions have 1–2 failed logins first. ~6% of days are absent.
- 30% of accounts are remote workers who use `Remote-Home` via `VPN-01` on ~40% of days.
- IT-Ops accounts are admins: 0–3 privileged actions per session on their admin systems; some weekend work.
- Benign drift: in the evaluation window, ~2% of user-days include a legitimate first visit to another department system (source of realistic false positives).
- `U099` and `U100` are new hires who start in the evaluation window (insufficient baseline).

## Injected scenarios (evaluation window only)

| ID | Count | Label | Description |
|---|---:|---|---|
| SCN-01 | 3 | injected_risk | Login 01:00–04:00, then access to an admin system |
| SCN-02 | 3 | injected_risk | 6–10 failed logins in a few minutes, then success |
| SCN-03 | 3 | injected_risk | 02:05 failures → 02:08 success → `ADMIN-SERVER-9` → privileged action (includes `U010`) |
| SCN-04 | 3 | injected_risk | Non-admin privileged action on `DC-01` during work hours |
| SCN-05 | 2 | injected_risk | Login from an unfamiliar location label, then `BACKUP-01` |
| SCN-06 | 3 | benign_unusual | Approved overnight migration on `BACKUP-01` — has a change record |
| SCN-07 | 2 | injected_risk | Single quiet access to an admin system in work hours (designed to be hard) |

## Limitations

- Behaviour is simpler and more regular than real enterprise activity, so metrics are optimistic.
- Scenario designs and detector rules were written by the same team; the held-out seed only varies randomness, not attacker behaviour.
- Location labels are invented strings, not geolocation. Real location data is affected by VPNs and proxies.
- No HR data, shift rosters or ticketing system beyond the small synthetic change-record table.
