#!/usr/bin/env python3
"""stock-ripple gate - T11's cross-page write-propagation oracle (2026-08-26).

Runs tools/prove_stock_ripple.mjs: stage a part at min_qty+1, read index's
low-stock tile (pre), issue 1 through inventory's OWN Use modal (the atomic
inventory_deduct RPC), reload index - the tile must read pre+1. Write-side
sibling of cross_surface_agreement (which locks READ-parity only).

Hygiene: the part's qty is snapshotted + restored, probe transactions
(WH-T11-PROBE) deleted with NO time window (marker rows are artifacts by
definition - a window once spared an older orphan), both verified; ABORTs
on no stageable part.

Discipline (carried from validate_offline_queued.py):
  - retry-once before failing (full-suite live gates flake under load).
  - node invoked DIRECTLY, never npx (the repo path contains an ampersand).
  - utf-8 pinned on the subprocess decode; PASS matched line-anchored.
  - SKIPs cleanly when node / the local stack is absent — a gate that cannot
    run must say SKIP, not PASS.
  - the prover ABORTS (exit 2) on dirty pre-state rather than deleting rows it
    did not create; that surfaces here as FAIL with the abort line.

Re-drive: node tools/prove_stock_ripple.mjs
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
        [node, str(ROOT / "tools" / "prove_stock_ripple.mjs")],
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
        print("SKIP stock-ripple — node not on PATH (live browser gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP stock-ripple — local stack down (Flask :5000 / Supabase :54321)")
        return 0

    try:
        ok, tail = _run(node)
        if not ok:
            ok, tail = _run(node)
    except subprocess.TimeoutExpired:
        print("FAIL stock-ripple — timed out at 240s")
        return 1

    print(f"  {'PASS' if ok else 'FAIL'}  {tail[:220]}")
    if not ok:
        print("FAIL stock-ripple — the write did not propagate to the ops-home tile (or cleanup failed).")
        return 1
    print("PASS stock-ripple — a stock write on inventory is visible on the ops-home tile within one reload.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
