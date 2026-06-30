#!/usr/bin/env python3
"""validate_atomic_writes.py - Arc S (Resilience/DR) C-lens cell `atomic_multistep`.
================================================================================
No partial-write corruption. A multi-step write splits into two classes:

  CORRUPTION class — both writes must agree or an invariant breaks. These MUST be
    atomic (one RPC = one transaction). The inventory deduction (balance UPDATE +
    ledger INSERT) is the corruption path: a half-done deduction changes the
    on-hand qty with no matching transaction row = unreconcilable audit trail.

  MIRROR/ORPHAN class — a secondary best-effort write whose source-of-truth is
    already saved (pm_completion -> logbook mirror; project -> items). A failure
    here is recoverable IF it is SURFACED to the user (not silently swallowed) so
    they can retry. These must show the partial state, not pretend success.

This gate asserts:
  1. inventory_deduct() RPC exists in a migration (SECURITY DEFINER, hive-scoped).
  2. logbook.html routes EVERY parts deduction through db.rpc('inventory_deduct')
     and has NO remaining raw inventory_items.update + inventory_transactions.insert
     pair (the old non-atomic path).
  3. The mirror-class writes surface partial failure (pm-scheduler logbook-mirror
     + project-manager items) instead of silently committing.

Exit 0 = corruption path atomic + mirror paths surfaced; 1 = a gap. Stdlib, $0.
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
MIGRATIONS = ROOT / "supabase" / "migrations"
G = "\033[92m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _migrations_text() -> str:
    if not MIGRATIONS.is_dir():
        return ""
    return "\n".join(_read(p) for p in sorted(MIGRATIONS.glob("*.sql")))


def main() -> int:
    print(f"{B}Arc S - atomic multi-step writes (C-lens, no partial-write){X}")
    print("=" * 62)
    issues = []
    sql = _migrations_text()
    logbook = _read(ROOT / "logbook.html")

    # 1. the atomic RPC exists, DEFINER + search_path pinned
    rpc_def = re.search(r"CREATE\s+OR\s+REPLACE\s+FUNCTION\s+public\.inventory_deduct\b[^;]*?"
                        r"SECURITY\s+DEFINER[^;]*?SET\s+search_path", sql, re.IGNORECASE | re.DOTALL)
    ok1 = bool(rpc_def)
    print(f"  {(G+'PASS'+X) if ok1 else (R+'FAIL'+X)}  inventory_deduct() RPC (DEFINER + search_path) in a migration")
    if not ok1:
        issues.append("inventory_deduct RPC missing")

    # 2. logbook uses the RPC and has NO raw deduction pair left
    uses_rpc = "rpc('inventory_deduct'" in logbook or 'rpc("inventory_deduct"' in logbook
    raw_pair = bool(re.search(r"from\(['\"]inventory_items['\"]\)\.update\(", logbook)) and \
               bool(re.search(r"from\(['\"]inventory_transactions['\"]\)\.insert\(", logbook))
    ok2 = uses_rpc and not raw_pair
    detail2 = []
    if not uses_rpc: detail2.append("does not call rpc('inventory_deduct')")
    if raw_pair:     detail2.append("still has a raw inventory_items.update + inventory_transactions.insert pair")
    print(f"  {(G+'PASS'+X) if ok2 else (R+'FAIL'+X)}  logbook.html deduction is atomic-only {('· ' + '; '.join(detail2)) if detail2 else ''}")
    if not ok2:
        issues.append("logbook deduction not fully atomic")

    # 3. mirror-class partial failures are surfaced (not silent)
    pm = _read(ROOT / "pm-scheduler.html")
    pm_surfaces = bool(re.search(r"logbook[^\n]*fail|Logbook entry failed|PM saved\. Logbook", pm, re.IGNORECASE))
    print(f"  {(G+'PASS'+X) if pm_surfaces else (R+'FAIL'+X)}  pm-scheduler surfaces logbook-mirror failure (no silent partial)")
    if not pm_surfaces:
        issues.append("pm-scheduler does not surface logbook-mirror failure")

    pmgr = _read(ROOT / "project-manager.html")
    pmgr_surfaces = bool(re.search(r"item[^\n]*fail|could not (add|save) item|scope item", pmgr, re.IGNORECASE)) \
                    or "23505" in pmgr  # link/items partial-state surfaced or guarded
    print(f"  {(G+'PASS'+X) if pmgr_surfaces else (R+'FAIL'+X)}  project-manager surfaces item/link partial-failure")
    if not pmgr_surfaces:
        issues.append("project-manager does not surface item partial-failure")

    if issues:
        print(f"\n{R}{B}  ATOMIC-WRITES: FAIL{X} - {'; '.join(issues)}")
        return 1
    print(f"\n{G}{B}  ATOMIC-WRITES: PASS{X} - corruption path atomic; mirror paths surface partial failure.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
