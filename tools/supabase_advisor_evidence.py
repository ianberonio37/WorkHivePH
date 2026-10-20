#!/usr/bin/env python3
"""supabase_advisor_evidence.py - the committed evidence behind BRH classes P..Y (2026-10-21).

Ian, 2026-10-21: *"I just got an email from Vercel and Supabase, kindly check those and add appropriate number of
trajectories in our trajectories roadmap."* Supabase's two emails of 2026-10-20: "Action required: security
vulnerabilities detected in your projects" (critical: rls_disabled_in_public on project workhive) and "Final notice: new
tables in public need grants from October 30". The emails name one lint; the advisor they link holds the whole list.

This tool turns what was read into ONE committed JSON, so tools/bug_hunt_inventory.py measures the classes from a file
(deterministic, replayable) and never from a live connection:
  - the production security advisor (get_advisors type=security through the claude.ai Supabase connector, read-only)
  - production's schema fingerprint (one read-only SELECT through the same connector: every public function's
    definition hash, SECURITY DEFINER and anon EXECUTE; every table/view's columns and RLS; every policy)
  - the local database, read-only: each anon-executable definer function's body (does it check the caller?), the API
    roles' table/view privileges, and which functions a migration meant to close to anon but anon can still run

    python tools/supabase_advisor_evidence.py --advisor .tmp/mail/prod_security_advisors.json \
        --prod-fingerprint .tmp/mail/fp_prod_raw.txt [--out supabase_advisor_evidence.json]

How the two production inputs were read (no credential leaves the connector; both are SELECT-only):
  claude -p "<call get_advisors for project hzyvnjtisfgbksicrouu, type security>" --tools "" \
      --allowedTools mcp__claude_ai_Supabase__get_advisors --setting-sources user --no-session-persistence
  claude -p "<call execute_sql once with .tmp/mail/fingerprint.sql>" --tools "" \
      --allowedTools mcp__claude_ai_Supabase__execute_sql --setting-sources user --no-session-persistence
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = "supabase_db_workhive"
MIG = ROOT / "supabase" / "migrations"
API = ("anon", "authenticated", "service_role")
# a function body that asks who is calling: an account, a role, a membership, an admin check, or an explicit refusal
CALLER_CHECK = re.compile(r"auth\.uid\(\)|auth\.role\(\)|is_platform_admin|user_can_access_hive|is_hive_member|"
                          r"auth_worker_names|current_setting\('request\.jwt|hive_members|raise\s+exception", re.I)


def psql(sql: str) -> str:
    r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-At", "-v",
                        "ON_ERROR_STOP=1"], input=sql, capture_output=True, text=True, encoding="utf-8", timeout=300)
    if r.returncode:
        raise SystemExit(f"local database read failed: {r.stderr.strip()[-300:]}")
    return r.stdout


def strip_sql(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    return re.sub(r"--[^\n]*", " ", sql)


def advisor_findings(path: Path) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    lints = (d.get("result") or d)["lints"]
    out = {}
    bt = chr(92) + chr(96)
    for L in lints:
        out[L["name"]] = {"level": L["level"], "title": L["title"],
                          "findings": [{"schema": (f.get("metadata") or {}).get("schema"),
                                        "name": (f.get("metadata") or {}).get("name"),
                                        "type": (f.get("metadata") or {}).get("type"),
                                        "detail": (f.get("detail") or "").replace(bt, "`"),
                                        "observed_at": f.get("observed_at")} for f in L.get("findings") or []]}
    return out


def prod_fingerprint(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))["result"]
    body = raw[raw.index("[{"):raw.rindex("}]") + 2]
    d = {}
    for r in json.loads(body):
        k, obj, h = r["line"].split("|", 2)
        d[(k, obj)] = h
    return d


def local_fingerprint() -> dict:
    sql = (ROOT / ".tmp" / "mail" / "fingerprint.sql").read_text(encoding="utf-8")
    d = {}
    for ln in psql(sql).splitlines():
        if ln.strip():
            k, obj, h = ln.split("|", 2)
            d[(k, obj)] = h
    return d


def caller_checks(names: list[str]) -> dict:
    if not names:
        return {}
    out = psql("select p.proname || chr(1) || p.prorettype::regtype::text || chr(1) || pg_get_functiondef(p.oid) || chr(2) "
               "from pg_proc p join pg_namespace n on n.oid = p.pronamespace where n.nspname = 'public' and "
               "p.proname = any(array[" + ",".join("'" + x + "'" for x in sorted(set(names))) + "]);")
    res = {}
    for chunk in out.split("\x02"):
        if "\x01" in chunk:
            name, rtype, body = chunk.strip().split("\x01", 2)
            res[name] = {"trigger": rtype == "trigger", "checks_caller": bool(CALLER_CHECK.search(body)),
                         "writes": bool(re.search(r"\b(insert\s+into|update\s+\S+\s+set|delete\s+from)\b", body, re.I))}
    return res


def api_grant_cells() -> list[dict]:
    """(role, kind) cells whose access no migration granted - it rests on Supabase's automatic grant, which stops for new
    tables (and for every replay of the schema) on 2026-10-30."""
    name = r"(?:public\.)?\"?[a-z_][a-z0-9_]*\"?"
    grant = re.compile(r"\bgrant\s+[a-z ,()_]+?\s+on\s+(?:table\s+|sequence\s+)?(" + name + r"(?:\s*,\s*" + name +
                       r")*)\s+to\s+([a-z_, ]+)", re.I)
    explicit: dict[str, set] = {}
    for f in sorted(MIG.glob("*.sql")):
        for m in grant.finditer(strip_sql(f.read_text(encoding="utf-8", errors="replace"))):
            roles = {r.strip().lower() for r in m.group(2).split(",")} & set(API)
            for t in re.split(r"\s*,\s*", m.group(1)):
                explicit.setdefault(t.split(".")[-1].strip('"').lower(), set()).update(roles)
    out = psql("select c.relname || '|' || c.relkind::text || '|' || coalesce((select string_agg(distinct "
               "a.grantee::regrole::text, ',') from aclexplode(c.relacl) a where a.grantee in ('anon'::regrole, "
               "'authenticated'::regrole, 'service_role'::regrole)), '') from pg_class c join pg_namespace n on "
               "n.oid = c.relnamespace where n.nspname = 'public' and c.relkind in ('r', 'p', 'v', 'm') order by 1;")
    kinds = {"r": "table", "p": "table", "v": "view", "m": "materialized view"}
    cells: dict[tuple, list] = {}
    for ln in out.splitlines():
        nm, kind, roles = ln.split("|")
        for role in sorted({r for r in roles.split(",") if r} - explicit.get(nm, set())):
            cells.setdefault((role, kinds[kind]), []).append(nm)
    return [{"role": r, "kind": k, "objects": sorted(v)} for (r, k), v in sorted(cells.items())]


def revokes_that_do_not_hold() -> list[dict]:
    """Functions a migration revoked from anon or PUBLIC that anon can execute today. Supabase grants EXECUTE to anon
    EXPLICITLY on every new function, so `revoke ... from public` never reaches it; and DROP + CREATE (or a new
    signature) restores the defaults, undoing a revoke that did."""
    rx = re.compile(r"\brevoke\s+(?:all|execute)(?:\s+privileges)?\s+on\s+(?:function|routine)\s+(?:public\.)?"
                    r"([a-z_][a-z0-9_]*)\s*\(([^)]*)\)\s+from\s+([a-z_, ]+)", re.I)
    revoked: dict[str, list] = {}
    for f in sorted(MIG.glob("*.sql")):
        for m in rx.finditer(strip_sql(f.read_text(encoding="utf-8", errors="replace"))):
            roles = {r.strip().lower() for r in m.group(3).split(",")}
            if roles & {"anon", "public"}:
                revoked.setdefault(m.group(1).lower(), []).append((f.name, sorted(roles)))
    out = psql("select p.proname || '|' || pg_get_function_identity_arguments(p.oid) || '|' || p.prosecdef::text || '|' || "
               "has_function_privilege('anon', p.oid, 'execute')::text from pg_proc p join pg_namespace n on "
               "n.oid = p.pronamespace where n.nspname = 'public' and p.prokind = 'f';")
    res = []
    for ln in out.splitlines():
        name, args, definer, anon = ln.split("|")
        if anon == "true" and name in revoked:
            last, roles = revoked[name][-1]
            res.append({"name": name, "args": args, "security_definer": definer == "true", "revoked_in": last,
                        "revoked_from": roles,
                        "why": ("revoked from PUBLIC only - anon keeps its own explicit grant" if "anon" not in roles
                                else "revoked from anon, then the function was re-created and took the defaults again")})
    return sorted(res, key=lambda r: r["name"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--advisor", required=True)
    ap.add_argument("--prod-fingerprint", required=True)
    ap.add_argument("--out", default=str(ROOT / "supabase_advisor_evidence.json"))
    a = ap.parse_args()
    adv = advisor_findings(Path(a.advisor))
    P, L = prod_fingerprint(Path(a.prod_fingerprint)), local_fingerprint()
    prod_only = sorted(o for (k, o) in P if (k, o) not in L)
    anon_definer = [f["name"] for f in adv.get("anon_security_definer_function_executable", {}).get("findings", [])]
    checks = caller_checks(anon_definer)
    dropped = {o.split("(")[0] for o in prod_only}
    unchecked = sorted(n for n in set(anon_definer) if n in checks and not checks[n]["trigger"]
                       and not checks[n]["checks_caller"] and n not in dropped)
    doc = {
        "read": "2026-10-21",
        "project": "workhive (hzyvnjtisfgbksicrouu)",
        "source": "Supabase security advisor (get_advisors, type=security) and a read-only schema fingerprint, both through "
                  "the claude.ai Supabase connector; the local database read-only",
        "emails": ["2026-10-20 Action required: security vulnerabilities detected in your projects (rls_disabled_in_public, "
                   "critical, issues as of 17 Oct 2026)",
                   "2026-10-20 Final notice: new tables in public need grants from October 30"],
        "advisor": {k: {"level": v["level"], "title": v["title"], "count": len(v["findings"])} for k, v in adv.items()},
        "P_rls_disabled": [f["name"] for f in adv.get("rls_disabled_in_public", {}).get("findings", [])],
        "Q_prod_only": prod_only,
        "R_definer_views": [f["name"] for f in adv.get("security_definer_view", {}).get("findings", [])],
        "S_anon_definer_unchecked": [{"name": n, "writes": checks[n]["writes"]} for n in unchecked],
        "T_search_path_mutable": sorted(f["name"] for f in adv.get("function_search_path_mutable", {}).get("findings", [])
                                        if f["name"] not in dropped),
        "U_extension_in_public": [f["name"] for f in adv.get("extension_in_public", {}).get("findings", [])],
        "V_matview_in_api": [f["name"] for f in adv.get("materialized_view_in_api", {}).get("findings", [])],
        "W_leaked_password_protection": [f["detail"] for f in adv.get("auth_leaked_password_protection", {}).get("findings", [])],
        "X_api_grant_cells": api_grant_cells(),
        "Y_revokes_that_do_not_hold": [r for r in revokes_that_do_not_hold() if r["name"] not in unchecked],
        "not_seeded": {"rls_enabled_no_policy": "INFO: a table with RLS on and no policy refuses anon and authenticated "
                                                 "entirely - the safe state for a server-only table",
                       "authenticated_security_definer_function_executable": "the signed-in RPC surface; each function's "
                                                 "own caller check is the S and Y classes' subject, not a separate row"},
    }
    Path(a.out).write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {Path(a.out).name}: P {len(doc['P_rls_disabled'])} · Q {len(doc['Q_prod_only'])} · "
          f"R {len(doc['R_definer_views'])} · S {len(doc['S_anon_definer_unchecked'])} · T {len(doc['T_search_path_mutable'])} · "
          f"U {len(doc['U_extension_in_public'])} · V {len(doc['V_matview_in_api'])} · W {len(doc['W_leaked_password_protection'])} · "
          f"X {len(doc['X_api_grant_cells'])} cells · Y {len(doc['Y_revokes_that_do_not_hold'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
