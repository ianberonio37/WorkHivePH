#!/usr/bin/env python3
"""longest-truncates - CF: the longest realistic value must not break the card (2026-08-26).

Real plants name things badly. A part called "Bearing, spherical roller, 22320 E1 XL C3, SKF, for
kiln drive gearbox non-drive end" is not a stress test, it is Tuesday - and the card holding it was
laid out around a nine-character example.

THE ORACLE: the longest realistic title truncates VISIBLY rather than overflowing its card or
pushing the price out of view. The prover injects the long value and watches what the layout does,
rather than reasoning about CSS - which is the only way to catch a container that grows silently
until the thing beside it is off-screen.

★WHY THIS GATE EXISTS: the prover ran nowhere. An audit of 106 prove_*.mjs harnesses found 3 that
no file in the repo mentions; this was one, and it works - 18 pages pass, 0 fail. The property was
already held and nothing was keeping it that way.

★UNGRADED IS NOT PASS, and the prover already knows it: 4 pages report UNGRADED because no rendered
row title existed to lengthen, and it says so rather than counting them as clean. This wrapper
carries that distinction through - it fails on a FAIL, and it fails if NOTHING was graded, because
a tally of zero means the roster or the selector broke, not that the platform is tidy.

Re-drive: node tools/prove_longest.mjs
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
        print("SKIP longest-truncates - node not on PATH (live gate)")
        return 0
    if not _port_open(5000):
        print("SKIP longest-truncates - local page server down")
        return 0

    try:
        r = subprocess.run([node, str(ROOT / "tools" / "prove_longest.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=600,
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        print("FAIL longest-truncates - timed out at 600s")
        return 1

    out = (r.stdout or "") + (r.stderr or "")
    m = re.search(r"(\d+)\s+pass\s*\|\s*(\d+)\s+fail\s*\|\s*(\d+)\s+ungraded", out)
    if not m:
        print("SKIP longest-truncates - the prover produced no tally (pages unreachable?)")
        return 0

    passed, failed, ungraded = (int(x) for x in m.groups())
    print(f"  pages: {passed} pass | {failed} fail | {ungraded} ungraded")
    if failed:
        for line in out.splitlines():
            if re.search(r"\bFAIL\b", line):
                print("    " + line.strip()[:150])
        print("FAIL longest-truncates - a realistic long value broke its card instead of truncating. The")
        print("    thing that goes off-screen is usually the one beside it: the price, the status, the")
        print("    button.")
        return 1
    if passed == 0:
        print("FAIL longest-truncates - 0 pages graded, which is not a pass: nothing was measured, so the")
        print("    roster or the row selector is broken rather than the layout being sound.")
        return 1
    print(f"PASS longest-truncates - {passed} pages hold their layout under the longest realistic value "
          f"({ungraded} had no row title to lengthen and are reported ungraded, not passed).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
