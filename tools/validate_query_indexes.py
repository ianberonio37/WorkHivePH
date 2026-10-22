#!/usr/bin/env python3
"""query-indexes - SL LB2 (2026-10-20): every page's queries stay on an index as their tables grow.

WHAT THE LB2 MEASUREMENT FOUND (rows SL3083-SL3117: 34 pages; every read each page makes - its own db.from / db.rpc
chains and the shared scripts it loads, 424 reads and 111 RPC calls, 524 distinct statements - translated into the SQL PostgREST runs
with the row's cast's real values and EXPLAIN ANALYZEd as that cast, RLS on, after its tables were GROWN inside one
rolled-back transaction from their own rows to 50k-130k rows; every page-load read RPC run the same way, with
auto_explain logging each statement inside it):
  * 42 reads on 16 pages and the shared worker drawer, and one RPC, sequentially scanned a growing table - or walked a
    whole index to filter it - for want of an index: every hive-scoped PM scope read walked ALL scope items (56,733 removed to keep 29: no
    hive_id key); alert-hub's failed-automation read scanned every hive's last day; community's reported-post read
    walked the hive's whole audit log; founder-console's audit stream, feedback inbox and seller list, the admin
    dispute queue, the visitor's own votes and the public feed were Seq Scans or whole-set sorts; a member's logbook
    by name (worker drawer, resume, assistant) had no index at all (the only worker_name index is partial to hive-less
    rows); the logbook's team list sorted the hive's 20,832 rows for 50; "fixes for this machine" scanned 49,846
    fault_knowledge rows; an entry's XP lookup scanned 97,191; compute_hive_readiness counted voice notes by scanning
    every entry. supabase/migrations/20261020000001_lb2_query_indexes.sql adds the 19 indexes; re-measured after,
    every one of those reads uses its index.
  * the rest that still read a growing table end to end are not index-shaped, and are listed with their exact change
    in the LB2 report (.tmp/slw/lb2_evidence.json "known"): a filter on a per-row SECURITY DEFINER call (is_mine /
    to_me / from_me), RLS-only reads whose policy is an OR around a hashed IN-subplan, DISTINCT ON / GROUP BY views
    over a hive's whole history, and admin reads that pull tens of thousands of rows to sum in the browser.

WHAT THIS HOLDS
  STATIC (always):
    1. each index below is declared in supabase/migrations - the last DDL naming it creates it, on the same table,
       the same key columns in the same order and direction, the same partial predicate;
    2. each page read it serves still has the shape it was measured in (an anchor on the page's own code): a read
       that changes is re-measured, not assumed to stay on its index.
  LIVE (when the local database answers; SKIP otherwise - never a fail):
    3. each index exists in the local database (declared and never applied is a red);
    4. inside ONE rolled-back transaction the reads' tables are grown from their own rows (session_replication_role =
       replica: no trigger fires, no FK is checked; uuids remapped so the platform gains hives, people and assets),
       ANALYZEd, and each read's EXPLAIN - as its cast, RLS on - uses its index and does not Seq Scan the table. The
       grown tables are vacuumed after, so the dead rows of the rollback do not linger in the planner's statistics.

    python tools/validate_query_indexes.py
    python tools/validate_query_indexes.py --static-only
    python tools/validate_query_indexes.py --self-test
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
MIG = ROOT / "supabase" / "migrations"
DB = "supabase_db_workhive"
ENV = dict(os.environ, MSYS_NO_PATHCONV="1")


def chain(rel: str, *parts: str) -> str:
    """a regex for ONE query chain: .from('<rel>') followed, in order, by each part, never crossing into another .from("""
    gap = r"(?:(?!\.from\()[\s\S]){0,900}?"
    return r"\.from\(\s*['\"]%s['\"]\s*\)" % re.escape(rel) + "".join(gap + p for p in parts)


# name, table, key columns, partial predicate, the page reads it serves (file, anchor), the live probe
INDEXES = [
    {"name": "idx_pm_scope_items_hive_id", "table": "pm_scope_items", "cols": ["hive_id"], "where": None,
     "reads": [("alert-hub.html", chain("v_pm_scope_items_truth", r"\.eq\('hive_id', HIVE_ID\)", r"\.eq\('is_overdue', true\)")),
               ("hive.html", chain("v_pm_scope_items_truth", r"\.eq\('hive_id', HIVE_ID\)")),
               ("index.html", chain("v_pm_scope_items_truth", r"\.eq\('hive_id', HIVE_ID\)", r"\.eq\('is_overdue', true\)")),
               ("dayplanner.html", r"pmQ = pmQ\.or\(`hive_id\.eq\.\$\{HIVE_ID\},hive_id\.is\.null`\)")],
     "probe": {"cast": "driverben", "hive": "Dela Cruz Delivery Fleet",
               "sql": "SELECT pm_asset_id, asset_name, next_due_date, days_until_due, is_overdue FROM public.v_pm_scope_items_truth "
                      "WHERE hive_id = '{hive}' AND is_overdue = true ORDER BY days_until_due, id LIMIT 500"}},
    {"name": "idx_automation_log_hive_triggered", "table": "automation_log", "cols": ["hive_id", "triggered_at desc"], "where": None,
     "reads": [("alert-hub.html", chain("automation_log", r"\.eq\('hive_id', HIVE_ID\)", r"\.eq\('status', 'failed'\)", r"\.order\('triggered_at'"))],
     "probe": {"cast": "driverben", "hive": "Dela Cruz Delivery Fleet",
               "sql": "SELECT job_name, status, detail, triggered_at FROM public.automation_log WHERE hive_id = '{hive}' AND status = 'failed' "
                      "AND triggered_at >= now() - interval '1 day' ORDER BY triggered_at DESC, id LIMIT 10"}},
    {"name": "idx_hive_audit_log_hive_action_created", "table": "hive_audit_log", "cols": ["hive_id", "action", "created_at desc"], "where": None,
     "reads": [("community.html", chain("hive_audit_log", r"\.eq\('hive_id', HIVE_ID\)\.eq\('action', 'report_post'\)", r"\.order\('created_at'"))],
     "probe": {"cast": "jeepneyoscarph", "hive": "Ramos Jeepney Line",
               "sql": "SELECT meta, created_at FROM public.hive_audit_log WHERE hive_id = '{hive}' AND action = 'report_post' "
                      "ORDER BY created_at DESC, id LIMIT 200"}},
    {"name": "idx_hive_audit_log_created", "table": "hive_audit_log", "cols": ["created_at desc"], "where": None,
     # OPC (2026-10-22): the console's trail is every hive's, read by the admin-only founder_audit_feed
     "reads": [("supabase/migrations", r"from hive_audit_log\s+order by created_at desc, id limit least\(")],
     "probe": {"cast": "leandromarquez",
               "sql": "SELECT id, action, actor, target_type, target_name, hive_id, created_at, meta FROM public.hive_audit_log "
                      "ORDER BY created_at DESC, id LIMIT 50"}},
    {"name": "idx_platform_feedback_created", "table": "platform_feedback", "cols": ["created_at desc"], "where": None,
     # the inbox's one read (SL LB1 probes one past 500); the console runs it from operator-actions.js since OPC
     "reads": [("platform-actions.html", chain("platform_feedback", r"\.order\('created_at', \{ ascending: false \}\)", r"\.limit\(500 \+ 1\)")),
               ("operator-actions.js", chain("platform_feedback", r"\.order\('created_at', \{ ascending: false \}\)", r"\.limit\(500 \+ 1\)"))],
     "probe": {"cast": "leandromarquez",
               "sql": "SELECT id, created_at, kind, subject, status FROM public.platform_feedback ORDER BY created_at DESC, id LIMIT 500"}},
    {"name": "idx_platform_feedback_votes_token", "table": "platform_feedback_votes", "cols": ["voter_token"], "where": None,
     "reads": [("feedback/index.html", chain("platform_feedback_votes", r"\.eq\('voter_token', tok\)"))],
     "probe": {"cast": None, "sql": "SELECT feedback_id FROM public.platform_feedback_votes WHERE voter_token = '{token}' LIMIT 500"}},
    {"name": "idx_mkt_disputes_created", "table": "marketplace_disputes", "cols": ["created_at"], "where": None,
     "reads": [("marketplace-admin.html", chain("marketplace_disputes", r"\.order\('created_at', \{ ascending: true \}\)", r"\.limit\(100\)"))],
     "probe": {"cast": "leandromarquez",
               "sql": "SELECT id, order_id, listing_id, opened_by, seller_name, reason, status, created_at FROM public.marketplace_disputes "
                      "ORDER BY created_at, id LIMIT 100"}},
    {"name": "idx_marketplace_sellers_created", "table": "marketplace_sellers", "cols": ["created_at desc"], "where": None,
     "reads": [("marketplace-admin.html", chain("v_marketplace_sellers_truth", r"\.order\('created_at', \{ ascending: false \}\)", r"\.limit\(100 \+ 1\)")),
               ("platform-actions.html", chain("v_marketplace_sellers_truth", r"\.order\('created_at', \{ ascending: false \}\)")),
               ("operator-actions.js", chain("v_marketplace_sellers_truth", r"\.order\('created_at', \{ ascending: false \}\)"))],
     "probe": {"cast": "leandromarquez",
               "sql": "SELECT id, worker_name, tier, kyb_verified, created_at, active_listings_count FROM public.v_marketplace_sellers_truth "
                      "ORDER BY created_at DESC, id LIMIT 100"}},
    {"name": "idx_mkt_listings_status_created", "table": "marketplace_listings", "cols": ["status", "created_at"], "where": None,
     "reads": [("marketplace-admin.html", chain("v_marketplace_listings_truth", r"\.eq\('status', status\)", r"\.order\('created_at', \{ ascending: true \}\)")),
               ("operator-actions.js", chain("v_marketplace_listings_truth", r"\.eq\('status', 'draft'\)\.order\('created_at', \{ ascending: true \}\)"))],
     "probe": {"cast": "leandromarquez",
               "sql": "SELECT id, title, status, created_at FROM public.v_marketplace_listings_truth WHERE status = 'published' "
                      "ORDER BY created_at, id LIMIT 100"}},
    {"name": "idx_logbook_worker_created", "table": "logbook", "cols": ["worker_name", "created_at desc"], "where": None,
     "reads": [("worker-drawer.js", chain("logbook", r"\.eq\('worker_name', workerName\)\.order\('created_at', \{ ascending: false \}\)")),
               ("resume.html", chain("v_logbook_truth", r"\.eq\('worker_name', wname\)\.order\('created_at'"))],
     "probe": {"cast": "driverben", "hive": "Dela Cruz Delivery Fleet",
               "sql": "SELECT machine, problem, created_at FROM public.logbook WHERE worker_name = '{name}' ORDER BY created_at DESC, id LIMIT 3"}},
    {"name": "idx_logbook_hive_entry_date", "table": "logbook", "cols": ["hive_id", "date desc"], "where": None,
     "reads": [("logbook.html", chain("logbook", r"\.eq\('hive_id', HIVE_ID\)", r"\.order\('date', \{ ascending: false \}\)"))],
     "probe": {"cast": "bryangarcia", "hive": "Baguio Textile Mills",
               "sql": "SELECT id, date, machine, status FROM public.logbook WHERE hive_id = '{hive}' ORDER BY date DESC, id LIMIT 50"}},
    {"name": "idx_logbook_hive_status", "table": "logbook", "cols": ["hive_id", "status"], "where": None,
     "reads": [("logbook.html", chain("logbook", r"\.eq\('hive_id', HIVE_ID\)\.eq\('status', 'Closed'\)")),
               ("hive.html", chain("v_logbook_truth", r"\.eq\('hive_id', HIVE_ID\)", r"\.eq\('status', 'Open'\)"))],
     "probe": {"cast": "driverben", "hive": "Tan Delivery Vans",
               "sql": "SELECT worker_name FROM public.v_logbook_truth WHERE hive_id = '{hive}' AND status = 'Open' LIMIT 2000"}},
    {"name": "idx_fault_knowledge_machine_created", "table": "fault_knowledge", "cols": ["machine", "created_at desc"], "where": None,
     "reads": [("logbook.html", chain("fault_knowledge", r"\.eq\('machine', machineId\)", r"\.order\('created_at', \{ ascending: false \}\)"))],
     "probe": {"cast": "bryangarcia", "hive": "Baguio Textile Mills",
               "sql": "SELECT problem, created_at FROM public.fault_knowledge WHERE machine = '{machine}' AND problem IS NOT NULL "
                      "ORDER BY created_at DESC, id LIMIT 5"}},
    {"name": "idx_xp_log_source_live", "table": "achievement_xp_log", "cols": ["source_id"], "where": "reversed_at is null",
     # the logbook's receipt read, named _logXpNote(sourceId) by SL LB1 (the same query: one source's live awards)
     "reads": [("logbook.html", chain("achievement_xp_log", r"\.eq\('source_id', sourceId\)\.is\('reversed_at', null\)")),
               ("pm-scheduler.html", chain("achievement_xp_log", r"\.eq\('source_id', sourceId\)\.is\('reversed_at', null\)"))],
     "probe": {"cast": "bryangarcia", "hive": "Baguio Textile Mills",
               "sql": "SELECT xp_earned FROM public.achievement_xp_log WHERE source_id = '{source}' AND reversed_at IS NULL LIMIT 20"}},
    {"name": "idx_xp_log_earned", "table": "achievement_xp_log", "cols": ["earned_at desc"], "where": None,
     "reads": [("achievements.html", chain("achievement_xp_log", r"\.gte\('earned_at', _weekAgoIso\)"))],
     "probe": {"cast": "davidvelasco", "hive": "Lucena Pharmaceutical Mfg.",
               "sql": "SELECT xp_earned FROM public.achievement_xp_log WHERE earned_at >= now() - interval '7 days' LIMIT 1000"}},
    {"name": "idx_community_posts_public_feed", "table": "community_posts", "cols": ["created_at desc"],
     "where": "public and not flagged and deleted_at is null",
     "reads": [("public-feed.html", chain("v_community_posts_truth", r"\.eq\('public', true\)", r"\.eq\('flagged', false\)", r"\.is\('deleted_at', null\)",
                                          r"\.order\('created_at', \{ ascending: false \}\)")),
               ("community.html", chain("v_community_posts_truth", r"\.eq\('public', true\)", r"\.eq\('flagged', false\)", r"\.is\('deleted_at', null\)",
                                        r"\.order\('created_at', \{ ascending: false \}\)"))],
     "probe": {"cast": None,
               "sql": "SELECT id, author_name, content, category, created_at FROM public.v_community_posts_truth WHERE public = true AND flagged = false "
                      "AND deleted_at IS NULL ORDER BY created_at DESC, id LIMIT 20"}},
    {"name": "idx_marketplace_sellers_hive_id", "table": "marketplace_sellers", "cols": ["hive_id"], "where": None,
     "reads": [("community.html", chain("v_marketplace_sellers_truth", r"\.eq\('hive_id', hiveId\)"))],
     "probe": {"cast": "jeepneyoscarph", "hive": "Ramos Jeepney Line",
               "sql": "SELECT worker_name, tier, total_sales, rating_avg FROM public.v_marketplace_sellers_truth WHERE hive_id = '{hive}'"}},
    {"name": "idx_marketplace_sellers_auth_uid", "table": "marketplace_sellers", "cols": ["auth_uid"], "where": None,
     "reads": [("marketplace-seller.html", chain("v_marketplace_sellers_truth", r"\.or\(_mine\)"))],
     "probe": {"cast": "bryangarcia", "hive": "Baguio Textile Mills",
               "sql": "SELECT * FROM public.v_marketplace_sellers_truth WHERE (auth_uid = '{uid}' OR (auth_uid IS NULL AND worker_name = '{name}'))"}},
    {"name": "idx_service_providers_auth_uid", "table": "service_providers", "cols": ["auth_uid"], "where": "auth_uid is not null",
     # 20261020000003: my_service_provider_ids()'s own-profile arm and person_credit_balance()'s provider join
     "reads": [("supabase/migrations", r"select sp\.id from public\.service_providers sp\s+where sp\.auth_uid = auth\.uid\(\)")],
     # the reads it serves run as the functions' OWNER (no one signed in may read service_providers directly)
     "probe": {"cast": "owner",
               "sql": "SELECT sp.id FROM public.service_providers sp WHERE sp.auth_uid = "
                      "(SELECT u.id FROM auth.users u WHERE split_part(u.email, '@', 1) = 'bryangarcia')"}},
    {"name": "idx_voice_journal_hive_created", "table": "voice_journal_entries", "cols": ["hive_id", "created_at desc"], "where": None,
     # compute_hive_readiness() is SECURITY DEFINER: its count runs as the owner, so the probe does too
     "reads": [("supabase/migrations", r"FROM public\.voice_journal_entries vje[\s\S]{0,300}?vje\.hive_id = ")],
     "probe": {"cast": "owner", "hive": "Tan Delivery Vans",
               "sql": "SELECT count(*) FROM public.voice_journal_entries vje WHERE vje.hive_id = '{hive}' AND vje.created_at >= now() - interval '30 days'"}},
]

# the live growth: (depth copies, tenant copies, depth step in days) per table - every probe's tables and the tables
# their views join or their policies ask, so RLS and the joins are planned at size too
GROW = {
    "hives": (0, 50, 0), "hive_members": (0, 50, 0), "worker_profiles": (0, 50, 0),
    "pm_assets": (0, 60, 0), "pm_scope_items": (0, 60, 0), "asset_nodes": (0, 60, 0),
    "automation_log": (4, 55, 7), "platform_feedback": (49, 2950, 3), "platform_feedback_votes": (0, 3000, 0),
    "marketplace_disputes": (49, 1950, 3), "marketplace_sellers": (0, 1500, 0), "marketplace_listings": (0, 1000, 0),
    "logbook": (1, 2, 45), "fault_knowledge": (0, 1, 0), "achievement_xp_log": (1, 2, 30),
    "community_posts": (9, 290, 30), "voice_journal_entries": (4, 45, 30),
    # the shapes (20261020000003): the tables their probes read, so a per-row call or a full read shows at size
    "service_providers": (0, 1000, 0), "service_requests": (9, 490, 7), "marketplace_reviews": (9, 490, 7),
    "marketplace_inquiries": (9, 490, 7), "inventory_items": (0, 100, 0), "inventory_transactions": (4, 45, 30),
    "skill_badges": (0, 100, 0),
}
SEEDS = [  # empty tables are seeded first, from rows that existed before the growth
    "insert into public.platform_feedback_votes (feedback_id, voter_token) select id, md5(id::text) from public.platform_feedback;",
    "insert into public.marketplace_disputes (listing_id, opened_by, seller_name, reason, status) select id, 'lb2 buyer', seller_name, "
    "'lb2 synthetic', 'open' from public.marketplace_listings order by created_at limit 10;",
]
# ── the shapes (20261020000003): reads no index could serve until their policy, view or function changed ─────────────
# Each object's LAST definition in supabase/migrations must keep the shape that was measured (a later migration that
# re-creates it the old way is a red), and - live - the database must hold that definition.
M3 = "20261020000003_lb2_read_shapes.sql"
SHAPES = [
    {"label": "analytics_events_select_admin asks is_platform_admin() once per statement", "kind": "policy",
     "table": "analytics_events", "name": "analytics_events_select_admin",
     "must": [r"\(\s*select\s+public\.is_platform_admin\(\)\s*\)"], "live": r"\(\s*SELECT\s+is_platform_admin\(\)"},
    {"label": "v_marketplace_listings_truth.is_mine is the reader's listing ids, asked once", "kind": "view",
     "name": "v_marketplace_listings_truth", "invoker": True,
     "must": [r"l\.id\s*=\s*ANY\s*\(\s*ARRAY\s*\(\s*SELECT\s+public\.my_listing_ids\(\)\s*\)\s*\)\s*AS\s+is_mine"],
     "mustnot": [r"listing_is_mine\("], "live": r"my_listing_ids\(\)"},
    {"label": "v_marketplace_inquiries_truth.to_me / from_me are the reader's ids, asked once", "kind": "view",
     "name": "v_marketplace_inquiries_truth", "invoker": True,
     "must": [r"my_listing_ids\(\)[\s\S]*AS\s+to_me", r"my_inquiry_ids\(\)[\s\S]*AS\s+from_me"],
     "mustnot": [r"listing_is_mine\(", r"inquiry_is_from_me\("], "live": r"my_inquiry_ids\(\)"},
    # LB2 x BRH-R (20261022000005): the public grid runs as its reader, who may not read auth_uid - so is_mine is the
    # reader's listing ids asked once (the truth view's shape), never auth_uid and never a definer call per row
    {"label": "v_marketplace_listings_public.is_mine is the reader's listing ids, asked once", "kind": "view",
     "name": "v_marketplace_listings_public", "invoker": True,
     "must": [r"l\.id\s*=\s*ANY\s*\(\s*ARRAY\s*\(\s*SELECT\s+public\.my_listing_ids\(\)[^)]*\)\s*\)\s*\)\s*AS\s+is_mine"],
     "mustnot": [r"listing_is_mine\(", r"l\.auth_uid"], "live": r"my_listing_ids\(\)"},
    {"label": "my_service_provider_ids() is a UNION of its two arms, each on an index", "kind": "function",
     "name": "my_service_provider_ids", "must": [r"\bunion\b"], "mustnot": [r"\bor\s*\(\s*sp\.provider_type"], "live": r"\bunion\b"},
    {"label": "v_service_provider_truth counts each provider's jobs and reviews per provider (LATERAL)", "kind": "view",
     "name": "v_service_provider_truth", "invoker": True,
     "must": [r"left\s+join\s+lateral[\s\S]*?sr\.matched_provider_id\s*=\s*sp\.id"], "live": r"LEFT JOIN LATERAL"},
    {"label": "get_hive_trade_peers narrows lvl to the hive's active members", "kind": "function", "name": "get_hive_trade_peers",
     "must": [r"sb\.auth_uid\s+IN\s*\(\s*SELECT\s+m\.auth_uid\s+FROM\s+public\.hive_members\s+m"], "live": r"sb\.auth_uid IN \(SELECT m\.auth_uid"},
    {"label": "get_credit_ledger_totals gives an admin the totals the ledger keeps", "kind": "function", "name": "get_credit_ledger_totals",
     "must": [r"from\s+public\.service_credit_ledger_totals", r"security\s+invoker"], "live": r"service_credit_ledger_totals"},
    {"label": "the ledger keeps its totals as it is written", "kind": "trigger", "table": "service_credit_ledger",
     "name": "trg_keep_ledger_totals", "must": [r"after\s+insert\s+or\s+update\s+or\s+delete\s+on\s+public\.service_credit_ledger"]},
    {"label": "my_recent_xp asks each of the reader's names for its own newest rows", "kind": "function", "name": "my_recent_xp",
     "must": [r"cross\s+join\s+lateral", r"where\s+l\.worker_name\s*=\s*n\.name", r"security\s+invoker"], "live": r"cross join lateral"},
]
# grown-size probes of the shapes, in the same rolled-back transaction as the index probes: a view read EXPLAINed as its
# cast, or a function CALLED as its cast with auto_explain logging every statement inside it. Each must not Seq Scan
# the tables it names (and must use the index it names, when it names one).
SHAPE_PROBES = [
    {"label": "is_mine on v_marketplace_listings_truth", "cast": "bryangarcia", "kind": "explain", "noseq": ["marketplace_listings"],
     "sql": "SELECT count(*) FROM public.v_marketplace_listings_truth WHERE is_mine = true"},
    {"label": "to_me on v_marketplace_inquiries_truth", "cast": "bryangarcia", "kind": "explain", "noseq": ["marketplace_inquiries"],
     "sql": "SELECT count(*) FROM public.v_marketplace_inquiries_truth WHERE to_me = true"},
    {"label": "from_me on v_marketplace_inquiries_truth", "cast": "isidrosuarez", "kind": "explain", "noseq": ["marketplace_inquiries"],
     "sql": "SELECT id FROM public.v_marketplace_inquiries_truth WHERE from_me = true ORDER BY created_at DESC LIMIT 50"},
    # the reader's ids are found inside my_listing_ids() on idx_marketplace_listings_auth_uid; the view then looks rows up by id
    {"label": "is_mine on v_marketplace_listings_public", "cast": "isidrosuarez", "kind": "explain", "noseq": ["marketplace_listings"],
     "sql": "SELECT count(*) FROM public.v_marketplace_listings_public WHERE is_mine = true"},
    {"label": "v_service_provider_truth for one provider", "cast": "davidvelasco", "kind": "explain",
     "noseq": ["service_requests", "marketplace_reviews"],
     "sql": "SELECT display_name, tier, completed_jobs, rating_avg FROM public.v_service_provider_truth WHERE id = '{provider}'"},
    {"label": "a member's inventory transactions (inventory.html)", "cast": "davidvelasco", "hive": "Lucena Pharmaceutical Mfg.",
     "kind": "explain", "noseq": ["inventory_items", "inventory_transactions"],
     "sql": "SELECT * FROM public.v_inventory_transactions_truth WHERE (auth_uid = '{uid}' OR (auth_uid IS NULL AND worker_name = '{name}')) "
            "AND created_at >= now() - interval '365 days' ORDER BY created_at DESC, id LIMIT 500"},
    {"label": "a hive's overdue PM scope (alert-hub.html)", "cast": "driverben", "hive": "Dela Cruz Delivery Fleet", "kind": "explain",
     "noseq": ["pm_assets", "pm_scope_items", "hive_members"],
     "sql": "SELECT pm_asset_id FROM public.v_pm_scope_items_truth WHERE hive_id = '{hive}' AND is_overdue = true ORDER BY days_until_due, id LIMIT 500"},
    {"label": "a member's own hives (every RLS membership check)", "cast": "davidvelasco", "kind": "explain", "noseq": ["hive_members"],
     "uses": "idx_hive_members_auth_uid",
     "sql": "SELECT hm.hive_id FROM public.hive_members hm WHERE hm.auth_uid = (SELECT auth.uid()) AND hm.status = 'active'"},
    {"label": "my_service_provider_ids()", "cast": "davidvelasco", "kind": "call", "noseq": ["service_providers"],
     "sql": "SELECT count(*) FROM (SELECT public.my_service_provider_ids()) s"},
    {"label": "my_credit_balance()", "cast": "isidrosuarez", "kind": "call", "noseq": ["service_providers"],
     "sql": "SELECT public.my_credit_balance() IS NOT NULL"},
    {"label": "get_hive_trade_peers()", "cast": "jeepneyoscarph", "hive": "Ramos Jeepney Line", "kind": "call", "noseq": ["skill_badges"],
     "sql": "SELECT count(*) FROM (SELECT public.get_hive_trade_peers('{hive}')) s"},
    {"label": "my_recent_xp(30)", "cast": "davidvelasco", "kind": "call", "noseq": ["achievement_xp_log"], "uses": "idx_xp_log_worker",
     "sql": "SELECT count(*) FROM public.my_recent_xp(30)"},
    {"label": "get_credit_ledger_totals() as an admin", "cast": "leandromarquez", "kind": "call", "noseq": ["service_credit_ledger"],
     "sql": "SELECT count(*) FROM public.get_credit_ledger_totals()"},
]
# a policy that compares against a bare auth.uid() makes every subquery inside it unindexable under RLS (the call is
# inlined per row and is not leakproof): measured, `hm.auth_uid = auth.uid()` read all of hive_members (2,625 rows
# removed, 3.5 ms) where `hm.auth_uid = (select auth.uid())` was one index probe (0.037 ms). 20261020000003 wrapped all
# 480 calls in 225 policies; no policy may bring one back.
BARE_UID = re.compile(r"(?<!select )(?<!SELECT )\bauth\.uid\(\)", re.I)
LEDGER_RECONCILE = (
    "select coalesce(string_agg(coalesce(a.entry_type, t.entry_type) || ' ledger ' || coalesce(a.s::text, '-') || '/' || "
    "coalesce(a.c::text, '-') || ' kept ' || coalesce(t.total::text, '-') || '/' || coalesce(t.entries::text, '-'), '; '), '') "
    "from (select entry_type, sum(amount) s, count(*) c from public.service_credit_ledger group by 1) a "
    "full join (select entry_type, total, entries from public.service_credit_ledger_totals where entries > 0) t "
    "on t.entry_type = a.entry_type where a.s is distinct from t.total or a.c is distinct from t.entries;")
PERSON = {"worker_name", "author_name", "seller_name", "buyer_name", "reviewer_name", "actor", "display_name", "submitted_by",
          "opened_by", "wo_assigned_to", "last_completed_by", "acted_by", "created_by", "approved_by", "voter_token"}
COL_RULE = {("community_reactions", "emoji"): "src.emoji", ("marketplace_reviews", "direction"): "src.direction"}
CAP = 130000


# ── static ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _sql_code(src: str) -> str:
    src = re.sub(r"/\*[\s\S]*?\*/", " ", src)
    return re.sub(r"--[^\n]*", " ", src)


def _code(src: str) -> str:
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    src = re.sub(r"<!--[\s\S]*?-->", "", src)
    return re.sub(r"(?m)(?<![:\"'`\\/])//[^\n]*$", "", src)


def _norm_cols(s: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    res = []
    for c in out:
        c = re.sub(r"\s+", " ", c.replace('"', "")).strip().lower()
        c = re.sub(r"\s+asc$", "", c)
        if c:
            res.append(c)
    return res


def _norm_pred(s: str | None) -> str | None:
    if s is None:
        return None
    s = s.replace('"', "").lower()
    s = re.sub(r"\(\s*(\w+)\s*=\s*true\s*\)", r"\1", s)
    s = re.sub(r"\(\s*(\w+)\s*=\s*false\s*\)", r"not \1", s)
    s = re.sub(r"\b(\w+)\s*=\s*true\b", r"\1", s)
    s = re.sub(r"\b(\w+)\s*=\s*false\b", r"not \1", s)
    return re.sub(r"[\s()]+", "", s)


CREATE_RX = re.compile(r"create\s+(?:unique\s+)?index\s+(?:concurrently\s+)?(?:if\s+not\s+exists\s+)?\"?(\w+)\"?\s+on\s+(?:only\s+)?"
                       r"(?:\"?public\"?\.)?\"?(\w+)\"?\s*(?:using\s+\"?\w+\"?\s*)?\(", re.I)
DROP_RX = re.compile(r"drop\s+index\s+(?:concurrently\s+)?(?:if\s+exists\s+)?([\w\".,\s]+?)(?:\s+cascade|\s+restrict)?\s*;", re.I)


def declared(migs: dict[str, str]) -> dict[str, dict | None]:
    """replay every migration in order: index name -> its last definition (None when the last DDL dropped it)"""
    state: dict[str, dict | None] = {}
    for name in sorted(migs):
        code = _sql_code(migs[name])
        events = []
        for m in CREATE_RX.finditer(code):
            i, depth = m.end() - 1, 0
            for j in range(i, len(code)):
                if code[j] == "(":
                    depth += 1
                elif code[j] == ")":
                    depth -= 1
                    if depth == 0:
                        break
            cols = _norm_cols(code[i + 1:j])
            tail = code[j + 1:code.find(";", j) if code.find(";", j) >= 0 else len(code)]
            wm = re.search(r"\bwhere\b([\s\S]*)$", tail, re.I)
            events.append((m.start(), m.group(1).lower(), {"table": m.group(2).lower(), "cols": cols,
                                                          "where": _norm_pred(wm.group(1)) if wm else None, "file": name}))
        for m in DROP_RX.finditer(code):
            for nm in m.group(1).split(","):
                nm = nm.strip().replace('"', "").split(".")[-1].lower()
                if nm:
                    events.append((m.start(), nm, None))
        for _, nm, ev in sorted(events, key=lambda e: e[0]):
            state[nm] = ev
    return state


def _stmt_end(code: str, start: int, kind: str) -> int:
    """where the statement that starts at `start` ends: a function's body is dollar-quoted, everything else ends at ;"""
    if kind == "function":
        m = re.compile(r"\$(\w*)\$").search(code, start)
        if m:
            close = code.find(m.group(0), m.end())
            if close >= 0:
                semi = code.find(";", close + len(m.group(0)))
                return semi if semi >= 0 else len(code)
    semi = code.find(";", start)
    return semi if semi >= 0 else len(code)


def latest_defs(migs: dict[str, str]) -> dict:
    """replay every migration in order: (kind, name[, table]) -> (text of its LAST create, file), None when dropped last"""
    state: dict = {}
    for fname in sorted(migs):
        code = _sql_code(migs[fname])
        ev = []
        for m in re.finditer(r"\b(create(?:\s+or\s+replace)?|drop)\s+policy\s+(?:if\s+exists\s+)?(\"[^\"]+\"|\w+)\s+on\s+(?:only\s+)?"
                             r"(?:\"?public\"?\.)?\"?(\w+)\"?", code, re.I):
            ev.append((m.start(), ("policy", m.group(2).strip('"').lower(), m.group(3).lower()), m.group(1).lower().startswith("create"), "policy"))
        for m in re.finditer(r"\b(create(?:\s+or\s+replace)?|drop)\s+view\s+(?:if\s+exists\s+)?(?:\"?public\"?\.)?\"?(\w+)\"?", code, re.I):
            ev.append((m.start(), ("view", m.group(2).lower()), m.group(1).lower().startswith("create"), "view"))
        for m in re.finditer(r"\b(create(?:\s+or\s+replace)?|drop)\s+function\s+(?:if\s+exists\s+)?(?:\"?public\"?\.)?\"?(\w+)\"?\s*\(",
                             code, re.I):
            ev.append((m.start(), ("function", m.group(2).lower()), m.group(1).lower().startswith("create"), "function"))
        for m in re.finditer(r"\bcreate\s+(?:or\s+replace\s+)?(?:constraint\s+)?trigger\s+\"?(\w+)\"?[\s\S]*?\bon\s+(?:\"?public\"?\.)?\"?(\w+)\"?",
                             code, re.I):
            ev.append((m.start(), ("trigger", m.group(1).lower(), m.group(2).lower()), True, "trigger"))
        for m in re.finditer(r"\bdrop\s+trigger\s+(?:if\s+exists\s+)?\"?(\w+)\"?\s+on\s+(?:\"?public\"?\.)?\"?(\w+)\"?", code, re.I):
            ev.append((m.start(), ("trigger", m.group(1).lower(), m.group(2).lower()), False, "trigger"))
        for pos, key, is_create, kind in sorted(ev, key=lambda e: e[0]):
            state[key] = (code[pos:_stmt_end(code, pos, kind)], fname) if is_create else None
    return state


def _shape_key(sh: dict) -> tuple:
    return (sh["kind"], sh["name"].lower()) if sh["kind"] in ("view", "function") else (sh["kind"], sh["name"].lower(), sh["table"].lower())


def shape_problems(migs: dict[str, str], files: dict[str, str]) -> list[str]:
    bad = []
    defs = latest_defs(migs)
    for sh in SHAPES:
        d = defs.get(_shape_key(sh), "missing")
        if d == "missing":
            bad.append(f"{sh['label']}: {sh['kind']} {sh['name']} is not defined in supabase/migrations")
            continue
        if d is None:
            bad.append(f"{sh['label']}: {sh['kind']} {sh['name']} is dropped by a later migration")
            continue
        text, fname = d
        for rx in sh.get("must", []):
            if not re.search(rx, text, re.I):
                bad.append(f"{sh['label']}: its last definition ({fname}) lost the measured shape /{rx[:70]}/")
        for rx in sh.get("mustnot", []):
            if re.search(rx, text, re.I):
                bad.append(f"{sh['label']}: its last definition ({fname}) is back to the shape that read every row /{rx[:70]}/")
        if sh.get("invoker") and not re.search(r"security_invoker\s*=\s*(?:on|true)", text, re.I):
            bad.append(f"{sh['label']}: its last definition ({fname}) has no security_invoker - CREATE OR REPLACE VIEW without it "
                       "turns the view into an owner view that reads with RLS off")
    for fname in sorted(migs):
        if fname <= M3:
            continue
        code = _sql_code(migs[fname])
        for m in re.finditer(r"\bcreate\s+policy\b", code, re.I):
            stmt = code[m.start():_stmt_end(code, m.start(), "policy")]
            if BARE_UID.search(stmt):
                bad.append(f"{fname}: a policy compares against a bare auth.uid() - write (select auth.uid()) so the subqueries in it can "
                           "use an index ({})".format(re.sub(r"\s+", " ", stmt)[:90]))
    ach = _code(files.get("achievements.html", ""))
    if not re.search(r"db\.rpc\(\s*'my_recent_xp'", ach):
        bad.append("achievements.html: Recent activity no longer reads my_recent_xp() - a direct read walks everyone's XP history")
    return bad


def static_problems(migs: dict[str, str], files: dict[str, str]) -> list[str]:
    bad = shape_problems(migs, files)
    state = declared(migs)
    for ix in INDEXES:
        d = state.get(ix["name"].lower(), "missing")
        if d == "missing":
            bad.append(f"{ix['name']}: not declared in supabase/migrations")
            continue
        if d is None:
            bad.append(f"{ix['name']}: dropped by a later migration - its read is back to scanning {ix['table']}")
            continue
        if d["table"] != ix["table"]:
            bad.append(f"{ix['name']}: declared on {d['table']}, not {ix['table']}")
        if d["cols"] != ix["cols"]:
            bad.append(f"{ix['name']}: declared on ({', '.join(d['cols'])}), the measured read needs ({', '.join(ix['cols'])})")
        if (d["where"] or None) != _norm_pred(ix["where"]):
            bad.append(f"{ix['name']}: partial predicate is {d['where']!r}, the read needs {_norm_pred(ix['where'])!r}")
        for f, rx in ix["reads"]:
            if f == "supabase/migrations":
                if not any(re.search(rx, _sql_code(s)) for s in migs.values()):
                    bad.append(f"{ix['name']}: the definer function's read it serves is gone from supabase/migrations - re-measure")
                continue
            if not re.search(rx, _code(files.get(f, ""))):
                bad.append(f"{f}: the read {ix['name']} serves changed shape - re-measure its plan at grown size and update the gate")
    # a total summed in the browser from a capped read is wrong past the cap and grows with every row: the credit position
    # reads one row per entry type from the database (get_credit_ledger_totals, 20261020000002), never the ledger rows
    if not any(re.search(r"create or replace function public\.get_credit_ledger_totals\(\)", _sql_code(s)) for s in migs.values()):
        bad.append("supabase/migrations: get_credit_ledger_totals is gone - the credit position is back to a browser sum")
    pa = _code(files.get("platform-actions.html", ""))
    if not re.search(r"db\.rpc\('get_credit_ledger_totals'\)", pa):
        bad.append("platform-actions.html: the credit position no longer reads its totals from get_credit_ledger_totals")
    if re.search(r"v_service_credit_ledger_truth'\)\.select\('entry_type, amount'\)\.limit\(", pa):
        bad.append("platform-actions.html: the credit position sums ledger rows from a capped read again (wrong past the cap)")
    return bad


def load() -> tuple[dict[str, str], dict[str, str]]:
    migs = {p.name: p.read_text(encoding="utf-8", errors="replace") for p in MIG.glob("*.sql")}
    names = {f for ix in INDEXES for f, _ in ix["reads"] if f != "supabase/migrations"} | {"platform-actions.html", "achievements.html"}
    files = {f: (ROOT / f).read_text(encoding="utf-8", errors="replace") for f in sorted(names) if (ROOT / f).exists()}
    return migs, files


# ── live ───────────────────────────────────────────────────────────────────────────────────────────────────────────
def _psql(sql: str, timeout: int = 60, args: list[str] | None = None) -> tuple[int, str, str]:
    try:
        r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-X"] + (args or ["-At"]),
                           input=sql, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, env=ENV)
        return r.returncode, r.stdout, r.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return 99, "", str(e)


def _lit(s: str) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def judge(plan: str, ix: dict) -> str | None:
    """None when the plan reads the table through its index; else why not"""
    if re.search(r"Seq Scan on %s\b" % re.escape(ix["table"]), plan):
        return f"Seq Scan on {ix['table']}"
    if not re.search(r"\b%s\b" % re.escape(ix["name"]), plan):
        used = sorted(set(re.findall(r"(?:Index Scan|Index Only Scan|Bitmap Index Scan)(?: Backward)? (?:using|on) (\w+)", plan)))
        return f"{ix['name']} not used (plan uses: {', '.join(used) or 'no index'})"
    return None


def _grow_sql(meta: dict) -> str:
    out = []
    for tbl, (d, n_ten, step) in GROW.items():
        t = meta.get(tbl)
        if not t:
            continue
        pk = t["pk"] or []
        uniq = set(t["uniq"] or [])
        cols, exprs = [], []
        for c in t["cols"]:
            name, typ = c["name"], c["type"]
            if c["generated"] or c["identity"]:
                continue
            is_pk = name in pk
            ten = "g > %d" % d
            if is_pk and len(pk) == 1 and "nextval(" in (c["default"] or ""):
                continue
            if (tbl, name) in COL_RULE:
                e = COL_RULE[(tbl, name)]
            elif typ == "uuid":
                e = ("md5(src.%s::text || ':' || g)::uuid" % name) if is_pk else \
                    ("case when %s then md5(src.%s::text || ':' || g)::uuid else src.%s end" % (ten, name, name))
            elif (c["width"] or 0) > 400 and typ in ("jsonb", "json", "text") and not c["notnull"] and name not in uniq and not is_pk:
                e = "null"
            elif typ.startswith("vector") and not c["notnull"]:
                e = "null"
            elif typ in ("text", "character varying") or typ.startswith("character varying"):
                if is_pk:
                    e = "src.%s || '_' || g" % name
                elif name in PERSON:
                    e = "case when %s then left(src.%s || ' ' || g, 50) else src.%s end" % (ten, name, name)
                elif name == "username":
                    e = "case when %s then left(src.%s, 24) || '_' || g else src.%s end" % (ten, name, name)
                elif name == "email":
                    e = "case when %s then g || '.' || src.%s else src.%s end" % (ten, name, name)
                elif name in uniq and not (c["ndistinct"] is not None and 0 < c["ndistinct"] <= 25):
                    e = "src.%s || '_' || g" % name
                else:
                    e = "src.%s" % name
            elif typ.startswith("character(") and name in uniq:
                n = int(re.search(r"\((\d+)\)", typ).group(1))
                e = "case when %s then upper(substr(md5(src.%s::text || g::text), 1, %d)) else src.%s end" % (ten, name, n, name)
            elif typ.startswith("timestamp"):
                # depth copies step back in time; tenant copies jitter by seconds so no two rows share a timestamp
                e = ("case when g <= %d then src.%s - (g * %d) * interval '1 day' else src.%s - g * interval '7 seconds' end" % (d, name, step, name)) \
                    if step else "src.%s - g * interval '7 seconds'" % name
            elif typ == "date" and step:
                e = "case when g <= %d then src.%s - (g * %d) else src.%s end" % (d, name, step, name)
            else:
                e = "src.%s" % name
            cols.append('"%s"' % name)
            exprs.append(e)
        out.append("insert into public.%s (%s) select %s from (select * from public.%s) src cross join generate_series(1, %d) g "
                   "limit %d on conflict do nothing;" % (tbl, ", ".join(cols), ", ".join(exprs), tbl, d + n_ten, CAP))
        out.append("\\if :ERROR \\echo '@@GROWERR %s' :'LAST_ERROR_MESSAGE' \\endif" % tbl)
    return "\n".join(out)


META_SQL = r"""
select json_object_agg(c.relname, json_build_object(
  'cols', (select json_agg(json_build_object('name', a.attname, 'type', format_type(a.atttypid, a.atttypmod), 'notnull', a.attnotnull,
            'default', pg_get_expr(d.adbin, d.adrelid), 'identity', a.attidentity <> '', 'generated', a.attgenerated <> '',
            'ndistinct', (select s.n_distinct from pg_stats s where s.schemaname = 'public' and s.tablename = c.relname and s.attname = a.attname),
            'width', (select s.avg_width from pg_stats s where s.schemaname = 'public' and s.tablename = c.relname and s.attname = a.attname))
            order by a.attnum)
           from pg_attribute a left join pg_attrdef d on d.adrelid = a.attrelid and d.adnum = a.attnum
          where a.attrelid = c.oid and a.attnum > 0 and not a.attisdropped),
  'pk', (select json_agg(a.attname) from pg_index i join pg_attribute a on a.attrelid = i.indrelid and a.attnum = any(i.indkey)
          where i.indrelid = c.oid and i.indisprimary),
  'uniq', (select json_agg(distinct a.attname) from pg_index i join pg_attribute a on a.attrelid = i.indrelid and a.attnum = any(i.indkey)
            where i.indrelid = c.oid and i.indisunique and not i.indisprimary)))
  from pg_class c join pg_namespace n on n.oid = c.relnamespace
 where n.nspname = 'public' and c.relkind = 'r' and c.relname = any(%s);
"""


def live() -> tuple[str, list[str]]:
    """('skip'|'pass'|'fail', lines)"""
    rc, out, err = _psql("select 1", timeout=20)
    if rc != 0 or out.strip() != "1":
        return "skip", [f"SKIP live half - the local database did not answer ({(err or out).strip()[:80]})"]
    names = [ix["name"] for ix in INDEXES]
    rc, out, err = _psql("select string_agg(indexname, ' ') from pg_indexes where schemaname = 'public' and indexname = any(%s)"
                         % _lit("{" + ",".join(names) + "}"))
    have = set((out or "").split())
    lines = []
    missing = [n for n in names if n not in have]
    for n in missing:
        lines.append(f"FAIL {n}: declared in supabase/migrations but not in the local database - apply 20261020000001_lb2_query_indexes.sql")
    shape_fail = live_shape_definitions(lines)
    # the casts, their hives, the values a probe names
    casts = sorted({ix["probe"]["cast"] for ix in INDEXES if ix["probe"]["cast"] not in (None, "owner")}
                   | {p["cast"] for p in SHAPE_PROBES})
    hives = sorted({ix["probe"].get("hive") for ix in INDEXES if ix["probe"].get("hive")} | {p["hive"] for p in SHAPE_PROBES if p.get("hive")})
    q = ("select json_build_object("
         "'users', (select json_object_agg(split_part(email, '@', 1), id) from auth.users where split_part(email, '@', 1) = any(%s)), "
         "'hives', (select json_object_agg(name, id) from public.hives where name = any(%s)), "
         "'names', (select json_object_agg(m.auth_uid::text || '|' || m.hive_id::text, m.worker_name) from public.hive_members m "
         "           where m.auth_uid is not null and m.hive_id in (select id from public.hives where name = any(%s))), "
         "'token', (select md5(id::text) from public.platform_feedback order by created_at, id limit 1), "
         "'machine', (select machine from public.fault_knowledge where machine is not null and problem is not null "
         "            group by machine order by count(*) desc, machine limit 1), "
         "'source', (select source_id from public.achievement_xp_log where source_id is not null and reversed_at is null "
         "           group by source_id order by count(*) desc, source_id limit 1), "
         "'provider', (select id::text from public.service_providers order by created_at, id limit 1))"
         % (_lit("{" + ",".join(casts) + "}"), _lit("{" + ",".join('"%s"' % h for h in hives) + "}"),
            _lit("{" + ",".join('"%s"' % h for h in hives) + "}")))
    rc, out, err = _psql(q)
    try:
        ref = json.loads(out.strip())
    except ValueError:
        return "fail", lines + [f"FAIL live half - could not resolve the casts ({err.strip()[:120]})"]
    rc, out, err = _psql(META_SQL % _lit("{" + ",".join(GROW) + "}"))
    try:
        meta = json.loads(out.strip())
    except ValueError:
        return "fail", lines + [f"FAIL live half - could not read the catalog ({err.strip()[:120]})"]

    script = ["\\set ON_ERROR_STOP 0", "\\set ON_ERROR_ROLLBACK on", "\\set QUIET on", "\\pset pager off", "\\pset format unaligned",
              "\\pset tuples_only on", "SET application_name = 'lb2_gate';", "LOAD 'auto_explain';", "BEGIN;", "SET LOCAL statement_timeout = '90s';",
              "SET LOCAL lock_timeout = '5s';", "SET LOCAL session_replication_role = replica;"]
    script += SEEDS
    script.append(_grow_sql(meta))
    script.append("SET LOCAL session_replication_role = origin;")
    script.append("ANALYZE " + ", ".join("public.%s" % t for t in GROW) + ";")
    script.append("\\echo '@@SIZES'")
    script.append("SELECT string_agg(relname || '=' || reltuples::bigint, ' ') FROM pg_class WHERE relnamespace = 'public'::regnamespace "
                  "AND relname = ANY(%s);" % _lit("{" + ",".join(GROW) + ",hive_audit_log}"))
    probes = []
    for ix in INDEXES:
        if ix["name"] in missing:
            continue
        p = ix["probe"]
        hive = (ref.get("hives") or {}).get(p.get("hive") or "", "") if p.get("hive") else ""
        uid = (ref.get("users") or {}).get(p["cast"] or "", "") if p["cast"] not in (None, "owner") else ""
        name = (ref.get("names") or {}).get(uid + "|" + hive, "") if uid and hive else ""
        if (p.get("hive") and not hive) or (p["cast"] not in (None, "owner") and not uid):
            lines.append(f"FAIL {ix['name']}: its probe's cast or hive is not in the local database ({p['cast']}, {p.get('hive')})")
            missing.append(ix["name"])
            continue
        sql = (p["sql"].replace("{hive}", hive).replace("{uid}", uid).replace("{name}", name.replace("'", "''"))
               .replace("{token}", ref.get("token") or "").replace("{machine}", (ref.get("machine") or "").replace("'", "''"))
               .replace("{source}", (ref.get("source") or "").replace("'", "''")))
        probes.append((ix, sql))
        script.append("\\echo '@@Q %s'" % ix["name"])
        if p["cast"] == "owner":
            script.append("RESET ROLE;")
        elif p["cast"] is None:
            script.append("SET LOCAL ROLE anon;")
            script.append("SET LOCAL request.jwt.claims = '{\"role\":\"anon\"}';")
        else:
            script.append("SET LOCAL ROLE authenticated;")
            script.append("SET LOCAL request.jwt.claims = %s;" % _lit(json.dumps({"sub": uid, "role": "authenticated", "aud": "authenticated"})))
        script.append("EXPLAIN " + sql + ";")
        script.append("\\if :ERROR \\echo '@@ERR' :'LAST_ERROR_MESSAGE' \\endif")
        script.append("RESET ROLE;")
    sprobes = []
    for i, p in enumerate(SHAPE_PROBES):
        hive = (ref.get("hives") or {}).get(p.get("hive") or "", "") if p.get("hive") else ""
        uid = (ref.get("users") or {}).get(p["cast"], "")
        name = (ref.get("names") or {}).get(uid + "|" + hive, "") if uid and hive else ""
        if not uid or (p.get("hive") and not hive):
            lines.append(f"FAIL shape probe '{p['label']}': its cast or hive is not in the local database ({p['cast']}, {p.get('hive')})")
            shape_fail = True
            continue
        sql = (p["sql"].replace("{hive}", hive).replace("{uid}", uid).replace("{name}", name.replace("'", "''"))
               .replace("{provider}", ref.get("provider") or ""))
        sprobes.append((i, p))
        script += ["\\echo '@@S %d'" % i, "\\warn '@@S %d'" % i]
        if p["kind"] == "call":
            # every statement inside the function, planned and run, logged to this client (never called as a role
            # without EXECUTE: from a superuser session stepped down, that denial segfaults PostgreSQL 17.6)
            script += ["SET LOCAL auto_explain.log_min_duration = 0;", "SET LOCAL auto_explain.log_nested_statements = on;",
                       "SET LOCAL auto_explain.log_analyze = on;", "SET LOCAL auto_explain.log_timing = off;",
                       "SET LOCAL auto_explain.log_level = notice;", "SET LOCAL client_min_messages = notice;"]
        script.append("SET LOCAL ROLE authenticated;")
        script.append("SET LOCAL request.jwt.claims = %s;" % _lit(json.dumps({"sub": uid, "role": "authenticated", "aud": "authenticated"})))
        script.append(("EXPLAIN " if p["kind"] == "explain" else "") + sql + ";")
        script.append("\\if :ERROR \\echo '@@ERR' :'LAST_ERROR_MESSAGE' \\endif")
        script.append("RESET ROLE;")
        if p["kind"] == "call":
            script += ["SET LOCAL auto_explain.log_min_duration = -1;", "SET LOCAL client_min_messages = warning;"]
    script += ["\\echo '@@END'", "\\warn '@@END'"]
    script.append("ROLLBACK;")
    try:
        r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-X"], input="\n".join(script) + "\n",
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=420, env=ENV)
        text, etext = r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        _psql("select pg_terminate_backend(pid) from pg_stat_activity where application_name = 'lb2_gate' and pid <> pg_backend_pid()")
        return "fail", lines + ["FAIL live half - the grown-size EXPLAIN did not finish in 420 s (backend ended, transaction rolled back)"]
    finally:
        # the rollback leaves dead rows and the in-place reltuples of its ANALYZE: vacuum puts the statistics back
        _psql("".join("VACUUM (ANALYZE) public.%s;\n" % t for t in GROW), timeout=300, args=["-q"])
    blocks, cur, sizes = {}, None, ""
    for ln in text.splitlines() + ["@@END"] + etext.splitlines():
        if ln.strip() == "@@END":
            cur = None
            continue
        m = re.match(r"@@([QS]) (\w+)$", ln.strip())
        if m:
            cur = m.group(2) if m.group(1) == "Q" else "@S" + m.group(2)
            blocks.setdefault(cur, [])
            continue
        if ln.startswith("@@SIZES"):
            cur = "@sizes"
            continue
        if cur == "@sizes":
            sizes, cur = ln.strip(), None
            continue
        if cur:
            blocks[cur].append(ln)
    growerr = [ln for ln in text.splitlines() if ln.startswith("@@GROWERR")]
    bad = 0
    for ix, sql in probes:
        pl = "\n".join(blocks.get(ix["name"], []))
        if "@@ERR" in pl or not pl.strip():
            lines.append(f"FAIL {ix['name']}: the probe did not plan ({pl.strip()[:160]})")
            bad += 1
            continue
        why = judge(pl, ix)
        if why:
            lines.append(f"FAIL {ix['name']}: at grown size the read {ix['reads'][0][0]} serves does not use it - {why}")
            bad += 1
    for i, p in sprobes:
        pl = "\n".join(blocks.get("@S%d" % i, []))
        why = shape_judge(pl, p)
        if why:
            lines.append(f"FAIL shape '{p['label']}' at grown size as {p['cast']}: {why}")
            bad += 1
    if growerr:
        lines.append("NOTE growth: " + "; ".join(g[9:120] for g in growerr[:3]))
    lines.append("grown: " + sizes[:400])
    return ("fail" if (bad or missing or shape_fail) else "pass"), lines


def shape_judge(plan: str, p: dict) -> str | None:
    """None when the probe's plan (or, for a call, every statement inside it) reads its tables through an index"""
    if "@@ERR" in plan or "ERROR:" in plan:
        return "the probe did not run (%s)" % next((x.strip() for x in plan.splitlines() if "ERR" in x), "")[:140]
    if p["kind"] == "call" and "plan:" not in plan:
        return "auto_explain logged no statement - the function's inside was not seen"
    if not re.search(r"(?:Scan|Result|Aggregate|Limit|Append)", plan):
        return "no plan came back"
    for t in p.get("noseq", []):
        # a node marked "never executed" read nothing (an admin's call never runs the non-admin arm, for one)
        if any(re.search(r"Seq Scan on %s\b" % re.escape(t), ln) and "never executed" not in ln for ln in plan.splitlines()):
            return f"Seq Scan on {t}"
    if p.get("uses") and not re.search(r"\b%s\b" % re.escape(p["uses"]), plan):
        used = sorted(set(re.findall(r"(?:Index Scan|Index Only Scan|Bitmap Index Scan)(?: Backward)? (?:using|on) (\w+)", plan)))
        return f"{p['uses']} not used (plan uses: {', '.join(used) or 'no index'})"
    return None


def live_shape_definitions(lines: list[str]) -> bool:
    """the database holds the shapes as declared, no policy compares against a bare auth.uid(), and the kept credit
    totals equal the ledger's. Appends FAIL lines; returns True when something failed."""
    failed = False
    q = ("select json_build_object("
         "'policies', (select json_object_agg(c.relname || '.' || p.polname, coalesce(pg_get_expr(p.polqual, p.polrelid), '') || ' ' || "
         "              coalesce(pg_get_expr(p.polwithcheck, p.polrelid), '')) from pg_policy p join pg_class c on c.oid = p.polrelid "
         "              where c.relnamespace = 'public'::regnamespace), "
         "'views', (select json_object_agg(c.relname, pg_get_viewdef(c.oid, true) || ' @@OPTIONS ' || coalesce(array_to_string(c.reloptions, ','), '')) "
         "              from pg_class c where c.relnamespace = 'public'::regnamespace and c.relkind = 'v' and c.relname = any(%s)), "
         "'functions', (select json_object_agg(p.proname, pg_get_functiondef(p.oid)) from pg_proc p "
         "              where p.pronamespace = 'public'::regnamespace and p.proname = any(%s)), "
         "'triggers', (select json_agg(t.tgname || '.' || c.relname) from pg_trigger t join pg_class c on c.oid = t.tgrelid "
         "              where not t.tgisinternal and t.tgname = any(%s)))"
         % (_lit("{" + ",".join(s["name"] for s in SHAPES if s["kind"] == "view") + "}"),
            _lit("{" + ",".join(s["name"] for s in SHAPES if s["kind"] == "function") + "}"),
            _lit("{" + ",".join(s["name"] for s in SHAPES if s["kind"] == "trigger") + "}")))
    rc, out, err = _psql(q)
    try:
        cat = json.loads(out.strip())
    except ValueError:
        lines.append(f"FAIL the shapes - could not read the catalog ({(err or out).strip()[:120]})")
        return True
    pol, views, fns, trg = cat.get("policies") or {}, cat.get("views") or {}, cat.get("functions") or {}, set(cat.get("triggers") or [])
    for sh in SHAPES:
        if sh["kind"] == "policy":
            text = pol.get(f"{sh['table']}.{sh['name']}")
        elif sh["kind"] == "view":
            text = views.get(sh["name"])
        elif sh["kind"] == "function":
            text = fns.get(sh["name"])
        else:
            text = "present" if f"{sh['name']}.{sh['table']}" in trg else None
        if text is None:
            lines.append(f"FAIL {sh['label']}: {sh['kind']} {sh['name']} is not in the local database - apply {M3}")
            failed = True
            continue
        if sh.get("live") and not re.search(sh["live"], text, re.I):
            lines.append(f"FAIL {sh['label']}: the local database still holds the old shape - apply {M3}")
            failed = True
        if sh.get("invoker") and not re.search(r"@@OPTIONS .*security_invoker=(?:on|true)", text, re.I):
            lines.append(f"FAIL {sh['label']}: the local view lost security_invoker - it reads as its owner, with RLS off")
            failed = True
    bare = sorted(k for k, v in pol.items() if BARE_UID.search(v))
    if bare:
        lines.append(f"FAIL {len(bare)} polic{'y' if len(bare) == 1 else 'ies'} compare against a bare auth.uid() - every subquery in "
                     f"them reads its table in full under RLS: {', '.join(bare[:8])}{' ...' if len(bare) > 8 else ''}")
        failed = True
    rc, out, err = _psql(LEDGER_RECONCILE)
    if rc != 0:
        lines.append(f"FAIL the kept credit totals could not be reconciled ({(err or out).strip()[:120]})")
        failed = True
    elif out.strip():
        lines.append(f"FAIL the kept credit totals disagree with the ledger: {out.strip()[:300]}")
        failed = True
    return failed


# ── run ────────────────────────────────────────────────────────────────────────────────────────────────────────────
def run() -> int:
    migs, files = load()
    bad = static_problems(migs, files)
    for b in bad:
        print("  FAIL " + b)
    if bad:
        print(f"FAIL query-indexes - {len(bad)} static problem(s)")
        return 1
    nreads = sum(len(ix["reads"]) for ix in INDEXES)
    if "--static-only" in sys.argv:
        print(f"PASS query-indexes (static) - {len(INDEXES)} indexes declared as measured, {nreads} page-read anchors hold; live half not run")
        return 0
    verdict, lines = live()
    for ln in lines:
        print("  " + ln)
    if verdict == "fail":
        print("FAIL query-indexes - the grown-size plans do not hold")
        return 1
    tail = "live half SKIPPED (no local database)" if verdict == "skip" else \
        (f"each of the {len(INDEXES)} reads, EXPLAINed at grown size as its cast, uses its index and scans no table; the "
         f"{len(SHAPES)} shapes hold in the database, no policy compares against a bare auth.uid(), the kept credit totals "
         f"reconcile with the ledger, and {len(SHAPE_PROBES)} shape probes stay off full reads at grown size")
    print(f"PASS query-indexes - {len(INDEXES)} indexes declared as measured in supabase/migrations, {nreads} page-read anchors hold; {tail}")
    return 0


def self_test() -> int:
    ok = True

    def expect(name, cond):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + name)
        ok = ok and cond
    migs, files = load()
    expect("the real tree passes (static)", not static_problems(migs, files))
    MF = "20261020000001_lb2_query_indexes.sql"

    def mutm(a, b, extra=None):
        m = dict(migs)
        assert a in m[MF], a[:60]
        m[MF] = m[MF].replace(a, b, 1)
        if extra:
            m.update(extra)
        return bool(static_problems(m, files))

    def mutf(f, a, b):
        m = dict(files)
        assert a in m[f], (f, a[:60])
        m[f] = m[f].replace(a, b, 1)
        return bool(static_problems(migs, m))
    expect("an index removed from the migration fails", mutm(
        "create index if not exists idx_pm_scope_items_hive_id\n  on public.pm_scope_items (hive_id);", ""))
    expect("an index on the wrong columns fails", mutm(
        "on public.logbook (worker_name, created_at desc);", "on public.logbook (worker_name);"))
    expect("an index whose order is turned around fails", mutm(
        "on public.automation_log (hive_id, triggered_at desc);", "on public.automation_log (triggered_at desc, hive_id);"))
    expect("a partial index whose predicate changed fails", mutm(
        "where public and not flagged and deleted_at is null;", "where public;"))
    expect("an index dropped by a LATER migration fails", mutm("", "", {
        "20991231000001_x.sql": "drop index if exists public.idx_fault_knowledge_machine_created;"}))
    expect("an index created on another table fails", mutm(
        "on public.marketplace_disputes (created_at);", "on public.marketplace_orders (created_at);"))
    expect("a hot read that loses its hive filter fails", mutf("alert-hub.html",
        ".eq('hive_id', HIVE_ID)   // F3-arc F5: was RLS-only", ".eq('job_name', 'x')   // F3-arc F5: was RLS-only"))
    expect("the XP lookup that loses its live-row filter fails", mutf("logbook.html",
        ".eq('source_id', entry.id).is('reversed_at', null)", ".eq('source_id', entry.id)"))
    expect("the public feed reordered fails", mutf("public-feed.html", ".eq('flagged', false)", ".eq('flagged', true)"))
    # the live judge, on plans
    ix = next(i for i in INDEXES if i["name"] == "idx_pm_scope_items_hive_id")
    expect("a plan that Seq Scans the table fails", bool(judge("Seq Scan on pm_scope_items s  (cost=0.00..9.00 rows=1)", ix)))
    expect("a plan through another index fails", bool(judge("Index Scan using idx_pm_scope_items_asset_id on pm_scope_items s", ix)))
    expect("a plan through its own index passes", judge("Bitmap Index Scan on idx_pm_scope_items_hive_id  (cost=0.00..4.81 rows=69)", ix) is None)
    expect("a word-prefix of the table name is not the table", judge(
        "Seq Scan on pm_scope_items_archive x\n  ->  Index Scan using idx_pm_scope_items_hive_id on pm_scope_items s", ix) is None)
    # the shapes (20261020000003): a later migration that brings the old shape back is a red
    def later(sql):
        m = dict(migs)
        m["20991231000002_later.sql"] = sql
        return bool(shape_problems(m, files))
    expect("the analytics admin policy re-created with a per-row call fails", later(
        "drop policy if exists analytics_events_select_admin on public.analytics_events;\n"
        "create policy analytics_events_select_admin on public.analytics_events for select to authenticated using (is_platform_admin());"))
    expect("my_service_provider_ids() back to its OR fails", later(
        "create or replace function public.my_service_provider_ids() returns setof uuid language sql stable security definer "
        "set search_path to 'pg_catalog', 'public' as $$ select sp.id from public.service_providers sp where sp.auth_uid = auth.uid() "
        "or (sp.provider_type = 'hive' and sp.hive_id in (select hm.hive_id from public.hive_members hm)) $$;"))
    expect("an invoker view re-created WITHOUT security_invoker fails", later(
        "create or replace view public.v_marketplace_listings_truth as select l.id, "
        "l.id = ANY (ARRAY( SELECT public.my_listing_ids())) AS is_mine from marketplace_listings l;"))
    expect("is_mine back to the per-row definer call fails", later(
        "create or replace view public.v_marketplace_listings_truth with (security_invoker = on) as select l.id, "
        "listing_is_mine(l.id) AS is_mine from marketplace_listings l;"))
    expect("a NEW policy with a bare auth.uid() fails", later(
        "create policy p_new on public.logbook for select using (hive_id in (select hm.hive_id from hive_members hm "
        "where hm.auth_uid = auth.uid()));"))
    expect("a new policy with the wrapped call passes", not later(
        "create policy p_new on public.logbook for select using (hive_id in (select hm.hive_id from hive_members hm "
        "where hm.auth_uid = (select auth.uid())));"))
    expect("the ledger trigger dropped by a later migration fails", later(
        "drop trigger if exists trg_keep_ledger_totals on public.service_credit_ledger;"))
    expect("achievements back to the direct XP read fails", mutf("achievements.html", "db.rpc('my_recent_xp'", "db.rpc('nothing_real'"))
    sp = next(p for p in SHAPE_PROBES if p["label"].startswith("a member's own hives"))
    expect("a membership read that Seq Scans hive_members fails the shape judge", bool(shape_judge(
        "Seq Scan on hive_members hm  (cost=7.77..218.45 rows=1 width=16)\n  Filter: (status = 'active'::text)", sp)))
    expect("a membership read on its index passes the shape judge", shape_judge(
        "Index Scan using idx_hive_members_auth_uid on hive_members hm  (cost=8.11..16.14 rows=1 width=16)", sp) is None)
    cp = next(p for p in SHAPE_PROBES if p["kind"] == "call")
    expect("a call whose inside was never logged fails the shape judge", bool(shape_judge("Result  (cost=0.00..0.01 rows=1)", cp)))
    # the replay reads both migration dialects (pg_dump's quoted form too)
    st = declared({"a.sql": 'CREATE INDEX "idx_q" ON "public"."t" USING "btree" ("a", "b" DESC) WHERE ("p" = true);'})
    expect("a pg_dump-style definition is read", st.get("idx_q") == {"table": "t", "cols": ["a", "b desc"], "where": "p", "file": "a.sql"})
    # the judge on a REAL plan: with index scans switched off for one transaction (nothing is changed or locked), the
    # live probe's plan must read as a failure - the live half can go red on what the database actually does
    rc, out, _ = _psql("select 1", timeout=20)
    if rc == 0 and out.strip() == "1":
        rc, out, err = _psql("begin; set local enable_indexscan = off; set local enable_bitmapscan = off; "
                             "explain select id from public.pm_scope_items where hive_id = (select id from public.hives order by created_at limit 1); "
                             "rollback;", args=["-At", "-q"])
        expect("a real plan with the index switched off fails the judge", rc == 0 and bool(judge(out, ix)))
        # the reconciliation has teeth: a ledger row written past the trigger (replica role skips it) must show as a
        # disagreement - inside a transaction that is rolled back, so nothing is kept
        rc, out, err = _psql("begin; set local session_replication_role = replica; "
                             "insert into public.service_credit_ledger (account_type, account_id, entry_type, amount, note) "
                             "values ('consumer', gen_random_uuid(), 'adjustment', 1, 'query-indexes self-test'); "
                             "set local session_replication_role = origin; " + LEDGER_RECONCILE + " rollback;", args=["-At", "-q"])
        expect("a ledger row the kept totals missed is reported", rc == 0 and "adjustment" in out)
    else:
        print("  skip a real plan with the index switched off (no local database)")
    print("PASS self-test" if ok else "FAIL self-test")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else run())
