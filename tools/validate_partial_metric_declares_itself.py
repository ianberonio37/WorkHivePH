#!/usr/bin/env python3
"""partial-metric-declared - T47: a partial OEE must say so (2026-08-26).

OEE is a product of three factors - Availability x Performance x Quality. Computing two
and calling the result "OEE" is not a rounding difference: it is a DIFFERENT AND HIGHER
number, because the missing factor can only reduce it. A plant reporting 88% to
management when the three-factor figure would be lower has not made a small error, it
has made a claim it cannot defend the moment somebody asks how it was computed - and
"somebody asks how it was computed" is exactly the reader T47 is about.

THE PLATFORM GETS THIS RIGHT, and this gate keeps it right. analytics renders:

    OEE (AVG, PARTIAL) 88% · Avg across 20 assets · WORLD CLASS · ISO 22400-2:2014 ·
    Availability x Quality only. Add each asset's cycle time to include Performance.

Value, denominator, standard, WHICH FACTORS ARE IN IT, and what to do about the missing
one. A skeptic can hand-check the arithmetic and knows precisely what they are checking.

THE ASSERTION: wherever a headline OEE figure is rendered, the same card names its factor
basis - a partial marker plus the factors included, or a full three-factor statement.
What it may never be is a bare "OEE 88%".

★IT DOES NOT ASSERT THE VALUE, NOR DEMAND FULL OEE. Whether this hive has cycle times is
a data question, not a defect, and the honest response to missing data is to say what is
missing - which is what the card does. The failure gated here is SILENCE about the basis,
not the partiality itself.

Re-drive: node tools/prove_partial_metric_declares_itself.mjs
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
        print("SKIP partial-metric-declared - node not on PATH (live gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP partial-metric-declared - local stack down")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_partial_metric_declares_itself.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=420,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        return bool(re.search(r"^\s*PASS", out, re.M)), out

    try:
        ok, out = run()
        if not ok:
            ok, out = run()
    except subprocess.TimeoutExpired:
        print("FAIL partial-metric-declared - timed out at 420s")
        return 1

    for line in out.strip().splitlines()[-3:]:
        print("  " + line.strip()[:170])
    if not ok:
        print("FAIL partial-metric-declared - a headline OEE does not name its factor basis, so it reads")
        print("    as the full three-factor product. Availability x Quality is HIGHER than Availability")
        print("    x Performance x Quality, so the omission always flatters - say which factors are in.")
        return 1
    print("PASS partial-metric-declared - the OEE headline names its factor basis, so nobody can mistake "
          "a two-factor figure for the full product.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
