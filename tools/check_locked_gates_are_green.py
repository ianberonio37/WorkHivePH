""" -*- coding: utf-8 -*-
Do the gates behind a LOCKED trajectory actually pass? (T129, 2026-08-28)

`validate_trajectory_registry` asserts that a locked trajectory NAMES gates and that those gates are
REGISTERED in run_platform_checks. It never asserts they are GREEN. So "locked, 100%" means the
gates EXIST — and the programme's headline percentage inherits exactly that meaning, no more.

★THIS TOOL DOES NOT DECIDE WHETHER THAT IS WRONG. Whether `locked` should REQUIRE a green result is
a decision about what the roadmap's number means, and it belongs to whoever owns the roadmap. What
was missing was not a policy — it was the ability to ASK. This answers the question and reports;
it does not redefine the status or fail a build.

MEASURED on first use: 42 python-runnable gates behind 19 locked trajectories → 40 pass, 2 fail.
One of the two was the harness (a 120s timeout on a gate that passes in ~140s), the other was real:
a gate still asserting a localStorage key format that a later fix had changed. So the honest answer
that day was "41 of 42, and the one red was a gate lagging a fix, not a product regression" — three
different sentences, only one of them true, and none of them reachable without running the gates.

★AND THE FIRST HAND-ROLLED VERSION OF THIS AUDIT REPORTED 0 PASS / 42 FAIL. The gate list had been
written with CRLF endings, so every script path carried a trailing carriage return and none of them
existed. A 100% failure rate is never a finding — it is the instrument. That is the specific reason
this exists as a tool rather than as a shell loop somebody retypes: the loop is where the bug was.

USAGE:  python tools/check_locked_gates_are_green.py [--status locked|locking] [--timeout N]
Exit 0 always: a RECORDER. Read alongside tools/read_recorder_findings.py.
"""
from __future__ import annotations

import io
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "trajectory_registry.json"
BOARD = ROOT / "run_platform_checks.py"


def _board_scripts() -> dict:
    """gate id -> script path, read from the board itself.

    ★THE BOARD USES TWO ENTRY FORMATS AND MY FIRST PATTERN ONLY KNEW ONE. Most entries spread
    "id" and "script" across lines; a few are written inline on one line. Requiring a NEWLINE
    between them made this reader miss the inline ones, and it duly reported T2's
    live-page-journeys as "named by the registry, not on the board" - a confident finding against
    a gate that is registered and runnable. The registry validator disagreed, and it was right.
    Whitespace-flexible now: a file's formatting is not a fact about its contents.
    """
    s = io.open(BOARD, encoding="utf-8", errors="replace").read()
    return dict(re.findall(r'"id":\s*"([^"]+)"\s*,\s*"script":\s*"([^"]+)"', s, re.S))


def main() -> int:
    status = "locked"
    if "--status" in sys.argv:
        status = sys.argv[sys.argv.index("--status") + 1]
    timeout = 300
    if "--timeout" in sys.argv:
        timeout = int(sys.argv[sys.argv.index("--timeout") + 1])

    reg = json.load(io.open(REGISTRY, encoding="utf-8"))
    scripts = _board_scripts()

    todo, unregistered, non_python = [], [], []
    for t in reg["trajectories"]:
        if t.get("status") != status:
            continue
        for g in (t.get("artifacts", {}) or {}).get("gates") or []:
            base = g.split("(")[0]          # the registry allows a parenthetical qualifier
            sc = scripts.get(base)
            if not sc:
                unregistered.append((t["id"], base))
            elif not sc.endswith(".py"):
                non_python.append((t["id"], base, sc))
            else:
                todo.append((t["id"], base, sc))

    print(f"locked-gates-are-green - do the gates behind '{status}' trajectories actually pass?")
    print(f"  {len(todo)} python-runnable | {len(non_python)} non-python (skipped here) | "
          f"{len(unregistered)} not registered\n")

    npass, nfail = 0, 0
    for traj, gate, script in todo:
        p = ROOT / script
        if not p.exists():
            print(f"  MISSING  {traj:<6} {gate:<40} {script}")
            nfail += 1
            continue
        t0 = time.time()
        try:
            r = subprocess.run([sys.executable, str(p)], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=timeout, cwd=str(ROOT))
            ok = r.returncode == 0
        except subprocess.TimeoutExpired:
            # ★A TIMEOUT IS NOT A FAILURE, and conflating them is how this audit first lied.
            print(f"  TIMEOUT  {traj:<6} {gate:<40} exceeded {timeout}s - inconclusive, not red")
            continue
        secs = time.time() - t0
        if ok:
            npass += 1
        else:
            nfail += 1
            tail = (r.stdout or r.stderr or "").strip().splitlines()
            print(f"  FAIL     {traj:<6} {gate:<40} {secs:.0f}s")
            if tail:
                print(f"           {tail[-1][:120]}")

    for traj, gate in unregistered:
        print(f"  UNREG    {traj:<6} {gate:<40} named by the registry, not on the board")
    print(f"\n  {npass} pass | {nfail} fail | {len(non_python)} non-python not run")
    print("  exit 0 by design: this REPORTS what 'locked' currently rests on; it does not redefine it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
