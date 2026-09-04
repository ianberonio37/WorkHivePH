#!/usr/bin/env python3
"""fixed-chrome-budget — T113: what the floor viewport has left for work (2026-08-26).

320x640 is the budget-Android floor this platform targets. At that size the
question is not whether things FIT but how much room REMAINS after the
platform's own furniture: a fixed nav, a hub FAB, an AI widget, a page-guide
chip. Each is individually reasonable, none was ever measured TOGETHER, and that
is exactly how a page ends up spending a third of its screen before one row of
content is drawn. Measured across the eight pages a field phone lives in:
mean 26.1% covered, worst 36.6% (pm-scheduler), and on seven of eight the single
largest contributor is the same 64px guide chip.

Forward-only per page: chrome may shrink, never grow.

★THREE INSTRUMENT CORRECTIONS BEFORE ANY NUMBER WAS BANKED — the reason to trust
this one. The first run said index.html was 87.5% covered and blamed
#cursor-glow, a 440px pointer-following gradient that is pointer-events:none,
z-index:0 and 5% alpha: decoration sitting BEHIND everything, costing a person
nothing. The second said logbook was 50.9% and blamed a 280px `div.card` — the
"Log a Repair" FORM, sticky top-6 and 843px tall on a 640px screen, which cannot
stick at all (sticky needs to be shorter than the viewport) and scrolls exactly
like the content it is. Banking either would have sent someone deleting furniture
that does not exist or a panel a worker needs. The rules that survived:
CHROME IS WHAT INTERCEPTS A THUMB OR GETS ANNOUNCED, and CHROME PERSISTS WHILE
CONTENT MOVES UNDER IT — a viewport-height sticky element does neither.

Coverage is a UNION of viewport rows, never a sum: a nav and a chip that overlap
cost one band, and summing would report a number nobody experiences.

Re-drive: node tools/prove_fixed_chrome_budget.mjs
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
        print("SKIP fixed-chrome-budget — node not on PATH (live viewport gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP fixed-chrome-budget — local stack down (Flask :5000 / Supabase :54321)")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_fixed_chrome_budget.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=420,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        return bool(re.search(r"^\s*(PASS|BASELINE)", out, re.M)) and "FAIL" not in out, out

    try:
        ok, out = run()
        if not ok:
            ok, out = run()          # live viewport gates flake under full-suite load
    except subprocess.TimeoutExpired:
        print("FAIL fixed-chrome-budget — timed out at 420s")
        return 1

    for line in out.strip().splitlines()[-12:]:
        print("  " + line.strip()[:150])
    if not ok:
        print("FAIL fixed-chrome-budget — the platform took MORE of the 320x640 viewport than its "
              "baseline. Every pixel of persistent chrome is a pixel of work a field phone cannot show.")
        return 1
    print("PASS fixed-chrome-budget — persistent chrome held within its per-page floor budget.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
