#!/usr/bin/env python3
"""
validate_change_order_immutability.py — PJK1: a raised change order is a contract, not a draft.

THE DEFECT. project_change_orders is a CONTRACT AMENDMENT table: each row carries cost_impact_php
and schedule_impact_days, and a supervisor approving one is committing money. The approval ACT was
properly guarded (wh_guard_supervisor_approval refuses a non-supervisor approving, rejecting, or
editing an approved order) — but nothing protected the CONTENT or the EXISTENCE of a request
awaiting review.

Proven live 2026-07-28 as an ordinary worker: rewrote ANOTHER worker's pending order from
PHP 500,000 to PHP 9,999,999 and replaced its scope text, and the row still read
`requested_by = Wilfredo Malabanan`. The same worker could DELETE a pending order outright.

WHY THAT IS THE WORST PLACE FOR IT TO BE OPEN: the supervisor approves WHAT THEY ARE SHOWN, and
what they are shown was editable by anyone in the hive right up to the moment they clicked. There is
no auth_uid on this table (six of seven project tables lack one) and `projects` writes nothing to
hive_audit_log, so nothing recorded that the figure changed or who changed it.

THE GUARD IS IMMUTABILITY, NOT A ROLE CHECK, and the legitimate callers were measured before
tightening: there are exactly THREE update paths in the codebase (approveCO / rejectCO / cancelCO),
all of which set `status` plus the approver fields; there is NO edit-CO path anywhere and NO delete
path in any page or edge function. The commercial terms were already write-once in practice, so
making the database agree breaks zero callers — and immutability is a stronger, simpler guarantee
than "who may edit". A mistaken order is CANCELLED and re-raised, which leaves the original visible.

WHAT THIS GATE HOLDS:
  1. the trigger and its function still exist, and the trigger still covers UPDATE **and** DELETE
     (dropping DELETE would silently restore the "make it disappear" path);
  2. every commercial term is still named in the immutability check — a term dropped from that list
     becomes quietly editable again, which is the exact failure this arc found;
  3. status / approved_by / approved_at / rejection_reason are NOT frozen, because freezing them
     would break the lifecycle the table exists for (a guard that blocks approval is not a fix);
  4. LIVE: the trigger is actually attached and enabled on the table.

Live tier SKIPS cleanly (exit 0) without docker. Self-test: --selftest.
"""
from __future__ import annotations
import io, json, subprocess, sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GREEN, RED, YELLOW, BOLD, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"
ROOT = Path(__file__).resolve().parent.parent
MIG = ROOT / "supabase" / "migrations" / "20260728000022_a_change_order_is_a_contract_not_a_draft.sql"

# The commercial terms of a raised amendment. Each must stay in the immutability comparison.
FROZEN_TERMS = [
    "co_number", "title", "scope_change", "reason",
    "cost_impact_php", "schedule_impact_days", "requested_by",
    "project_id", "hive_id",
]

# The lifecycle fields. These must stay MUTABLE or the table stops working.
MUST_STAY_MUTABLE = ["status", "approved_by", "approved_at", "rejection_reason"]


def psql(sql):
    try:
        p = subprocess.run(["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres",
                            "-d", "postgres", "-t", "-A", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=45)
        return None if p.returncode != 0 else (p.stdout or "").strip()
    except Exception:
        return None


def selftest():
    probs = []
    if len(FROZEN_TERMS) < 9:
        probs.append("FROZEN_TERMS shrank — a commercial term would become editable again")
    for must in ("cost_impact_php", "schedule_impact_days", "requested_by"):
        if must not in FROZEN_TERMS:
            probs.append(f"{must} must be frozen — it is what makes the row a commitment")
    for keep in MUST_STAY_MUTABLE:
        if keep in FROZEN_TERMS:
            probs.append(f"{keep} must stay MUTABLE — freezing it breaks approve/reject/cancel")
    if not MIG.exists():
        probs.append("the migration this gate guards is missing")
    if probs:
        print("SELFTEST FAIL:")
        for x in probs:
            print("  " + x)
    else:
        print("SELFTEST PASS")
    return 1 if probs else 0


def main():
    if "--selftest" in sys.argv:
        return selftest()

    print(f"\n{BOLD}CHANGE-ORDER IMMUTABILITY (a raised amendment is a contract, not a draft){RESET}")
    print("-" * 74)
    fails = 0
    sql = MIG.read_text(encoding="utf-8", errors="replace") if MIG.exists() else ""

    checks = [
        ("guard function defined", "FUNCTION public.guard_change_order_terms_immutable()" in sql),
        # DELETE coverage is called out separately: losing it silently restores "make it disappear".
        ("trigger covers UPDATE and DELETE", "BEFORE UPDATE OR DELETE ON public.project_change_orders" in sql),
        ("delete refused with a reason", "cannot be deleted" in sql and "Cancel it instead" in sql),
        ("service_role path preserved", "auth.uid() IS NULL" in sql),
    ]
    for term in FROZEN_TERMS:
        checks.append((f"{term} frozen", f"NEW.{term}" in sql and "IS DISTINCT FROM" in sql))
    for keep in MUST_STAY_MUTABLE:
        # The lifecycle fields must NOT appear in the frozen comparison.
        checks.append((f"{keep} still mutable", f"NEW.{keep}" not in sql))

    for label, ok in checks:
        if ok:
            print(f"  {GREEN}PASS{RESET}  {label}")
        else:
            fails += 1
            print(f"  {RED}FAIL{RESET}  {label}")

    live = 0
    if psql("SELECT 1;") is None:
        print(f"  {YELLOW}SKIP{RESET}  docker psql unavailable — attachment not checked")
    else:
        live = 1
        raw = psql("SELECT t.tgenabled FROM pg_trigger t "
                   "WHERE t.tgrelid = 'public.project_change_orders'::regclass "
                   "AND t.tgname = 'trg_change_order_terms_immutable' AND NOT t.tgisinternal;")
        if raw and raw.strip() in ("O", "A", "R"):
            print(f"  {GREEN}PASS{RESET}  trigger attached and enabled on project_change_orders")
        else:
            fails += 1
            print(f"  {RED}FAIL{RESET}  trigger is missing or DISABLED on project_change_orders "
                  f"(tgenabled={raw!r}) — a disabled trigger looks present and enforces nothing")

    print(f"\n  Summary: {len(checks) + live - fails} pass · {fails} fail")
    (ROOT / "change_order_immutability_report.json").write_text(
        json.dumps({"validator": "change_order_immutability",
                    "frozen_terms": FROZEN_TERMS, "fail": fails}, indent=2), encoding="utf-8")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
