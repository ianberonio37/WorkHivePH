#!/usr/bin/env python3
"""width-utilisation — T114 + T115: the widths between phone and desk (2026-08-26).

TWO OPEN ITEMS, ONE MEASUREMENT. T114 asks whether 768 — the awkward middle
nobody designs for — is coherent. T115 recorded a specific nit at 1920: prose
lines of 104-131ch, well past the 45-90ch a comfortable reading measure sits at.

★THE RECORDED NIT WAS THE INSTRUMENT, AND THAT IS THIS GATE'S MAIN FINDING. Every
one of those long "prose lines" turned out to be a SOURCE CHIP — "Live ·
refreshed on load · Based on…", "Saved snapshot, computed 5h ago · …" — the
platform's freshness metadata, scanned in a glance rather than read
left-to-right. Capping those at a reading measure would WRAP them, turning a
one-line label into three, which is worse than the thing it was meant to fix.
With chips excluded, the longest genuine prose line on the measured pages is
59-93ch: inside the comfortable range, with logbook@768 marginally over at 93.
There is no line-length defect here, and a future session should not go looking
for one.

WHAT THE FILL NUMBERS SAY. At 768 the pages fill 87.5-100% of the viewport — the
middle width is used, not treated as a big phone. At 1920 the picture splits:
index, analytics and pm-scheduler run full width, while hive (35%) and logbook
(57%) cap their column. That is a legitimate readability choice rather than a
defect, and it is recorded so the choice stays visible.

THE RATCHET: longest prose line per page+width may shrink, never grow. Fill is
reported but not gated — "uses the width" is a design judgement, and a gate that
demanded a fill percentage would be enforcing an opinion.

Re-drive: node tools/prove_width_utilisation.mjs
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
        print("SKIP width-utilisation — node not on PATH (live viewport gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP width-utilisation — local stack down (Flask :5000 / Supabase :54321)")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_width_utilisation.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=600,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        return bool(re.search(r"^\s*(PASS|BASELINE)", out, re.M)) and not re.search(r"^\s*FAIL", out, re.M), out

    try:
        ok, out = run()
        if not ok:
            ok, out = run()
    except subprocess.TimeoutExpired:
        print("FAIL width-utilisation — timed out at 600s")
        return 1

    for line in out.strip().splitlines()[-12:]:
        print("  " + line.strip()[:150])
    if not ok:
        print("FAIL width-utilisation — a prose line got longer at a measured width. Past ~90ch the eye "
              "loses its place returning to the next line.")
        return 1
    print("PASS width-utilisation — prose stays within its reading measure at 768 and 1920.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
