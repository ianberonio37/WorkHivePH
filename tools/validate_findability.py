#!/usr/bin/env python3
"""Findability benchmark gate — T173's lock (2026-08-25).

Wraps tools/findability_benchmark.mjs: 20 common tasks phrased as USER QUESTIONS,
each answered from a cold page via the global hub in <= 2 interactions, asked AS
the persona who owns the question (worker default; supervisor-lane questions
declare role:'supervisor' — the hub's role scoping is design, not a defect).

Its FIRST runs caught four real wayfinding defects (Hive Board supervisor-gated
against its own worker-daily declaration; Voice Journal and Reports hidden from
the personas who own them; Eng. Design excluding supervisors, who ARE the
engineer persona in practice). This gate keeps the 20/20 from regressing.

Skips cleanly when node or the local stack is absent. Re-drive:
node tools/findability_benchmark.mjs
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


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("SKIP findability-benchmark - node not on PATH (live browser gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP findability-benchmark - local stack down (Flask :5000 / Supabase :54321)")
        return 0
    # utf-8 pinned: Windows' cp1252 subprocess decode mangles the prover's punctuation
    # (the offline-queued gate's recorded first bug).
    r = subprocess.run(
        [node, str(ROOT / "tools" / "findability_benchmark.mjs")],
        cwd=str(ROOT), capture_output=True, text=True, timeout=900,
        encoding="utf-8", errors="replace",
    )
    out = (r.stdout or "") + (r.stderr or "")
    m = re.search(r"findability: (\d+)/(\d+)", out)
    for line in out.splitlines():
        if line.startswith("FAIL"):
            print(f"  {line[:160]}")
    if not m:
        print("FAIL findability-benchmark - no score line in output (runner crashed?)")
        return 1
    got, total = int(m.group(1)), int(m.group(2))
    if got != total:
        print(f"FAIL findability-benchmark - {got}/{total} questions answered in <=2 interactions")
        return 1
    print(f"PASS findability-benchmark - {got}/{total} questions answered in <=2 interactions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
