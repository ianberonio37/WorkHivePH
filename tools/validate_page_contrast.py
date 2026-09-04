#!/usr/bin/env python3
"""page-contrast — T116: the zero that IS certified, and the one page where it is not (2026-08-26).

tools/prove_page_contrast.mjs is a mature two-oracle instrument — it drives axe
for WCAG 2.x and live-state-runner's APCA maths for this platform's dark surfaces
— and it had NO GATE. A contrast instrument nobody runs on the board is a
contrast regression nobody sees.

★READING THE INCOMPLETE SET, WHICH IS WHY THIS GATE EXISTS. axe reports 0
violations across 26 pages, and on its own that is a FALSE 100: it also reports
1,513 INCOMPLETE — "element's background color could not be determined" — because
axe cannot see behind composited alpha or a gradient, which is most of this
platform. A zero over an abstention that large means nothing by itself.

WHAT MAKES IT REAL is the second oracle. APCA measured 3,000+ text nodes with
0 failing, 0 inconclusive and NO truncation, and on 23 of 24 pages its denominator
is LARGER than axe's abstention set — so the nodes axe declined to judge have a
verdict from an instrument built to composite alpha, average gradient stops and
resolve background-clip:text glyphs. That is corroboration, not a second guess.

★THE ONE EXCEPTION IS NAMED RATHER THAN ROUNDED AWAY: on assistant, axe left 18
incomplete while APCA measured 15. The two counts are in DIFFERENT UNITS (axe
counts elements, APCA counts text nodes), so this is not proof of three unjudged
nodes — it is the one page where the covering argument is not clearly safe, and
it is recorded as a residual instead of being folded into the green.

ASSERTED: axe violations 0, APCA failing 0, APCA inconclusive 0, no truncation
(a cap must never hide under "0 failing"), and the report must not be a --teeth
run, which plants deliberately failing nodes into the same file.

Re-drive: node tools/prove_page_contrast.mjs
"""
import io
import json
import shutil
import socket
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "page_contrast_report.json"


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("SKIP page-contrast — node not on PATH (live gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP page-contrast — local stack down (Flask :5000 / Supabase :54321)")
        return 0

    try:
        subprocess.run([node, str(ROOT / "tools" / "prove_page_contrast.mjs")],
                       cwd=str(ROOT), capture_output=True, text=True, timeout=1500,
                       encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        print("FAIL page-contrast — timed out at 1500s")
        return 1

    if not REPORT.exists():
        print("FAIL page-contrast — the prover wrote no report")
        return 1
    d = json.loads(REPORT.read_text(encoding="utf-8"))

    # a --teeth run PLANTS failing nodes into this same file; grading it would be grading the probe
    if d.get("teethRun"):
        print("FAIL page-contrast — this report is a --teeth run, which plants deliberately failing "
              "nodes. Re-run without --teeth before grading.")
        return 1

    res = d.get("results") or []
    if isinstance(res, dict):
        res = list(res.values())
    if not res:
        print("FAIL page-contrast — NOTHING WAS MEASURED. Zero failures over an empty denominator is "
              "not a pass.")
        return 1

    fails, notes = [], []
    tot_inc = tot_meas = 0
    for r in res:
        page = r.get("page", "?")
        w, a = r.get("wcag") or {}, r.get("apca") or {}
        v = len(w.get("violations") or [])
        inc = len(w.get("incomplete") or [])
        meas = a.get("measured") or 0
        tot_inc += inc
        tot_meas += meas
        if v:
            fails.append(f"{page}: {v} axe contrast violation(s)")
        if a.get("failing"):
            fails.append(f"{page}: {a['failing']} APCA failure(s)")
        if a.get("inconclusive"):
            fails.append(f"{page}: {a['inconclusive']} APCA inconclusive — neither oracle has a verdict")
        if a.get("truncated"):
            fails.append(f"{page}: APCA measurement TRUNCATED — a cap must never hide under '0 failing'")
        if inc and meas < inc:
            notes.append(f"{page}: axe left {inc} incomplete, APCA measured {meas} — different units, "
                         f"but the one place the covering argument is not clearly safe")

    print(f"  pages {len(res)} | axe violations 0 required | axe incomplete {tot_inc} "
          f"| APCA measured {tot_meas}, failing 0 required")
    for n in notes:
        print(f"    residual: {n}")
    if fails:
        print("FAIL page-contrast:")
        for x in fails[:8]:
            print("    - " + x)
        return 1
    print(f"PASS page-contrast — 0 violations and 0 APCA failures over {tot_meas} measured text nodes; "
          f"axe's {tot_inc} abstentions are covered by the oracle built to see behind them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
