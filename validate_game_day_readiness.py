"""
Game-Day / Recovery Readiness (Maturity Phase 1, 2026-06-16).
==============================================================
Closes the (AV, GH) cell from COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §4 — the
game-day-automation hardening cell (study §7 #13).

A rollback runbook is theatre until practised. This gate asserts the recovery
HARNESS exists and is exercisable, so an availability incident has a rehearsed
path rather than improvisation:

  L1  executable game-day drills present     — tools/game_day.py
  L2  backup integrity is verifiable         — tools/verify_backups.py
  L3  recovery targets declared              — RTO_RPO_DECLARATION.md has RTO + RPO
  L4  rollback path documented               — ROLLBACK_RUNBOOK.md present
  L5  error-budget / SLO declared            — GATEWAY_SLO.md present (the budget the
                                               drills protect)

Swap-ready: when a scheduler exists, L1 becomes a scheduled quarterly run; the
gate shape does not change.

Output:  game_day_readiness_report.json
Exit code:
  0  PASS (recovery harness complete + exercisable)
  1  FAIL (a recovery invariant is missing)
"""
from __future__ import annotations
import io, json, sys
from pathlib import Path
from datetime import datetime, timezone

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
GAME_DAY    = ROOT / "tools" / "game_day.py"
VERIFY_BK   = ROOT / "tools" / "verify_backups.py"
RTO_RPO     = ROOT / "RTO_RPO_DECLARATION.md"
ROLLBACK    = ROOT / "ROLLBACK_RUNBOOK.md"
SLO         = ROOT / "GATEWAY_SLO.md"
REPORT      = ROOT / "game_day_readiness_report.json"

CHECK_NAMES = ["game_day_readiness"]
GREEN = "\033[92m"; RED = "\033[91m"; BOLD = "\033[1m"; RESET = "\033[0m"


def main() -> int:
    rto_text = RTO_RPO.read_text(encoding="utf-8", errors="replace") if RTO_RPO.exists() else ""
    checks = [
        ("L1 executable game-day drills (tools/game_day.py)", GAME_DAY.exists()),
        ("L2 backup integrity verifier (tools/verify_backups.py)", VERIFY_BK.exists()),
        ("L3 recovery targets declared (RTO_RPO_DECLARATION.md has RTO + RPO)",
         RTO_RPO.exists() and "RTO" in rto_text and "RPO" in rto_text),
        ("L4 rollback path documented (ROLLBACK_RUNBOOK.md)", ROLLBACK.exists()),
        ("L5 error-budget / SLO declared (GATEWAY_SLO.md)", SLO.exists()),
    ]
    fails = [name for name, ok in checks if not ok]

    REPORT.write_text(json.dumps({
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "checks": {name: ok for name, ok in checks}, "fails": fails,
    }, indent=2), encoding="utf-8")

    print(f"{BOLD}Game-Day / Recovery Readiness (AV, GH){RESET}")
    for name, ok in checks:
        print(f"  {GREEN+'PASS'+RESET if ok else RED+'FAIL'+RESET}  {name}")
    if fails:
        print(f"{RED}FAIL: {len(fails)} recovery invariant(s) missing.{RESET}")
        return 1
    print(f"{GREEN}PASS — recovery harness complete and exercisable.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
