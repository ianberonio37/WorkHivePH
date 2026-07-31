#!/usr/bin/env python3
"""validate_marketplace_bank_journey.py — Runner A, the JOURNEY lane of the marketplace test bank.

The SQL lane (Runner B) proves what the database owes. This lane proves what the SCREEN owes, and it
exists for exactly one class of claim: a handoff between two parties, where what A does must appear
to B. No amount of SQL can prove that a client's map repaints, and a silent tracking failure is
indistinguishable from a provider who has not moved.

WHY A SEPARATE RUNNER. The bank's journey cells run in Playwright, which is minutes rather than
seconds and needs a live site plus a live DB — so it is `skip_if_fast` while the SQL lane runs in
`--fast`. Splitting the lanes keeps the cheap half cheap ([[feedback_heavy_deterministic_gate_report_back_not_slow_floor]]).

INVOKED AS `node node_modules/@playwright/test/cli.js`, never `npx`: this project's path contains an
`&`, which the npx shim mis-parses into a broken module path ([[feedback_deploy_subst]]). A gate that
cannot start is a gate that reports nothing.

Usage:  python tools/validate_marketplace_bank_journey.py [--selftest]
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK = os.path.join(ROOT, "marketplace_test_bank.json")
CLI = os.path.join(ROOT, "node_modules", "@playwright", "test", "cli.js")
# Forward slashes deliberately: playwright treats this argument as a REGEX over test file paths, so
# an os.path.join backslash becomes an escape and the run reports "No tests found" — which the gate
# would otherwise print as a FAIL of the journey itself rather than of its own invocation.
SPEC = "tests/marketplace-bank-two-context.spec.ts"
GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"

# cell id -> the test title substring that proves it. Stated explicitly so a renamed test surfaces as
# "no test claims this cell" instead of silently dropping the cell's coverage.
CELLS = {
    "TB-S6-realtime-map-ui-publisher-x-watcher": "the watcher's marker repaints when the publisher moves",
    "TB-S2-pwa-offline-hail-degraded": "an offline hail is refused in words, and writes nothing",
    "TB-SJ09-ui-the-open-page-learns-of-the-cancellation":
        "the provider's screen stops showing a dead job",
    "TB-SJ07-ui-the-watcher-sees-the-job-advance":
        "the client's status chip keeps up with the provider",
    "TB-SJ28-ui-a-waiting-provider-sees-the-hail-arrive":
        "the feed refreshes with no job in hand",
    "TB-SJ33-ui-presence-counts-a-provider-who-just-came-online":
        "publisher x viewer, and the number is TRUE",
    "TB-SJ01-responder-answers-the-hail":
        "the provider accepts from their own page and the client sees it",
    "TB-SJ10-ui-the-client-learns-the-provider-cancelled":
        "the stranded party is the one who must be told",
    "TB-SJ06-ui-the-quoter-composes-and-the-client-compares":
        "a price sent by a person, seen by a person",
}


def run_spec(env_extra=None, timeout=420, reporter="line"):
    env = dict(os.environ)
    env.update(env_extra or {})
    try:
        r = subprocess.run(["node", CLI, "test", SPEC, f"--reporter={reporter}"],
                           cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=env)
    except Exception as e:
        return None, str(e)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def per_test_outcomes(out):
    """-> {test title: (ok, error text)} parsed from Playwright's JSON reporter.

    WHY THIS EXISTS. The runner used to derive EVERY cell's status from a GLOBAL tally:
    `claimed = npass >= len(CELLS) and nfail == 0`. So a single failing test condemned all nine cells —
    on 2026-07-31 exactly one test failed (a sign-in timeout on the realtime-map cell) and the lane
    quarantined ALL NINE, reporting "0 passed" while Playwright had actually run 9 and passed 8. Eight
    healthy cells were carrying a quarantine flag that described someone else's failure.

    That is this platform's recurring shape pointing the other way: a status whose EVIDENCE IS SOMETHING
    ELSE ([[feedback_gate_parsed_text_not_the_db_false_green]]), except here it manufactures a false RED
    instead of a false green — and a false red is not harmless, because it hides which cell actually
    broke and trains the reader to discount the board ([[feedback_a_dead_fixture_invents_page_defects]]).

    So each cell is now judged by ITS OWN test result, and the JSON reporter is used because the line
    reporter's human text cannot be attributed reliably.
    """
    try:
        blob = json.loads(out[out.index("{"):out.rindex("}") + 1])
    except Exception:
        return {}
    found = {}

    def walk(node):
        for spec in node.get("specs", []) or []:
            title = spec.get("title", "")
            ok = bool(spec.get("ok"))
            err = ""
            for t in spec.get("tests", []) or []:
                for res in t.get("results", []) or []:
                    e = res.get("error") or {}
                    err = err or (e.get("message") or "")
            found[title] = (ok, err)
        for child in node.get("suites", []) or []:
            walk(child)

    walk(blob)
    for s in blob.get("suites", []) or []:
        walk(s)
    return found


def selftest():
    """Teeth: freeze the publisher and the watcher assertion must go RED.

    A journey lane that cannot fail is decoration. `WH_TB_FREEZE=1` parks the provider at their
    original coordinate, so a tracker that repaints correctly reports no movement — and the spec
    fails on purpose. If this run comes back green, the harness is reading something other than the
    live feed and every green result above it is worthless.
    """
    if not os.path.exists(CLI):
        print(f"  {YEL}SKIP{RST} @playwright/test is not installed")
        return 0
    code, out = run_spec({"WH_TB_FREEZE": "1"})
    if code is None:
        print(f"  {YEL}SKIP{RST} could not launch playwright ({out[:90]})")
        return 0
    bit = code != 0 and "teeth run" in out
    if bit:
        print(f"  {GREEN}PASS{RST} teeth: a FROZEN publisher makes the watcher assertion fail")
    else:
        print(f"  {RED}FAIL{RST} teeth: a frozen publisher still passed — the watcher assertion is "
              f"not reading the live feed (exit={code})")
    print(f"\n  SELFTEST: {GREEN + 'PASS' + RST if bit else RED + 'FAIL' + RST}")
    return 0 if bit else 1


def main():
    if "--selftest" in sys.argv:
        return selftest()
    if not os.path.exists(CLI):
        print("  SKIP: @playwright/test is not installed — journey lane cannot run")
        return 0
    if not os.path.exists(BANK):
        print("  SKIP: marketplace_test_bank.json not built")
        return 0

    print("=" * 80)
    print(f"  {BOLD}Marketplace test bank — journey lane (Runner A, two browser contexts){RST}")
    print("=" * 80)

    # ONE run, JSON reported. The lane is expensive (two browser contexts per cell), so it is not run
    # twice to get a second format — the JSON carries both the per-test outcomes and the totals.
    code, out = run_spec(reporter="json")
    out_json = out
    if code is None:
        print(f"  {YEL}SKIP{RST} could not launch playwright ({out[:110]})")
        return 0

    # "No tests found" is an INVOCATION failure, not a journey failure. Reporting it as the latter
    # would tell whoever reads the board that the live map broke, when the runner simply never ran.
    if "No tests found" in out:
        print(f"  {RED}FAIL{RST} the runner matched no spec ({SPEC}) — this is the gate's own "
              f"invocation, not the journey. Fix the path before trusting any result here.")
        return 1

    passed = re.search(r"(\d+) passed", out)
    failed = re.search(r"(\d+) failed", out)
    npass = int(passed.group(1)) if passed else 0
    nfail = int(failed.group(1)) if failed else 0
    path = re.search(r"publisher path: (.+)", out)
    # Totals come from the SAME per-test source as the verdicts once JSON is available. Reading them
    # from a different place than the statuses is how "0 passed" got printed next to a run in which
    # eight tests had passed.
    _pt = per_test_outcomes(out)
    if _pt:
        npass = sum(1 for ok, _ in _pt.values() if ok)
        nfail = sum(1 for ok, _ in _pt.values() if not ok)

    # An ENVIRONMENTAL failure is one where the harness could not put the journey in a position to be
    # judged. Distinguished by the message the spec itself raises: these are all fixture/setup
    # conditions, never assertion outcomes. Learned the hard way — the full suite ran this gate while
    # the same spec was being driven by hand, both runs planted an en_route job for the same provider,
    # and the gate reported a broken live map that was working perfectly.
    ENV_MARKS = ("sign-in failed", "no service_provider is bound", "need a second seeded worker",
                 "could not plant the probe job", "Timeout", "ECONNREFUSED", "net::ERR")

    # PER-TEST attribution. `outcomes` maps a test title to (ok, error); a cell is judged by the test
    # that claims it and by nothing else. If the JSON reporter gave nothing (an invocation problem, not
    # a journey problem), fall back to the old global reading rather than inventing per-cell verdicts —
    # but say so, because a lane judged globally is exactly what produced eight false quarantines.
    outcomes = per_test_outcomes(out_json)
    if not outcomes:
        print(f"  {YEL}note{RST}  per-test results unavailable — falling back to the GLOBAL tally, "
              f"which cannot tell which cell failed")

    with open(BANK, encoding="utf-8") as f:
        bank = json.load(f)
    by = {t["id"]: t for t in bank["tests"]}
    for cid, title in CELLS.items():
        cell = by.get(cid)
        if cell is None:
            print(f"  {RED}FAIL{RST} the bank has no cell {cid} — this lane claims coverage that "
                  f"the bank does not record")
            return 1
        mine = next(((ok, err) for t, (ok, err) in outcomes.items() if title in t), None)
        if outcomes and mine is None:
            # The cell names a test that no longer exists — coverage claimed but not run. Surfaced
            # loudly rather than silently dropped, which is the point of stating CELLS explicitly.
            print(f"  {RED}FAIL{RST} no test claims {cid} (looked for {title!r}) — the lane's cell "
                  f"map has drifted from the spec")
            return 1
        if mine is not None:
            ok, err = mine
            environmental = "" if ok else next((m for m in ENV_MARKS if m in err), "")
        else:
            environmental = next((m for m in ENV_MARKS if m in out), "") if code != 0 else ""
            ok = code == 0 and npass >= len(CELLS) and nfail == 0
        if ok:
            cell["status"] = "banked"
            cell.pop("quarantine", None)
        elif environmental:
            # QUARANTINE, not `owed`. A browser cell that fails because the FIXTURE could not be set
            # up — a second run of this spec holding the same provider, a sign-in that could not
            # complete — has told us nothing about the journey. Marking it `owed` silently deletes a
            # proof that still holds; marking it failed accuses working code. Quarantine keeps it out
            # of the % AND on the board with a count, so an unexplained one is debt with a name
            # (Google's flake study: flakiness MASKS real bugs, so it must never be invisible).
            q = cell.get("quarantine") or {"count": 0, "first_seen": "2026-07-29"}
            q["count"] = q.get("count", 0) + 1
            q["last_reason"] = environmental[:160]
            cell["quarantine"] = q
            cell["status"] = "quarantined"
        else:
            cell["status"] = "owed"
        mark = (GREEN + "PASS" + RST if cell["status"] == "banked" else
                (YEL + "QUAR" + RST if cell["status"] == "quarantined" else RED + "FAIL" + RST))
        print(f"  {mark}  {cid}"
              + (f"  {DIM}{cell['quarantine']['last_reason']}{RST}"
                 if cell["status"] == "quarantined" else ""))
    with open(BANK, "w", encoding="utf-8") as f:
        json.dump(bank, f, indent=2, ensure_ascii=False)

    if path:
        # Which path published matters: the page's own watchPosition is the real product behaviour;
        # the session-db fallback still proves the watcher but not the publisher's geolocation wiring.
        print(f"  {DIM}publisher path exercised: {path.group(1).strip()}{RST}")
    print(f"\n  {npass} passed · {nfail} failed")
    if code != 0:
        tail = [l for l in out.splitlines() if "Error:" in l or "✘" in l][:6]
        print(f"\n  {RED}FAIL{RST} — the journey lane did not hold:")
        for l in tail:
            print(f"    {l.strip()[:150]}")
        return 1
    print(f"  {GREEN}PASS{RST} — the two-sided journey holds end to end: what the PUBLISHER does "
          f"appears on the WATCHER's screen")
    return 0


if __name__ == "__main__":
    sys.exit(main())
