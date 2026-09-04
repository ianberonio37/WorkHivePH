#!/usr/bin/env python3
"""tile-count-agreement gate - T19's tile->list handoff oracle (2026-08-26).

Runs tools/prove_tile_count_agreement.mjs: the number a person taps must be
the number they land on. pm-overdue: tile N -> ?filter=overdue chip active +
the page's own "N of M assets past due" agrees. open-jobs: tile N (a HIVE
count) -> ?view=team&status=Open -> N team rows (cap-guarded). At birth it
caught tile=9 landing on the mine-pill's 2 - the two-windows-one-metric
class as a tap; fixed by carrying the window in the href. The low-stock
tile's multi-band handoff is a RECORDED follow-up, not a silent skip.

Discipline (carried from validate_offline_queued.py):
  - retry-once before failing (full-suite live gates flake under load).
  - node invoked DIRECTLY, never npx (the repo path contains an ampersand).
  - utf-8 pinned on the subprocess decode; PASS matched line-anchored.
  - SKIPs cleanly when node / the local stack is absent — a gate that cannot
    run must say SKIP, not PASS.
  - the prover ABORTS (exit 2) on dirty pre-state rather than deleting rows it
    did not create; that surfaces here as FAIL with the abort line.

Re-drive: node tools/prove_tile_count_agreement.mjs
"""
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _run(node: str) -> tuple[bool, str]:
    r = subprocess.run(
        [node, str(ROOT / "tools" / "prove_tile_count_agreement.mjs")],
        cwd=str(ROOT), capture_output=True, text=True, timeout=240,
        encoding="utf-8", errors="replace",
    )
    out = (r.stdout or "") + (r.stderr or "")
    passed = bool(re.search(r"^\s*PASS", out, re.M))
    tail = out.strip().splitlines()[-3:] if out.strip() else ["<no output>"]
    return passed, " | ".join(line.strip() for line in tail)


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("SKIP tile-count-agreement — node not on PATH (live browser gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP tile-count-agreement — local stack down (Flask :5000 / Supabase :54321)")
        return 0

    try:
        ok, tail = _run(node)
        if not ok:
            ok, tail = _run(node)
    except subprocess.TimeoutExpired:
        print("FAIL tile-count-agreement — timed out at 240s")
        return 1

    print(f"  {'PASS' if ok else 'FAIL'}  {tail[:220]}")
    if not ok:
        print("FAIL tile-count-agreement — a tile number does not match its landing view.")
        return 1
    print("PASS tile-count-agreement — every covered tile lands on the number it names.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
