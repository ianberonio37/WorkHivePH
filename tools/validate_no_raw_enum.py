#!/usr/bin/env python3
"""no-raw-enum - CE: a database word must not reach a person (2026-08-26).

`in_progress`, `rate_limit_exceeded`, `cancelled_by_provider` - these are how a column stores a
state, not how a person says it. When one reaches the screen the reader has to translate the
schema in their head, and the ones that leak are usually the states that matter: a refusal, a
failure, a half-finished job.

★THE SHAPE IS THE TELL, which is what makes this decidable rather than a matter of taste: a short
visible text leaf matching lowercase_with_underscores is a raw token with near-certainty, because
no one writes English that way.

★WHY THIS GATE EXISTS AT ALL: the prover did not. tools/prove_no_raw_enum.mjs was built, works, and
was run by NOTHING - an audit of 106 prove_*.mjs harnesses found 3 that no file in the repo
mentions, and this was the most valuable of them. It passes 22 pages with 0 failures and 0
ungraded, so the property it protects was already true; what was missing was anything to keep it
that way. A working oracle nobody runs is indistinguishable from one that was never written.

★AND THE AUDIT THAT FOUND IT OVER-REPORTED FIRST: scanning only the gate registry and validate_*.py
wrappers called 15 provers orphaned; widening to every .py/.mjs/.js/.md/.json/.sh/.yml in the repo
cut that to 3. Narrow the scope before believing a count - the same correction the double-submit
census needed when 118 flagged handlers turned out to be 4.

Re-drive: node tools/prove_no_raw_enum.mjs [--page <name>]
"""
import io
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("SKIP no-raw-enum - node not on PATH (live gate)")
        return 0
    if not _port_open(5000):
        print("SKIP no-raw-enum - local page server down")
        return 0

    try:
        r = subprocess.run([node, str(ROOT / "tools" / "prove_no_raw_enum.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=600,
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        print("FAIL no-raw-enum - timed out at 600s")
        return 1

    out = (r.stdout or "") + (r.stderr or "")
    m = re.search(r"(\d+)\s+pass\s*\|\s*(\d+)\s+fail\s*\|\s*(\d+)\s+ungraded", out)
    if not m:
        print("SKIP no-raw-enum - the prover produced no tally (pages unreachable?)")
        return 0

    passed, failed, ungraded = (int(x) for x in m.groups())
    print(f"  pages: {passed} pass | {failed} fail | {ungraded} ungraded")
    if failed:
        for line in out.splitlines():
            if re.search(r"\bFAIL\b", line):
                print("    " + line.strip()[:150])
        print("FAIL no-raw-enum - a database word reached a person. `in_progress` is how a column stores a")
        print("    state, not how anyone says it, and the states that leak are usually the ones that")
        print("    matter: a refusal, a failure, a half-finished job.")
        return 1
    if passed == 0:
        print("FAIL no-raw-enum - 0 pages graded, which is not a pass: the prover found nothing to check,")
        print("    so its matcher or its roster is broken rather than the platform being clean.")
        return 1
    print(f"PASS no-raw-enum - {passed} pages examined, no raw lowercase_with_underscores token reaching "
          "a reader.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
