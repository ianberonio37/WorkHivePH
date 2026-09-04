#!/usr/bin/env python3
"""timed-journey gate — the T9/T10/T13 shared oracle, slice 1 (2026-08-26).

Runs tools/prove_timed_journey.mjs: each case is one user JOB with a stated
budget - the prover walks the scripted core path and reports measured wall
time vs budget. Slice 1: T13's handover-read (worker @390 opens shift-brain;
usable = verdict resolved + carry-forward list populated or honestly empty).
The machine measures the PLATFORM's share (time until the read is possible),
never the human's reading time; a breach is a slowness-regression signal.
Write-journeys (T9 time-to-logged, T10 completion loop) are later slices.

Discipline: retry-once, node direct (ampersand path), utf-8 pinned,
line-anchored PASS, SKIP when node/stack absent.

Re-drive: node tools/prove_timed_journey.mjs
"""
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# A BROKEN MACHINE IS NOT A BROKEN PRODUCT (2026-08-28). This gate drives a real browser and had no
# health check, so an infra death read as a product failure. Measured the same day on dialog-floor: the
# prover died on `SIGN-IN FAILED: Failed to fetch` after Docker Desktop stopped, and the gate reported a
# layout defect that no run had measured. A false RED is worse than a SKIP - a skip says "not measured",
# a red sends someone to read page code that was never wrong, and gates that cry wolf get excluded.
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from browser_gate_health import infra_exhausted
except Exception:                      # never let the health check itself break a gate
    def infra_exhausted(_output):      # noqa: D103
        return None



def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _run(node: str) -> tuple[bool, str, str]:
    r = subprocess.run(
        [node, str(ROOT / "tools" / "prove_timed_journey.mjs")],
        cwd=str(ROOT), capture_output=True, text=True, timeout=300,
        encoding="utf-8", errors="replace",
    )
    out = (r.stdout or "") + (r.stderr or "")
    passed = bool(re.search(r"^\s*PASS", out, re.M))
    tail = out.strip().splitlines()[-3:] if out.strip() else ["<no output>"]
    return passed, " | ".join(line.strip() for line in tail), out


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("SKIP timed-journey-family — node not on PATH (live browser gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP timed-journey-family — local stack down (Flask :5000 / Supabase :54321)")
        return 0

    try:
        ok, tail, out = _run(node)
        if not ok:
            ok, tail, out = _run(node)
    except subprocess.TimeoutExpired:
        print("FAIL timed-journey-family — timed out at 300s")
        return 1

    print(f"  {'PASS' if ok else 'FAIL'}  {tail[:220]}")
    if not ok:
        verdict = infra_exhausted(out)
        if verdict:
            print(f"  SKIP (infrastructure): {verdict}")
            return 0
        # NAME WHAT FAILED. The verdict line above is a 3-line tail, which on 2026-08-28 read
        # "waiting for locator('#f-problem') | | FAIL 0/5 pages" - enough to know something broke and
        # not enough to know WHICH page or WHY, so diagnosing meant re-running the prover by hand.
        # A gate that reports a failure owes the reader the evidence it already has in memory.
        for _l in [l.rstrip() for l in out.splitlines() if l.strip()][-14:]:
            print("    | " + _l[:160])
        print("FAIL timed-journey-family — a journey exceeded its stated budget (slowness regression).")
        return 1
    print("PASS timed-journey-family — every covered journey completed within its stated budget.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
