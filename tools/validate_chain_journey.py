#!/usr/bin/env python3
"""chain-journey gate - T29's per-hop context harness, slice 1 (2026-08-26).

Runs tools/prove_chain_journey.mjs: a multi-page chain must CARRY its context
at every hop and Back must walk it in reverse. Slice 1: alert-hub's PM alert
names its asset -> following it opens THAT asset's pm-scheduler detail
(#det-name matches, no re-find) -> one Back returns to a rendered alert-hub.
ABORTs (exit 2) when no PM alert exists - never invents a subject.

Discipline (carried from validate_offline_queued.py):
  - retry-once before failing (full-suite live gates flake under load).
  - node invoked DIRECTLY, never npx (the repo path contains an ampersand).
  - utf-8 pinned on the subprocess decode; PASS matched line-anchored.
  - SKIPs cleanly when node / the local stack is absent — a gate that cannot
    run must say SKIP, not PASS.
  - the prover ABORTS (exit 2) on dirty pre-state rather than deleting rows it
    did not create; that surfaces here as FAIL with the abort line.

Re-drive: node tools/prove_chain_journey.mjs
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
        [node, str(ROOT / "tools" / "prove_chain_journey.mjs")],
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
        print("SKIP chain-journey — node not on PATH (live browser gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP chain-journey — local stack down (Flask :5000 / Supabase :54321)")
        return 0

    try:
        ok, tail = _run(node)
        if not ok:
            ok, tail = _run(node)
    except subprocess.TimeoutExpired:
        print("FAIL chain-journey — timed out at 240s")
        return 1

    print(f"  {'PASS' if ok else 'FAIL'}  {tail[:220]}")
    if not ok:
        print("FAIL chain-journey — a hop dropped its context (or Back broke the chain).")
        return 1
    print("PASS chain-journey — every covered hop carries its subject; Back walks the chain.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
