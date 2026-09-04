#!/usr/bin/env python3
"""queue-drain gate - T14's other half (2026-08-26).

Runs tools/prove_queue_drain.mjs: offline the write is HELD with ZERO server
writes, on reconnect it DRAINS, exactly ONCE, and the queue store empties.
The offline-queued family proved the holding half; its own header deferred this
one because a drain probe writes real rows - so this one writes a MARKED row
and deletes it, and ABORTs rather than measuring on dirty state.

Discipline (carried from validate_offline_queued.py):
  - retry-once before failing (full-suite live gates flake under load).
  - node invoked DIRECTLY, never npx (the repo path contains an ampersand).
  - utf-8 pinned on the subprocess decode; PASS matched line-anchored.
  - SKIPs cleanly when node / the local stack is absent — a gate that cannot
    run must say SKIP, not PASS.
  - the prover ABORTS (exit 2) on dirty pre-state rather than deleting rows it
    did not create; that surfaces here as FAIL with the abort line.

Re-drive: node tools/prove_queue_drain.mjs
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
        [node, str(ROOT / "tools" / "prove_queue_drain.mjs")],
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
        print("SKIP queue-drain — node not on PATH (live browser gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP queue-drain — local stack down (Flask :5000 / Supabase :54321)")
        return 0

    try:
        ok, tail = _run(node)
        if not ok:
            ok, tail = _run(node)
    except subprocess.TimeoutExpired:
        print("FAIL queue-drain — timed out at 240s")
        return 1

    print(f"  {'PASS' if ok else 'FAIL'}  {tail[:220]}")
    if not ok:
        print("FAIL queue-drain — the queue did not hold, did not drain, drained twice, or did not clean up.")
        return 1
    print("PASS queue-drain — held offline, drained once on reconnect, queue emptied, probe row cleaned.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
