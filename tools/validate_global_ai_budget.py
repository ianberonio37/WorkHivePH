#!/usr/bin/env python3
"""validate_global_ai_budget.py — FREE_TIER_QUOTA_ROADMAP Q6 ratchet.

The per-hive/per-user/per-solo/per-route gates all key on a TENANT. None protect the
one resource that binds first at 10k (grounded 2026-07-05): the LLM provider budget is
ORG-LEVEL, a single key shared across ALL tenants. This gate proves the GLOBAL layer
exists, is ATOMIC (a single hot counter row must be row-locked, not read-then-upsert),
FAILS OPEN (a global chokepoint must never hard-block all AI), and is WIRED at the
gateway chokepoint. It FAILs if any of those regress.

Checks (each with teeth via --self-test):
  C1 table       ai_global_budget singleton + shed/deny telemetry columns
  C2 atomic RPC  consume_ai_global_budget is SECURITY DEFINER + FOR UPDATE (row lock) + search_path pinned
  C3 seed        singleton 'global' row seeded ON CONFLICT DO NOTHING
  C4 grant       EXECUTE granted so the edge role can call the RPC
  C5 breaker     daily circuit-breaker branch (day_count >= p_rpd -> deny all)
  C6 smoother    per-minute burst wall SHEDS background but PASSES interactive (p_is_background gate)
  C7 fail-open   checkGlobalAIBudget returns allowed=true on RPC error/exception
  C8 wired       ai-gateway imports checkGlobalAIBudget, calls it, returns globalBudgetResponse

USAGE:      python tools/validate_global_ai_budget.py
Self-test:  python tools/validate_global_ai_budget.py --self-test
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = ROOT / "supabase" / "migrations"
RATE_LIMIT = ROOT / "supabase" / "functions" / "_shared" / "rate-limit.ts"
GATEWAY = ROOT / "supabase" / "functions" / "ai-gateway" / "index.ts"
GREEN, RED = "\033[92m", "\033[91m"
RST = "\033[0m"


def _migrations_text() -> str:
    if not MIGRATIONS.is_dir():
        return ""
    return "\n".join(p.read_text(encoding="utf-8", errors="replace")
                     for p in sorted(MIGRATIONS.glob("*.sql")))


def evaluate(mig: str, rl: str, gw: str) -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []

    # C1 — singleton table with telemetry columns
    has_table = bool(re.search(r"CREATE TABLE (?:IF NOT EXISTS )?public\.ai_global_budget", mig, re.I))
    has_singleton = bool(re.search(r"CHECK\s*\(\s*id\s*=\s*'global'\s*\)", mig, re.I))
    has_telem = ("shed_count_today" in mig and "deny_count_today" in mig)
    c1 = has_table and has_singleton and has_telem
    checks.append(("C1 table", c1,
                   "ai_global_budget singleton + shed/deny telemetry"
                   if c1 else f"missing (table={has_table} singleton={has_singleton} telem={has_telem})"))

    # C2 — atomic RPC: SECURITY DEFINER + FOR UPDATE row lock + search_path pinned
    fn_m = re.search(r"CREATE OR REPLACE FUNCTION public\.consume_ai_global_budget.*?\$fn\$;", mig, re.S | re.I)
    fn = fn_m.group(0) if fn_m else ""
    c2 = bool(fn) and ("SECURITY DEFINER" in fn) and ("FOR UPDATE" in fn) and bool(re.search(r"SET search_path\s*=\s*public", fn, re.I))
    checks.append(("C2 atomic RPC", c2,
                   "consume_ai_global_budget: SECURITY DEFINER + FOR UPDATE + search_path"
                   if c2 else "RPC missing atomicity guard (need SECURITY DEFINER + FOR UPDATE + search_path)"))

    # C3 — singleton seeded
    c3 = bool(re.search(r"INSERT INTO public\.ai_global_budget\s*\(id\)\s*VALUES\s*\('global'\)\s*ON CONFLICT", mig, re.I))
    checks.append(("C3 seed", c3, "singleton 'global' seeded ON CONFLICT" if c3 else "missing singleton seed"))

    # C4 — EXECUTE granted
    c4 = bool(re.search(r"GRANT EXECUTE ON FUNCTION public\.consume_ai_global_budget", mig, re.I))
    checks.append(("C4 grant", c4, "EXECUTE granted to edge role" if c4 else "missing GRANT EXECUTE"))

    # C5 — daily circuit-breaker branch (deny ALL when day pool exhausted)
    c5 = bool(re.search(r"IF\s+v_day\s*>=\s*p_rpd\s+THEN", fn, re.I)) and ("'global-day'" in fn)
    checks.append(("C5 breaker", c5, "daily circuit-breaker denies all at pool exhaustion"
                   if c5 else "missing daily circuit-breaker branch"))

    # C6 — per-minute smoother sheds background but passes interactive
    c6 = bool(re.search(r"IF\s+v_min\s*>=\s*p_rpm\s+AND\s+p_is_background\s+THEN", fn, re.I)) and ("'global-minute'" in fn)
    checks.append(("C6 smoother", c6, "minute wall sheds background, passes interactive (voice)"
                   if c6 else "missing background-only shed at minute wall"))

    # C7 — fail-open in checkGlobalAIBudget (error AND catch paths return allowed:true)
    guard_m = re.search(r"export async function checkGlobalAIBudget\b.*?\n}", rl, re.S)
    guard = guard_m.group(0) if guard_m else ""
    # both the (error || !row) branch and the catch branch must return allowed:true
    failopen = len(re.findall(r"return\s*\{\s*allowed:\s*true", guard)) >= 2
    c7 = bool(guard) and failopen and ("consume_ai_global_budget" in guard)
    checks.append(("C7 fail-open", c7, "checkGlobalAIBudget fails open on error+exception"
                   if c7 else "guard missing or not fail-open (need allowed:true on both error and catch)"))

    # C8 — wired at the gateway chokepoint
    c8 = ("checkGlobalAIBudget" in gw) and ("globalBudgetResponse" in gw) and bool(
        re.search(r"await\s+checkGlobalAIBudget\s*\(", gw))
    checks.append(("C8 wired", c8, "ai-gateway calls checkGlobalAIBudget + returns globalBudgetResponse"
                   if c8 else "gateway not wired to the global guard"))

    # C9 — chain-depth telemetry: migration has depth cols + recorder RPC + grant; the
    # ai-chain exposes the onServed hook; the gateway feeds it via record_ai_chain_depth.
    mig_depth = ("depth_samples_today" in mig and "depth_sum_today" in mig
                 and bool(re.search(r"CREATE OR REPLACE FUNCTION public\.record_ai_chain_depth", mig, re.I))
                 and bool(re.search(r"GRANT EXECUTE ON FUNCTION public\.record_ai_chain_depth", mig, re.I)))
    gw_depth = ("record_ai_chain_depth" in gw) and ("onServed" in gw)
    c9 = mig_depth and gw_depth
    checks.append(("C9 depth-telem", c9, "chain-depth recorder RPC + onServed hook wired at gateway"
                   if c9 else f"chain-depth telemetry incomplete (migration={mig_depth} gateway={gw_depth})"))

    return checks


def main() -> int:
    self_test = "--self-test" in sys.argv[1:]
    mig = _migrations_text()
    rl = RATE_LIMIT.read_text(encoding="utf-8", errors="replace") if RATE_LIMIT.exists() else ""
    gw = GATEWAY.read_text(encoding="utf-8", errors="replace") if GATEWAY.exists() else ""
    checks = evaluate(mig, rl, gw)

    print("=" * 74)
    print("  FREE_TIER_QUOTA_ROADMAP Q6 — global org-shared LLM budget guard")
    print("=" * 74)
    passed = sum(1 for _, ok, _ in checks if ok)
    for name, ok, detail in checks:
        tag = f"{GREEN}ok{RST}  " if ok else f"{RED}FAIL{RST}"
        print(f"  {tag} {name:16s} {detail}")
    print(f"\n  {passed}/{len(checks)} checks green")

    if self_test:
        # TEETH 1: empty inputs -> every check fails.
        empty_all_fail = all(not ok for _, ok, _ in evaluate("", "", ""))
        # TEETH 2: a gateway that imports but never CALLS the guard -> C8 fails.
        gw_no_call = 'import { checkGlobalAIBudget, globalBudgetResponse } from "x";'
        c8_only = dict((n, ok) for n, ok, _ in evaluate(mig, rl, gw_no_call))
        wiring_tooth = c8_only.get("C8 wired") is False
        # TEETH 3: a guard with only ONE fail-open path (error branch hard-denies) -> C7 fails.
        # Synthetic (deterministic — independent of the real file's exact whitespace).
        rl_one_failopen = (
            "export async function checkGlobalAIBudget(db) {\n"
            "  try {\n"
            '    const { data, error } = await db.rpc("consume_ai_global_budget", {});\n'
            "    const row = data[0];\n"
            "    if (error || !row) { return { allowed: false, minute_remaining: 0, day_remaining: 0 }; }\n"
            "    return { allowed: row.allowed };\n"
            "  } catch {\n"
            "    return { allowed: true, minute_remaining: rpm, day_remaining: rpd };\n"
            "  }\n"
            "}"
        )
        c7_tooth = dict((n, ok) for n, ok, _ in evaluate(mig, rl_one_failopen, gw)).get("C7 fail-open") is False
        good = empty_all_fail and wiring_tooth and c7_tooth
        print(f"  TEETH [{GREEN+'PASS'+RST if good else RED+'FAIL'+RST}] "
              f"empty=all-fail:{empty_all_fail}  no-call->C8-fail:{wiring_tooth}  one-failopen->C7-fail:{c7_tooth}")
        if not good:
            return 1

    print()
    failed = [n for n, ok, _ in checks if not ok]
    if failed:
        print(f"  {RED}FAIL{RST} — {len(failed)} check(s) regressed: {', '.join(failed)}")
        return 1
    print(f"  {GREEN}PASS{RST} — global org-shared LLM budget guard is present, atomic, fail-open, and wired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
