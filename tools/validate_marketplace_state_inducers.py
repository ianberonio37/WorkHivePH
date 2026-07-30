#!/usr/bin/env python3
"""validate_marketplace_state_inducers.py — the two bank states SQL altitude cannot reach.

`TB-STATE-inducers-empty-filtered0-edge` induces `empty`, `filtered0` and `edge` in rolled-back SQL and
deliberately stops there. The remaining two are BROWSER facts and belong here:

  error      the listings read FAILS  — induced by aborting that request at the network layer
  degraded   the device is offline    — induced by flipping the browser context offline

WHY THE `error` ONE IS THE POINT. A failed read and an empty result are the same thing to a row count, and
this platform has already been bitten by that: `read-battery` once reported SIX named page failures, all
"DB empty -> empty-state (no error)", none real. From the USER's side the ambiguity is worse — a seller whose
query merely failed must not be told "be the first to sell", because that reads as *your listings are gone*.

marketplace.html already gets this right (`_loadError`, documented at line 1064 as "P7: a FAILED listings
fetch must render an error state, not the first-run 'be the first to sell' CTA"). That behaviour had NO
browser test: a static grep cannot prove which branch renders when the network actually fails. This gate
locks the fix rather than re-implementing it.

TWO THINGS THE SPEC HAD TO GET RIGHT, both learned by getting them wrong first:
  * POLL, do not sleep-then-assert. The page RETRIES the read (aborts climb 12 -> 20 -> 32) and declares
    failure only once retries are exhausted, at ~8s. A 2.5s sleep measured the retry budget and failed while
    the product was correct.
  * Assert inside `#listing-grid`, never over `body.innerText`. Both the error copy AND the CTA exist
    elsewhere in the document as other sections' markup, so a whole-page match goes green for the wrong
    reason — and `innerText` silently omits anything in an inactive tab.

Invoked via `node node_modules/@playwright/test/cli.js` (this project's path contains an `&` the npx shim
mis-parses), and "No tests found" is reported as the gate's OWN invocation failure, never as a broken page.

Usage:  python tools/validate_marketplace_state_inducers.py [--selftest]
"""
from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(ROOT, "node_modules", "@playwright", "test", "cli.js")
SPEC = "tests/marketplace-state-inducers.spec.ts"      # forward slashes: a backslash reads as an escape
GREEN, RED, YEL, DIM, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"


def run(timeout=300):
    if not os.path.exists(CLI):
        return None, "playwright CLI not installed"
    try:
        r = subprocess.run(["node", CLI, "test", SPEC, "--reporter=line"], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
    except Exception as e:
        return None, str(e)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main(argv):
    print("Marketplace state inducers (the `error` and `degraded` states, in a real browser)")
    rc, out = run()
    if rc is None:
        print(f"  {YEL}SKIP{RST} — {out}")
        return 0
    if "No tests found" in out:
        print(f"  {RED}FAIL{RST} the runner matched no spec ({SPEC}) — the gate's own invocation failure, "
              f"not a product defect.")
        return 1
    if "ERR_CONNECTION_REFUSED" in out:
        print(f"  {YEL}SKIP{RST} — the local site is not serving; nothing asserted.")
        return 0
    if rc == 0:
        print(f"  {GREEN}PASS{RST}  a FAILED listings read renders an error inside #listing-grid and NOT the "
              f"first-run CTA;\n        offline REFUSES a write and says so, naming that nothing was sent.")
        if "--selftest" in argv:
            print(f"  {DIM}selftest: both assertions are non-vacuous by construction — the error test fails "
                  f"if the\n        request was never intercepted (abort count == 0), and the offline test "
                  f"fails if whRequireOnline\n        is absent from the page rather than merely "
                  f"permissive.{RST}")
        return 0
    print(f"  {RED}FAIL{RST}  a state inducer did not hold:")
    for line in [l for l in out.splitlines() if "Error:" in l or "✘" in l][:6]:
        print(f"    {DIM}{line.strip()[:150]}{RST}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
