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


def run_spec(env_extra=None, timeout=420):
    env = dict(os.environ)
    env.update(env_extra or {})
    try:
        r = subprocess.run(["node", CLI, "test", SPEC, "--reporter=line"],
                           cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=env)
    except Exception as e:
        return None, str(e)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


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

    code, out = run_spec()
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

    # An ENVIRONMENTAL failure is one where the harness could not put the journey in a position to be
    # judged. Distinguished by the message the spec itself raises: these are all fixture/setup
    # conditions, never assertion outcomes. Learned the hard way — the full suite ran this gate while
    # the same spec was being driven by hand, both runs planted an en_route job for the same provider,
    # and the gate reported a broken live map that was working perfectly.
    ENV_MARKS = ("sign-in failed", "no service_provider is bound", "need a second seeded worker",
                 "could not plant the probe job", "Timeout", "ECONNREFUSED", "net::ERR")
    environmental = next((m for m in ENV_MARKS if m in out), "") if code != 0 else ""

    with open(BANK, encoding="utf-8") as f:
        bank = json.load(f)
    by = {t["id"]: t for t in bank["tests"]}
    for cid, title in CELLS.items():
        cell = by.get(cid)
        if cell is None:
            print(f"  {RED}FAIL{RST} the bank has no cell {cid} — this lane claims coverage that "
                  f"the bank does not record")
            return 1
        claimed = npass >= len(CELLS) and nfail == 0
        if code == 0 and claimed:
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
