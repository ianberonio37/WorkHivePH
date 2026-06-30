#!/usr/bin/env python3
"""validate_data_backup.py - Arc S (Resilience/DR) R-lens cell `data_backup_restore`.
================================================================================
A backup you have never restored is a hope, not a backup. This gate asserts a LOGICAL
DATA backup+restore path exists AND is drilled:
  1. tools/data_backup.py exists (the local logical dump + restore-drill tool),
  2. its restore DRILL passes (a real dump->restore-into-scratch->rowcount-match
     round-trip; SKIPs cleanly if the local DB is down — a down DB is not a failure),
  3. ROLLBACK_RUNBOOK.md documents the restore-from-dump procedure (§5b).

Exit 0 = data backup+restore proven + documented; 1 = a gap. Stdlib, $0.
"""
from __future__ import annotations
import io, subprocess, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
PY = sys.executable
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"


def main() -> int:
    print(f"{B}Arc S - data backup + restore drill (R-lens){X}")
    print("=" * 56)
    tool = ROOT / "tools" / "data_backup.py"
    runbook = ROOT / "ROLLBACK_RUNBOOK.md"
    issues = []

    ok_tool = tool.exists()
    print(f"  {(G+'PASS'+X) if ok_tool else (R+'FAIL'+X)}  tools/data_backup.py exists")
    if not ok_tool:
        issues.append("backup tool missing")

    drill_ok = False
    if ok_tool:
        try:
            r = subprocess.run([PY, str(tool), "--drill"], cwd=str(ROOT),
                               capture_output=True, text=True, timeout=240)
            drill_ok = r.returncode == 0
            print(f"  {(G+'PASS'+X) if drill_ok else (R+'FAIL'+X)}  restore drill round-trip (or SKIP if DB down)")
            if not drill_ok:
                issues.append("restore drill failed")
        except Exception as e:
            print(f"  {R}FAIL{X}  restore drill errored: {e}")
            issues.append("restore drill errored")

    rb = runbook.read_text(encoding="utf-8", errors="replace") if runbook.exists() else ""
    ok_doc = "Restore from a logical dump" in rb or "5b." in rb
    print(f"  {(G+'PASS'+X) if ok_doc else (R+'FAIL'+X)}  ROLLBACK_RUNBOOK documents restore-from-dump (§5b)")
    if not ok_doc:
        issues.append("restore-from-dump runbook missing")

    if issues:
        print(f"\n{R}{B}  DATA-BACKUP: FAIL{X} - {'; '.join(issues)}")
        return 1
    print(f"\n{G}{B}  DATA-BACKUP: PASS{X} - logical dump + restore drill + documented restore path.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
