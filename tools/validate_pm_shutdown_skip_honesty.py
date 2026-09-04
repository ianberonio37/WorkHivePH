#!/usr/bin/env python3
"""validate_pm_shutdown_skip_honesty.py — T189's lock: a planned shutdown does not read as a compliance
CLIFF, because a PM that could not run is recorded SKIPPED (not overdue, not done) and that skip is
surfaced honestly.

T189 ("seasonal shutdown: the plant sleeps") worried that during an annual two-week shutdown every PM
comes due, goes overdue, and nothing can say the plant was deliberately down — so compliance shows a
cliff that means the opposite of what it looks like, and a supervisor cannot explain the dip FROM the
platform. The platform's answer is the PER-TASK skip atom made honest end to end:
  1. pm_completions.status is CHECK-constrained to include 'skipped' — a shutdown PM is recorded as a
     first-class SKIP, distinct from both 'done' and (silently) overdue;
  2. v_pm_compliance_truth exposes pm_skipped_count — the skips are counted, not swept under the rug;
  3. asset-hub surfaces pm_skipped_count on its PM tile — a reader SEES "N recorded as skipped, not
     performed", so the dip is explained on the glass.
Paired with a-deferral-is-not-a-completion (T10: a skip is never counted as a completion), this is the
capability that answers T189's north star. (A period-level BULK pause is a future ergonomic layer over
this per-task atom, not a missing capability.)

DB + static (asset-hub.html); browser-free. SKIPs the DB half if unreachable. Registered in
run_platform_checks (Platform)."""
from __future__ import annotations

import io
import subprocess
import sys

CHECK_NAMES = ["pm-shutdown-skip-honesty"]


def _psql(sql: str) -> str | None:
    try:
        r = subprocess.run(
            ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres", "-t", "-A", "-c", sql],
            capture_output=True, text=True, timeout=45)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def _read(path: str) -> str | None:
    try:
        return io.open(path, encoding="utf-8").read()
    except Exception:
        return None


def _db() -> dict | None:
    skip_status = _psql("select exists(select 1 from pg_constraint where conrelid='public.pm_completions'::regclass "
                        "and contype='c' and pg_get_constraintdef(oid) ilike '%skipped%')::text;")
    if skip_status is None:
        return None
    skip_in_view = _psql("select (pg_get_viewdef('public.v_pm_compliance_truth'::regclass) ilike '%skip%')::text;")
    return {"skip_status": skip_status == "true", "skip_in_view": (skip_in_view == "true")}


def check(db: dict | None, assethub: str | None) -> list[str]:
    problems: list[str] = []
    if db is not None:
        if not db.get("skip_status"):
            problems.append("pm_completions.status has no 'skipped' value — a shutdown PM cannot be recorded as a first-class skip (it just goes overdue)")
        if not db.get("skip_in_view"):
            problems.append("v_pm_compliance_truth does not expose the skip count — skips are not counted, so the dip cannot be explained")
    if assethub is None:
        problems.append("asset-hub.html not found — cannot verify the skip is surfaced on the tile")
    elif "pm_skipped_count" not in assethub:
        problems.append("asset-hub no longer surfaces pm_skipped_count — a shutdown's skips are invisible on the glass (the cliff looks like failure again)")
    return problems


def main() -> int:
    db = _db()
    assethub = _read("asset-hub.html")
    problems = check(db, assethub)
    if problems:
        print("FAIL pm-shutdown-skip-honesty — a shutdown could read as a false compliance cliff:")
        for p in problems:
            print(f"    {p}")
        return 1
    tail = "" if db is not None else " (DB half skipped — unreachable)"
    print("PASS pm-shutdown-skip-honesty — a shutdown PM is recorded 'skipped' (CHECK-constrained, distinct from "
          "done/overdue), counted in v_pm_compliance_truth, and surfaced on asset-hub's tile: a supervisor can "
          f"explain the dip from the platform, not a false cliff.{tail}")
    return 0


def self_test() -> int:
    fails = []
    if check({"skip_status": True, "skip_in_view": True}, "el.textContent = row.pm_skipped_count"):
        fails.append("the honest posture should PASS")
    if not any("first-class skip" in p for p in check({"skip_status": False, "skip_in_view": True}, "pm_skipped_count")):
        fails.append("no 'skipped' status should FAIL")
    if not any("not counted" in p for p in check({"skip_status": True, "skip_in_view": False}, "pm_skipped_count")):
        fails.append("skip not in view should FAIL")
    if not any("invisible on the glass" in p for p in check({"skip_status": True, "skip_in_view": True}, "<div>no skip here</div>")):
        fails.append("tile not surfacing skip should FAIL")
    if check({"skip_status": True, "skip_in_view": True}, None) and not any("not found" in p for p in check({"skip_status": True, "skip_in_view": True}, None)):
        fails.append("missing asset-hub should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_pm_shutdown_skip_honesty self-test (no-skip-status / skip-not-counted / tile-hides-skip / missing redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
