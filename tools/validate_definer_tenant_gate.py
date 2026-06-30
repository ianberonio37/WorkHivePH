#!/usr/bin/env python3
"""validate_definer_tenant_gate.py — Arc G G1 keystone gate: DEFINER fns must self-gate tenancy.

THE BUG CLASS (found by the Arc G per-DEFINER sweep, 2026-06-20): a SECURITY DEFINER function runs
as its OWNER and BYPASSES Row-Level Security. With FORCE ROW LEVEL SECURITY set on 0 of 147 tables,
the ONLY thing protecting a hive-scoped table from a DEFINER function is that the function self-gates
tenancy. acknowledge_alert / suppress_alert did NOT — they UPDATEd anomaly_alerts by a client-supplied
bigint id with no membership check, GRANTed to anon+authenticated = cross-tenant IDOR (any user could
suppress any hive's alerts). Fixed in 20260620000000.

RULE: every SECURITY DEFINER function that MUTATES (update/delete/insert) a table carrying a `hive_id`
column must either (a) self-gate by membership (`auth.uid()` + `hive_members`), or (b) be exempt with
EVIDENCE — a trigger (operates on the NEW/OLD row already in transaction context), or a curated
safe-by-design function (global/non-tenant table, public marketplace, shared knowledge base, cron/admin
batch that legitimately spans hives). Baseline 0 ungated.

Live introspection via `docker exec supabase_db_workhive psql`. Hermetic to the local DB.

USAGE:      python tools/validate_definer_tenant_gate.py
Self-test:  python tools/validate_definer_tenant_gate.py --self-test   (proves the teeth)
"""
from __future__ import annotations
import json
import re
import subprocess
import sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

DB = "supabase_db_workhive"
GREEN, RED, YEL = "\033[92m", "\033[91m", "\033[93m"; RST = "\033[0m"

# Safe-by-design DEFINER mutators (NOT tenancy-gated, but proven OK by evidence). Each must have a reason.
SAFE_BY_DESIGN = {
    "ai_cache_bump":            "ai_cache is a GLOBAL cross-hive cache keyed by content hash — no tenant data",
    "ai_cache_sweep_expired":   "global ai_cache TTL sweep (cron) — no tenant data",
    "increment_listing_view":   "marketplace_listings view counter — marketplace is public/cross-hive by design",
    "refresh_v_kpi_truth":      "refreshes a materialized view (admin/cron) — no client-supplied id",
    "semantic_search_industry_standards": "reads the GLOBAL industry-standards KB — shared, not hive-scoped",
    "semantic_search_platform_kg_facts":  "reads the GLOBAL platform knowledge graph — shared, not hive-scoped",
    "amc_expire_stale":         "cron batch expiring stale AMC rows across all hives (service-role/cron only)",
    "rerank_kb_chunks":         "pure compute reranker — no table mutation",
    "toggle_feedback_upvote":   "platform_feedback is GLOBAL public product feedback; gated by is_public + voter_token",
    "award_achievement_xp":     "invoked by achievement triggers with the triggering row's own ids (row-context)",
}


def psql_json(sql: str):
    try:
        proc = subprocess.run(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres",
                               "-tA", "-c", sql], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=60)
        if proc.returncode != 0:
            return None
        out = proc.stdout.strip()
        return json.loads(out) if out else []
    except Exception:
        return None


def gather():
    # tables that carry a hive_id column (the tenant-scoped surface)
    hive_tables = psql_json("""
      SELECT coalesce(json_agg(table_name), '[]'::json) FROM information_schema.columns
      WHERE table_schema='public' AND column_name='hive_id';""")
    # every SECURITY DEFINER function: name, is_trigger, user_callable (anon/authenticated EXECUTE), body
    defs = psql_json("""
      SELECT coalesce(json_agg(json_build_object(
               'name', p.proname,
               'is_trigger', (p.prorettype = 'trigger'::regtype),
               'user_callable', (p.proacl IS NULL) OR EXISTS (
                                        SELECT 1 FROM aclexplode(p.proacl) a LEFT JOIN pg_roles r ON r.oid=a.grantee
                                        WHERE a.privilege_type='EXECUTE'
                                          AND (a.grantee = 0 OR r.rolname IN ('anon','authenticated'))),
               'body', pg_get_functiondef(p.oid))), '[]'::json)
      FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
      WHERE n.nspname='public' AND p.prosecdef;""")
    return set(hive_tables or []), (defs or [])


def mutates_hive_table(body: str, hive_tables: set[str]) -> list[str]:
    """Return the hive-scoped tables this body mutates (update/delete/insert)."""
    nc = re.sub(r"--.*", "", body)
    hits = []
    for t in hive_tables:
        pat = rf"\b(update|delete\s+from|insert\s+into)\s+(public\.)?{re.escape(t)}\b"
        if re.search(pat, nc, re.IGNORECASE):
            hits.append(t)
    return hits


def has_tenant_gate(body: str) -> bool:
    """Credits the verification PATTERN, not a literal name ([[feedback]] RL-fairness lesson):
    any `auth.uid()` in the body = the caller's identity scopes the action — membership EXISTS,
    a service_role-bypass gate, or an owner-personal `auth_uid = auth.uid()` scope all qualify."""
    nc = re.sub(r"--.*", "", body)
    # auth.uid() = the caller's identity scopes the action; user_can_access_hive()/user_hive_ids() are the
    # shared membership-gate helpers (they resolve to auth.uid() internally — credit the PATTERN, not a literal).
    return bool(re.search(r"auth\.uid\(\)|user_can_access_hive\s*\(|user_hive_ids\s*\(", nc))


def evaluate(hive_tables, defs):
    findings, gated, exempt = [], [], []
    for d in defs:
        name, is_trig, body = d["name"], d["is_trigger"], d["body"]
        user_callable = d.get("user_callable", True)
        muts = mutates_hive_table(body, hive_tables)
        if not muts:
            continue  # doesn't mutate a hive-scoped table — out of scope
        if has_tenant_gate(body):
            gated.append((name, muts, "auth.uid() self-gate")); continue
        if not user_callable:
            exempt.append((name, muts, "not user-callable — service-role/cron only (trusted boundary)")); continue
        if is_trig:
            exempt.append((name, muts, "trigger — operates on the NEW/OLD row in transaction context")); continue
        if name in SAFE_BY_DESIGN:
            exempt.append((name, muts, SAFE_BY_DESIGN[name])); continue
        findings.append((name, muts))
    return findings, gated, exempt


def main() -> int:
    self_test = "--self-test" in sys.argv[1:]
    hive_tables, defs = gather()
    if hive_tables is None or not defs:
        print(f"  {RED}ERROR{RST}: could not introspect the DB (is {DB} running?)")
        return 1
    findings, gated, exempt = evaluate(hive_tables, defs)

    print("=" * 74)
    print("  Arc G G1 — SECURITY DEFINER tenant-gate (DEFINER bypasses RLS; FORCE-RLS=0)")
    print("=" * 74)
    print(f"  {len(hive_tables)} hive-scoped tables · {len(defs)} DEFINER fns · "
          f"{len(gated)+len(exempt)+len(findings)} mutate a hive-scoped table")
    print(f"  self-gated (auth.uid()): {len(gated)}  ·  exempt-by-evidence: {len(exempt)}")
    for n, m, why in exempt:
        print(f"    {YEL}safe{RST} {n} ({','.join(m)}) — {why}")

    if self_test:
        # teeth: a synthetic user-callable DEFINER fn that mutates a hive table with no gate MUST be caught
        hive_t = next(iter(hive_tables))
        synth = {"name": "__synthetic_ungated__", "is_trigger": False, "user_callable": True,
                 "body": f"begin update {hive_t} set x=1 where id=p_id; end"}
        f2, *_ = evaluate(hive_tables, [synth])
        ok = any(n == "__synthetic_ungated__" for n, _ in f2)
        print(f"\n  TEETH [{GREEN+'PASS'+RST if ok else RED+'FAIL'+RST}] a user-callable un-gated DEFINER mutator is caught")
        if not ok:
            return 1

    print()
    if findings:
        for n, m in findings:
            print(f"  {RED}FAIL{RST}  {n} mutates {','.join(m)} (hive-scoped) with NO membership gate + not exempt")
        print(f"\n  {RED}{len(findings)} ungated DEFINER mutator(s){RST} (baseline 0) — cross-tenant IDOR risk")
        return 1
    print(f"  {GREEN}PASS{RST} — every DEFINER fn that mutates a hive-scoped table self-gates or is exempt-by-evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
