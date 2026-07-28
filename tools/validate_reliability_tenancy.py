#!/usr/bin/env python3
"""
validate_reliability_tenancy.py — AHK4: reliability data is hive-private, PARENT included.

THE CLASS. FMEA modes, RCM strategies, Weibull fits and P-F intervals are competitive plant
knowledge — what breaks, how often, and what a plant does about it. Cross-hive read or write is a
leak, and the write half is the one that was open.

FOUND BY THE AH13 WALK (2026-07-28). Reads were already correctly isolated: 0 rows across all four
tables when read as a member of another hive, verified live and worth recording as a real result.
Writes had the PM13 gap — the WITH CHECK validated that hive_id is one the caller belongs to and
said NOTHING about whether the PARENT it points at lives there. Probed live, both accepted:

    rcm_fmea_modes  hive_id = MINE, asset_id     = another hive's asset node
    rcm_strategies  hive_id = MINE, fmea_mode_id = another hive's failure mode

An instrument error nearly recorded that walk as clean: the first probe came back BLOCKED with
23514 and it looked like isolation holding. 23514 is check_violation, not 42501 — it was the
decision-enum CHECK rejecting an invalid value of the probe's own making, and the tenancy question
was still untested. Verify WHAT blocked a write, never merely THAT something did.

Migration 20260728000017 closed it with four RESTRICTIVE policies. This gate keeps them closed.

WHY RESTRICTIVE MATTERS ENOUGH TO ASSERT SEPARATELY: a PERMISSIVE policy ORs with the existing ones,
so re-adding these as permissive would not tighten anything — it would WIDEN access while looking
like a guard. Only RESTRICTIVE ANDs. A gate that checked merely "a policy named X exists" would
pass that rewrite happily.

Live tier SKIPS cleanly (exit 0) without docker. Self-test: --selftest.
"""
from __future__ import annotations
import io, json, subprocess, sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GREEN, RED, YELLOW, BOLD, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"
ROOT = Path(__file__).resolve().parent.parent

# (table, policy, child fk column, parent table, parent's hive-bearing column)
GUARDED = [
    ("rcm_fmea_modes", "rcm_fmea_modes_parent_hive_guard", "asset_id",     "asset_nodes",     "hive_id"),
    ("rcm_strategies", "rcm_strategies_parent_hive_guard", "fmea_mode_id", "rcm_fmea_modes",  "hive_id"),
    ("weibull_fits",   "weibull_fits_parent_hive_guard",   "asset_id",     "asset_nodes",     "hive_id"),
    ("pf_intervals",   "pf_intervals_parent_hive_guard",   "asset_id",     "asset_nodes",     "hive_id"),
]


def psql(sql):
    try:
        p = subprocess.run(["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres",
                            "-d", "postgres", "-t", "-A", "-F", "|", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60)
        return None if p.returncode != 0 else (p.stdout or "").strip()
    except Exception:
        return None


def selftest():
    probs = []
    if len(GUARDED) < 4:
        probs.append("GUARDED shrank — a reliability table lost its parent-hive guard from the gate")
    tables = {g[0] for g in GUARDED}
    for required in ("rcm_fmea_modes", "rcm_strategies", "weibull_fits", "pf_intervals"):
        if required not in tables:
            probs.append(f"{required} must be covered — it holds competitive plant knowledge")
    # The strategy guard must chain through the MODE, not the asset: a strategy has no asset_id.
    strat = [g for g in GUARDED if g[0] == "rcm_strategies"]
    if strat and strat[0][3] != "rcm_fmea_modes":
        probs.append("rcm_strategies must be validated against its FMEA MODE's hive, not an asset's")
    print("SELFTEST PASS" if not probs else "SELFTEST FAIL:\n  " + "\n  ".join(probs))
    return 1 if probs else 0


def main():
    if "--selftest" in sys.argv:
        return selftest()

    print(f"\n{BOLD}RELIABILITY TENANCY (a child row's PARENT must live in its own hive){RESET}")
    print("-" * 74)

    if psql("SELECT 1;") is None:
        print(f"  {YELLOW}SKIP{RESET}  docker psql unavailable")
        return 0

    fails = 0
    checked = 0
    report = {}

    for table, policy, fk, parent, parent_hive in GUARDED:
        row = psql(
            "SELECT p.permissive, COALESCE(pg_get_expr(p.polwithcheck, p.polrelid), '') "
            "FROM (SELECT polname, polpermissive AS permissive, polwithcheck, polrelid "
            "      FROM pg_policy WHERE polrelid = 'public.{t}'::regclass) p "
            "WHERE p.polname = '{n}';".format(t=table, n=policy))
        checked += 1
        if not row:
            fails += 1
            report[table] = "missing"
            print(f"  {RED}FAIL{RESET}  {table}: {policy} is GONE — a row may again claim a parent "
                  f"in another hive")
            continue

        parts = row.split("|", 1)
        permissive = (parts[0] or "").strip()
        expr = parts[1] if len(parts) > 1 else ""

        # PERMISSIVE ('t') ORs with the others and would WIDEN, not tighten.
        if permissive != "f":
            fails += 1
            report[table] = "permissive"
            print(f"  {RED}FAIL{RESET}  {table}: {policy} is PERMISSIVE — it ORs with the existing "
                  f"policies and widens access instead of restricting it")
            continue

        # The WITH CHECK must actually reach the PARENT table and compare its hive.
        reaches_parent = f"public.{parent}" in expr or f" {parent} " in expr
        compares_hive = parent_hive in expr and fk in expr
        if not (reaches_parent and compares_hive):
            fails += 1
            report[table] = "weakened"
            print(f"  {RED}FAIL{RESET}  {table}: {policy} no longer joins {parent} on {fk} to "
                  f"compare {parent_hive} — it is checking the row's own hive only, which is the "
                  f"original gap")
            continue

        report[table] = "guarded"
        print(f"  {GREEN}PASS{RESET}  {table}: RESTRICTIVE, and validates {parent}.{parent_hive} "
              f"via {fk}")

    # LIVE: nothing in the data already violates it. A guard that was added while violations
    # existed would silently keep them — WITH CHECK applies to new rows, never to old ones.
    for table, _policy, fk, parent, _ph in GUARDED:
        raw = psql(
            f"SELECT count(*) FROM public.{table} c JOIN public.{parent} p ON p.id = c.{fk} "
            f"WHERE p.hive_id IS DISTINCT FROM c.hive_id;")
        try:
            n = int((raw or "0").splitlines()[0])
        except (ValueError, IndexError):
            n = -1
        checked += 1
        if n > 0:
            fails += 1
            print(f"  {RED}FAIL{RESET}  {table}: {n} existing row(s) already point at a parent in "
                  f"another hive — WITH CHECK does not apply retroactively")
        elif n < 0:
            print(f"  {YELLOW}WARN{RESET}  {table}: cross-hive row scan did not return a count")
        else:
            print(f"  {GREEN}PASS{RESET}  {table}: 0 existing rows cross a hive boundary")

    print(f"\n  Summary: {checked - fails} pass · {fails} fail")
    (ROOT / "reliability_tenancy_report.json").write_text(
        json.dumps({"validator": "reliability_tenancy", "policies": report, "fail": fails},
                   indent=2), encoding="utf-8")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
