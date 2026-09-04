#!/usr/bin/env python3
"""validate_staged_stock_guard.py — T11's S4 lock: a part staged for a predicted failure cannot be
silently consumed; the write path refuses with a legible, actionable sentence.

Walked live (T11, S4): the Use dialog computed 'Available: 0 pcs (1 on hand - 1 staged for a
predicted failure)' and Confirm Use COMMITTED anyway — the staged unit for the predicted repair
vanished with no warning (the toast celebrated 'now OUT OF STOCK'). The display had the number;
the WRITE PATH had no guard (fix-every-path-that-mutates). Fixed 2026-09-02 (migration
20260902000003, mirroring the marketplace credit-hold): BEFORE INSERT guard on consuming
transactions refuses when the write would push on-hand below the actively-staged total, errcode
check_violation (whWriteError surfaces the sentence verbatim), naming the staged asset + the
action that can work. Proven both directions in rolled-back txs: the walked item (Bearing 6310,
0 free, staged for CR-001) REFUSED with the full voice; a free item still inserts.

Gate: structure (trigger + function shape) AND a BEHAVIORAL replay — a rolled-back tx as a real
member attempting to consume a staged item must be refused (runs only when an active staged item
with a resolvable member exists; structure-only otherwise). Skips clean when docker is down.
"""
from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK_NAMES = ["staged-stock-guard"]


def _psql(sql: str, timeout: int = 25):
    try:
        out = subprocess.run(
            ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres", "-t", "-A", "-c", sql],
            capture_output=True, text=True, timeout=timeout)
        return (out.stdout or "") + (out.stderr or "")
    except Exception:
        return None


def main() -> int:
    trig = _psql("SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
                 "WHERE c.relname='inventory_transactions' AND t.tgname='trg_guard_staged_stock'")
    if trig is None:
        print("SKIP staged-stock-guard — DB down; re-run with the stack up.")
        return 0
    problems = []
    if not trig.strip().startswith("1"):
        problems.append("trg_guard_staged_stock is missing on inventory_transactions — a staged part "
                        "can be silently consumed again (the T11 S4)")
    fn = _psql("SELECT prosrc FROM pg_proc WHERE proname='guard_staged_stock'") or ""
    if "parts_staged_reservations" not in fn or "check_violation" not in fn:
        problems.append("guard_staged_stock no longer reads parts_staged_reservations / raises "
                        "check_violation — the refusal lost its source or its legible surface")
    # Behavioral replay (only when a probe target exists): member consuming a fully-staged item.
    probe = _psql(
        "SELECT r.item_id || '|' || r.hive_id || '|' || hm.auth_uid "
        "FROM parts_staged_reservations r "
        "JOIN inventory_items i ON i.id=r.item_id "
        "JOIN hive_members hm ON hm.hive_id=r.hive_id AND hm.status='active' AND hm.auth_uid IS NOT NULL "
        "WHERE r.consumed_at IS NULL AND r.released_at IS NULL AND i.qty_on_hand <= r.qty_reserved LIMIT 1")
    behavioral = "not run (no fully-staged item to probe)"
    if probe and probe.strip() and "|" in probe:
        item_id, hive_id, uid = probe.strip().split("|")[:3]
        replay = _psql(
            "BEGIN; "
            f"SELECT set_config('request.jwt.claims', '{{\"sub\":\"{uid}\",\"role\":\"authenticated\"}}', true); "
            "SET LOCAL role authenticated; "
            f"INSERT INTO inventory_transactions (worker_name,item_id,type,qty_change,note,hive_id) "
            f"VALUES ('gate-probe','{item_id}','use',-1,'staged-stock-guard gate probe','{hive_id}'); "
            "ROLLBACK;", timeout=30)
        if replay is None or "staged" not in replay or "ERROR" not in replay:
            problems.append("BEHAVIORAL: consuming a fully-staged item was NOT refused in the replay "
                            "tx — the guard exists but does not bite")
        else:
            behavioral = "refused with the staged-part voice (replayed live, rolled back)"
    if problems:
        print("FAIL staged-stock-guard:")
        for p in problems:
            print("    " + p)
        return 1
    print(f"PASS staged-stock-guard — trigger wired, function reads reservations and raises "
          f"check_violation; behavioral: {behavioral}.")
    return 0


def self_test() -> int:
    # structure-shape teeth (pure logic; the live behavioral is main()'s job)
    fails = []
    fn_good = "... parts_staged_reservations ... check_violation ..."
    if "parts_staged_reservations" not in fn_good or "check_violation" not in fn_good:
        fails.append("healthy shape should pass")
    fn_bad = "... something else ..."
    if not ("parts_staged_reservations" not in fn_bad or "check_violation" not in fn_bad):
        fails.append("a gutted function must redden")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_staged_stock_guard self-test (shape checks; the live replay runs in main)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
