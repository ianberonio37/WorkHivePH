#!/usr/bin/env python3
"""bank_depth_snapshot.py — run the FULL bank classify (no time budget) and write a
sha-anchored snapshot the momentum stop guard can VERIFY instantly.

The ★×17 envelope hole, board-time edition (2026-09-03): the guard's fail-closed classify
has a 20s budget, and under a running full board the ~5,300-row classify + docker subprocesses
never finish — so every (d) sentinel during a board run is refused as 'could not be VERIFIED',
even when the depth was measured moments earlier. The fix keeps fail-closed semantics without
loosening the bind: THIS tool does the same measurement the guard would (same classify, same
_is_browser_gated), and stamps the result with the sha256 of live_mcp_registry.json. The guard
accepts the snapshot ONLY while the registry's sha still matches — any restamp, settle, or edit
changes the file and the snapshot self-invalidates back to fail-closed. Memoization with a
tamper-evident anchor, not a second source of truth.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join(ROOT, "live_mcp_registry.json")
SNAPSHOT = os.path.join(ROOT, ".tmp", "bank_depth_snapshot.json")


def registry_sha() -> str:
    h = hashlib.sha256()
    with open(REGISTRY, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    spec = importlib.util.spec_from_file_location(
        "_vlmb_snap", os.path.join(ROOT, "tools", "validate_live_mcp_bank.py"))
    V = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(V)
    import momentum_stop_guard as G

    sha_before = registry_sha()
    with open(REGISTRY, encoding="utf-8") as f:
        reg = json.load(f)
    rows = reg["scenarios"] if isinstance(reg, dict) and "scenarios" in reg else reg
    gates, urls = V.gate_ids(), V.surface_urls(reg)
    owed = stale = non_browser = 0
    for r in rows:
        st, _why = V.classify(r, gates, urls)
        if st not in ("owed", "stale"):
            continue
        if st == "owed":
            owed += 1
        else:
            stale += 1
        if not G._is_browser_gated(r):
            non_browser += 1
    # the anchor is the registry AS CLASSIFIED — if it changed mid-run, refuse to stamp
    if registry_sha() != sha_before:
        print("REFUSED: live_mcp_registry.json changed during the classify — re-run.")
        return 1
    snap = {"registry_sha": sha_before, "owed": owed, "stale": stale,
            "total": owed + stale, "non_browser": non_browser,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
    os.makedirs(os.path.dirname(SNAPSHOT), exist_ok=True)
    tmp = SNAPSHOT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(snap, f)
    os.replace(tmp, SNAPSHOT)
    print(f"snapshot written: owed={owed} stale={stale} non_browser={non_browser} "
          f"sha={sha_before[:12]}…")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
