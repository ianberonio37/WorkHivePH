#!/usr/bin/env python3
"""
gen_cross_hive_read_recipes — P-B "cross-hive read refusal" recipes per page (2026-09-05).

For each page in PAGE_TABLES, write tools/psql_probes/<page>__cross_hive_read_refused.sql from the template
that locked llm-observability / founder-console today: pick, IN THE DATABASE, an active member of exactly
one hive whose own hive has rows in the table and a foreign hive that also has rows; impersonate the member
(SET LOCAL ROLE authenticated + jwt claims); the foreign hive must read 0 rows (a USING clause FILTERS) and
the member's own hive must read > 0 (the control that proves the query itself works). Both counts are taken
inside a transaction that is rolled back. A table with rows in fewer than two hives cannot be proved either
way and is reported, not faked.

  python tools/gen_cross_hive_read_recipes.py            # write + run every recipe, print PASS/FAIL per page
  python tools/gen_cross_hive_read_recipes.py --page alert-hub.html
"""
from __future__ import annotations
import io, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tools" / "psql_probes"
PSQL = ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres", "-tA"]

# page -> the hive-scoped tables/views its READ path leans on (from the page's .from('x').select grep, 2026-09-05)
PAGE_TABLES = {
    "agentic-rag-observability.html": ["agentic_rag_traces"],
    "ai-quality.html": ["ai_cost_log", "ai_reply_feedback"],
    "plant-connections.html": ["gateway_audit_log", "integration_configs", "sensor_topic_map"],
    "analytics.html": ["analytics_snapshots"],
    "assistant.html": ["asset_nodes", "pm_assets", "voice_journal_entries"],
    "community.html": ["community_replies", "community_reactions", "community_xp"],
    "inventory.html": ["asset_nodes", "projects", "project_links"],
    "ph-intelligence.html": ["hive_benchmarks"],
    "pm-scheduler.html": ["pm_assets", "pm_completions", "pm_scope_items"],
    "project-report.html": ["project_links"],
    "resume.html": ["resume_documents"],
    "voice-journal.html": ["voice_journal_entries"],
    "asset-hub.html": ["asset_nodes", "pm_completions", "rcm_fmea_modes"],
    "alert-hub.html": ["alert_dismissals", "amc_briefings", "automation_log"],
    "marketplace.html": ["service_providers"],
    # views: security-invoker views over hive tables, read with the same RLS
    "achievements.html": ["v_worker_achievements_truth"],
    "analytics-report.html": ["v_hives_truth"],
    "marketplace-admin.html": ["v_marketplace_listings_truth"],
    "marketplace-seller-profile.html": ["v_marketplace_inquiries_truth"],
    "public-feed.html": ["v_community_posts_truth"],
    "skillmatrix.html": ["v_skill_badges_truth"],
    "platform-actions.html": ["platform_feedback"],
    "audit-log.html": ["hive_audit_log"],   # P112 (2026-09-05)
}

# PLATFORM-SCOPED by design (measured 2026-09-05): a member of one hive legitimately reads these rows from other hives -
# the marketplace and the public feed are cross-hive surfaces and an inquiry's hive_id is the BUYER's provenance,
# addressed to a seller elsewhere. Their hive_id is provenance, not a tenant boundary, so "cross-hive read refusal"
# does not apply; the pages are reported n/a with this reason and no recipe is written for them.
# views whose TENANT column is not hive_id (v_hives_truth is the hives table itself: one row per hive, keyed by id)
TENANT_COL = {"v_hives_truth": "id"}

PLATFORM_SCOPE = {
    "platform-actions.html": "platform_feedback is the platform-wide inbox a platform admin reads across every hive by design (hive_id = the sender's provenance)",
    "marketplace.html": "service_providers is a platform directory (hive_id = provenance)",
    "marketplace-admin.html": "v_marketplace_listings_truth is the platform-wide marketplace",
    "marketplace-seller-profile.html": "v_marketplace_inquiries_truth rows carry the buyer's hive; the seller reads inquiries addressed to him",
    "public-feed.html": "v_community_posts_truth is the public cross-hive feed",
}


def psql(sql: str) -> str:
    r = subprocess.run(PSQL + ["-c", sql], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "").strip() + (("\nERROR: " + r.stderr.strip()) if r.returncode else "")


def hive_spread(table: str) -> int:
    col = TENANT_COL.get(table, "hive_id")
    out = psql(f"select count(distinct {col}) from {table} where {col} is not null")
    return int(out) if out.isdigit() else -1


def recipe(page: str, tables: list[str]) -> str:
    slug = page.replace(".html", "")
    head = [
        f"-- cross_hive_read_refused ({slug}, P-B, generated 2026-09-05 by tools/gen_cross_hive_read_recipes.py): every",
        f"-- hive-scoped table this page reads ({', '.join(tables)}) must refuse a foreign hive in the DATABASE. RLS USING",
        "-- clauses FILTER rather than raise, so the probe counts rows as a member of exactly one hive: a foreign hive with",
        "-- rows reads 0, the member's own hive reads > 0 (the control). Fixtures are chosen live; a table with rows in",
        "-- fewer than two hives reports 'n/a' and is excluded from the expectations by the generator.",
    ]
    expects, body = [], []
    for t in tables:
        k = t.replace("v_", "").replace("_truth", "")
        hc = TENANT_COL.get(t, "hive_id")
        expects += [f"-- expect: {k}_fixture \\| t", f"-- expect: {k}_foreign_rows \\| 0", f"-- expect: {k}_own_rows_gt0 \\| t"]
        body.append(f"""
CREATE TEMP TABLE _fx_{k} AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.{hc} FROM {t} x WHERE x.{hc} IS NOT NULL AND x.{hc} <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.{hc} AND z.status = 'active')
        GROUP BY x.{hc} ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM {t} x WHERE x.{hc} = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_{k} TO authenticated;
SELECT '{k}_fixture | ' || ((SELECT me FROM _fx_{k}) IS NOT NULL AND (SELECT foreign_hive FROM _fx_{k}) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_{k})::text, 'role','authenticated')::text, true);
SELECT '{k}_foreign_rows | ' || (SELECT count(*) FROM {t} WHERE {hc} = (SELECT foreign_hive FROM _fx_{k}));
SELECT '{k}_own_rows_gt0 | ' || ((SELECT count(*) FROM {t} WHERE {hc} = (SELECT mine FROM _fx_{k})) > 0);
ROLLBACK;""")
    return "\n".join(head + expects) + "\n" + "\n".join(body) + "\n"


def main() -> int:
    only = sys.argv[sys.argv.index("--page") + 1] if "--page" in sys.argv else None
    summary = []
    for page, tables in PAGE_TABLES.items():
        if only and page != only:
            continue
        if page in PLATFORM_SCOPE:
            summary.append((page, "n/a", "platform-scoped by design: " + PLATFORM_SCOPE[page])); continue
        usable = [t for t in tables if hive_spread(t) >= 2]
        skipped = [t for t in tables if t not in usable]
        if not usable:
            summary.append((page, "n/a", f"no table with rows in >= 2 hives ({', '.join(tables)}) - missing DATA, not a ceiling: run tools/seed_second_hive_rows.py (extend it for these tables) and re-run")); continue
        path = OUT / f"{page.replace('.html', '')}__cross_hive_read_refused.sql"
        io.open(path, "w", encoding="utf-8", newline="").write(recipe(page, usable))
        out = psql("\\i /dev/stdin") if False else None
        r = subprocess.run("docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA < \"" + str(path) + "\"", shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
        lines = [l for l in (r.stdout or "").splitlines() if " | " in l]
        errs = [l for l in (r.stderr or "").splitlines() if "ERROR" in l]
        bad = [l for l in lines if l.endswith("| false") or (l.split(" | ")[0].endswith("_foreign_rows") and not l.endswith("| 0"))]
        verdict = "PASS" if lines and not bad and not errs else "FAIL"
        summary.append((page, verdict, f"{len(lines)} checks; tables={usable}" + (f"; skipped(n/a)={skipped}" if skipped else "") + (f"; bad={bad[:2]}" if bad else "") + (f"; errors={errs[:1]}" if errs else "")))
    for s in summary:
        print(f"  {s[1]:4} {s[0]:32} {s[2]}")
    return 0 if all(s[1] != "FAIL" for s in summary) else 1


if __name__ == "__main__":
    sys.exit(main())
