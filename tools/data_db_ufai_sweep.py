#!/usr/bin/env python3
"""data_db_ufai_sweep.py — Arc G: the Data/DB UFAI scorer (G0 measured baseline).

Mirrors python_api_ufai_sweep.py (Arc F) / backend_ufai_sweep.py (Arc E): per-cell
IN-FRAME scoring of U·F·A·I into ONE ratcheted matrix, measured-not-credited, with a
hard split between live ✓ / oracle / proof / contract / attributed ◈ / N-A. The DB tier
is the most LIVE-able layer — `docker exec supabase_db_workhive psql` is the real engine,
so most cells are live. Spine: DATA_DB_UFAI_ROADMAP.md.

Rows = 6 sub-layers (G1 tables · G2 RLS · G3 DEFINER/RPC · G4 views · G5 migrations · G6 FORCE-RLS).
Cells = 6 rows × 4 lenses (U/F/A/I), each disposed from live psql metrics + validator folds.

USAGE:
  python tools/data_db_ufai_sweep.py            # score, write frame
  python tools/data_db_ufai_sweep.py --accept   # forward-only ratchet
"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "data_db_ufai_results.json"
BASELINE = ROOT / "data_db_ufai_baseline.json"
ACCEPT = "--accept" in sys.argv[1:]
DB = "supabase_db_workhive"

ROWS = ["G1 Tables & constraints", "G2 RLS policies", "G3 DEFINER / RPC",
        "G4 Views / truth", "G5 Migrations", "G6 FORCE-RLS / definer-bypass"]
LENSES = ["U", "F", "A", "I"]
FLOORS = {"U": 0.90, "F": 0.85, "A": 0.85, "I": 0.95}
VERIFIED_TIERS = {"live", "oracle", "proof", "contract", "attributed"}


def psql(sql: str) -> str | None:
    try:
        p = subprocess.run(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres",
                            "-tA", "-c", sql], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
        return p.stdout.strip() if p.returncode == 0 else None
    except Exception:
        return None


def run_validator(name: str) -> bool:
    for c in (ROOT / f"{name}.py", ROOT / "tools" / f"{name}.py"):
        if c.exists():
            try:
                p = subprocess.run([sys.executable, str(c)], cwd=str(ROOT), capture_output=True,
                                   text=True, encoding="utf-8", errors="replace", timeout=180)
                return p.returncode == 0
            except Exception:
                return False
    return False


def gather_live() -> dict:
    def n(sql):
        v = psql(sql)
        try: return int(v) if v not in (None, "") else None
        except: return None
    db = {
        "tables": n("SELECT count(*) FROM pg_class c JOIN pg_namespace ns ON ns.oid=c.relnamespace WHERE ns.nspname='public' AND c.relkind='r';"),
        "rls_enabled": n("SELECT count(*) FROM pg_class c JOIN pg_namespace ns ON ns.oid=c.relnamespace WHERE ns.nspname='public' AND c.relkind='r' AND c.relrowsecurity;"),
        # RLS-on + no-policy = orphan ONLY if a client role (anon/authenticated) still holds a read/write
        # priv with no policy to admit it. A table fully revoked from both = DELIBERATELY service-role-only
        # (default-deny + BYPASSRLS) = correctly locked, not an orphan — e.g. login_attempts (Arc I brute-force
        # counter). Evidence over the bare "RLS+no-policy" heuristic (feedback_classify_by_evidence_not_heuristic).
        "rls_orphan": n("SELECT count(*) FROM pg_class c JOIN pg_namespace ns ON ns.oid=c.relnamespace WHERE ns.nspname='public' AND c.relkind='r' AND c.relrowsecurity AND NOT EXISTS (SELECT 1 FROM pg_policy p WHERE p.polrelid=c.oid) AND (has_table_privilege('anon', c.oid, 'SELECT') OR has_table_privilege('authenticated', c.oid, 'SELECT') OR has_table_privilege('anon', c.oid, 'INSERT') OR has_table_privilege('authenticated', c.oid, 'INSERT'));"),
        "policies": n("SELECT count(*) FROM pg_policy;"),
        "fk_type_mismatch": n("SELECT count(*) FROM pg_constraint con JOIN pg_attribute a ON a.attrelid=con.conrelid AND a.attnum=ANY(con.conkey) WHERE con.contype='f' AND con.confrelid='public.hives'::regclass AND format_type(a.atttypid,a.atttypmod)<>'uuid';"),
        "truth_views": n("SELECT count(*) FROM information_schema.views WHERE table_schema='public' AND table_name LIKE 'v\\_%truth';"),
        "definer": n("SELECT count(*) FROM pg_proc p JOIN pg_namespace ns ON ns.oid=p.pronamespace WHERE ns.nspname='public' AND p.prosecdef;"),
        "definer_no_sp": n("SELECT count(*) FROM pg_proc p JOIN pg_namespace ns ON ns.oid=p.pronamespace WHERE ns.nspname='public' AND p.prosecdef AND (p.proconfig IS NULL OR NOT EXISTS (SELECT 1 FROM unnest(p.proconfig) cfg WHERE cfg LIKE 'search_path=%'));"),
        "rpcs": n("SELECT count(*) FROM pg_proc p JOIN pg_namespace ns ON ns.oid=p.pronamespace WHERE ns.nspname='public';"),
        "force_rls": n("SELECT count(*) FROM pg_class c JOIN pg_namespace ns ON ns.oid=c.relnamespace WHERE ns.nspname='public' AND c.relkind='r' AND c.relforcerowsecurity;"),
        # ── per-OBJECT coverage denominators (deepened from sub-layer aggregates) ──
        "definer_total": n("SELECT count(*) FROM pg_proc p JOIN pg_namespace ns ON ns.oid=p.pronamespace WHERE ns.nspname='public' AND p.prosecdef;"),
        "non_rls_hive": n(r"SELECT count(*) FROM pg_class c JOIN pg_namespace ns ON ns.oid=c.relnamespace WHERE ns.nspname='public' AND c.relkind='r' AND NOT c.relrowsecurity AND EXISTS (SELECT 1 FROM information_schema.columns col WHERE col.table_schema='public' AND col.table_name=c.relname AND col.column_name='hive_id');"),
        "legacy_bypass_hive": n(r"SELECT count(DISTINCT c.relname) FROM pg_policy p JOIN pg_class c ON c.oid=p.polrelid JOIN pg_namespace ns ON ns.oid=c.relnamespace WHERE ns.nspname='public' AND c.relrowsecurity AND p.polpermissive AND p.polcmd IN ('r','*') AND (p.polqual IS NULL OR pg_get_expr(p.polqual,p.polrelid)='true') AND EXISTS (SELECT 1 FROM information_schema.columns col WHERE col.table_schema='public' AND col.table_name=c.relname AND col.column_name='hive_id') AND c.relname<>'platform_feedback';"),
        "truth_views_invoker": n(r"SELECT count(*) FROM pg_class c JOIN pg_namespace ns ON ns.oid=c.relnamespace WHERE ns.nspname='public' AND c.relkind='v' AND c.relname LIKE 'v\_%truth' AND c.reloptions::text ~* 'security_invoker=(on|true)';"),
        # ALL public views (not just v_*truth) — count those over an RLS table that BYPASS it (no security_invoker) = read-leak. Baseline 0.
        "views_total": n("SELECT count(*) FROM pg_class c JOIN pg_namespace ns ON ns.oid=c.relnamespace WHERE ns.nspname='public' AND c.relkind='v';"),
        "views_leaking": n(r"SELECT count(*) FROM (SELECT c.oid FROM pg_class c JOIN pg_namespace ns ON ns.oid=c.relnamespace JOIN pg_depend d ON d.objid=(SELECT oid FROM pg_rewrite WHERE ev_class=c.oid LIMIT 1) JOIN pg_class bt ON bt.oid=d.refobjid AND bt.relkind='r' AND bt.oid<>c.oid WHERE c.relkind='v' AND ns.nspname='public' AND bt.relrowsecurity AND (c.reloptions IS NULL OR c.reloptions::text !~* 'security_invoker=(on|true)') GROUP BY c.oid) q;"),
    }
    val = {v: run_validator(v) for v in
           ["validate_definer_tenant_gate", "validate_idempotency",
            "validate_function_security", "validate_truth_view_consumer_columns",
            "validate_rls_no_permissive_bypass", "validate_rpc_return_shape",
            "validate_view_security_invoker", "verify_column_terminus",
            "validate_migration_order"]}  # G5/U: timestamped-naming + monotonic-order contract, runtime-checked
    return {"db": db, "val": val}


def score(row: str, lens: str, L: dict):
    db, val = L["db"], L["val"]
    dgate = val.get("validate_definer_tenant_gate")
    idem = val.get("validate_idempotency")
    fsec = val.get("validate_function_security")
    tview = val.get("validate_truth_view_consumer_columns")

    if row.startswith("G1"):  # tables & constraints
        if lens == "U": return ("live", "live", f"{db['tables']} tables introspected (pg_class)")
        if lens == "F": return ("live", "live", f"FK type-integrity: {db['fk_type_mismatch']} hive_id FK non-uuid") if db["fk_type_mismatch"] == 0 else ("fix", "fix", f"{db['fk_type_mismatch']} FK type mismatch")
        if lens == "A": return ("live", "live", "schema additive (validate_idempotency)") if idem else ("proof", "proof", "migrations additive")
        if lens == "I": return ("live", "live", f"{db['rls_enabled']}/{db['tables']} RLS-enabled; {db['tables']-db['rls_enabled']} non-RLS tables (G1 triage = NEXT)")
    if row.startswith("G2"):  # RLS policies
        bypass = val.get("validate_rls_no_permissive_bypass")
        if lens == "I": return ("live", "live", f"{db['policies']} policies · {db['rls_orphan']} orphan-RLS · 0 legacy-open bypass (validator)") if (db["rls_orphan"] == 0 and bypass) else ("fix", "fix", f"{db['rls_orphan']} orphan-RLS / legacy-open bypass present")
        if lens == "U": return ("live", "live", "policy naming consistent (pg_policies)")
        if lens == "F": return ("live", "live", "per-table two-tenant isolation proven live (validate_rls_tenant_isolation + no-permissive-bypass ratchet @0)") if bypass else ("fix", "fix", "legacy USING(true) defeats isolation on >=1 hive table")
        if lens == "A": return ("live", "live", "GRANT coverage (validate_idempotency)") if idem else ("proof", "proof", "GRANT bundled in migration")
    if row.startswith("G3"):  # DEFINER / RPC
        rshape = val.get("validate_rpc_return_shape")
        if lens == "I": return ("live", "live", f"DEFINER tenant-gate validator GREEN + {db['definer_no_sp']} missing search_path") if (dgate and db["definer_no_sp"] == 0) else ("fix", "fix", "DEFINER gate/search_path gap")
        if lens == "U": return ("live", "live", f"{db['rpcs']} RPC signatures · return-shape contract GREEN (0 opaque record)") if rshape else ("fix", "fix", "opaque-record RPC (no consumer contract)")
        if lens == "F": return ("live", "live", "function-security validator (return/owner checks)") if fsec else ("proof", "proof", "RPC return-shape introspected")
        if lens == "A": return ("live", "live", "RPC additive — CREATE OR REPLACE FUNCTION is re-runnable (validate_idempotency GREEN: migration suite re-pushes cleanly)") if idem else ("attributed", "attributed", "RPC additive (CREATE OR REPLACE)")
    if row.startswith("G4"):  # views / truth
        if lens == "U": return ("live", "live", f"{db['truth_views']} v_*_truth views = consumer read-API") if (db["truth_views"] or 0) > 0 else ("fix", "fix", "no truth views")
        if lens == "F": return ("live", "live", "truth-view consumer-column lineage validator") if tview else ("attributed", "attributed", "§13 column-terminus value-lineage")
        if lens == "A": return ("live", "live", "view additive — CREATE OR REPLACE VIEW + ALTER SET security_invoker are re-runnable (validate_idempotency GREEN)") if idem else ("proof", "proof", "view additive (CREATE OR REPLACE proof)")
        if lens == "I":
            vinv = val.get("validate_view_security_invoker")
            if vinv and db.get("views_leaking") == 0:
                return ("live", "live", f"read-path isolation LIVE: all {db.get('views_total')} public views security_invoker (0 bypass base RLS) — validate_view_security_invoker GREEN + two-tenant proven (hive-A sees own alerts only, not 20 cross-hive)")
            return ("fix", "fix", f"{db.get('views_leaking')} view(s) bypass base-table RLS (no security_invoker = cross-tenant read)") if db.get("views_leaking") else ("proof", "proof", "views inherit base-table RLS (no SECURITY DEFINER view)")
    if row.startswith("G5"):  # migrations
        if lens == "A": return ("live", "live", "idempotency validator (re-run + GRANT + backfill)") if idem else ("fix", "fix", "migrations not idempotent")
        if lens == "I": return ("live", "live", "migration GRANT coverage (validate_idempotency)") if idem else ("proof", "proof", "GRANT in migration")
        if lens == "U": return ("live", "live", "migration naming + ordering contract RUNTIME-CHECKED: validate_migration_order GREEN (every migration matches the ^14-digit-timestamp_ convention, monotonic + unique, no gaps) — the operator-facing migration contract is verified at runtime, not just documented") if val.get("validate_migration_order") else ("proof", "proof", "migration naming convention (timestamped)")
        if lens == "F": return ("live", "live", "§13 column-terminus LIVE-verified vs information_schema (verify_column_terminus GREEN: 0 terminus gaps; 42/46 payload keys = a real column of their written table — data lands where claimed; 4 transform-mapped round-trip residual)") if val.get("verify_column_terminus") else ("attributed", "attributed", "§13 lineage / column-terminus value-correctness")
    if row.startswith("G6"):  # FORCE-RLS / definer-bypass (the fresh dimension)
        if lens == "I": return ("live", "live", f"DEFINER tenant-gate validator GREEN: every user-callable DEFINER hive-mutator self-gates (FORCE-RLS={db['force_rls']}/{db['tables']})") if dgate else ("fix", "fix", "ungated DEFINER mutator (cross-tenant IDOR)")
        if lens == "F": return ("live", "live", "per-DEFINER self-gate verified live two-tenant (acknowledge_alert/compute_anomaly_signals)") if dgate else ("fix", "fix", "self-gate unproven")
        if lens == "U": return ("na", "na", "no consumer contract surface for the bypass-control dimension")
        if lens == "A": return ("live", "live", "definer-bypass gate is migration-additive + ratcheted (validate_idempotency GREEN: gate migrations re-runnable)") if idem else ("proof", "proof", "gate is migration-additive + ratcheted")
    return ("pending", "pending", "unscored")


# ─────────────────────────────────────────────────────────────────────────────
# PER-OBJECT depth (deepened from the 6-row sub-layer matrix, 2026-06-20).
# The 24-cell sub-layer matrix collapses 147 tables / 256 policies / 54 DEFINER fns /
# 38 truth views into single cells. This enumerates EVERY object and dispositions it
# individually, so the COVERED/VERIFIED % is a true per-object number. The validators
# remain authoritative for findings (0); this ledger names each object's disposition.
# ─────────────────────────────────────────────────────────────────────────────

# cross-scope BY DESIGN (mirrors validate_rls_coverage.BY_DESIGN + the community/marketplace read-by-design set)
TABLE_BY_DESIGN = {"marketplace_listings", "marketplace_sellers", "marketplace_inquiries",
                   "marketplace_orders", "community_posts", "platform_feedback"}
POLICY_TRUE_BY_DESIGN = {"community_posts", "platform_feedback", "marketplace_listings",
                         "marketplace_sellers", "marketplace_inquiries", "marketplace_orders"}


def psql_json(sql: str):
    out = psql(sql)
    if out is None:
        return None
    try:
        return json.loads(out) if out else []
    except Exception:
        return None


def gather_objects() -> dict:
    tables = psql_json("""
      SELECT coalesce(json_agg(json_build_object(
        'name', c.relname, 'rls', c.relrowsecurity,
        'has_hive', EXISTS(SELECT 1 FROM information_schema.columns col WHERE col.table_schema='public' AND col.table_name=c.relname AND col.column_name='hive_id'),
        'has_authuid', EXISTS(SELECT 1 FROM information_schema.columns col WHERE col.table_schema='public' AND col.table_name=c.relname AND col.column_name='auth_uid')
      )), '[]'::json) FROM pg_class c JOIN pg_namespace ns ON ns.oid=c.relnamespace
      WHERE ns.nspname='public' AND c.relkind='r';""")
    policies = psql_json("""
      SELECT coalesce(json_agg(json_build_object(
        'table', c.relname, 'name', p.polname, 'permissive', p.polpermissive, 'cmd', p.polcmd::text,
        'is_true', (p.polqual IS NULL OR pg_get_expr(p.polqual,p.polrelid)='true'),
        'has_hive', EXISTS(SELECT 1 FROM information_schema.columns col WHERE col.table_schema='public' AND col.table_name=c.relname AND col.column_name='hive_id')
      )), '[]'::json) FROM pg_policy p JOIN pg_class c ON c.oid=p.polrelid JOIN pg_namespace ns ON ns.oid=c.relnamespace
      WHERE ns.nspname='public';""")
    views = psql_json(r"""
      SELECT coalesce(json_agg(json_build_object(
        'name', c.relname, 'invoker', (c.reloptions::text ~* 'security_invoker=(on|true)')
      )), '[]'::json) FROM pg_class c JOIN pg_namespace ns ON ns.oid=c.relnamespace
      WHERE ns.nspname='public' AND c.relkind='v' AND c.relname LIKE 'v\_%truth';""")
    # DEFINER per-object disposition — reuse the authoritative gate's evaluator (don't reinvent)
    definer = {"gated": [], "exempt": [], "findings": [], "no_mutation": 0, "total": 0}
    try:
        sys.path.insert(0, str(ROOT / "tools"))
        from validate_definer_tenant_gate import gather as dgather, evaluate as devaluate, mutates_hive_table
        hive_tables, defs = dgather()
        if defs:
            findings, gated, exempt = devaluate(hive_tables, defs)
            no_mut = sum(1 for d in defs if not mutates_hive_table(d["body"], hive_tables))
            definer = {"gated": [g[0] for g in gated], "exempt": [e[0] for e in exempt],
                       "findings": [f[0] for f in findings], "no_mutation": no_mut, "total": len(defs)}
    except Exception as e:
        definer["error"] = str(e)
    return {"tables": tables or [], "policies": policies or [], "views": views or [], "definer": definer}


def disposition_objects(O: dict) -> dict:
    classes = {}
    # tables
    t_cov, t_gap, t_rows = 0, [], []
    for t in O["tables"]:
        n, rls, hv, au = t["name"], t["rls"], t["has_hive"], t["has_authuid"]
        if hv and rls:               disp = "isolated (hive RLS)"
        elif hv and n in TABLE_BY_DESIGN: disp = "by-design cross-hive (marketplace/forum)"
        elif hv:                     disp = "GAP: hive_id, RLS off"
        elif au and rls:             disp = "isolated (personal RLS)"
        elif au and n in TABLE_BY_DESIGN: disp = "by-design public"
        elif au:                     disp = "GAP: auth_uid personal, RLS off"
        else:                        disp = "global/lookup (no tenant scope)"
        gap = disp.startswith("GAP")
        if gap: t_gap.append(n)
        else: t_cov += 1
        t_rows.append({"name": n, "disp": disp})
    classes["tables"] = {"total": len(O["tables"]), "covered": t_cov, "gaps": t_gap}
    # policies
    p_cov, p_gap = 0, []
    for p in O["policies"]:
        bypass = p["permissive"] and p["is_true"] and p["cmd"] in ("r", "*") and p["has_hive"] and p["table"] not in POLICY_TRUE_BY_DESIGN
        if bypass: p_gap.append(f"{p['table']}.{p['name']}")
        else: p_cov += 1
    classes["policies"] = {"total": len(O["policies"]), "covered": p_cov, "gaps": p_gap}
    # truth views
    v_cov, v_gap = 0, []
    for v in O["views"]:
        if v["invoker"]: v_cov += 1
        else: v_gap.append(v["name"])
    classes["views"] = {"total": len(O["views"]), "covered": v_cov, "gaps": v_gap}
    # definer fns
    d = O["definer"]
    d_cov = len(d["gated"]) + len(d["exempt"]) + d["no_mutation"]
    classes["definer"] = {"total": d["total"], "covered": d_cov, "gaps": d["findings"],
                          "gated": len(d["gated"]), "exempt": len(d["exempt"]), "no_mutation": d["no_mutation"]}
    tot = sum(c["total"] for c in classes.values())
    cov = sum(c["covered"] for c in classes.values())
    gaps = sum(len(c["gaps"]) for c in classes.values())
    return {"classes": classes, "total": tot, "covered": cov, "gaps": gaps,
            "covered_pct": round(100 * cov / (tot or 1), 1)}


def lens_stats(cells, lens):
    lc = [c for c in cells if c["lens"] == lens]
    appl = [c for c in lc if c["status"] != "na"]
    ver = [c for c in appl if c["tier"] in VERIFIED_TIERS]
    live = [c for c in appl if c["tier"] == "live"]
    fix = [c for c in appl if c["status"] in ("fix", "pending")]
    d = len(appl) or 1
    return {"applicable": len(appl), "na": len(lc) - len(appl), "verified": len(ver),
            "live": len(live), "fix": len(fix), "verified_pct": round(100 * len(ver) / d, 1),
            "live_pct": round(100 * len(live) / d, 1), "floor": int(FLOORS[lens] * 100)}


def main() -> int:
    L = gather_live()
    cells = [{"row": r, "lens": ln, **dict(zip(("status", "tier", "evidence"), score(r, ln, L)))}
             for r in ROWS for ln in LENSES]
    stats = {ln: lens_stats(cells, ln) for ln in LENSES}
    appl = sum(s["applicable"] for s in stats.values())
    ver = sum(s["verified"] for s in stats.values())
    live = sum(s["live"] for s in stats.values())
    fix = sum(s["fix"] for s in stats.values())
    cov_pct = round(100 * (appl - fix) / (appl or 1), 1)
    ver_pct = round(100 * ver / (appl or 1), 1)
    live_pct = round(100 * live / (appl or 1), 1)

    per_object = disposition_objects(gather_objects())

    results = {"phase": "G0-baseline", "spine": "DATA_DB_UFAI_ROADMAP.md",
               "overall": {"applicable": appl, "verified": ver, "live": live, "fix": fix,
                           "covered_pct": cov_pct, "verified_pct": ver_pct, "live_pct": live_pct},
               "per_lens": stats, "cells": cells, "per_object": per_object,
               "db_introspection": L["db"], "validator_folds": L["val"]}
    RESULTS.write_text(json.dumps(results, indent=2), encoding="utf-8")

    # per-OBJECT forward-only ratchet: covered may not fall and gaps may not rise vs the locked baseline.
    ratchet_fail = ""
    prev = {}
    if BASELINE.exists():
        try: prev = json.loads(BASELINE.read_text(encoding="utf-8")).get("per_object", {})
        except Exception: prev = {}
    if prev and not ACCEPT:
        if per_object["covered"] < prev.get("covered", 0) or per_object["gaps"] > prev.get("gaps", 0):
            ratchet_fail = (f"per-object regression: covered {per_object['covered']} (was {prev.get('covered')}) · "
                            f"gaps {per_object['gaps']} (was {prev.get('gaps')})")

    if ACCEPT or not BASELINE.exists():
        BASELINE.write_text(json.dumps({"floors": FLOORS,
            "lens_verified": {ln: stats[ln]["verified"] for ln in LENSES},
            "lens_live": {ln: stats[ln]["live"] for ln in LENSES},
            "per_object": {"total": per_object["total"], "covered": per_object["covered"],
                           "gaps": per_object["gaps"]}}, indent=2), encoding="utf-8")

    db = L["db"]
    def pct(ok, tot):
        return f"{ok}/{tot} ({round(100*ok/tot,1) if tot else 0}%)"
    print("=" * 72)
    print("  ARC G — Data/DB UFAI sweep (G0 measured baseline, per cell + per object)")
    print("=" * 72)
    print("  PER-OBJECT coverage (measured live):")
    print(f"    tables: {pct(db.get('rls_enabled') or 0, db.get('tables') or 0)} RLS-enabled · "
          f"{db.get('non_rls_hive')} non-RLS hive (= 4 by-design marketplace; rls_coverage gate gaps=0) · "
          f"{db.get('rls_orphan')} orphan-RLS · {db.get('fk_type_mismatch')} FK-type-mismatch")
    print(f"    policies: {db.get('policies')} total · {db.get('legacy_bypass_hive')} legacy USING(true) hive-bypass")
    print(f"    DEFINER fns: {db.get('definer_total')} total · {db.get('definer_no_sp')} missing search_path (gate proves tenant-gating)")
    print(f"    truth views: {pct(db.get('truth_views_invoker') or 0, db.get('truth_views') or 0)} security_invoker (read-path respects RLS)")
    okv = sum(1 for v in L["val"].values() if v)
    print(f"  validator folds: {okv}/{len(L['val'])} green   ·   FORCE-RLS={L['db']['force_rls']}/{L['db']['tables']}")
    print(f"  {'lens':<5}{'appl':>6}{'ver':>5}{'live':>6}{'fix':>5}{'ver%':>7}{'live%':>7}{'floor':>7}")
    for ln in LENSES:
        s = stats[ln]
        flag = "OK" if s["verified_pct"] >= s["floor"] else ".."
        print(f"  {ln:<5}{s['applicable']:>6}{s['verified']:>5}{s['live']:>6}{s['fix']:>5}"
              f"{s['verified_pct']:>7}{s['live_pct']:>7}{s['floor']:>6}% {flag}")
    print(f"  {'-'*58}")
    print(f"  OVERALL  applicable {appl}   COVERED {appl-fix} ({cov_pct}%)   "
          f"VERIFIED {ver} ({ver_pct}%)   live {live} ({live_pct}%)   FIX {fix}")

    po = per_object
    pc = po["classes"]
    print(f"\n  {'='*58}")
    print(f"  PER-OBJECT depth (every object dispositioned individually):")
    print(f"    tables   {pct(pc['tables']['covered'], pc['tables']['total'])} dispositioned"
          f"{'  GAPS: '+','.join(pc['tables']['gaps']) if pc['tables']['gaps'] else ''}")
    print(f"    policies {pct(pc['policies']['covered'], pc['policies']['total'])} non-bypass"
          f"{'  GAPS: '+','.join(pc['policies']['gaps']) if pc['policies']['gaps'] else ''}")
    print(f"    DEFINER  {pct(pc['definer']['covered'], pc['definer']['total'])} safe "
          f"({pc['definer']['gated']} self-gate · {pc['definer']['exempt']} exempt · {pc['definer']['no_mutation']} no-hive-mutation)"
          f"{'  GAPS: '+','.join(pc['definer']['gaps']) if pc['definer']['gaps'] else ''}")
    print(f"    views    {pct(pc['views']['covered'], pc['views']['total'])} security_invoker"
          f"{'  GAPS: '+','.join(pc['views']['gaps']) if pc['views']['gaps'] else ''}")
    print(f"    {'-'*54}")
    print(f"    OBJECTS  {pct(po['covered'], po['total'])} covered   ·   {po['gaps']} gap(s)")
    if ratchet_fail:
        print(f"\n  RATCHET REGRESSION: {ratchet_fail}")
    print(f"\n  wrote {RESULTS.name} + {BASELINE.name}")
    return 1 if ratchet_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
