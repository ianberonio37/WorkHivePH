#!/usr/bin/env python3
"""
seed_demo_day.py - give the demo worker a REAL day for the Day Planner shot.
============================================================================
Ian, reviewing the reel: "there [is] no even seeded infos on the screenshot
when you are doing the demo." Measured, he is exactly right for the Day
Planner: `schedule_items` is keyed by worker_name, and the demo identity
(Pablo Aguilar) has **zero** rows - Bryan Garcia has 131, Pablo has none. So
the chapter filmed "Nothing planned yet" and a row of zeros.

Missing data is a seeding job, never a blocker. This writes a believable
maintenance day for the demo worker - a morning PM, a corrective job, a parts
pickup, a handover - spread across today and the next two days so the
"Today / This week" tiles both have something to count.

Idempotent: it deletes only the rows it previously wrote (marked in notes)
before re-inserting, so re-running never doubles up.

CLI:
    python tools/seed_demo_day.py                 # seed for the demo worker
    python tools/seed_demo_day.py --worker "Pablo Aguilar" --days 3
    python tools/seed_demo_day.py --check         # report only
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date, timedelta

MARK = "[demo-seed]"
CONTAINER = "supabase_db_workhive"

# A plausible maintenance day: PMs in the morning, correctives after, admin last.
DAY0 = [
    ("07:00", "08:00", "pm", "Line 1 pump PM - vibration + grease"),
    ("08:30", "10:00", "corrective", "Replace worn drive belt, Mixer 2"),
    ("10:30", "11:15", "parts", "Collect bearing 6310 C3 from stores"),
    ("13:00", "14:30", "pm", "Compressor CB-700 monthly checklist"),
    ("15:00", "15:45", "admin", "Log the morning's repairs"),
]
DAY1 = [
    ("07:30", "09:00", "pm", "Conveyor drive inspection"),
    ("09:30", "11:00", "corrective", "Chase intermittent trip on Panel 3"),
    ("14:00", "15:00", "admin", "Shift handover notes"),
]
DAY2 = [
    ("07:00", "09:30", "pm", "Quarterly gearbox oil change"),
    ("10:00", "11:30", "parts", "Stock count - critical spares"),
]


def psql(sql: str) -> str:
    r = subprocess.run(
        ["docker", "exec", CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
         "-t", "-A", "-c", sql],
        capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:400])
    return r.stdout.strip()


def q(v: str) -> str:
    return "'" + v.replace("'", "''") + "'"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker", default="Pablo Aguilar")
    ap.add_argument("--days", type=int, default=3)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    # AUTH_UID IS LOAD-BEARING. This platform resolves identity by auth_uid,
    # not by name (RLS reads auth.uid()), so rows written with a null auth_uid
    # exist in the table and are INVISIBLE to the signed-in user - the first
    # seed pass wrote 11 rows and the Day Planner still filmed "0 scheduled".
    uid = psql(f"select auth_uid from hive_members where worker_name = {q(a.worker)} "
               f"and auth_uid is not null limit 1;")
    if not uid:
        print(f"  ERROR: no auth_uid for {a.worker} - rows would be invisible to RLS")
        return 1
    print(f"  auth_uid: {uid}")

    have = psql(f"select count(*) from schedule_items where worker_name = {q(a.worker)};")
    print(f"{a.worker}: {have} schedule_items before")
    if a.check:
        return 0

    # remove only OUR previous seed, so real rows are never touched
    psql(f"delete from schedule_items where worker_name = {q(a.worker)} "
         f"and notes like {q(MARK + '%')};")

    today = date.today()
    plans = [DAY0, DAY1, DAY2][:max(1, a.days)]
    # `id` is TEXT with no default - the app mints ids client-side, so the
    # seeder must too. Deterministic ids keep the delete/re-insert idempotent.
    rows = []
    for offset, day in enumerate(plans):
        d = today + timedelta(days=offset)
        for n, (start, end, cat, title) in enumerate(day):
            rid = f"demo-{d.isoformat()}-{n}"
            rows.append(
                f"({q(rid)}, {q(a.worker)}, {q(title)}, {q(d.isoformat())}, {q(start)}, "
                f"{q(end)}, {q(cat)}, {q(MARK + ' demo reel')}, 'planned', {q(uid)})")

    psql("insert into schedule_items "
         "(id, worker_name, title, date, start_time, end_time, category, notes, "
         "item_status, auth_uid) "
         "values " + ",".join(rows) + ";")

    after = psql(f"select count(*) from schedule_items where worker_name = {q(a.worker)};")
    # `date` is stored as TEXT (the app writes ISO strings), so compare as text
    todays = psql(f"select count(*) from schedule_items where worker_name = {q(a.worker)} "
                  f"and date = current_date::text;")
    print(f"{a.worker}: {after} schedule_items after ({todays} today)")
    withuid = psql(f"select count(*) from schedule_items where worker_name = {q(a.worker)} "
                   f"and date = current_date::text and auth_uid is not null;")
    print(f"  today rows carrying auth_uid: {withuid}")
    if int(todays) == 0 or int(withuid) == 0:
        print("  ERROR: today has no RLS-visible items - the Day Planner would film empty")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
