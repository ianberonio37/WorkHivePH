#!/usr/bin/env python3
"""validate_ai_retrieval_isolation.py — Arc H H1 keystone: AI retrieval RPCs must not bypass tenancy.

THE BUG CLASS (OWASP LLM08 Vector & Embedding Weaknesses + the Arc-G DEFINER bypass on the READ path):
a SECURITY DEFINER function runs as its OWNER and BYPASSES Row-Level Security. The semantic-search /
RAG-retrieval RPCs (match_procedural_memories, semantic_search_kb, semantic_search_kg_facts, …) are
DEFINER, filter rows by a CLIENT-SUPPLIED `p_hive_id` (or `p_auth_uid`) with NO membership check, and
are GRANTed to anon+authenticated. So any user/anon can pass ANOTHER hive's id + an embedding and
retrieve that hive's KB documents / knowledge-graph facts / agent procedural-memories cross-tenant —
the read-path twin of the Arc-G mutation IDOR (`validate_definer_tenant_gate`, which only checked writes).

RULE: a user-callable SECURITY DEFINER function that filters by a client `hive_id`/`auth_uid` parameter
must SELF-GATE — the param must be verified against the caller's membership (`user_hive_ids()` /
`hive_members` + `auth.uid()`), or the function must be exempt with EVIDENCE (global/shared KB with NO
hive param, service-role-only, or a self-scoped `auth.uid()` read). Baseline 0 ungated.

Live introspection via `docker exec supabase_db_workhive psql`. Hermetic to the local DB.

USAGE:      python tools/validate_ai_retrieval_isolation.py
Self-test:  python tools/validate_ai_retrieval_isolation.py --self-test   (proves the teeth)
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

# Safe-by-design retrieval DEFINER fns (no tenant param OR proven exempt). Each must have a reason.
SAFE_BY_DESIGN = {
    "semantic_search_industry_standards": "reads the GLOBAL industry-standards KB — shared, no hive param",
    "semantic_search_platform_kg_facts":  "reads the GLOBAL platform knowledge graph — shared, no hive param",
    "rerank_kb_chunks":                   "pure reranker over caller-supplied chunk ids — no hive-scoped read",
    "match_persona_knowledge":            "global persona KB, security_invoker (RLS applies), no hive param",
}


def psql_json(sql: str):
    try:
        p = subprocess.run(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres", "-tA", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        if p.returncode != 0:
            return None
        out = p.stdout.strip()
        return json.loads(out) if out else []
    except Exception:
        return None


def gather():
    return psql_json("""
      SELECT coalesce(json_agg(json_build_object(
        'name', p.proname,
        'secdef', p.prosecdef,
        'is_trigger', (p.prorettype = 'trigger'::regtype),
        'args', pg_get_function_arguments(p.oid),
        'user_callable', (p.proacl IS NULL) OR EXISTS (
                                 SELECT 1 FROM aclexplode(p.proacl) a LEFT JOIN pg_roles r ON r.oid=a.grantee
                                 WHERE a.privilege_type='EXECUTE'
                                   AND (a.grantee = 0 OR r.rolname IN ('anon','authenticated'))),
        'body', pg_get_functiondef(p.oid))), '[]'::json)
      FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
      WHERE n.nspname='public' AND p.prosecdef AND p.prorettype <> 'trigger'::regtype;""")


# a client tenant-scope parameter the body filters on
TENANT_PARAM = re.compile(r"\b(p_hive_id|match_hive_id|hive_id|p_auth_uid|match_auth_uid|auth_uid)\b", re.I)


def has_tenant_param(args: str) -> str | None:
    m = re.search(r"\b(p_hive_id|match_hive_id|p_auth_uid|match_auth_uid)\b", args, re.I)
    return m.group(1) if m else None


def filters_on_param(body: str, param: str) -> bool:
    nc = re.sub(r"--.*", "", body)
    # e.g. "hive_id = p_hive_id" / "f.hive_id = p_hive_id" / "= match_hive_id"
    return bool(re.search(rf"=\s*{re.escape(param)}\b", nc) or re.search(rf"\b{re.escape(param)}\s*=", nc))


def has_self_gate(body: str) -> bool:
    """A real membership self-gate: user_hive_ids() / hive_members + auth.uid()."""
    nc = re.sub(r"--.*", "", body)
    return bool(re.search(r"user_can_access_hive\s*\(", nc)
                or re.search(r"user_hive_ids\s*\(", nc)
                or (re.search(r"hive_members", nc) and re.search(r"auth\.uid\(\)", nc))
                or re.search(r"auth\.uid\(\)\s*=\s*\w*auth_uid", nc))


def evaluate(defs):
    findings, gated, exempt = [], [], []
    for d in defs:
        name, body, args = d["name"], d["body"], d["args"]
        if not d.get("user_callable", True):
            continue  # service-role only — trusted boundary (out of scope)
        param = has_tenant_param(args)
        if not param:
            continue  # no client tenant param → out of scope (global KB etc.)
        if not filters_on_param(body, param):
            continue  # takes the param but doesn't filter on it directly → out of scope
        if has_self_gate(body):
            gated.append((name, param, "membership self-gate")); continue
        if name in SAFE_BY_DESIGN:
            exempt.append((name, param, SAFE_BY_DESIGN[name])); continue
        findings.append((name, param))
    return findings, gated, exempt


def main() -> int:
    self_test = "--self-test" in sys.argv[1:]
    defs = gather()
    if defs is None:
        print(f"  {RED}ERROR{RST}: could not introspect (is {DB} running?)")
        return 1
    findings, gated, exempt = evaluate(defs)

    print("=" * 76)
    print("  Arc H H1 — AI retrieval tenant-isolation (OWASP LLM08; DEFINER read bypasses RLS)")
    print("=" * 76)
    print(f"  {len(defs)} DEFINER fns · self-gated: {len(gated)} · exempt-by-evidence: {len(exempt)} · findings: {len(findings)}")
    for n, p, why in exempt:
        print(f"    {YEL}safe{RST} {n} ({p}) — {why}")
    for n, p, why in gated:
        print(f"    {GREEN}gated{RST} {n} ({p}) — {why}")

    if self_test:
        synth = [{"name": "__synthetic_ungated__", "secdef": True, "is_trigger": False,
                  "user_callable": True, "args": "p_query vector, p_hive_id uuid",
                  "body": "create function f() returns setof x as $$ select * from kb where hive_id = p_hive_id $$"}]
        f2, *_ = evaluate(synth)
        ok = any(n == "__synthetic_ungated__" for n, _ in f2)
        print(f"\n  TEETH [{GREEN+'PASS'+RST if ok else RED+'FAIL'+RST}] a user-callable DEFINER read filtering on a client hive_id with no self-gate is caught")
        if not ok:
            return 1

    print()
    if findings:
        for n, p in findings:
            print(f"  {RED}FAIL{RST}  {n} (DEFINER) filters by client {p} with NO membership gate + user-callable — cross-tenant retrieval IDOR (LLM08)")
        print(f"\n  {RED}{len(findings)} ungated AI-retrieval RPC(s){RST} (baseline 0) — cross-tenant vector/knowledge leak")
        return 1
    print(f"  {GREEN}PASS{RST} — every user-callable DEFINER retrieval RPC self-gates tenancy or is exempt-by-evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
