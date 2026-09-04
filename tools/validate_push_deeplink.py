#!/usr/bin/env python3
"""push-deeplink gate — T105: a push keeps its DESTINATION (2026-08-26).

Runs tools/prove_push_deeplink.mjs, which loads the SHIPPING sw.js, installs the
notificationclick listener it registers, and dispatches a synthetic click against
a fake clients registry. Three cases:

  no tab open        -> openWindow at the FULL target (query intact)
  tab on wrong query -> the tab is NAVIGATED there  <- the defect this locks
  tab already there  -> focus only, no reload under a user mid-task

THE DEFECT. The handler matched an open tab on `c.url.includes(target.split('?')[0])`
— the path, query discarded — and returned focus. Every url notify-push sends puts
its destination in the query (?tab=services, ?asset=, ?post=), so a provider with
marketplace-seller already open on a different tab tapped a job-offer push and got
their existing view focused, with nothing to say a destination had been promised.
Resurrection: RED on the pre-fix worker for the wrong-query case ONLY — cases 1 and
3 pass in both worlds, which is how a specific oracle should behave.

NOT REDUNDANT WITH push-handler-contract (the §12 proof, in that gate's own
words). It holds seven invariants and its passing summary reads "the tap lands
SOMEWHERE" — its invariant 6 asks only that the handler focus a tab or open one.
The broken code focused a tab, so all seven invariants passed green while the
destination was being dropped. That gate asks whether something happens; this one
asks whether the RIGHT thing happens. An oracle that does not match the claim is
the failure mode both of them exist to avoid.

No browser, no stack, no network: this reads a file and runs a function, so it is a
fast static-tier gate. It needs node only because sw.js is JavaScript.

Re-drive: node tools/prove_push_deeplink.mjs
"""
import io
import re
import shutil
import subprocess
import sys
from pathlib import Path

# the prover's output carries an em-dash; a cp1252 stdout would raise mid-print and lose the
# verdict AFTER the work was done (the encoding lesson that once ate a whole file rewrite).
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("SKIP push-deeplink — node not on PATH (sw.js is JavaScript)")
        return 0
    try:
        r = subprocess.run(
            [node, str(ROOT / "tools" / "prove_push_deeplink.mjs")],
            cwd=str(ROOT), capture_output=True, text=True, timeout=90,
            encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        print("FAIL push-deeplink — timed out at 90s")
        return 1
    out = (r.stdout or "") + (r.stderr or "")
    for line in out.strip().splitlines():
        print("  " + line.strip()[:200])
    if not re.search(r"^\s*PASS", out, re.M):
        print("FAIL push-deeplink — notificationclick does not honour the push's destination.")
        print("    Fix in sw.js: focus the matching tab AND navigate it when the query differs,")
        print("    and bump CACHE_NAME so installed PWAs do not keep the old worker.")
        return 1
    print("PASS push-deeplink — a push lands on what it promised: opened, navigated, or already there.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
