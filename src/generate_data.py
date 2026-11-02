"""Generate a fully synthetic login/access log for the Group 8B demo.

Every account, system, location and event below is invented. The output is
deterministic for a given seed so evaluation results are reproducible.

Usage:
    python -m src.generate_data            # writes data/synthetic/*.csv
    python -m src.generate_data --users 200 --seed 8
"""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from src.config import (
    BASELINE_DAYS,
    DATA_DIR,
    EVAL_DAYS,
    START_DATE,
    TZ_OFFSET_HOURS,
)

TZ = timezone(timedelta(hours=TZ_OFFSET_HOURS))

DEPARTMENTS = {
    "Finance": {"prefix": "FIN", "office": "Office-A"},
    "HR": {"prefix": "HR", "office": "Office-A"},
    "Engineering": {"prefix": "ENG", "office": "Office-B"},
    "IT-Ops": {"prefix": "ITO", "office": "Office-B"},
    "Sales": {"prefix": "SAL", "office": "Office-C"},
    "Research": {"prefix": "RES", "office": "Office-C"},
}
SHARED_SYSTEMS = ["MAIL-01", "INTRANET-01"]
ADMIN_SYSTEMS = ["ADMIN-SERVER-9", "DC-01", "BACKUP-01"]
FOREIGN_LOCATIONS = ["Remote-X", "Remote-Y", "Remote-Z"]


@dataclass
class User:
    user_id: str
    department: str
    laptop: str
    office: str
    home_systems: list[str]
    start_hour: int
    shift_hours: int = 8
    is_admin: bool = False
    remote_worker: bool = False
    first_day: int = 0  # day index of first activity (new hires > 0)
    admin_systems: list[str] = field(default_factory=list)


class EventLog:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def add(self, ts: datetime, user: User, event_type: str, system: str, source: str,
            location: str, result: str = "not_applicable", privileged: bool = False,
            scenario_id: str = "", ground_truth: str = "normal") -> None:
        self.rows.append({
            "timestamp": ts,
            "user_id": user.user_id,
            "department": user.department,
            "event_type": event_type,
            "system": system,
            "source": source,
            "location": location,
            "result": result,
            "privileged": privileged,
            "scenario_id": scenario_id,
            "ground_truth": ground_truth,
        })


def make_users(rng: random.Random, n_users: int) -> list[User]:
    depts = list(DEPARTMENTS)
    users = []
    for i in range(1, n_users + 1):
        dept = depts[(i - 1) % len(depts)]
        # U010 is the documented walkthrough account, so pin it to Finance.
        if i == 10:
            dept = "Finance"
        info = DEPARTMENTS[dept]
        pool = [f"{info['prefix']}-SERVER-{k}" for k in range(1, 5)] + \
               [f"{info['prefix']}-APP-{k}" for k in range(1, 3)]
        home = rng.sample(pool, k=2) + SHARED_SYSTEMS
        is_admin = dept == "IT-Ops"
        users.append(User(
            user_id=f"U{i:03d}",
            department=dept,
            laptop=f"{info['prefix']}-LAPTOP-{i}",
            office=info["office"],
            home_systems=home,
            start_hour=rng.choice([7, 8, 8, 9, 9, 9, 10]),
            is_admin=is_admin,
            remote_worker=rng.random() < 0.3,
            admin_systems=rng.sample(ADMIN_SYSTEMS, k=2) if is_admin else [],
        ))
    # Two IT-Ops accounts work a regular night shift: normal for them.
    night = [u for u in users if u.department == "IT-Ops"][:2]
    for u in night:
        u.start_hour = 22
    # The last two accounts are new hires with almost no history.
    for offset, u in enumerate(users[-2:]):
        u.first_day = BASELINE_DAYS + 2 + offset
    return users


def at(day: date, hour: float) -> datetime:
    """Timestamp `hour` hours after midnight of `day` (hour may exceed 24)."""
    return datetime(day.year, day.month, day.day, tzinfo=TZ) + timedelta(hours=hour)


def routine_day(rng: random.Random, log: EventLog, user: User, day_idx: int, day: date,
                pool_for_dept: dict[str, list[str]]) -> None:
    weekend = day.weekday() >= 5
    if weekend and not (user.is_admin and rng.random() < 0.25):
        return
    if rng.random() < 0.06:  # leave / sick day
        return

    remote = user.remote_worker and rng.random() < 0.4
    location = "Remote-Home" if remote else user.office
    source = "VPN-01" if remote else f"{user.office.upper()}-NET"

    sessions = rng.randint(1, 3)
    for _ in range(sessions):
        t = user.start_hour + rng.uniform(0, user.shift_hours - 0.5)
        loc = "" if rng.random() < 0.01 else location  # occasional missing field
        if rng.random() < 0.06:
            for _ in range(rng.choice([1, 1, 2])):
                log.add(at(day, t), user, "login", user.laptop, source, loc, "failure")
                t += rng.uniform(0.01, 0.05)
        log.add(at(day, t), user, "login", user.laptop, source, loc, "success")
        for system in rng.sample(user.home_systems, k=rng.randint(1, 3)):
            t += rng.uniform(0.05, 1.0)
            log.add(at(day, t), user, "remote_access", system, source, loc)
        if user.is_admin:
            for _ in range(rng.randint(0, 3)):
                t += rng.uniform(0.05, 0.5)
                log.add(at(day, t), user, "privileged_action",
                        rng.choice(user.admin_systems), source, loc, privileged=True)

    # Benign drift: occasionally a legitimate first visit to another dept system.
    if day_idx >= BASELINE_DAYS and rng.random() < 0.02:
        extra = [s for s in pool_for_dept[user.department] if s not in user.home_systems]
        if extra:
            t = user.start_hour + rng.uniform(1, user.shift_hours - 1)
            log.add(at(day, t), user, "remote_access", rng.choice(extra), source, location)


# --- injected scenarios -------------------------------------------------------
# Each scenario writes a short, labelled event sequence on one user-day.

def scn01_offhours_new_system(rng, log, u, day):
    """Login at an unusual hour followed by access to a never-seen system."""
    t = rng.uniform(1.0, 4.0)
    src, loc = "VPN-01", "Remote-Home"
    log.add(at(day, t), u, "login", u.laptop, src, loc, "success", scenario_id="SCN-01", ground_truth="injected_risk")
    log.add(at(day, t + 0.1), u, "remote_access", rng.choice(ADMIN_SYSTEMS), src, loc,
            scenario_id="SCN-01", ground_truth="injected_risk")


def scn02_failed_burst(rng, log, u, day):
    """Burst of failed sign-ins then a success (possible password guessing)."""
    t = u.start_hour + rng.uniform(0.5, 3.0)
    src, loc = "VPN-01", u.office
    for _ in range(rng.randint(6, 10)):
        log.add(at(day, t), u, "login", u.laptop, src, loc, "failure", scenario_id="SCN-02", ground_truth="injected_risk")
        t += rng.uniform(0.005, 0.02)
    log.add(at(day, t), u, "login", u.laptop, src, loc, "success", scenario_id="SCN-02", ground_truth="injected_risk")
    log.add(at(day, t + 0.05), u, "remote_access", u.home_systems[0], src, loc,
            scenario_id="SCN-02", ground_truth="injected_risk")


def scn03_full_chain(rng, log, u, day):
    """02:05 failures -> 02:08 success -> new admin server -> privileged action."""
    src, loc = "VPN-TEST-1", "Remote-Home"
    t = 2 + 5 / 60
    for _ in range(6):
        log.add(at(day, t), u, "login", u.laptop, src, loc, "failure", scenario_id="SCN-03", ground_truth="injected_risk")
        t += 0.4 / 60
    log.add(at(day, 2 + 8 / 60), u, "login", u.laptop, src, loc, "success", scenario_id="SCN-03", ground_truth="injected_risk")
    log.add(at(day, 2 + 10 / 60), u, "remote_access", "ADMIN-SERVER-9", src, loc,
            scenario_id="SCN-03", ground_truth="injected_risk")
    log.add(at(day, 2 + 13 / 60), u, "privileged_action", "ADMIN-SERVER-9", src, loc, privileged=True,
            scenario_id="SCN-03", ground_truth="injected_risk")


def scn04_unexpected_privilege(rng, log, u, day):
    """Non-admin account performs a privileged action on a domain controller in work hours."""
    t = u.start_hour + rng.uniform(1, 5)
    src, loc = f"{u.office.upper()}-NET", u.office
    log.add(at(day, t), u, "login", u.laptop, src, loc, "success", scenario_id="SCN-04", ground_truth="injected_risk")
    log.add(at(day, t + 0.1), u, "remote_access", "DC-01", src, loc, scenario_id="SCN-04", ground_truth="injected_risk")
    log.add(at(day, t + 0.15), u, "privileged_action", "DC-01", src, loc, privileged=True,
            scenario_id="SCN-04", ground_truth="injected_risk")


def scn05_new_location(rng, log, u, day):
    """Sign-in from an unfamiliar location label, then a new system."""
    t = u.start_hour + rng.uniform(0.5, 4)
    loc = rng.choice(FOREIGN_LOCATIONS)
    log.add(at(day, t), u, "login", u.laptop, "VPN-02", loc, "success", scenario_id="SCN-05", ground_truth="injected_risk")
    log.add(at(day, t + 0.2), u, "remote_access", "BACKUP-01", "VPN-02", loc,
            scenario_id="SCN-05", ground_truth="injected_risk")


def scn06_approved_maintenance(rng, log, u, day):
    """BENIGN: approved overnight migration on a new system (has a change record)."""
    src, loc = "VPN-01", "Remote-Home"
    log.add(at(day, 23.1), u, "login", u.laptop, src, loc, "success", scenario_id="SCN-06", ground_truth="benign_unusual")
    log.add(at(day, 23.3), u, "remote_access", "BACKUP-01", src, loc, scenario_id="SCN-06", ground_truth="benign_unusual")
    log.add(at(day, 23.6), u, "remote_access", u.home_systems[0], src, loc, scenario_id="SCN-06", ground_truth="benign_unusual")


def scn07_low_and_slow(rng, log, u, day):
    """Stealthy: one quiet visit to an unfamiliar system in normal hours."""
    t = u.start_hour + rng.uniform(2, 6)
    src, loc = f"{u.office.upper()}-NET", u.office
    log.add(at(day, t), u, "remote_access", rng.choice(ADMIN_SYSTEMS), src, loc,
            scenario_id="SCN-07", ground_truth="injected_risk")


SCENARIOS = {
    "SCN-01": (scn01_offhours_new_system, 3),
    "SCN-02": (scn02_failed_burst, 3),
    "SCN-03": (scn03_full_chain, 3),
    "SCN-04": (scn04_unexpected_privilege, 3),
    "SCN-05": (scn05_new_location, 2),
    "SCN-06": (scn06_approved_maintenance, 3),
    "SCN-07": (scn07_low_and_slow, 2),
}


def generate(n_users: int = 100, seed: int = 8) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (events, users, change_records, scenario_manifest)."""
    rng = random.Random(seed)
    users = make_users(rng, n_users)
    log = EventLog()
    pool_for_dept = {
        d: [f"{i['prefix']}-SERVER-{k}" for k in range(1, 5)] + [f"{i['prefix']}-APP-{k}" for k in range(1, 3)]
        for d, i in DEPARTMENTS.items()
    }
    days = [START_DATE + timedelta(days=i) for i in range(BASELINE_DAYS + EVAL_DAYS)]

    for idx, day in enumerate(days):
        for u in users:
            if idx >= u.first_day:
                routine_day(rng, log, u, idx, day, pool_for_dept)

    # Scenario targets: established, non-admin day-shift accounts (U010 reserved for SCN-03).
    eligible = [u for u in users if not u.is_admin and u.first_day == 0 and u.start_hour < 20 and u.user_id != "U010"]
    rng.shuffle(eligible)
    eval_weekdays = [d for d in days[BASELINE_DAYS:] if d.weekday() < 5]
    assignments = []
    cursor = 0
    for scn_id, (fn, count) in SCENARIOS.items():
        for k in range(count):
            if scn_id == "SCN-03" and k == 0:
                user = next(u for u in users if u.user_id == "U010")
            else:
                user = eligible[cursor]
                cursor += 1
            day = eval_weekdays[(cursor * 3 + k) % len(eval_weekdays)]
            fn(rng, log, user, day)
            assignments.append({"scenario_id": scn_id, "user_id": user.user_id, "day": day.isoformat(),
                                "description": fn.__doc__.strip()})

    events = pd.DataFrame(log.rows).sort_values(["timestamp", "user_id"]).reset_index(drop=True)
    events.insert(0, "event_id", [f"E{i:06d}" for i in range(1, len(events) + 1)])
    events["timestamp"] = events["timestamp"].map(lambda t: t.replace(microsecond=0).isoformat())

    users_df = pd.DataFrame([{
        "user_id": u.user_id, "department": u.department, "is_admin": u.is_admin,
        "night_shift": u.start_hour >= 20, "remote_worker": u.remote_worker,
        "first_active_day": (START_DATE + timedelta(days=u.first_day)).isoformat(),
    } for u in users])

    # Approved change records (synthetic): the SCN-06 maintenance windows plus unrelated noise.
    changes = []
    for a in assignments:
        if a["scenario_id"] == "SCN-06":
            changes.append({"change_id": f"CHG-{len(changes) + 1:04d}", "user_id": a["user_id"], "date": a["day"],
                            "window": "23:00-02:00", "systems": "BACKUP-01",
                            "description": "Approved overnight backup migration (synthetic)",
                            "approved_by": "SYNTH-MANAGER-01"})
    for u in rng.sample([u for u in users if u.is_admin], k=3):
        d = rng.choice(days[BASELINE_DAYS:])
        changes.append({"change_id": f"CHG-{len(changes) + 1:04d}", "user_id": u.user_id, "date": d.isoformat(),
                        "window": "18:00-20:00", "systems": ";".join(u.admin_systems),
                        "description": "Routine patch window (synthetic)", "approved_by": "SYNTH-MANAGER-02"})
    return events, users_df, pd.DataFrame(changes), pd.DataFrame(assignments)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--users", type=int, default=100)
    parser.add_argument("--seed", type=int, default=8)
    parser.add_argument("--out", type=Path, default=DATA_DIR)
    args = parser.parse_args()
    if not 100 <= args.users <= 500:
        parser.error("--users must be between 100 and 500 (project brief range)")

    events, users, changes, scenarios = generate(args.users, args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    events.to_csv(args.out / "events.csv", index=False)
    users.to_csv(args.out / "users.csv", index=False)
    changes.to_csv(args.out / "change_records.csv", index=False)
    scenarios.to_csv(args.out / "scenario_manifest.csv", index=False)
    print(f"Wrote {len(events):,} events for {users.shape[0]} users to {args.out}")
    print(f"Injected scenarios: {len(scenarios)}  |  change records: {len(changes)}")


if __name__ == "__main__":
    main()
