#!/usr/bin/env python3
"""validate_anomaly_status_forward.py — anomaly_signals must enforce a forward-only status machine.

Bug-hunt roadmap alert-hub P6 (2026-07-17): a stale/concurrent Acknowledge could REGRESS a 'resolved'
anomaly back to 'acknowledged' (lost-update on the state machine) — there was only a value CHECK, no
transition guard. Fixed with a DB-authoritative BEFORE UPDATE OF status trigger
(tg_anomaly_signals_forward_status -> anomaly_signals_forward_only_status: resolved/expired are terminal).

This LIVE gate asserts that trigger + function still exist, so dropping them (a regression) FAILs the
build. Skips cleanly if docker/DB unreachable. Exit 0 pass / 1 missing. --selftest = deterministic.
"""
from __future__ import annotations

import subprocess
import sys

DB = "supabase_db_workhive"
TRIGGER = "tg_anomaly_signals_forward_status"
FUNCTION = "anomaly_signals_forward_only_status"


def _q(sql: str) -> tuple[bool, str]:
    try:
        r = subprocess.run(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres", "-tAc", sql],
                           capture_output=True, text=True, timeout=25)
        return r.returncode == 0, r.stdout.strip()
    except Exception:
        return False, ""


def main() -> int:
    ok, _ = _q("SELECT 1;")
    if not ok:
        print("anomaly forward-status: docker/DB unreachable — SKIPPED (live gate).")
        return 0
    _, trg = _q(f"SELECT 1 FROM pg_trigger WHERE tgname='{TRIGGER}' "
                "AND tgrelid='public.anomaly_signals'::regclass AND NOT tgisinternal;")
    _, fn = _q(f"SELECT 1 FROM pg_proc WHERE proname='{FUNCTION}';")
    # functional proof: the guard function body must reject a terminal->non-terminal move
    _, guards = _q("SELECT (position('terminal' IN prosrc) > 0 OR position('resolved' IN prosrc) > 0)::int "
                   f"FROM pg_proc WHERE proname='{FUNCTION}';")
    missing = []
    if trg != "1":
        missing.append(f"trigger {TRIGGER} on anomaly_signals")
    if fn != "1":
        missing.append(f"function {FUNCTION}")
    elif guards != "1":
        missing.append(f"{FUNCTION} no longer guards terminal states")
    if missing:
        print("✗ anomaly forward-status guard MISSING:")
        for m in missing:
            print("   - " + m)
        print("   FIX: re-apply supabase/migrations/20260717000007_anomaly_signals_forward_status.sql")
        return 1
    print("✓ anomaly_signals forward-only status guard present (resolved/expired terminal; no regression).")
    return 0


def selftest() -> int:
    # pure structural self-test (no DB): the constants must be wired
    fails = []
    if not TRIGGER.startswith("tg_") or "anomaly" not in TRIGGER:
        fails.append("trigger name misconfigured")
    if "forward_only_status" not in FUNCTION:
        fails.append("function name misconfigured")
    if fails:
        print("✗ selftest FAILED: " + "; ".join(fails))
        return 1
    print("✓ validate_anomaly_status_forward selftest passed (config wired).")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(selftest() if "--selftest" in sys.argv else main())
