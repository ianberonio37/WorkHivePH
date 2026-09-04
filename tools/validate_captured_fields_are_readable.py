#!/usr/bin/env python3
"""captured-fields-are-readable - T15: the read path shows what the form captured (2026-08-27).

Runs tools/prove_captured_fields_are_readable.mjs.

Generalising T15's LOTO finding asked the whole question rather than the one instance: of the 15
columns logbook writes, WHICH does a reader never see? Four sat in the identical shape - selected,
mapped, restored into the EDIT FORM, rendered nowhere. Two of them are T15's own scenario:

    readings_json        1767 of 3811 rows   what the last person measured
    failure_consequence  1075 of 3811 rows   incl. "Safety risk"

*THE FIRST FIX WAS HALF A FIX, WHICH IS WHY THIS GATE CHECKS BOTH SURFACES. The LOTO badge landed
on the entry CARD only, so the safety flag vanished on drill-down - the detail modal being exactly
where someone reads carefully before opening a machine. The cause was structural and worth naming:
lotoBadge was declared `const` INSIDE renderEntries, so the modal could not have called it. The fix
promotes it to a shared helper; the gate asserts both surfaces so "it renders somewhere" can never
again read as covered.

THE ORACLE is the database per surface: the card list's badge COUNT must equal the rows on the
visible page carrying a consequence, and a modal opened on an entry the DB says has readings must
show them WITH UNITS. Counts, not presence - a badge rendering for the wrong rows is its own defect,
and the first LOTO run read 0-and-was-correct, proving a presence check can pass while blind.

Read-only. Re-drive: node tools/prove_captured_fields_are_readable.mjs
"""
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

# The prover prints a degree sign in its unit assertions and this repo runs on a cp1252 console;
# an unpinned stdout raises UnicodeEncodeError and the CRASH reads as a gate FAILURE rather than an
# encoding problem. Pin utf-8 the way the sibling live gates do.
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _run(node: str):
    r = subprocess.run([node, str(ROOT / "tools" / "prove_captured_fields_are_readable.mjs")],
                       cwd=str(ROOT), capture_output=True, text=True, timeout=240,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    return bool(re.search(r"^PASS", out, re.M)), " | ".join(
        l.strip() for l in (out.strip().splitlines()[-3:] or ["<no output>"]))


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("SKIP captured-fields-are-readable - node not on PATH (live browser gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP captured-fields-are-readable - local stack down")
        return 0
    try:
        ok, tail = _run(node)
        if not ok:
            ok, tail = _run(node)
    except subprocess.TimeoutExpired:
        print("FAIL captured-fields-are-readable - timed out at 240s")
        return 1
    print(f"  {'PASS' if ok else 'FAIL'}  {tail[:220]}")
    if not ok:
        print("FAIL captured-fields-are-readable - a column the form captures is invisible to a "
              "reader on the card, in the detail modal, or renders without its unit.")
        return 1
    print("PASS captured-fields-are-readable - readings and failure consequence reach the reader.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
