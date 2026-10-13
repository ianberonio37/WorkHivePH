#!/usr/bin/env python3
"""
validate_author_can_edit_own_work.py — a person must be able to amend their own work.

THE BUG THIS RATCHETS (2026-10-04). logbook's write policies are

    logbook_update : (auth.uid() IS NOT NULL) AND (auth_uid = auth.uid())
    logbook_delete : (auth.uid() IS NOT NULL) AND (auth_uid = auth.uid())

and 27,420 of 31,241 entries (87.8%) carried auth_uid NULL, so `NULL = auth.uid()` was NULL and never
true. There is no second permissive policy for either command, so there was no other path: those entries
were READABLE and permanently un-amendable and un-deletable by the people who wrote them. Proven by
impersonation rather than inferred - acting as the resolved author, the row read 1 and both UPDATE and
DELETE returned 0 - and a 0-row UPDATE raises no error, so a worker amended an entry, saw nothing go
wrong, and lost the amendment. inventory_items (10) and asset_nodes (24) had the same shape.

Migration 20261004000002 bound the author from the roster where (hive_id, worker_name) resolved to
EXACTLY ONE auth_uid: logbook and inventory_items are now 100%, asset_nodes left 19 rows unbound because
the stored name matches no roster row and guessing an owner is worse than leaving one unbound.

WHAT THIS ASSERTS, as a FORWARD-ONLY ratchet:
  1. the unbound count never GROWS for any guarded table - a new write that forgets the identity is
     caught here rather than by the person who cannot edit their entry a month later;
  2. the write policies still KEY on auth_uid - if a future migration loosens them, this ratchet would
     otherwise keep passing while measuring something that no longer matters, which is the vacuous-gate
     trap. A policy that stops naming auth_uid is reported, not silently tolerated.

Static against the live schema + a count query. Self-test: --selftest pins both directions.
Output: author_can_edit_own_work_report.json. Exit 1 on a regression, else 0.
"""
from __future__ import annotations

import datetime
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASELINE = ROOT / "author_can_edit_own_work_baseline.json"
REPORT = ROOT / "author_can_edit_own_work_report.json"

GREEN, RED, YELLOW, RESET, BOLD = "\033[92m", "\033[91m", "\033[93m", "\033[0m", "\033[1m"

# table -> the policy names whose predicate must keep naming auth_uid
GUARDED = {
    "logbook": ["logbook_update", "logbook_delete"],
    "inventory_items": ["inventory_items_write"],
    "asset_nodes": ["asset_nodes_write"],
}

# ★THESE POLICIES NOW CARRY THE WHOLE WEIGHT, BECAUSE THE CLIENT BELT WAS REMOVED (2026-10-04).
# marketplace.html used to filter its watchlist and saved-search reads AND deletes by
# .eq('worker_name', WORKER_NAME) on top of RLS. That was redundant - the policy is
#     USING / CHECK (worker_name IN (SELECT auth_worker_names()))
# and auth_worker_names() is a SECURITY DEFINER function returning the names belonging to auth.uid(),
# read from hive_members and marketplace_sellers - and it was harmful: WORKER_NAME is localStorage text,
# so once it drifted the filter narrowed RLS's correct answer to nothing (an empty watchlist on a read; a
# 204 no-op on a delete that the person was told had worked). The filters are gone and RLS does the
# scoping it was already doing. The cost of that simplification is a DEPENDENCY, so it is asserted here:
# if one of these policies is dropped or stops deriving from auth.uid(), those reads become unscoped and
# this gate says so. Verified when the filters were removed: achievement_xp_log holds 31,941 rows across
# 29 names and RLS alone returned exactly the 2,553 belonging to the caller, 0 belonging to anyone else.
NAME_DERIVED = {
    "marketplace_watchlist": ["mkt_watchlist_owner_rw"],
    "marketplace_saved_searches": ["mkt_saved_searches_owner_rw"],
    "achievement_xp_log": ["ach_log_owner_read"],
}


def _q(sql: str) -> list[list[str]]:
    r = subprocess.run(
        ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
         "-tAF\x1f", "-c", sql],
        capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"psql failed: {r.stderr.strip()[:300]}")
    return [ln.split("\x1f") for ln in r.stdout.strip().splitlines() if ln.strip()]


def measure() -> dict:
    out = {"unbound": {}, "policies": {}}
    for tbl in GUARDED:
        rows = _q(f"select count(*) filter (where auth_uid is null), count(*) from public.{tbl};")
        out["unbound"][tbl] = {"null": int(rows[0][0]), "total": int(rows[0][1])}
    # The predicates contain NEWLINES (a policy with a subquery is pretty-printed), and this reader
    # splits psql's output by line - so a multi-line predicate arrived as several bogus rows and the
    # unpack blew up. Collapse the whitespace in SQL, where the row boundary is still known.
    pol = _q("select tablename, policyname, "
             "regexp_replace(coalesce(qual,'') || ' ' || coalesce(with_check,''), E'[\\n\\r\\t]+', ' ', 'g') "
             "from pg_policies where schemaname='public' and tablename in "
             "('logbook','inventory_items','asset_nodes','marketplace_watchlist',"
             "'marketplace_saved_searches','achievement_xp_log');")
    out["policies_derive_uid"] = {}
    for tbl, name, pred in pol:
        out["policies"][f"{tbl}.{name}"] = ("auth_uid" in pred)
        # "derives from the session" means the predicate reaches auth.uid() somehow: directly, or through
        # auth_worker_names(), the SECURITY DEFINER function that maps auth.uid() to the caller's names.
        out["policies_derive_uid"][f"{tbl}.{name}"] = ("auth.uid()" in pred) or ("auth_worker_names" in pred)
    return out


def audit(m: dict, floors: dict) -> list[str]:
    problems = []
    for tbl, c in m["unbound"].items():
        floor = floors.get(tbl)
        if floor is not None and c["null"] > floor:
            problems.append(
                f"{tbl}: rows with NO auth_uid rose {floor} -> {c['null']} of {c['total']}. Each one is a "
                f"row its own author cannot UPDATE or DELETE (the write policy keys on auth_uid), and the "
                f"failure is SILENT - a 0-row update raises nothing. Bind the identity on write.")
    # the name-derived policies that now carry the whole weight (see NAME_DERIVED)
    for tbl, names in NAME_DERIVED.items():
        for name in names:
            full = f"{tbl}.{name}"
            if full not in m["policies"]:
                problems.append(
                    f"{full} is GONE. marketplace.html's watchlist/saved-search reads and deletes no longer "
                    f"carry a client-side owner filter - that policy IS the scoping now, so without it those "
                    f"queries return everyone's rows. Restore the policy or put the filter back.")
            elif not m["policies_derive_uid"].get(full):
                problems.append(
                    f"{full} no longer derives from auth.uid() (directly or via auth_worker_names()). A "
                    f"display-name predicate that is not anchored to the session is forgeable, and the client "
                    f"filter that used to narrow it has been removed.")

    for key, names in GUARDED.items():
        for name in names:
            full = f"{key}.{name}"
            if full not in m["policies"]:
                problems.append(f"{full} no longer exists - this ratchet counts unbound rows because that "
                                f"policy made them unwritable; if the policy changed, re-point the gate")
            elif not m["policies"][full]:
                problems.append(f"{full} no longer keys on auth_uid - the unbound count above has stopped "
                                f"meaning anything, so this gate would pass while measuring nothing")
    return problems


def selftest() -> int:
    probs = []
    m = {"unbound": {"logbook": {"null": 5, "total": 100}},
         "policies": {"logbook.logbook_update": True, "logbook.logbook_delete": True,
                      "inventory_items.inventory_items_write": True,
                      "asset_nodes.asset_nodes_write": True,
                      "marketplace_watchlist.mkt_watchlist_owner_rw": True,
                      "marketplace_saved_searches.mkt_saved_searches_owner_rw": True,
                      "achievement_xp_log.ach_log_owner_read": True},
         "policies_derive_uid": {"marketplace_watchlist.mkt_watchlist_owner_rw": True,
                                 "marketplace_saved_searches.mkt_saved_searches_owner_rw": True,
                                 "achievement_xp_log.ach_log_owner_read": True}}
    if not audit(m, {"logbook": 0}):
        probs.append("a RISE in unbound rows (0 -> 5) was not caught - the ratchet has no teeth")
    if audit(m, {"logbook": 5}):
        probs.append("an unchanged count at the floor was flagged - the ratchet would block honest work")
    m_nd = {"unbound": {}, "policies": {"marketplace_watchlist.mkt_watchlist_owner_rw": False},
            "policies_derive_uid": {"marketplace_watchlist.mkt_watchlist_owner_rw": False}}
    probs_nd = audit(m_nd, {})
    if not any("no longer derives from auth.uid()" in x for x in probs_nd):
        probs.append("a name-derived policy that stopped reaching auth.uid() was not reported - the "
                     "watchlist reads have no client filter left, so that is an unscoped read")
    m_gone = {"unbound": {}, "policies": {}, "policies_derive_uid": {}}
    if not any("is GONE" in x for x in audit(m_gone, {})):
        probs.append("a MISSING name-derived policy was not reported")
    m2 = dict(m, policies=dict(m["policies"], **{"logbook.logbook_update": False}))
    if not any("stopped meaning anything" in p for p in audit(m2, {"logbook": 5})):
        probs.append("a policy that stopped naming auth_uid was not reported - the gate could go vacuous")
    print("SELFTEST PASS" if not probs else "SELFTEST FAIL:\n  " + "\n  ".join(probs))
    return 1 if probs else 0


def main() -> int:
    if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")
    if "--selftest" in sys.argv:
        return selftest()

    m = measure()
    floors = {}
    if BASELINE.exists():
        try:
            floors = json.loads(BASELINE.read_text(encoding="utf-8")).get("floors", {})
        except Exception:
            floors = {}
    problems = audit(m, floors)
    ok = not problems

    print(f"\n{BOLD}AUTHOR CAN EDIT OWN WORK (a row with no bound identity is un-amendable by its author){RESET}")
    print("-" * 78)
    for tbl, c in m["unbound"].items():
        bound = c["total"] - c["null"]
        pct = round(100 * bound / c["total"], 1) if c["total"] else None
        flag = GREEN + "ok  " + RESET if c["null"] <= floors.get(tbl, c["null"]) else RED + "RISE" + RESET
        print(f"  {flag} {tbl:<18} identity bound on {bound}/{c['total']} ({pct}%)"
              f"   unbound: {c['null']}  (floor {floors.get(tbl, '-')})")
    for p in problems:
        print(f"  {RED}FAIL{RESET} {p}")
    if ok:
        BASELINE.write_text(json.dumps({
            "_doc": "Forward-only floors: the count of rows with NO auth_uid may fall, never rise. "
                    "asset_nodes keeps 19 - names that match no roster row, deliberately not guessed.",
            "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "floors": {t: min(c["null"], floors.get(t, c["null"])) for t, c in m["unbound"].items()},
            "measured": m["unbound"],
        }, indent=2) + "\n", encoding="utf-8")
        print(f"  {GREEN}PASS{RESET}  no table gained an unbound row; every write policy still keys on auth_uid")
    REPORT.write_text(json.dumps({"ok": ok, "measured": m, "failures": problems,
                                  "generated": datetime.datetime.now(datetime.timezone.utc).isoformat()},
                                 indent=2) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
