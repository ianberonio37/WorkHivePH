#!/usr/bin/env python3
"""
gen_write_authz_recipes — P-B "write-authz depth" recipes per page (2026-09-05).

For each page in PAGE_TABLES, write tools/psql_probes/<page>__write_authz_depth.sql: as an active member of
exactly one hive (SET LOCAL ROLE authenticated + jwt claims), a NO-OP UPDATE (SET <pk> = <pk>) and a DELETE on
a row of a FOREIGN hive must touch 0 rows (RLS USING clauses FILTER, they do not raise), and - the control - the
same no-op UPDATE on a row of the member's OWN hive must touch >= 1 row where the table's policy is a hive-member
ALL policy (the page's own write path). Every statement runs inside a transaction that is rolled back, and the
row count is re-checked afterwards. Tables with rows in fewer than two hives are reported n/a, never faked;
tables whose write policy is owner- or supervisor-scoped keep only the foreign-refusal half (the control would
need a different actor) and say so.

  python tools/gen_write_authz_recipes.py            # write + run every recipe, print PASS/FAIL per page
  python tools/gen_write_authz_recipes.py --page hive.html
"""
from __future__ import annotations
import io, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tools" / "psql_probes"
PSQL = ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres", "-tA"]

# page -> hive-scoped tables its WRITE path touches (from the page's .from('x').update/delete/upsert/insert grep)
PAGE_TABLES = {
    "asset-hub.html": ["asset_nodes", "pm_scope_items", "rcm_fmea_modes", "parts_staged_reservations"],
    "dayplanner.html": ["logbook", "schedule_items"],
    "hive.html": ["hive_members", "logbook"],
    "logbook.html": ["logbook", "pm_completions", "project_links", "asset_nodes"],
    "marketplace-seller.html": ["marketplace_listings", "marketplace_inquiries", "marketplace_reviews"],
    "marketplace-admin.html": ["marketplace_listings", "marketplace_orders", "marketplace_disputes"],
    "platform-actions.html": ["service_credit_topups", "marketplace_listings"],
    "report-sender.html": ["report_contacts"],
    "shift-brain.html": ["shift_plans"],
    "alert-hub.html": ["alert_dismissals", "amc_briefings", "anomaly_signals"],
    "assistant.html": ["ai_reply_feedback"],
}
# tables whose UPDATE policy is scoped to the row's OWNER or to SUPERVISORS, not to any hive member: the own-hive
# control cannot be proved with a plain member, so only the foreign-refusal half is asserted (stated in the recipe).
# marketplace_sellers: mkt_sellers_update keys on the profile's own auth_uid (or a marketplace admin) - a member may not
# edit a hive-mate's seller profile, so only the refusal half applies (2026-10-27)
OWNER_SCOPED = {"marketplace_sellers", "marketplace_listings", "marketplace_inquiries", "marketplace_reviews", "marketplace_orders",
                "marketplace_disputes", "service_credit_topups", "logbook", "hive_members", "report_contacts",
                "ai_reply_feedback", "alert_dismissals",
                "pm_completions",
                # the ledger: inventory_transactions_write WITH CHECK keys on the row's own auth_uid - a member may write
                # only their own movements (measured 2026-10-27: a hive-mate's row refused with 42501 on a no-op update)
                "inventory_transactions"}   # a member may not edit another worker's completion (measured 2026-09-05: own-hive no-op update touched 0)


def written_tables(page: str) -> set[str]:
    """The tables a page WRITES, measured from its own source: a `.from('x')` followed (before the next .from) by
    .insert / .update / .upsert / .delete (2026-10-14, SL S2 - the hand-kept PAGE_TABLES covered 11 pages)."""
    import re
    try:
        src = (ROOT / page).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    out = set()
    for m in re.finditer(r"\.from\(\s*['\"]([a-z0-9_]+)['\"]\s*\)", src):
        tail = src[m.end(): m.end() + 300].split(".from(")[0]
        if re.search(r"\.(insert|update|upsert|delete)\(", tail):
            out.add(m.group(1))
    return out


def hive_scoped(tables: set[str]) -> list[str]:
    if not tables:
        return []
    names = ",".join("'" + t + "'" for t in sorted(tables))
    out = psql("select distinct table_name from information_schema.columns where table_schema='public' "
               f"and column_name='hive_id' and table_name in ({names})")
    have = {l.strip() for l in out.splitlines() if l.strip() and "ERROR" not in l}
    # views are not written through; only base tables carry a write policy
    kinds = psql("select relname from pg_class where relkind = 'r' and relname in (" + names + ")")
    base = {l.strip() for l in kinds.splitlines() if l.strip()}
    return sorted(have & base)


def psql(sql: str) -> str:
    r = subprocess.run(PSQL + ["-c", sql], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "").strip() + (("\nERROR: " + r.stderr.strip()) if r.returncode else "")


def hive_spread(table: str) -> int:
    out = psql(f"select count(distinct hive_id) from {table} where hive_id is not null")
    return int(out) if out.isdigit() else -1


def pk_col(table: str) -> str:
    out = psql(f"select a.attname from pg_index i join pg_attribute a on a.attrelid = i.indrelid and a.attnum = any(i.indkey) where i.indrelid = 'public.{table}'::regclass and i.indisprimary limit 1")
    return out if out and "ERROR" not in out else "id"


# a marketplace row is written by its two PARTIES by account, from whichever hive it is stored in: the foreign
# fixture must be a row the member is neither the buyer nor the seller of (2026-10-27)
PARTY_TABLES = ("marketplace_inquiries", "marketplace_orders")
PARTY_SQL = ("\n          AND x.buyer_auth_uid IS DISTINCT FROM m.auth_uid"
             "\n          AND NOT EXISTS (SELECT 1 FROM marketplace_listings l WHERE l.id = x.listing_id AND l.auth_uid = m.auth_uid)")


def recipe(page: str, tables: list[str]) -> str:
    slug = page.replace(".html", "")
    head = [
        f"-- write_authz_depth ({slug}, P-B, generated 2026-09-05 by tools/gen_write_authz_recipes.py): the hive-scoped",
        f"-- tables this page WRITES ({', '.join(tables)}) must refuse a foreign hive in the DATABASE. A USING clause on",
        "-- UPDATE/DELETE filters, so a no-op UPDATE (pk = pk) and a DELETE on a foreign hive's row must touch 0 rows; the",
        "-- own-hive control must touch >= 1 where the write policy is hive-member ALL (owner/supervisor-scoped tables keep",
        "-- only the refusal half and say so). Everything runs inside a rolled-back transaction; counts are re-checked after.",
    ]
    expects, body = [], []
    for t in tables:
        k = t; pk = pk_col(t)
        # ★APPEND-ONLY BY POLICY, MEASURED (2026-10-14): an audit table (hive_audit_log, cmms_audit_log) has no UPDATE
        # policy at all, so "a member updates an own-hive row" can never hold - the S2 sweep read that as eleven failures.
        # Such a table, like an owner-scoped one, keeps only the refusal half.
        no_update = (psql("select count(*) from pg_policy p join pg_class c on c.oid = p.polrelid "
                          f"where c.relname = '{t}' and p.polcmd in ('w', '*')").strip() == "0"
                     # ...or by GRANT: cmms_audit_log has an UPDATE policy and no UPDATE privilege for authenticated
                     or psql(f"select has_table_privilege('authenticated', 'public.{t}', 'UPDATE')").strip() == "f")
        owner = t in OWNER_SCOPED or no_update
        expects += [f"-- expect: {k}_fixture \\| t", f"-- expect: {k}_foreign_update_touched \\| (0\\b|refused)",
                    f"-- expect: {k}_foreign_delete_touched \\| (0\\b|refused)"]
        if not owner:
            expects.append(f"-- expect: {k}_own_update_touched_gt0 \\| t")
        expects.append(f"-- expect: {k}_move_into_foreign \\| (0\\b|refused)")
        expects.append(f"-- forbid: {k}_move_into_foreign \\| [1-9]")   # a row moved into a foreign hive
        expects.append(f"-- expect: {k}_rows_restored \\| t")
        party = PARTY_SQL if t in PARTY_TABLES else ""
        body.append(f"""
CREATE TEMP TABLE _wx_{k} AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.{pk} FROM {t} x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active'){party}
        LIMIT 1) AS foreign_row,
       (SELECT x.{pk} FROM {t} x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT x.hive_id FROM {t} x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active'){party}
        LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM {t}) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM {t} x WHERE x.hive_id = m.hive_id)
  -- a VALID foreign row exists for this member (an empty one manufactured a 'move into NULL', 2026-10-27)
  AND EXISTS (SELECT 1 FROM {t} x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active'){party})
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.auth_uid = m.auth_uid)   -- by account, never by display name
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_{k} TO authenticated;
SELECT '{k}_fixture | ' || ((SELECT me FROM _wx_{k}) IS NOT NULL AND (SELECT foreign_row FROM _wx_{k}) IS NOT NULL);
-- every write probe runs through ONE exception-safe function (2026-10-14): a refused write (42501, a missing grant, a
-- guard trigger) returns 'refused <SQLSTATE>' instead of aborting the rolled-back transaction and every probe after it
CREATE FUNCTION pg_temp.wx_try_{k}(op text) RETURNS text LANGUAGE plpgsql AS $wx$
DECLARE n int;
BEGIN
  IF op = 'foreign_update' THEN UPDATE {t} SET {pk} = {pk} WHERE {pk} = (SELECT foreign_row FROM _wx_{k});
  ELSIF op = 'foreign_delete' THEN DELETE FROM {t} WHERE {pk} = (SELECT foreign_row FROM _wx_{k});
  ELSIF op = 'own_update' THEN UPDATE {t} SET {pk} = {pk} WHERE {pk} = (SELECT own_row FROM _wx_{k});
  ELSIF op = 'move' THEN UPDATE {t} SET hive_id = (SELECT foreign_hive FROM _wx_{k}) WHERE {pk} = (SELECT own_row FROM _wx_{k});
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n::text;
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused 42501';
  WHEN others THEN RETURN 'refused ' || SQLSTATE;
END $wx$;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_{k})::text, 'role','authenticated')::text, true);
SELECT '{k}_foreign_update_touched | ' || pg_temp.wx_try_{k}('foreign_update');
SELECT '{k}_foreign_delete_touched | ' || pg_temp.wx_try_{k}('foreign_delete');
SELECT '{k}_move_into_foreign | ' || pg_temp.wx_try_{k}('move');
""" + ("" if owner else f"""SELECT '{k}_own_update_touched_gt0 | ' || (pg_temp.wx_try_{k}('own_update') ~ '^[1-9]');
""") + f"""ROLLBACK;
SELECT '{k}_rows_restored | ' || ((SELECT count(*) FROM {t}) = (SELECT n0 FROM _wx_{k}));""")
    return "\n".join(head + expects) + "\n" + "\n".join(body) + "\n"


def main() -> int:
    only = sys.argv[sys.argv.index("--page") + 1] if "--page" in sys.argv else None
    summary = []
    plan = dict(PAGE_TABLES)
    if "--sl" in sys.argv:   # the SL S2 roster (2026-10-14): every page the sub-layer names, tables measured from its writes
        import json
        reg = json.loads((ROOT / "trajectory_registry.json").read_text(encoding="utf-8"))
        pages = sorted({t["sl"]["page"] for t in reg["trajectories"]
                        if (t.get("sl") or {}).get("sublayer") == "S2" and t.get("status") != "descoped"})
        plan = {pg: hive_scoped(set(PAGE_TABLES.get(pg, [])) | written_tables(pg)) for pg in pages}
    for page, tables in plan.items():
        if not tables:
            summary.append((page, "n/a", "writes no hive-scoped table - nothing to refuse")); continue
        if only and page != only:
            continue
        usable = [t for t in tables if hive_spread(t) >= 2]
        skipped = [t for t in tables if t not in usable]
        if not usable:
            summary.append((page, "n/a", f"no table with rows in >= 2 hives ({', '.join(tables)}) - missing DATA, not a ceiling: run tools/seed_second_hive_rows.py (extend it for these tables) and re-run")); continue
        path = OUT / f"{page.replace('.html', '')}__write_authz_depth.sql"
        io.open(path, "w", encoding="utf-8", newline="").write(recipe(page, usable))
        r = subprocess.run("docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA < \"" + str(path) + "\"", shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
        lines = [l for l in (r.stdout or "").splitlines() if " | " in l]
        errs = [l for l in (r.stderr or "").splitlines() if "ERROR" in l]
        # a write probe holds when it touched 0 rows or was refused; the own-hive control and the restore must read true
        bad = [l for l in lines if l.endswith("| false")
               or (any(x in l for x in ("_foreign_update_touched", "_foreign_delete_touched", "_move_into_foreign"))
                   and not (l.endswith("| 0") or " | refused" in l))]
        verdict = "PASS" if lines and not bad and not errs else "FAIL"
        summary.append((page, verdict, f"{len(lines)} checks; tables={usable}" + (f"; skipped(n/a)={skipped}" if skipped else "") + (f"; bad={bad[:2]}" if bad else "") + (f"; errors={errs[:1]}" if errs else "")))
        if verdict == "FAIL":
            path.unlink(missing_ok=True)   # a failing recipe must not enter the suite until its finding is dispositioned
    for s in summary:
        print(f"  {s[1]:4} {s[0]:28} {s[2]}")
    return 0 if all(s[1] != "FAIL" for s in summary) else 1


if __name__ == "__main__":
    sys.exit(main())
