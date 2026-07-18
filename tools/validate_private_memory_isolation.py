#!/usr/bin/env python3
# DEEPWALK-CELL: ai:* D24
"""
validate_private_memory_isolation.py  --  LIVE-tier LOCK for the "private conversation table has a
hive-wide READ policy" leak class.

Found live 2026-07-07 (dim-3): `agent_memory` (raw AI-companion conversation turns —
user_input / assistant_response / turn_text) had a SELECT policy `agent_memory_read` whose USING
clause was `auth.uid() = auth_uid OR (active member of the row's hive)`. Because Postgres OR's
permissive policies, ANY hive member could read ANY other member's private companion chat. Proven:
signed in as Leandro I read 13 of Bryan Garcia's private turns. This contradicted the table's own
design ("a worker's question ... doesn't leak"). Fixed (migration 20260707000008) to owner-only.

These tables hold PRIVATE, per-worker conversational data — their SELECT policies must scope to the
OWNER (auth.uid() = auth_uid / worker_id) and must NOT contain a hive_members membership check (a
cross-worker read branch). This gate introspects pg_policies and FAILS if any of them regresses.

Live-tier (skip_if_fast); SKIPS cleanly (exit 0) if the DB is down.

Usage:  python tools/validate_private_memory_isolation.py [--json] [--selftest]
Exit 0 = clean / skipped, 1 = a private table's SELECT policy allows a cross-worker read.
"""
import sys, json, subprocess, re

DOCKER_DB = ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-F", "\t", "-c"]

# Per-worker PRIVATE conversation/memory tables: their SELECT policies must be owner-scoped only.
# (ai_reply_feedback + auth_session_events are DELIBERATELY owner-OR-supervisor, so they are NOT here —
#  a supervisor read branch is legitimate moderation/oversight, not a leak.)
PRIVATE_TABLES = ["agent_memory", "agent_episodic_memory", "voice_journal_entries", "dialog_state"]
# The over-share tell: a SELECT USING predicate that reaches into hive_members (cross-worker read).
HIVE_MEMBER_RE = re.compile(r"hive_members", re.I)
# Owner-scoping tell: the predicate must bind to the caller's own row.
OWNER_RE = re.compile(r"auth\.uid\(\)\s*=\s*(auth_uid|worker_id)", re.I)


def psql(sql):
    try:
        r = subprocess.run(DOCKER_DB + [sql], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=45)
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def load_policies():
    """Return {table: [(policyname, using_predicate), ...]} for SELECT policies, or None if DB down."""
    tables = "','".join(PRIVATE_TABLES)
    out = psql(f"""SELECT tablename, policyname, coalesce(qual,'')
      FROM pg_policies WHERE schemaname='public' AND tablename IN ('{tables}')
        AND cmd IN ('SELECT','ALL');""")
    if out is None:
        return None
    pol = {}
    for ln in out.splitlines():
        parts = ln.split("\t")
        if len(parts) >= 3:
            pol.setdefault(parts[0].strip(), []).append((parts[1].strip(), parts[2].strip()))
    return pol


def analyze(policies):
    viols = []
    for tbl in PRIVATE_TABLES:
        pols = policies.get(tbl, [])
        for name, using in pols:
            if HIVE_MEMBER_RE.search(using):
                viols.append({"table": tbl, "policy": name, "issue": "SELECT policy reaches into hive_members (cross-worker read of private conversation data)"})
            elif not OWNER_RE.search(using):
                viols.append({"table": tbl, "policy": name, "issue": "SELECT policy is not owner-scoped (no auth.uid() = auth_uid/worker_id)"})
    return viols


def selftest():
    good = {
        "agent_memory": [("agent_memory_read", "((auth.uid() = auth_uid) OR (auth.uid() = worker_id))")],
        "voice_journal_entries": [("vj_read", "((auth.uid() IS NOT NULL) AND (auth.uid() = auth_uid))")],
        "dialog_state": [("ds_read", "(auth.uid() = worker_id)")],
    }
    leak = {
        "agent_memory": [("agent_memory_read", "((auth.uid() = auth_uid) OR (EXISTS (SELECT 1 FROM hive_members hm WHERE hm.auth_uid = auth.uid())))")],
        "voice_journal_entries": [("vj_read", "(auth.uid() = auth_uid)")],
        "dialog_state": [("ds_read", "(auth.uid() = worker_id)")],
    }
    open_all = {
        "agent_memory": [("agent_memory_read", "(auth.uid() IS NOT NULL)")],  # not owner-scoped
        "voice_journal_entries": [("vj_read", "(auth.uid() = auth_uid)")],
        "dialog_state": [("ds_read", "(auth.uid() = worker_id)")],
    }
    cases = [("owner-only (fixed)", good, 0), ("hive_members leak (the bug)", leak, 1), ("not owner-scoped", open_all, 1)]
    ok = True
    for name, pol, expect in cases:
        n = len(analyze(pol))
        status = "PASS" if n == expect else "FAIL"
        if n != expect:
            ok = False
        print(f"  selftest {status}: {name}  (expected {expect} viol, got {n})")
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        rc = selftest()
        print("private-memory-isolation selftest:", "OK" if rc == 0 else "FAILED")
        return rc
    as_json = "--json" in sys.argv
    policies = load_policies()
    if policies is None:
        msg = "local DB unreachable — private-memory-isolation check skipped"
        print(json.dumps({"skipped": True, "note": msg}) if as_json else "  SKIP: " + msg)
        return 0
    viols = analyze(policies)
    if as_json:
        print(json.dumps({"tables": PRIVATE_TABLES, "violations": viols, "count": len(viols)}, indent=2))
    else:
        print(f"private-memory-isolation (companion conversation tables are OWNER-read-only) {PRIVATE_TABLES}")
        if not viols:
            print("  PASS: every SELECT policy on the private conversation tables is owner-scoped (no cross-worker read)")
        else:
            print(f"  FAIL: {len(viols)} private-table SELECT policy leak(s):")
            for v in viols:
                print(f"    {v['table']}.{v['policy']}: {v['issue']}")
    return 1 if viols else 0


if __name__ == "__main__":
    sys.exit(main())
