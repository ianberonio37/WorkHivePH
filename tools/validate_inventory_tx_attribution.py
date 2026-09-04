#!/usr/bin/env python3
"""validate_inventory_tx_attribution.py — T11's lock: an inventory transaction's worker_name is the
SESSION's identity, never the payload's.

Walked live (T11, reproduced x2): both of Bryan Garcia's "Use" writes stored
worker_name='Leandro Marquez' — the column was client-supplied, so any part-take can bear anyone's
name, and the audit surfaces display worker_name. Fixed 2026-09-02 (migration
20260902000002_inventory_tx_server_attribution): a BEFORE INSERT trigger derives worker_name +
auth_uid from auth.uid() + hive_members for the row's hive (JWT-not-body, the XP/exam discipline),
with the vetted service-write bypass; the 2 existing misattributed rows were repaired. Proven in a
rolled-back tx as Bryan: payload said 'Leandro Marquez', RETURNING said 'Bryan Garcia'.

Lock (DB, via psql):
  1. The trigger trg_inventory_tx_attribution exists on inventory_transactions (BEFORE INSERT).
  2. The function derives from hive_members by auth.uid() and overrides new.worker_name.
  3. DATA: zero rows where auth_uid's membership name disagrees with the stored worker_name.
Skips cleanly when docker is down. Teeth: a missing trigger and a planted disagreement-count both redden.
"""
from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK_NAMES = ["inventory-tx-attribution"]


def _psql(sql: str):
    try:
        out = subprocess.run(
            ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres", "-t", "-A", "-c", sql],
            capture_output=True, text=True, timeout=25)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


def check(trigger_def: str | None, fn_src: str | None, mismatch_count: str | None) -> list[str]:
    problems = []
    if trigger_def is None or "BEFORE INSERT" not in (trigger_def or ""):
        problems.append("trg_inventory_tx_attribution is missing (or not BEFORE INSERT) on "
                        "inventory_transactions — worker_name is client-supplied again (any part-take "
                        "can bear anyone's name)")
    if fn_src is not None and not ("hive_members" in fn_src and "auth.uid()" in fn_src and "worker_name" in fn_src):
        problems.append("derive_inventory_tx_attribution no longer derives worker_name from "
                        "hive_members by auth.uid() — the JWT-not-body discipline is broken")
    if mismatch_count is not None and mismatch_count.isdigit() and int(mismatch_count) > 0:
        problems.append(f"{mismatch_count} inventory_transactions row(s) carry a worker_name that "
                        "disagrees with their auth_uid's membership — misattributed audit rows exist")
    return problems


def main() -> int:
    trig = _psql("SELECT pg_get_triggerdef(t.oid) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
                 "WHERE c.relname='inventory_transactions' AND t.tgname='trg_inventory_tx_attribution'")
    if trig is None:
        print("SKIP inventory-tx-attribution — DB down; re-run with the stack up.")
        return 0
    fn = _psql("SELECT prosrc FROM pg_proc WHERE proname='derive_inventory_tx_attribution'")
    mism = _psql("SELECT count(*) FROM inventory_transactions tx JOIN hive_members hm ON "
                 "hm.auth_uid=tx.auth_uid AND hm.hive_id=tx.hive_id AND hm.status='active' "
                 "WHERE tx.auth_uid IS NOT NULL AND tx.worker_name IS DISTINCT FROM hm.worker_name")
    problems = check(trig or "", fn, mism)
    if problems:
        print("FAIL inventory-tx-attribution:")
        for p in problems:
            print("    " + p)
        return 1
    print("PASS inventory-tx-attribution — worker_name derives from the session (trigger wired, "
          "function reads hive_members by auth.uid(), zero misattributed rows).")
    return 0


def self_test() -> int:
    fails = []
    if check("CREATE TRIGGER trg_inventory_tx_attribution BEFORE INSERT ON ...", "hive_members auth.uid() worker_name", "0"):
        fails.append("healthy state should PASS")
    if not any("missing" in p for p in check(None, "x", "0")):
        fails.append("a missing trigger must redden")
    if not any("misattributed" in p for p in check("BEFORE INSERT", "hive_members auth.uid() worker_name", "3")):
        fails.append("a planted mismatch count must redden")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_inventory_tx_attribution self-test (missing trigger + planted mismatches both redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
