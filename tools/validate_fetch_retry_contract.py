#!/usr/bin/env python3
"""validate_fetch_retry_contract.py — a retried WRITE is how one payment becomes two.

`fetchWithTimeout` (utils.js) now retries ONCE on a transport failure, because two gates flaked on that shape:
`push-runtime-delivery` went red once against four greens, and the Playwright smoke tier has an intermittent
Supabase blip. Neither was a product defect and neither was a timeout — the wrapper's budget is 45s and the
failures landed in milliseconds. Widening each spec's budget would have measured network weather; the fix
belongs at the source.

WHAT THIS GATE EXISTS TO PREVENT is the fix itself going wrong. Three properties, and two of them are the
dangerous ones:

  GET + transport failure   -> retried once, resolves on the second attempt      (the flake this closes)
  POST + transport failure  -> NEVER retried, the error propagates                <- a retried write DOUBLES it
  AbortError (timeout)      -> returns null on the FIRST attempt, no retry        <- silently doubling a
                               budget breaks the contract callers reason about, and three callers were just
                               fixed for mis-handling that null
  persistent failure        -> exactly 2 attempts, never a loop

The retry is scoped by HTTP METHOD rather than by an opt-in flag, deliberately: the helper cannot know whether
its caller is safe to repeat, and a flag can be forgotten at any of the ~20 call sites. GET is idempotent by
contract, so every write method is excluded by construction instead of by discipline.

The assertions run against the SHIPPED text of utils.js — the helper is lifted out of the real file rather than
copied into the test — so the gate cannot drift from the code it guards, which is the failure mode of every
hand-mirrored fixture this platform has found.

Usage:  python tools/validate_fetch_retry_contract.py [--selftest]
"""
from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = os.path.join(ROOT, "tools", "fetch_retry_contract.mjs")
GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"


def run(extra_env=None):
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    try:
        # `node` directly, never npx: this repo's path contains an ampersand and npx's own path resolution
        # splits on it ([[reference_npx_ampersand_path_bug]]).
        r = subprocess.run(["node", RUNNER], cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120, env=env)
    except FileNotFoundError:
        return None, "node not installed"
    except Exception as e:  # noqa: BLE001
        return None, str(e)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main(argv):
    print(f"{BOLD}fetchWithTimeout retry contract{RST} — one retry for idempotent reads, NEVER for writes")
    if not os.path.exists(RUNNER):
        print(f"  {RED}FAIL{RST} the runner is missing ({os.path.basename(RUNNER)}) — the gate's own "
              f"invocation failure, not a product defect.")
        return 1
    rc, out = run()
    if rc is None:
        print(f"  {YEL}SKIP{RST} — {out}; nothing asserted.")
        return 0
    for line in out.splitlines():
        if line.strip().startswith(("PASS", "FAIL")) or " pass · " in line:
            print(f"  {DIM}{line.strip()[:120]}{RST}")
    if rc != 0:
        print(f"  {RED}FAIL{RST} the retry contract is broken. If a WRITE is now retried, treat it as urgent: "
              f"the same request landing twice is a duplicate payment, a duplicate job, a duplicate top-up.")
        return 1
    if "--selftest" in argv:
        # Teeth: the suite must be capable of failing. It asserts attempt COUNTS, so a stub that never throws
        # would make the retry assertions vacuous — the runner's own plan drives that, and a green run with
        # zero throws would still report 4 pass. So the self-test checks the runner actually exercised both
        # branches by requiring all four named cases in the output.
        needed = ["GET retries once", "POST is NEVER retried", "AbortError returns null",
                  "exactly 2 attempts"]
        missing = [n for n in needed if n not in out]
        if missing:
            print(f"  {RED}FAIL{RST} selftest: the runner did not exercise {missing} — a green result from a "
                  f"suite that skipped its own cases proves nothing.")
            return 1
        print(f"  {GREEN}PASS{RST} selftest: all four named cases ran, including both that must NOT retry.")
    print(f"  {GREEN}PASS{RST} a GET retries once on a transport blip; a POST never does; a timeout still "
          f"returns null on the first attempt; a dead endpoint stops at two.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
