-- ─── Phase E — drop the 10 L3 permissive policies ──────────────────────────
--
-- PRODUCTION_FIXES.md #36 (RLS readiness) catalogued 10 USING(true) WITH
-- CHECK(true) policies on 5 hive-scoped tables. Today they are the string-
-- identity backbone (anon CRUD with JS-layer hive_id filter). With Phase
-- A+B+C-data complete, the auth-gated sibling policies on each table can
-- now actually gate access:
--   - Phase A: confirmed every L3 table has auth.uid()-using siblings for
--     all 4 CRUD verbs (validate_auth_migration_readiness L1 PASS).
--   - Phase B: 9 user-facing pages now require `_authUid` at init
--     (stale-localStorage workers redirect to signin instead of slipping
--     through with auth_uid=null inserts).
--   - Phase C-data: 19 straggler rows backfilled (auth_uid = wp.auth_uid)
--     across pm_completions, logbook, inventory_transactions,
--     marketplace_sellers; dynamic scan verified 0 remaining.
--
-- This migration drops the permissive policies. Postgres RLS uses OR
-- semantics across multiple policies on the same operation: ANY policy
-- passing = access granted. Today, USING(true) always passes, so the
-- auth.uid()-gated siblings are dead code. After this drop, only the
-- siblings remain — they actually gate access.
--
-- Reversibility: the dropped policies can be re-CREATEd from the original
-- migration files (20260420000000_baseline.sql, 20260430000000_community_tables.sql,
-- 20260430000002_community_xp.sql) if Phase E surfaces unexpected breakage.
-- Recovery window: while the user-base is still small, re-apply takes one
-- migration; for larger deployments, plan a more careful rollback path.
--
-- Verification after applying:
--   1. python validate_rls_readiness.py     → L3 should drop to PASS
--   2. python run_platform_checks.py --fast → guardian baseline stays clean
--   3. Smoke-test the 5 affected tables in WorkHive Tester:
--      - logbook: read+write entries (authed worker → ✓; anon → 401)
--      - inventory: read+write parts
--      - community: read posts, write reply, react
--   4. Re-run Phase C-data Q2 scan → still 0 stragglers
--
-- Each DROP uses IF EXISTS so re-runs of this migration are idempotent.

BEGIN;

-- inventory_transactions: 2 permissive policies on the same table
-- (allow_anon_all + open). Both drop together.
DROP POLICY IF EXISTS "allow_anon_all" ON public.inventory_transactions;
DROP POLICY IF EXISTS "open"           ON public.inventory_transactions;

-- logbook: single allow_anon_all FOR ALL policy
DROP POLICY IF EXISTS "allow_anon_all" ON public.logbook;

-- community_posts: 3 permissive policies (read, update, delete) — note
-- INSERT was already auth-gated (no permissive INSERT to drop)
DROP POLICY IF EXISTS "anon read community_posts"   ON public.community_posts;
DROP POLICY IF EXISTS "anon update community_posts" ON public.community_posts;
DROP POLICY IF EXISTS "anon delete community_posts" ON public.community_posts;

-- community_replies: 2 permissive policies (read, delete)
DROP POLICY IF EXISTS "anon read community_replies"   ON public.community_replies;
DROP POLICY IF EXISTS "anon delete community_replies" ON public.community_replies;

-- community_xp: 2 permissive policies (read, write)
DROP POLICY IF EXISTS "hive xp open read"  ON public.community_xp;
DROP POLICY IF EXISTS "hive xp open write" ON public.community_xp;

COMMIT;
