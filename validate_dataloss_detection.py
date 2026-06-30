#!/usr/bin/env python3
"""validate_dataloss_detection.py - Arc S (Resilience/DR) R-lens cell `dataloss_detection`.
================================================================================
PITR can only recover a silent loss if you NOTICE it inside the 7-day window. This
gate asserts the rowcount-snapshot monitor exists and runs: tools/dataloss_monitor.py
snapshots per-table counts and alerts on a sharp drop, so a rogue DELETE / bad backfill
is caught in hours (while PITR + the logical dump can still restore it).

  1. tools/dataloss_monitor.py exists,
  2. it runs clean (no anomalous drop since the last snapshot; SKIPs if DB down).

Exit 0 = silent-loss detection live; 1 = a gap (or an actual anomalous drop). Stdlib, $0.
"""
from __future__ import annotations
import io, subprocess, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
PY = sys.executable
G = "\033[92m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"


def main() -> int:
    print(f"{B}Arc S - silent data-loss detection (R-lens){X}")
    print("=" * 56)
    tool = ROOT / "tools" / "dataloss_monitor.py"
    if not tool.exists():
        print(f"  {R}FAIL{X}  tools/dataloss_monitor.py missing")
        print(f"\n{R}{B}  DATALOSS-DETECTION: FAIL{X}")
        return 1
    print(f"  {G}PASS{X}  tools/dataloss_monitor.py exists")
    try:
        r = subprocess.run([PY, str(tool)], cwd=str(ROOT), capture_output=True, text=True, timeout=120)
        ok = r.returncode == 0
        print(f"  {(G+'PASS'+X) if ok else (R+'FAIL'+X)}  monitor runs clean (no anomalous drop / baseline / SKIP)")
        if not ok:
            print(f"\n{R}{B}  DATALOSS-DETECTION: FAIL{X} - an anomalous row drop was flagged (investigate).")
            return 1
    except Exception as e:
        print(f"  {R}FAIL{X}  monitor errored: {e}")
        return 1
    print(f"\n{G}{B}  DATALOSS-DETECTION: PASS{X} - rowcount-snapshot monitor live.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
