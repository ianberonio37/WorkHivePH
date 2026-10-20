-- SL LB2 (2026-10-20): every page's queries stay on an index as their tables grow.
--
-- WHAT THE LB2 MEASUREMENT FOUND. Every read the 34 LB2 pages make (their own db.from chains and the shared scripts
-- they load - 424 reads, 524 distinct statements across the casts) was translated into the SQL PostgREST runs, with each row's
-- cast's real values, and EXPLAIN ANALYZEd as that cast (role authenticated or anon, RLS on) on the LOCAL database
-- after its tables were GROWN inside one rolled-back transaction: every table behind a page read copied from its own
-- rows - deeper history for the cast's own hive (timestamps shifted back) and ~100x more hives, people and assets
-- (every uuid remapped the same way in every table) - to 50k-130k rows for the history tables (logbook 125k,
-- hive_audit_log 121k, achievement_xp_log 97k, automation_log 75k, pm_scope_items 57k, marketplace_listings 56k,
-- fault_knowledge 50k, platform_feedback_votes 50k, ...). Nothing persisted; the tables were vacuumed after.
--
-- Each index below answers one read that, at that size, sequentially scanned a growing table or walked a whole index
-- to filter it (the page and line, then the plan it had):
--
--   pm_scope_items (hive_id)              v_pm_scope_items_truth .eq('hive_id') - alert-hub, hive board, home, logbook,
--                                         pm-scheduler, dayplanner: no hive key, so every hive-scoped PM read walked
--                                         ALL scope items (idx_pm_scope_items_asset_id, 56,733 rows removed) to keep 29.
--   automation_log (hive_id, triggered_at desc)   alert-hub "failed automations, last 24h": no hive key - it scanned
--                                         every hive's last day (job index, 2,343 rows) to return the hive's 0-10.
--   hive_audit_log (hive_id, action, created_at desc)   community's reported-post read (action = 'report_post'):
--                                         the hive's whole audit log (11,199 rows) filtered for one action.
--   hive_audit_log (created_at desc)      founder-console's latest 50 (scoped by RLS alone): Seq Scan on 121,212 rows
--                                         + top-N sort.
--   platform_feedback (created_at desc)   founder-console / platform-actions inbox, newest 500: Seq Scan + sort.
--   platform_feedback_votes (voter_token) feedback/ "my votes" by the visitor's token: Seq Scan on 50,010 rows. (The
--                                         2026-05-19 migration's (voter_token, voted_at) index is not in this database
--                                         - its table has no voted_at - so the read had no index at all.)
--   marketplace_disputes (created_at)     marketplace-admin's oldest-first queue: Seq Scan + sort (20,000 rows).
--   marketplace_sellers (created_at desc) marketplace-admin / founder-console / platform-actions seller lists: Seq Scan
--                                         of every seller plus a per-seller listings aggregate for EACH, then top-N.
--   marketplace_listings (status, created_at)   moderation queues (status = draft/published, oldest first): the
--                                         created_at index walked every listing to filter the status.
--   logbook (worker_name, created_at desc)   worker drawer (a member's open count + latest 3), resume's work history,
--                                         assistant's by-name count: no index served a hive member's name (the only
--                                         worker_name index is partial to hive_id IS NULL) - a Seq Scan, or the
--                                         created_at index walked backwards filtering 16,769 rows for 300.
--   logbook (hive_id, date desc)          logbook's team list and its CSV export page by date: every one of the hive's
--                                         20,832 rows read and sorted for the newest 50.
--   logbook (hive_id, status)             the open / closed work-order counts on logbook, hive board and home: the only
--                                         index carrying status puts maintenance_type before it, so a count walked the
--                                         hive's whole slice of that index.
--   fault_knowledge (machine, created_at desc)   logbook's "fixes for this machine" list and count: Seq Scan on 49,846.
--   achievement_xp_log (source_id) where reversed_at is null   the XP of one logbook entry / PM (logbook, pm-scheduler
--                                         reversal checks): Seq Scan on 97,191 rows.
--   achievement_xp_log (earned_at desc)   achievements' recent activity and XP-this-week (scoped by RLS alone): Seq Scan
--                                         + sort, and the week window walked idx_xp_log_worker on its second column.
--   community_posts (created_at desc) where public and not flagged and deleted_at is null
--                                         public feed (public-feed, community's network tab): every public post read
--                                         and sorted (4,500) for the newest 20.
--   marketplace_sellers (hive_id)         community's trade-peer seller cards (v_marketplace_sellers_truth .eq('hive_id')):
--                                         Seq Scan on every seller (17,016 removed for 1).
--   marketplace_sellers (auth_uid)        marketplace-seller's own seller row (.or(auth_uid / unbound name)): Seq Scan on
--                                         every seller; and auth_worker_names() - inside achievement_xp_log's read policy,
--                                         so in every XP read - asks marketplace_sellers by auth_uid too.
--   voice_journal_entries (hive_id, created_at desc)   compute_hive_readiness() (hive board): its voice-journal count
--                                         for the hive's last 30 days was a Seq Scan on every entry (26,950 removed).
--
-- NOT fixed here, because no index can (they are listed with their exact changes in the LB2 report): a filter on a
-- per-row SECURITY DEFINER function (v_marketplace_listings_truth.is_mine, v_marketplace_inquiries_truth.to_me /
-- from_me), reads scoped by RLS alone whose policy is an OR around a hashed IN-subplan (pm_scope_items_read walking
-- pm_assets, service_requests_party_read, my_service_provider_ids() - measured: an auth_uid index on
-- service_providers is NOT used by that OR, so it is not added), DISTINCT ON / GROUP BY views that read a hive's whole
-- history (v_risk_truth, v_sensor_truth, v_pm_compliance_truth), and admin reads that fetch tens of thousands of rows
-- to aggregate in the browser.
--
-- Plain CREATE INDEX (it runs inside the migration's transaction): seconds on today's tables. On a large production
-- table prefer CREATE INDEX CONCURRENTLY out of band. Forward-only; idempotent; gate: query-indexes
-- (tools/validate_query_indexes.py).

create index if not exists idx_pm_scope_items_hive_id
  on public.pm_scope_items (hive_id);

create index if not exists idx_automation_log_hive_triggered
  on public.automation_log (hive_id, triggered_at desc);

create index if not exists idx_hive_audit_log_hive_action_created
  on public.hive_audit_log (hive_id, action, created_at desc);

create index if not exists idx_hive_audit_log_created
  on public.hive_audit_log (created_at desc);

create index if not exists idx_platform_feedback_created
  on public.platform_feedback (created_at desc);

create index if not exists idx_platform_feedback_votes_token
  on public.platform_feedback_votes (voter_token);

create index if not exists idx_mkt_disputes_created
  on public.marketplace_disputes (created_at);

create index if not exists idx_marketplace_sellers_created
  on public.marketplace_sellers (created_at desc);

create index if not exists idx_mkt_listings_status_created
  on public.marketplace_listings (status, created_at);

create index if not exists idx_logbook_worker_created
  on public.logbook (worker_name, created_at desc);

create index if not exists idx_logbook_hive_entry_date
  on public.logbook (hive_id, date desc);

create index if not exists idx_logbook_hive_status
  on public.logbook (hive_id, status);

create index if not exists idx_fault_knowledge_machine_created
  on public.fault_knowledge (machine, created_at desc);

create index if not exists idx_xp_log_source_live
  on public.achievement_xp_log (source_id)
  where reversed_at is null;

create index if not exists idx_xp_log_earned
  on public.achievement_xp_log (earned_at desc);

create index if not exists idx_community_posts_public_feed
  on public.community_posts (created_at desc)
  where public and not flagged and deleted_at is null;

create index if not exists idx_marketplace_sellers_hive_id
  on public.marketplace_sellers (hive_id);

create index if not exists idx_marketplace_sellers_auth_uid
  on public.marketplace_sellers (auth_uid);

create index if not exists idx_voice_journal_hive_created
  on public.voice_journal_entries (hive_id, created_at desc);
