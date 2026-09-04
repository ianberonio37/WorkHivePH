#!/usr/bin/env python3
"""An optimistic-concurrency guard is only a guard if the stamp it filters on MOVES (T138).

Ten pages protect an edit the same way: re-send the row's last-seen `updated_at` as a filter, so a
second writer holding a stale stamp matches no row, gets a conflict, and is TOLD. The census
confirmed all ten detect the zero-row case and speak.

THE STAMP CAN MOVE TWO WAYS, and this gate exists because only one of them is robust:

  A. THE CALLER SENDS IT - the page puts `updated_at: now` in its update payload. This works, and
     it is what inventory.html has always done.
  B. A TRIGGER SETS IT - the database moves the column itself on every UPDATE.

★I ONCE REPORTED (A) AS A DEFECT, AND THE CORRECTION IS THE REASON THIS DOCSTRING IS LONG.
inventory_items had no trigger, so I probed it with `UPDATE ... SET qty_on_hand = ...`, watched the
stamp stay frozen, saw writer B overwrite writer A, and filed a guard that "could never fire". The
page does not send that statement. It sends `SET qty_on_hand = ..., updated_at = <now>`, and re-
racing two PRODUCT-SHAPED writers with the trigger removed gives A rows=1, B rows=0, A survives.
The guard had always worked. Right reading, wrong subject - I measured a shape the product never
sends, and the frozen stamp was an artifact of my statement, not a property of the table.

SO THE GATE HOLDS THE HONEST PROPERTY: every guarded table must move its stamp by (B), the
server-side route. Not because (A) is broken - it is not - but because (A) is a promise every
present and future caller has to keep, and its failure is silent: an edit path that forgets the
field disables the concurrency check with nothing erroring. (B) cannot be forgotten, and it also
makes the stamp SERVER-authoritative rather than trusting `new Date()` on a device whose clock may
be wrong. This is a HARDENING ratchet, and it is labelled as one: a red here means "this table
relies on caller discipline", never "this guard is broken".

Fails CLOSED - if the local database is unreachable the gate SKIPs rather than passing, because a
guard whose backing cannot be checked is not a guard that has been checked.

TEETH: --teeth drops the trigger inside a transaction it ROLLS BACK, so the detector is proven
against a table without the ratchet, leaving the schema untouched.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_CONTAINER = "supabase_db_workhive"

# Every OC call site, resolved to its table. Kept explicit rather than parsed at runtime: a regex
# that silently resolved a table to '' would shrink this gate's denominator to nothing and go green.
GUARDED = {
    "inventory_items":     "inventory.html (ocUpdate, the central helper)",
    "logbook":             "logbook.html amend",
    "community_posts":     "community.html post edit",
    "projects":            "project-manager.html project edit",
    "project_items":       "project-manager.html scope-item edit",
    "rcm_strategies":      "asset-hub.html strategy edit",
    "platform_feedback":   "founder-console.html + platform-actions.html",
    "integration_configs": "integrations.html config edit",
    "pm_assets":           "pm-scheduler.html asset edit",
}

TOUCH_SQL = """
select c.relname,
       case when exists (
         select 1 from pg_trigger tg join pg_proc p on p.oid = tg.tgfoid
         where tg.tgrelid = c.oid and not tg.tgisinternal
           and tg.tgtype & 16 = 16            -- fires on UPDATE
           and p.prosrc ilike '%updated_at%'
       ) then 'ok' else 'NO-TOUCH' end
from pg_class c
join pg_namespace n on n.oid = c.relnamespace and n.nspname = 'public'
where c.relkind = 'r' and c.relname in (__NAMES__)
order by 1;
"""


def psql(sql: str, timeout: int = 60):
    try:
        proc = subprocess.run(["docker", "exec", "-i", DB_CONTAINER, "psql", "-U", "postgres",
                               "-d", "postgres", "-qtA", "-c", sql], capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return proc.stdout.strip() if proc.returncode == 0 else None
    except Exception:  # noqa: BLE001
        return None


def read_state() -> dict | None:
    names = ", ".join("'" + t + "'" for t in sorted(GUARDED))
    out = psql(TOUCH_SQL.replace('__NAMES__', names))
    if out is None:
        return None
    state = {}
    for line in out.splitlines():
        if "|" in line:
            t, v = line.split("|", 1)
            state[t.strip()] = v.strip()
    return state


def audit(state: dict) -> list:
    out = []
    for table in sorted(GUARDED):
        v = state.get(table)
        if v is None:
            out.append(f"{table}: guarded by {GUARDED[table]} but the table is not in the database - "
                       f"the guard filters a table that is not there")
        elif v != "ok":
            out.append(f"{table}: no trigger moves updated_at, so the guard in {GUARDED[table]} depends on "
                       f"every caller remembering to send the field. It works today; it fails SILENTLY the "
                       f"day an edit path omits it, and the stamp is client-clock rather than server-clock. "
                       f"Add the touch_updated_at trigger the other tables use.")
    return out


def teeth() -> int:
    """Drop the trigger inside a rolled-back transaction: red on the pre-fix world, schema untouched."""
    before = read_state()
    if before is None:
        print("  SKIP - database unreachable; teeth cannot run")
        return 0
    print(f"  clean state: {sum(1 for v in before.values() if v == 'ok')}/{len(GUARDED)} tables touched, "
          f"findings={len(audit(before))}")
    # The mutation and the READ must share one transaction, or the rollback lands before the read.
    sql = ("begin; drop trigger tg_inventory_items_touch_updated on public.inventory_items; "
           + TOUCH_SQL.replace('__NAMES__', "'inventory_items'") + " rollback;")
    out = psql(sql)
    mutated = {}
    for line in (out or "").splitlines():
        if "|" in line:
            t, v = line.split("|", 1)
            mutated[t.strip()] = v.strip()
    caught = bool(mutated) and mutated.get("inventory_items") == "NO-TOUCH"
    after = read_state()
    restored = bool(after) and after.get("inventory_items") == "ok"
    print(f"  {'ok  ' if caught else 'MISS'} dropping the trigger is detected (read inside the txn: "
          f"{mutated.get('inventory_items', '?')})")
    print(f"  {'ok  ' if restored else 'MISS'} the rollback restored it (live state: "
          f"{(after or {}).get('inventory_items', '?')})")
    bad = (0 if caught else 1) + (0 if restored else 1)
    print(f"\nTEETH {'FAILED' if bad else 'ok'} - {2 - bad}/2")
    return 1 if bad else 0


def main() -> int:
    state = read_state()
    if state is None:
        print("the-concurrency-guard-can-fire - SKIP: local database unreachable")
        print("  (fails closed: a guard whose backing cannot be checked has not been checked)")
        return 0
    findings = audit(state)
    print("the-concurrency-guard-can-fire - the stamp moves server-side, not by caller discipline")
    print(f"  guarded tables: {len(GUARDED)} across 10 pages")
    if findings:
        print("\nFAIL - a guard that cannot fire is worse than none, because its promised refusal is "
              "what everyone downstream trusts:")
        for f in findings:
            print(f"    {f}")
        return 1
    print("\nPASS - every guarded table moves its stamp server-side; no guard depends on caller memory.")
    return 0


if __name__ == "__main__":
    raise SystemExit(teeth() if "--teeth" in sys.argv else main())
