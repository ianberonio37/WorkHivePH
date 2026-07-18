"""validate_inventory_txn_isolation.py — LIVE two-tenant ledger-write isolation gate.

Locks the cross-hive ledger-tamper hole found + live-exploited in the Inventory PDDA
arc (2026-07-12): `inventory_transactions_write` WITH CHECK was only `auth.uid() IS NOT
NULL`, so an authed worker could INSERT a ledger row against a FOREIGN hive's item and
the SECURITY DEFINER sync trigger mirrored the bogus qty_after onto that item's stored
qty_on_hand (cross-tenant stock corruption / ledger poisoning). Fixed by
20260712000011_inventory_txn_hive_scope_write_guard.sql (RLS hive-membership scope +
trigger hive-guard + qty_after >= 0 CHECK).

This gate does a ROLLED-BACK live probe against the running DB (docker psql), simulating a
real authenticated member, and asserts THREE invariants — so it catches a reverted
migration that a static file-parse would miss:
  1. XHIVE  — a member of hive A inserting a txn for an item in hive B is BLOCKED (42501).
  2. NEG    — a negative qty_after (a balance can't be < 0) is BLOCKED (23514).
  3. LEGIT  — a legit in-hive insert on the member's own item still SUCCEEDS (no regression).

Actors (member uid/hive, own item, foreign item) are chosen dynamically from the DB, so
the gate survives a reseed (which rotates auth_uids). Skips cleanly (exit 0) when the
local docker DB / a suitable two-hive fixture is absent, matching the other *_live gates.

Exit 0 = all three invariants hold (or skipped, env absent).  Exit 1 = an invariant failed.
"""

import sys, json, subprocess
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"; RESET = "\033[0m"; BOLD = "\033[1m"
ROOT = Path(__file__).resolve().parent.parent
DB = "supabase_db_workhive"
REPORT = ROOT / "inventory_txn_isolation_report.json"


def _psql(sql: str, stdin_mode: bool = False):
    """Run SQL in the local docker Postgres. Returns (rc, stdout+stderr) or None if docker/db absent."""
    try:
        if stdin_mode:
            p = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres",
                                "-X", "-q", "-v", "ON_ERROR_STOP=0"],
                               input=sql, capture_output=True, text=True, timeout=40)
        else:
            p = subprocess.run(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres",
                                "-X", "-A", "-t", "-c", sql],
                               capture_output=True, text=True, timeout=40)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception:
        return None


def _skip(reason: str) -> int:
    print(f"{YELLOW}  SKIP  {reason}{RESET}")
    REPORT.write_text(json.dumps({"validator": "inventory_txn_isolation", "skipped": True,
                                  "reason": reason}, indent=2), encoding="utf-8")
    return 0


def main() -> int:
    print(f"\n{BOLD}INVENTORY TXN ISOLATION (live two-tenant){RESET}")
    print("─" * 44)

    # ── Pick actors as the superuser (BYPASSRLS): a member's auth_uid + hive, an item in
    #    that hive (legit target), and an item in a DIFFERENT hive (foreign target). ───────
    pick = _psql(
        "SELECT hm.auth_uid, own.id, own.hive_id, foreign_i.id "
        "FROM hive_members hm "
        "JOIN inventory_items own      ON own.hive_id = hm.hive_id "
        "JOIN inventory_items foreign_i ON foreign_i.hive_id <> hm.hive_id "
        "WHERE hm.status='active' AND hm.auth_uid IS NOT NULL "
        "LIMIT 1;")
    if pick is None:
        return _skip("docker psql unavailable")
    rc, out = pick
    row = [ln for ln in out.splitlines() if "|" in ln]
    if not row:
        return _skip("no two-hive inventory fixture (need ≥2 hives with items + an active member)")
    uid, own_item, own_hive, foreign_item = [c.strip() for c in row[0].split("|")]

    # ── The rolled-back probe, run AS the authenticated member ────────────────────────────
    probe = f"""
BEGIN;
SET LOCAL ROLE authenticated;
SET LOCAL request.jwt.claims TO '{{"sub":"{uid}","role":"authenticated"}}';
DO $$
BEGIN
  BEGIN
    INSERT INTO inventory_transactions(id,item_id,type,qty_change,qty_after,hive_id,auth_uid,worker_name,created_at)
    VALUES('GATE-XHIVE','{foreign_item}','adjust',0,55555,'{own_hive}','{uid}','gate',now());
    RAISE NOTICE 'RESULT xhive=OPEN_VULN';
  EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'RESULT xhive=BLOCKED';
            WHEN others THEN RAISE NOTICE 'RESULT xhive=OTHER:%', SQLSTATE;
  END;
  BEGIN
    INSERT INTO inventory_transactions(id,item_id,type,qty_change,qty_after,hive_id,auth_uid,worker_name,created_at)
    VALUES('GATE-NEG','{own_item}','adjust',-99,-5,'{own_hive}','{uid}','gate',now());
    RAISE NOTICE 'RESULT neg=OPEN_VULN';
  EXCEPTION WHEN check_violation THEN RAISE NOTICE 'RESULT neg=BLOCKED';
            WHEN others THEN RAISE NOTICE 'RESULT neg=OTHER:%', SQLSTATE;
  END;
  BEGIN
    INSERT INTO inventory_transactions(id,item_id,type,qty_change,qty_after,hive_id,auth_uid,worker_name,created_at)
    VALUES('GATE-LEGIT','{own_item}','adjust',0,(SELECT qty_on_hand FROM inventory_items WHERE id='{own_item}'),'{own_hive}','{uid}','gate',now());
    RAISE NOTICE 'RESULT legit=OK';
  EXCEPTION WHEN others THEN RAISE NOTICE 'RESULT legit=REGRESSION:%', SQLSTATE;
  END;
END $$;
ROLLBACK;
"""
    res = _psql(probe, stdin_mode=True)
    if res is None:
        return _skip("docker psql unavailable (probe)")
    _, pout = res
    results = {}
    for ln in pout.splitlines():
        if "RESULT " in ln:
            body = ln.split("RESULT ", 1)[1].strip()
            if "=" in body:
                k, v = body.split("=", 1)
                results[k.strip()] = v.strip()

    checks = [
        ("xhive_blocked", results.get("xhive"), "BLOCKED",
         "a hive-A member's INSERT against a hive-B item is rejected (cross-tenant ledger tamper)"),
        ("negative_blocked", results.get("neg"), "BLOCKED",
         "a negative qty_after is rejected by the non-negative CHECK"),
        ("legit_ok", results.get("legit"), "OK",
         "a legit in-hive insert still succeeds (no regression)"),
    ]
    fails = 0
    for name, got, want, desc in checks:
        if got == want:
            print(f"  {GREEN}PASS{RESET}  {name}: {desc}")
        else:
            fails += 1
            print(f"  {RED}FAIL{RESET}  {name}: expected {want}, got {got!r} — {desc}")

    print(f"\n  Summary: {3 - fails} pass · {fails} fail  (actor uid={uid[:8]}… own_hive={own_hive[:8]}…)")
    REPORT.write_text(json.dumps({"validator": "inventory_txn_isolation", "skipped": False,
                                  "results": results, "fail": fails}, indent=2), encoding="utf-8")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
