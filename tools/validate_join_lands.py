#!/usr/bin/env python3
"""join-lands-on-roster gate — T6+T7's shared instrument close (2026-08-26).

Runs tools/prove_join_lands.mjs: a two-context paired journey where an OUTSIDE
worker joins the supervisor's hive by invite code (the same SECURITY DEFINER
join_hive_by_code path the UI submit calls) while the supervisor's hive.html
board is open. PASS bar: the join is VISIBLE on the supervisor's roster after
at most one reload, the DB row landed, and the probe row is cleaned + verified.

The prover also measures (never asserts) the realtime half: hive.html registers
no postgres_changes channel on hive_members, so realtime=false is the current
truth — recorded in the output so the day a channel is added the receipt flips.

Discipline (carried from validate_offline_queued.py):
  - retry-once before failing (full-suite live gates flake under load).
  - node invoked DIRECTLY, never npx (the repo path contains an ampersand).
  - utf-8 pinned on the subprocess decode; PASS matched line-anchored.
  - SKIPs cleanly when node / the local stack is absent — a gate that cannot
    run must say SKIP, not PASS.
  - the prover ABORTS (exit 2) on dirty pre-state rather than deleting rows it
    did not create; that surfaces here as FAIL with the abort line.

Re-drive: node tools/prove_join_lands.mjs
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
        [node, str(ROOT / "tools" / "prove_join_lands.mjs")],
        cwd=str(ROOT), capture_output=True, text=True, timeout=240,
        encoding="utf-8", errors="replace",
    )
    out = (r.stdout or "") + (r.stderr or "")
    passed = bool(re.search(r"^\s*PASS", out, re.M))
    tail = out.strip().splitlines()[-3:] if out.strip() else ["<no output>"]
    return passed, " | ".join(line.strip() for line in tail), out


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("SKIP join-lands-on-roster — node not on PATH (live browser gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP join-lands-on-roster — local stack down (Flask :5000 / Supabase :54321)")
        return 0

    try:
        ok, tail, out = _run(node)
        if not ok:
            ok, tail, out = _run(node)
    except subprocess.TimeoutExpired:
        print("FAIL join-lands-on-roster — timed out at 240s")
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
        print("FAIL join-lands-on-roster — the paired join journey did not land/clean.")
        return 1
    print("PASS join-lands-on-roster — the join lands on the watching supervisor's roster, probe row cleaned.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
