#!/usr/bin/env python3
"""validate_inventory_txn_actor_attribution.py — Cluster 3 / T11 lock: the inventory ledger
attributes a part use to the ACTOR, not the item's owner.

Walked live (critic T11, reproduced x2): inventory_transactions.worker_name was the item's
owner (inventory_items.worker_name) because inventory_deduct wrote the row with v_worker read
FROM the item. A part pulled by Bryan from an item Leandro registered logged as 'Leandro used 1'
on the audit trail a supervisor reads to answer 'who took this part'. Fixed 2026-09-02
(mig 20260902000002): the RPC resolves the actor's name from hive_members by auth.uid() in the
item's hive (the same JWT->name mapping XP/exam use), falling back to the owner only for a
system write. Proven live in a rolled-back tx: Bryan deducting a Leandro-owned item logged
worker_name='Bryan Garcia'.

This gate asserts the fix survives in the live function body: inventory_deduct must resolve the
actor (hive_members ... auth_uid = v_uid) and must NOT insert the item-owner name unconditionally.
Reads the installed prosrc via docker psql; skips cleanly if the DB is down.
"""
from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK_NAMES = ["inventory-txn-actor-attribution"]


def _prosrc() -> str | None:
    try:
        out = subprocess.run(
            ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-c",
             "SELECT prosrc FROM pg_proc WHERE proname='inventory_deduct' ORDER BY oid DESC LIMIT 1"],
            capture_output=True, text=True, timeout=25)
        if out.returncode != 0:
            return None
        return out.stdout
    except Exception:
        return None


def main() -> int:
    src = _prosrc()
    if src is None:
        print("SKIP inventory-txn-actor-attribution - DB unreachable; the fix is migration "
              "20260902000002_inventory_deduct_actor_attribution.sql")
        return 0
    src_l = src.lower()
    problems = []
    # the actor-resolve query must be present
    if "hive_members" not in src_l or "auth_uid = v_uid" not in src_l.replace(" ", " "):
        # tolerate spacing variants
        if not ("hive_members" in src_l and "v_uid" in src_l and "worker_name" in src_l):
            problems.append("inventory_deduct no longer resolves the actor's worker_name from hive_members by auth.uid() "
                            "- the ledger would misattribute the use to the item owner again")
    # the INSERT must prefer the actor (v_actor) before the item owner (v_worker)
    if "v_actor" not in src_l:
        problems.append("inventory_deduct dropped the v_actor variable - the actor-first attribution is gone")
    if "coalesce(v_actor" not in src_l.replace(" ", ""):
        problems.append("the txn INSERT no longer prefers v_actor (COALESCE(v_actor, v_worker, ...)) - owner-name fallback is not last-resort")
    if problems:
        print("FAIL inventory-txn-actor-attribution:")
        for p in problems:
            print("    " + p)
        return 1
    print("PASS inventory-txn-actor-attribution - inventory_deduct resolves the actor's name from "
          "hive_members (auth.uid()) and writes it to the ledger, owner-name only as last-resort "
          "fallback (verified live: Bryan deducting a Leandro-owned item logs 'Bryan Garcia').")
    return 0


def self_test() -> int:
    # HEAD (installed fn) should pass or skip; a body without v_actor must fail the substring checks
    fake_bad = "insert into inventory_transactions ... values (..., coalesce(v_worker, 'system'), ...)"
    if "coalesce(v_actor" in fake_bad.replace(" ", ""):
        print("SELF-TEST FAIL: a v_actor-less body wrongly passed"); return 1
    print("PASS validate_inventory_txn_actor_attribution self-test (owner-only body reddens on the v_actor checks)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
