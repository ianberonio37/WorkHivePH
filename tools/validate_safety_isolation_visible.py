#!/usr/bin/env python3
"""safety-isolation-visible - T15: the read path shows LOCK-OUT (2026-08-27).

Runs tools/prove_safety_isolation_visible.mjs. The point of searching fault history before opening a
machine is to learn how it was worked on last time, and "the last person locked this out / worked
under a permit" is the most consequential thing on the card. logbook CAPTURED loto_applied and
permit_reference on the form, STORED them on the row, and RESTORED them when an entry was edited -
and never showed them to anyone READING. 419 of 3,811 entries carry that data.

THE ORACLE compares the rendered badge COUNT against what the database says should be visible for
the same worker's most recent page. Not "a badge exists somewhere": a badge that renders for the
wrong rows is its own defect.

★THE SUBJECT MUST HAVE LOTO ON ITS VISIBLE PAGE. The first run used an account whose recent 20
entries contained none, read 0 badges, and 0 was CORRECT - a pass that proved nothing. The gate now
fails rather than passes when the chosen account has nothing to show.

Read-only. Re-drive: node tools/prove_safety_isolation_visible.mjs
"""
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

# The sample line carries a lock emoji, and this repo runs on a cp1252 console: printing it
# raised UnicodeEncodeError and the CRASH would have read as a gate FAILURE rather than an
# encoding problem. Pin utf-8 the way the other live gates here do.
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _run(node: str):
    r = subprocess.run([node, str(ROOT / "tools" / "prove_safety_isolation_visible.mjs")],
                       cwd=str(ROOT), capture_output=True, text=True, timeout=240,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    return bool(re.search(r"^PASS", out, re.M)), " | ".join(
        l.strip() for l in (out.strip().splitlines()[-3:] or ["<no output>"]))


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("SKIP safety-isolation-visible - node not on PATH (live browser gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP safety-isolation-visible - local stack down")
        return 0
    try:
        ok, tail = _run(node)
        if not ok:
            ok, tail = _run(node)
    except subprocess.TimeoutExpired:
        print("FAIL safety-isolation-visible - timed out at 240s")
        return 1
    print(f"  {'PASS' if ok else 'FAIL'}  {tail[:220]}")
    if not ok:
        print("FAIL safety-isolation-visible - lock-out / permit is not on the card, or the badge "
              "count does not match the database.")
        return 1
    print("PASS safety-isolation-visible - a reader sees that the machine was locked out.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
