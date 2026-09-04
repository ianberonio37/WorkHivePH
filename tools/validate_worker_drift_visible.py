#!/usr/bin/env python3
"""validate_worker_drift_visible.py — T186's lock: a worker drifting away is VISIBLE to a supervisor
while there is still time to help.

T186 ("week one: habit formation vs abandonment") found the failure: the platform knew who had stopped
— per-worker recency lived across four truth surfaces (worker_achievements.last_action_at,
v_worker_assignment_truth.last_job_at/.last_pm_at, v_community_reputation_truth.last_active_at) — but it
was NEVER surfaced to a supervisor. Built 2026-09-01: hive.html's supervisor-only Team Pulse panel now
reads v_worker_assignment_truth (row-per-member, so a never-engaged new worker with NULL activity is
included too) and renders a "Quiet 7+ days" line naming each drifted/never-active worker.

This gate holds that surface in place:
  1. hive.html has the #pulse-quiet-workers element (the drift line);
  2. loadTeamPulse reads v_worker_assignment_truth and both recency columns (last_job_at + last_pm_at),
     so it catches drifted AND never-engaged workers;
  3. it applies a quiet-days threshold (QUIET_DAYS) — a real inactivity cutoff, not a vibe; and
  4. it has an HONEST-DEGRADED path — an unread activity list must not imply everyone is active
     (a false "all clear"), the exact class T186 exists to prevent.

Static (file read), browser-free. Registered in run_platform_checks (Platform)."""
from __future__ import annotations

import io
import re
import sys

CHECK_NAMES = ["worker-drift-visible"]
PAGE = "hive.html"


def _read() -> str | None:
    try:
        return io.open(PAGE, encoding="utf-8").read()
    except Exception:
        return None


def check(html: str) -> list[str]:
    problems: list[str] = []
    if 'id="pulse-quiet-workers"' not in html:
        problems.append("no #pulse-quiet-workers element — drift has no surface (the supervisor cannot see who went quiet)")
    # the drift computation must read the recency view + BOTH recency columns
    reads_view = "v_worker_assignment_truth" in html
    if not reads_view:
        problems.append("hive.html does not read v_worker_assignment_truth — the drift line has no recency data source")
    else:
        # scope the checks to the DRIFT computation: anchor on the view read (added only by loadTeamPulse's
        # drift block), NOT on the first #pulse-quiet-workers occurrence (which is the HTML element, far
        # above the JS). A window around the view read captures the columns, threshold, and error path.
        idx = html.find("from('v_worker_assignment_truth')")
        if idx < 0:
            idx = html.find('from("v_worker_assignment_truth")')
        window = html[max(0, idx - 600): idx + 2200] if idx >= 0 else html
        if not ("last_job_at" in window and "last_pm_at" in window):
            problems.append("the drift computation does not use both last_job_at and last_pm_at — it would miss part of a worker's recency")
        if not re.search(r"QUIET_DAYS|>=\s*7|7\s*\*\s*86400000|quiet", window, re.I):
            problems.append("no inactivity threshold (QUIET_DAYS / 7-day cutoff) — 'drift' is not actually defined")
        # honest-degraded: on a read error it must NOT fall through to an implicit all-active
        if not re.search(r"\.error", window) or "unavailable" not in window.lower():
            problems.append("no honest-degraded path — an unread activity list must say so, not imply everyone is active (false all-clear)")
    return problems


def main() -> int:
    html = _read()
    if html is None:
        print(f"FAIL worker-drift-visible — {PAGE} not found or unreadable."); return 1
    problems = check(html)
    if problems:
        print("FAIL worker-drift-visible — a drifting worker is not made visible to a supervisor:")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS worker-drift-visible — hive.html's Team Pulse reads v_worker_assignment_truth (last_job_at + "
          "last_pm_at, row-per-member) and renders #pulse-quiet-workers naming workers quiet 7+ days (drifted or "
          "never-engaged), with an honest-degraded path so an unread list never reads as 'all active'.")
    return 0


def self_test() -> int:
    good = ('<p id="pulse-quiet-workers"></p>'
            + " db.from('v_worker_assignment_truth').select('worker_name, last_job_at, last_pm_at')"
            + " const QUIET_DAYS = 7; if (actRes.error) { qwEl.textContent = 'unavailable'; }")
    fails = []
    if check(good):
        fails.append("a complete drift surface should PASS")
    if not any("no surface" in p for p in check(good.replace('id="pulse-quiet-workers"', 'id="x"'))):
        fails.append("missing element should FAIL")
    if not any("recency data source" in p for p in check(good.replace("v_worker_assignment_truth", "v_other"))):
        fails.append("missing view should FAIL")
    if not any("both last_job_at" in p for p in check(good.replace("last_pm_at", "x"))):
        fails.append("missing a recency column should FAIL")
    if not any("threshold" in p for p in check(good.replace("QUIET_DAYS = 7", "X").replace("quiet", "z"))):
        fails.append("missing threshold should FAIL")
    if not any("honest-degraded" in p for p in check(good.replace("unavailable", "x"))):
        fails.append("missing honest-degraded path should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_worker_drift_visible self-test (no-element / no-view / missing-column / no-threshold / no-honest-degraded redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
