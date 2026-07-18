#!/usr/bin/env python3
# DEEPWALK-CELL: inventory D2
"""validate_inventory_ledger_reconciled.py -- LOCK for the inventory balance<->ledger seesaw.

ARC DI §10.5 anti-seesaw (2026-07-08). Stock level is ONE truth stored TWO ways:
  inventory_items.qty_on_hand        (the stored BALANCE)
  inventory_transactions.qty_after   (the LEDGER's running total)
A deep-walk probe found 25/27 items where these had drifted (qty_on_hand != the ledger's
latest qty_after) -- a classic "same truth, two copies" seesaw seeded by an opening-balance
+ random-timestamp ledger. Disposition (§10.5 tier-2): a reconcile TRIGGER
(migration 20260708000001) keeps the balance in lockstep on every movement, the seeder is
born-consistent, and THIS gate asserts the invariant holds as a fix-to-ZERO down-ratchet:

  CHECK A (balance vs ledger): every item with >=1 txn must have
          qty_on_hand == its newest qty_after (by created_at DESC, id DESC).  -> 0 drift.
  CHECK B (ledger internal consistency): within each item, ordered by (created_at, id),
          every qty_after == previous qty_after + this qty_change.            -> 0 breaks.

A non-zero A means a producer wrote the ledger without syncing the balance (or the trigger
is gone). A non-zero B means a producer wrote an inconsistent running total (or the seeder
regressed to the opening-balance/random-timestamp bug). Either re-opens the seesaw.

Live-tier (skip_if_fast); SKIPS cleanly (exit 0) if the local DB is down.

Usage:  python tools/validate_inventory_ledger_reconciled.py [--json] [--selftest]
Exit 0 = clean / skipped, 1 = >0 drift or >0 chain-breaks (or self-test failure).
"""
import sys, json, subprocess

DOCKER_DB = ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-c"]

# CHECK A -- stored balance vs the ledger's newest running total (items with a ledger).
DRIFT_SQL = """
WITH latest AS (
  SELECT DISTINCT ON (item_id) item_id, qty_after
  FROM public.inventory_transactions
  ORDER BY item_id, created_at DESC, id DESC
)
SELECT count(*)
FROM public.inventory_items i
JOIN latest l ON l.item_id = i.id
WHERE i.qty_on_hand IS DISTINCT FROM l.qty_after;
"""

DRIFT_SAMPLE_SQL = """
WITH latest AS (
  SELECT DISTINCT ON (item_id) item_id, qty_after
  FROM public.inventory_transactions
  ORDER BY item_id, created_at DESC, id DESC
)
SELECT i.part_number, i.qty_on_hand, l.qty_after
FROM public.inventory_items i
JOIN latest l ON l.item_id = i.id
WHERE i.qty_on_hand IS DISTINCT FROM l.qty_after
ORDER BY abs(i.qty_on_hand - l.qty_after) DESC LIMIT 8;
"""

# CHECK B -- the ledger's running total must chain (qty_after = prev + qty_change).
CHAIN_SQL = """
WITH ordered AS (
  SELECT item_id, qty_change, qty_after,
         lag(qty_after) OVER (PARTITION BY item_id ORDER BY created_at, id) AS prev_after
  FROM public.inventory_transactions
)
SELECT count(*) FROM ordered
WHERE prev_after IS NOT NULL
  AND qty_after IS DISTINCT FROM prev_after + qty_change;
"""

# Structural: the reconcile trigger must exist (the lock behind CHECK A).
TRIGGER_SQL = """
SELECT count(*) FROM pg_trigger
WHERE tgname = 'trg_inventory_sync_balance' AND NOT tgisinternal;
"""


def psql(sql):
    try:
        r = subprocess.run(DOCKER_DB + [sql], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=45)
        if r.returncode != 0:
            return None
        return (r.stdout or "").strip()
    except Exception:
        return None


def _int(out):
    try:
        return int((out or "").splitlines()[0].strip())
    except (ValueError, IndexError):
        return None


def analyze():
    drift = psql(DRIFT_SQL)
    if drift is None:
        return {"skipped": True, "reason": "local DB unreachable (docker supabase_db_workhive)"}
    n_drift = _int(drift)
    n_chain = _int(psql(CHAIN_SQL))
    n_trig = _int(psql(TRIGGER_SQL))
    if n_drift is None or n_chain is None:
        return {"skipped": True, "reason": f"unexpected psql output: drift={drift!r}"}
    samples = []
    if n_drift > 0:
        s = psql(DRIFT_SAMPLE_SQL) or ""
        for line in s.splitlines():
            if "|" in line:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 3:
                    samples.append(f"{parts[0]} balance={parts[1]} ledger={parts[2]}")
    return {"skipped": False, "drift": n_drift, "chain_breaks": n_chain,
            "trigger_present": (n_trig or 0) > 0, "samples": samples}


def run_selftest():
    """The queries must be real invariant checks, not trivially-PASS shapes."""
    problems = []
    if "DISTINCT ON (item_id)" not in DRIFT_SQL or "qty_on_hand IS DISTINCT FROM l.qty_after" not in DRIFT_SQL:
        problems.append("DRIFT_SQL must compare qty_on_hand to the newest ledger qty_after per item")
    if "lag(qty_after)" not in CHAIN_SQL or "prev_after + qty_change" not in CHAIN_SQL:
        problems.append("CHAIN_SQL must assert qty_after = prev qty_after + qty_change")
    live = analyze()
    if not live.get("skipped"):
        if live.get("drift", 0) != 0:
            problems.append(f"live balance drift is {live['drift']} (expected 0) -- seesaw breached")
        if live.get("chain_breaks", 0) != 0:
            problems.append(f"live ledger chain-breaks is {live['chain_breaks']} (expected 0)")
        if not live.get("trigger_present"):
            problems.append("reconcile trigger trg_inventory_sync_balance is MISSING (the lock is gone)")
    return problems


def main():
    as_json = "--json" in sys.argv
    if "--selftest" in sys.argv:
        probs = run_selftest()
        print(json.dumps({"selftest_problems": probs}, indent=2) if as_json
              else ("SELFTEST PASS" if not probs else "SELFTEST FAIL:\n  " + "\n  ".join(probs)))
        return 1 if probs else 0
    res = analyze()
    if as_json:
        print(json.dumps(res, indent=2))
    else:
        print("inventory balance<->ledger reconciliation (qty_on_hand must == newest qty_after; ledger must chain)")
        if res.get("skipped"):
            print(f"  SKIP -- {res['reason']}")
        else:
            ok = res["drift"] == 0 and res["chain_breaks"] == 0
            if ok:
                print(f"  PASS: 0 balance drift, 0 ledger chain-breaks "
                      f"(reconcile trigger {'present' if res['trigger_present'] else 'MISSING'})")
                if not res["trigger_present"]:
                    print("  WARN: data is clean but trg_inventory_sync_balance is missing -- "
                          "apply migration 20260708000001 or the seesaw can re-open.")
            else:
                if res["drift"] > 0:
                    print(f"  FAIL: {res['drift']} items' qty_on_hand != the ledger's latest qty_after "
                          f"(balance/ledger seesaw). Top: {', '.join(res['samples'])}")
                if res["chain_breaks"] > 0:
                    print(f"  FAIL: {res['chain_breaks']} ledger rows where qty_after != prev + qty_change "
                          f"(inconsistent running total; seeder or a producer regressed).")
                print("  Fix: apply migration 20260708000001 (reconcile trigger + backfill) and "
                      "reseed inventory with the born-consistent seeder.")
    if res.get("skipped"):
        return 0
    return 1 if (res["drift"] > 0 or res["chain_breaks"] > 0) else 0


if __name__ == "__main__":
    sys.exit(main())
