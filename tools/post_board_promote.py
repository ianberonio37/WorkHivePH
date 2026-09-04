#!/usr/bin/env python3
"""post_board_promote.py — replicate the executor-v3 post-board promotion: promote each LOCKING trajectory
to LOCKED iff every gate it names PASSED on the last FULL board (platform_health.json). Per-locking, never
board-green (a locking's own gates decide it, not an unrelated regression like clone-debt). Dry-run by
default; --apply writes.

WHY THIS EXISTS (not the inline executor): the executor that ran post-17176 (task b04qnl6b4) is an inline
prior-session command with no saved script. Its logic is deterministic and re-creatable from the same two
files, and the result is CONFIRMED by validate_locks_are_verified (the same validator the executor ran) — so
this is the move re-created, then checked, not a guess.

Gate-name forms a locking may cite (both handled):
  · a registered CHECK id, matching platform_health.validators[].id directly (e.g. 'hive-value-card');
  · a validate_*.py SCRIPT name, mapped to its id via the board's own {id: script} table (e.g.
    'validate_rls_tenant_isolation' -> the id whose script is tools/validate_rls_tenant_isolation.py).
A gate that resolves to neither, or whose board status is not PASS, KEEPS the trajectory at locking (never a
silent promote on an unverifiable gate — the 'a lock nothing runs' class).
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "trajectory_registry.json"
BOARD = ROOT / "run_platform_checks.py"
HEALTH = ROOT / "platform_health.json"


def _board_scripts() -> dict:
    s = io.open(BOARD, encoding="utf-8", errors="replace").read()
    return dict(re.findall(r'"id":\s*"([^"]+)"\s*,\s*"script":\s*"([^"]+)"', s, re.S))


def _status_map() -> dict:
    d = json.loads(io.open(HEALTH, encoding="utf-8").read())
    vs = d.get("validators") or []
    return {v.get("id"): (v.get("status") or "").upper() for v in vs if isinstance(v, dict)}, d.get("mode"), d.get("timestamp")


def _resolve(gate: str, status_by_id: dict, id_by_scriptbase: dict) -> str | None:
    base = gate.split("(")[0].strip()  # allow a parenthetical qualifier
    if base in status_by_id:
        return status_by_id[base]
    # a validate_* script name -> its id
    sb = base if base.endswith(".py") else base + ".py"
    sb = os.path.basename(sb)
    vid = id_by_scriptbase.get(sb)
    if vid:
        return status_by_id.get(vid)
    return None  # unresolvable


def main(apply: bool) -> int:
    if not HEALTH.exists():
        print("post-board-promote: platform_health.json absent — run a full board first."); return 1
    status_by_id, mode, ts = _status_map()
    if mode and mode != "full":
        print(f"post-board-promote: platform_health mode is '{mode}', NOT full — locks require a full board. Abort.")
        return 1
    scripts = _board_scripts()
    id_by_scriptbase = {os.path.basename(sc): i for i, sc in scripts.items()}
    reg = json.loads(io.open(REGISTRY, encoding="utf-8").read())
    lockable, kept = [], []
    for t in reg["trajectories"]:
        if t.get("status") != "locking":
            continue
        gates = (t.get("artifacts", {}) or {}).get("gates") or []
        if not gates:
            kept.append((t["id"], "no gates")); continue
        reasons = []
        ok = True
        for g in gates:
            st = _resolve(g, status_by_id, id_by_scriptbase)
            if st != "PASS":
                ok = False; reasons.append(f"{g.split('(')[0]}={st or 'not-on-board'}")
        if ok:
            lockable.append(t)
        else:
            kept.append((t["id"], "; ".join(reasons[:3])))
    print(f"board ts={ts} mode={mode}  |  lockable: {len(lockable)}   kept: {len(kept)}")
    for t in lockable[:60]:
        print(f"  LOCK  {t['id']}  {t['pct']}%->100")
    for tid, why in kept[:40]:
        print(f"  KEEP  {tid}  {why}")
    if apply and lockable:
        # ★2026-09-04 — VERIFY-AND-ROLLBACK. A prior --apply locked 221 while the board's
        # platform_health carried 60 FAIL, and validate_locks_are_verified then flagged 29 as
        # false-100%s (a locked row naming a gate that FAILED on that board). The gate resolution
        # here is correct (a fresh dry-run keeps exactly those 29), so the over-lock came from an
        # apply that read a STALE / mid-write platform_health — the board had only just finished.
        # The tool used to WRITE, run the audit, print 'ERR', and leave the false-100%s on disk.
        # Now it captures the prior state, and if the post-apply audit finds false-100%s it REVERTS
        # exactly those rows to locking (never shipping an unverified 100%). The audit is the teeth.
        prior = {t["id"]: (t.get("status"), t.get("pct")) for t in lockable}
        for t in lockable:
            t["status"] = "locked"; t["pct"] = 100
        def _write():
            fd, tmp = tempfile.mkstemp(dir=str(ROOT), suffix=".json"); os.close(fd)
            json.dump(reg, io.open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            os.replace(tmp, str(REGISTRY))
        _write()
        print(f"  APPLIED: {len(lockable)} locking->locked; registry written")
        av = subprocess.run([sys.executable, "tools/validate_locks_are_verified.py"],
                            capture_output=True, text=True, timeout=180,
                            env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        aout = (av.stdout or "") + (av.stderr or "")
        if av.returncode != 0 and "false 100" in aout:
            flagged = sorted(set(re.findall(r"^\s+((?:T|VD|VP|VM)\d+)\s+100%", aout, re.M)))
            by = {t["id"]: t for t in reg["trajectories"]}
            n = 0
            for tid in flagged:
                t = by.get(tid)
                if t and t.get("status") == "locked":
                    st, pc = prior.get(tid, ("locking", 90))
                    t["status"] = "locking"; t["pct"] = pc if isinstance(pc, int) else 90
                    t["basis"] = (t.get("basis", "") + " || AUTO-REVERTED by post_board_promote 2026-09-04: "
                                  "named gate FAILED on this board (stale-health false-100% guard). "
                                  f"pct -> {t['pct']}.").strip()
                    n += 1
            _write()
            print(f"  ROLLED BACK {n} false-100%(s) to locking (their named gate did NOT pass this board)")
        for cmd in (["tools/update_trajectory_scoreboard.py"], ["tools/validate_trajectory_registry.py"],
                    ["tools/validate_locks_are_verified.py"]):
            r = subprocess.run([sys.executable] + cmd, capture_output=True, text=True, timeout=180,
                               env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            print(f"  {'OK ' if r.returncode == 0 else 'ERR'} {cmd[0]}: {(r.stdout or r.stderr).strip().splitlines()[-1][:90] if (r.stdout or r.stderr).strip() else ''}")
    elif not apply:
        print("  (dry run — pass --apply to write)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main("--apply" in sys.argv))
