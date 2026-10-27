#!/usr/bin/env python3
"""prove_outcome_figures.py - the console's outcome figures, recomputed from the ledger (T2 OUT85-87, 2026-10-27).

The operator console's "Did they come back?" panel (founder-console.html #outcomes) shows, per page, three figures read
through founder_outcomes: USE in the last 7 days, RETURN within 7 and 30 days, and REPEAT USE within 7 days. A figure on
a founder screen is a claim about the ledger, and an RPC that agrees with itself proves nothing. So this gate:

  1. reads the RAW ledger (analytics_events, the same 90-day window) through psql and computes every figure in Python
     - a second implementation that shares no SQL with the RPC, so a wrong join or an off-by-one day in either one
     shows up as a disagreement;
  2. signs in as a platform admin, opens the console, and reads each figure as the page RENDERS it (the text of each
     [data-fig] span - "no one due yet" reads as 0 of 0);
  3. compares page by page, and names every page the ledger has and the screen dropped.

Three verdicts, one per OUT gate: use (OUT85), return (OUT86), repeat use (OUT87). A ledger whose figures are all zero
is VACUOUS, never a pass - 0 equals 0 on any implementation (the seeder seeders/analytics_history.py writes the shapes).

    python tools/prove_outcome_figures.py          # all three, report -> outcome_figures_report.json
    python tools/prove_outcome_figures.py --self-test
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "outcome_figures_report.json"
SEEDER = "http://127.0.0.1:5000"
P_DAYS = 90                      # what the console asks founder_outcomes for
ADMIN = {"email": "leandromarquez@auth.workhiveph.com", "password": "test1234"}   # local seed account, in marketplace_platform_admins
GATES = {
    "use": ("uses_7d", "use_accounts_7d", "use_sessions_7d"),
    "return": ("cohort_7", "returned_7", "cohort_30", "returned_30"),
    "repeat": ("repeat_cohort", "repeat_7"),
}


def psql(sql: str) -> str:
    r = subprocess.run(["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
                        "-tA", "-F", "\t", "-c", sql], capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise RuntimeError(r.stderr.strip()[:300])
    return r.stdout


def figures(rows: list[tuple], today: dt.date) -> dict:
    """rows: (page, is_use, auth_uid|None, session_id|None, manila_day). The figures founder_outcomes promises."""
    out: dict = defaultdict(lambda: dict.fromkeys(sum(GATES.values(), ()), 0))
    days: dict = defaultdict(set)
    use_days: dict = defaultdict(set)
    accounts: dict = defaultdict(set)
    sessions: dict = defaultdict(set)
    for page, is_use, uid, sid, d in rows:
        if not page:
            continue
        out[page]                                   # every page seen in the window has a row
        if is_use and d > today - dt.timedelta(days=7):
            out[page]["uses_7d"] += 1
            if uid:
                accounts[page].add(uid)
            else:
                sessions[page].add(sid)
        if uid:
            days[(page, uid)].add(d)
            if is_use:
                use_days[(page, uid)].add(d)
    for page in out:
        out[page]["use_accounts_7d"] = len(accounts[page])
        out[page]["use_sessions_7d"] = len({s for s in sessions[page] if s is not None})
    for (page, _uid), ds in days.items():
        d0 = min(ds)
        for n, cohort, returned in ((7, "cohort_7", "returned_7"), (30, "cohort_30", "returned_30")):
            if d0 <= today - dt.timedelta(days=n):
                out[page][cohort] += 1
                if any(d0 < d <= d0 + dt.timedelta(days=n) for d in ds):
                    out[page][returned] += 1
    for (page, _uid), ds in use_days.items():
        u0 = min(ds)
        if u0 <= today - dt.timedelta(days=7):
            out[page]["repeat_cohort"] += 1
            if len({d for d in ds if d <= u0 + dt.timedelta(days=7)}) >= 2:
                out[page]["repeat_7"] += 1
    return {p: dict(v) for p, v in out.items()}


def ledger() -> tuple[dict, dt.date]:
    today = dt.date.fromisoformat(psql("select (now() at time zone 'Asia/Manila')::date").strip())
    raw = psql(f"""select coalesce(page, props ->> 'page'), (event_name <> 'page_view')::int, coalesce(auth_uid::text, ''),
                          coalesce(session_id, ''), (created_at at time zone 'Asia/Manila')::date
                     from public.analytics_events
                    where created_at >= now() - make_interval(days => {max(P_DAYS, 31)})""")
    rows = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        page, is_use, uid, sid, d = line.split("\t")
        rows.append((page or None, is_use == "1", uid or None, sid or None, dt.date.fromisoformat(d)))
    return figures(rows, today), today


NONE_DUE = "no one due yet"


VIEWPORTS = {"phone-390": {"width": 390, "height": 844}, "desktop-1280": {"width": 1280, "height": 900}}


def screen(viewport: dict) -> dict:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport=viewport, service_workers="block")
        # THE INSTRUMENT MUST NOT WRITE TO THE LEDGER IT MEASURES. Every page this walk opens logs a page_view; one that
        # landed between the ledger read and the console's own read would be counted on one side only. This context's
        # event inserts are answered here and never reach the table.
        ctx.route("**/rest/v1/analytics_events*", lambda route: route.fulfill(status=201, body="")
                  if route.request.method == "POST" else route.continue_())
        p = ctx.new_page()
        p.goto(f"{SEEDER}/workhive/shift-brain.html", wait_until="domcontentloaded")
        p.wait_for_function("() => !!window._whSupabaseClient", timeout=15000)
        ok = p.evaluate("""async (a) => { const { error } = await window._whSupabaseClient.auth.signInWithPassword(a);
                                          return !error; }""", ADMIN)
        if not ok:
            raise RuntimeError("SIGN-IN FAILED - every reading after this would be a signed-out page")
        p.goto(f"{SEEDER}/workhive/founder-console.html", wait_until="load")
        # the panel lives in the Platform tab ("Who's using it?"); a hidden table's text is not what anyone sees
        p.click("#opc-tab-platform")
        p.wait_for_selector("#outcomes-content tr[data-out-page], #outcomes-content .honest-empty", timeout=45000)
        got = p.evaluate("""(none) => {
          const out = {};
          for (const tr of document.querySelectorAll('#outcomes-content tr[data-out-page]')) {
            const row = {};
            for (const s of tr.querySelectorAll('[data-fig]')) row[s.dataset.fig] = (s.innerText || '').replace(/[^0-9]/g, '');
            for (const td of tr.querySelectorAll('td[data-pair]')) {
              if ((td.innerText || '').toLowerCase().includes(none)) { const [k, c] = td.dataset.pair.split(','); row[k] = '0'; row[c] = '0'; }
            }
            out[tr.dataset.outPage] = row;
          }
          return out;
        }""", NONE_DUE)
        b.close()
    return {page: {k: int(v) for k, v in row.items() if v != ""} for page, row in got.items()}


def compare(truth: dict, seen: dict) -> dict:
    verdicts = {}
    for gate, keys in GATES.items():
        diffs, missing = [], []
        for page, figs in sorted(truth.items()):
            if page not in seen:
                missing.append(page)
                continue
            for k in keys:
                if seen[page].get(k) != figs[k]:
                    diffs.append(f"{page} {k}: screen {seen[page].get(k)} vs ledger {figs[k]}")
        extra = sorted(set(seen) - set(truth))
        live = sum(1 for f in truth.values() for k in keys if f[k])
        signal = {"use": "uses_7d", "return": "returned_7", "repeat": "repeat_7"}[gate]
        vacuous = not any(f[signal] for f in truth.values())
        verdict = "FAIL" if (diffs or missing or extra) else ("VACUOUS" if vacuous else "PASS")
        verdicts[gate] = {"verdict": verdict, "pages": len(truth), "nonzero_figures": live,
                          "diffs": diffs[:40], "missing_on_screen": missing, "not_in_ledger": extra}
    return verdicts


def self_test() -> int:
    t = dt.date(2026, 10, 27)
    D = lambda n: t - dt.timedelta(days=n)  # noqa: E731
    rows = [
        ("logbook", False, "a", "s1", D(20)), ("logbook", True, "a", "s1", D(20)), ("logbook", True, "a", "s2", D(18)),  # back in 7, repeat
        ("logbook", False, "b", "s3", D(40)), ("logbook", False, "b", "s4", D(15)),                                     # back in 30 only
        ("logbook", False, "c", "s5", D(3)),                                                                            # follow-up running
        ("logbook", True, None, "v1", D(2)), ("logbook", True, None, "v1", D(1)),                                      # signed-out: use only
        ("logbook", True, "d", "s6", D(1)),
    ]
    f = figures(rows, t)["logbook"]
    want = {"uses_7d": 3, "use_accounts_7d": 1, "use_sessions_7d": 1, "cohort_7": 2, "returned_7": 1,
            "cohort_30": 1, "returned_30": 1, "repeat_cohort": 1, "repeat_7": 1}
    bad = {k: (f[k], v) for k, v in want.items() if f[k] != v}
    if bad:
        print("SELF-TEST FAIL", bad)
        return 1
    v = compare({"logbook": f}, {"logbook": {**f, "returned_7": 0}})
    if v["return"]["verdict"] != "FAIL" or v["use"]["verdict"] != "PASS":
        print("SELF-TEST FAIL: a planted screen difference was not caught", v)
        return 1
    if compare({"x": dict.fromkeys(f, 0)}, {"x": dict.fromkeys(f, 0)})["use"]["verdict"] != "VACUOUS":
        print("SELF-TEST FAIL: an all-zero ledger passed")
        return 1
    print("self-test PASS (figures, a planted screen difference, an all-zero ledger)")
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    truth, today = ledger()
    # every OUT row is asked at phone-390 and desktop-1280: a figure the phone's table clips or drops is not shown
    by_vp = {name: compare(truth, screen(vp)) for name, vp in VIEWPORTS.items()}
    REPORT.write_text(json.dumps({"generated": dt.datetime.now().isoformat(timespec="seconds"), "manila_today": today.isoformat(),
                                  "p_days": P_DAYS, "viewports": by_vp}, indent=1) + "\n", encoding="utf-8")
    for vp, verdicts in by_vp.items():
        for gate, v in verdicts.items():
            print(f"  {v['verdict']:7s} {vp:12s} {gate:7s} {v['pages']} pages, {v['nonzero_figures']} non-zero figures"
                  + (f" - {len(v['diffs'])} differ, {len(v['missing_on_screen'])} missing" if v["verdict"] == "FAIL" else ""))
            for d in v["diffs"][:6] + [f"missing on screen: {m}" for m in v["missing_on_screen"][:6]]:
                print("     ", d)
    ok = all(v["verdict"] == "PASS" for verdicts in by_vp.values() for v in verdicts.values())
    print(f"{'PASS' if ok else 'FAIL'} outcome-figures - the console's use, return and repeat-use figures against the ledger")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
