#!/usr/bin/env python3
"""numeric-paste — T123: an unparseable paste must not blank a box in silence (2026-08-26).

Runs tools/prove_numeric_paste.mjs with a REAL clipboard.

★THE CLAIM HERE IS NARROWER THAN THE ONE I FIRST WROTE, because the resurrection
refuted it. The first measurement set `el.value = "1,500"` directly and watched
the field empty with validity VALID, and I wrote that up as "pasting a thousands
separator silently empties the box". Running the finished prover against the
PRE-FIX utils.js then passed four of five cases: with a real clipboard Chromium's
paste pipeline already strips the comma, the spaces and the trailing unit.
ASSIGNING a value and PASTING one are different mechanisms, and only one is what
a person does.

MEASURED DEFECT (the one that survived): an unparseable paste — "abc" — blanks
the field and says NOTHING. In a quantity box a silent blank is easy to miss and
the consequence is submitting no quantity. It now announces.

HARDENING, LABELLED AS SUCH: the helper also normalizes separators, whitespace
and trailing units itself, so the behaviour is the platform's own rather than one
engine's undocumented paste filtering. Whether other engines empty the field
instead is UNMEASURED — only Chromium is installed here — and this gate does not
claim otherwise.

Re-drive: node tools/prove_numeric_paste.mjs
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
        print("SKIP numeric-paste — node not on PATH (live clipboard gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP numeric-paste — local stack down (Flask :5000 / Supabase :54321)")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_numeric_paste.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=300,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        return bool(re.search(r"^\s*PASS", out, re.M)), out

    try:
        ok, out = run()
        if not ok:
            ok, out = run()
    except subprocess.TimeoutExpired:
        print("FAIL numeric-paste — timed out at 300s")
        return 1

    for line in out.strip().splitlines()[-7:]:
        print("  " + line.strip()[:150])
    if not ok:
        print("FAIL numeric-paste — a paste changed a number box wrongly, or an unparseable paste "
              "blanked it without saying so.")
        return 1
    print("PASS numeric-paste — clean pastes land, dirty ones normalize, and an unparseable one is "
          "refused out loud instead of blanking the box in silence.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
