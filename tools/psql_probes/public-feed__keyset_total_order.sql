-- keyset_total_order (public-feed): no post on two pages, none skipped - the pagination is a TOTAL
-- order. The cursor must carry the SAME key the ORDER does, so a tie on a page boundary is neither
-- duplicated nor skipped (the cursor re-run defect, MARKETPLACE_ITERATION_ROADMAP section 4).
--
-- ★THE LIVE DATA CANNOT EXERCISE THIS CLAIM, WHICH IS WHY THE TIE IS MANUFACTURED. Measured today:
-- 116 public posts, 116 distinct `created_at`, ZERO ties. Paginating over that proves only that
-- pagination works when the hard case never occurs - a vacuous green, and vacuity is the failure mode
-- this whole bank keeps re-learning. So the teeth FORCE a tie inside BEGIN/ROLLBACK and page across
-- it, and a CONTROL leg proves the naive one-column cursor genuinely breaks on the same rows. A test
-- that cannot fail is not evidence; a test whose control also passes is measuring nothing.
-- expect: keyset_index_present \| t
-- expect: ties_in_live_data \| 0
-- expect: naive_cursor_loses_a_row \| t
-- expect: keyset_cursor_loses_nothing \| t
-- expect: keyset_cursor_repeats_nothing \| t
-- expect: rows_restored_after_rollback \| t
SELECT 'keyset_index_present | ' || EXISTS (
  SELECT 1 FROM pg_indexes WHERE tablename = 'community_posts'
   AND indexdef ILIKE '%created_at%' AND indexdef ILIKE '%id%');

-- stated rather than hidden: the corpus has no tie today, so the teeth below make one
SELECT 'ties_in_live_data | ' || (SELECT count(*) - count(DISTINCT created_at) FROM community_posts);

CREATE TEMP TABLE _kfix AS SELECT count(*) AS n0 FROM community_posts;

BEGIN;
-- Force a tie on the page boundary: give the 2nd and 3rd newest posts the SAME created_at, so a
-- 2-row page ends exactly inside the tie - the only arrangement that distinguishes the two cursors.
CREATE TEMP TABLE _tied AS
SELECT id, created_at FROM community_posts ORDER BY created_at DESC, id DESC LIMIT 3;

UPDATE community_posts SET created_at = (SELECT min(created_at) FROM _tied)
 WHERE id IN (SELECT id FROM _tied);

-- page 1: the two newest under the full key
CREATE TEMP TABLE _p1 AS
SELECT id, created_at FROM community_posts ORDER BY created_at DESC, id DESC LIMIT 2;

-- NAIVE cursor: created_at only. Every row sharing the boundary timestamp is skipped, because
-- `created_at < boundary` excludes the tied sibling that page 1 never showed.
CREATE TEMP TABLE _p2_naive AS
SELECT id FROM community_posts
 WHERE created_at < (SELECT min(created_at) FROM _p1)
 ORDER BY created_at DESC, id DESC LIMIT 2;

-- KEYSET cursor: the same key the ORDER uses, compared as a tuple.
CREATE TEMP TABLE _p2_keyset AS
SELECT id FROM community_posts
 WHERE (created_at, id) < (SELECT created_at, id FROM _p1 ORDER BY created_at ASC, id ASC LIMIT 1)
 ORDER BY created_at DESC, id DESC LIMIT 2;

-- the control: the naive cursor must LOSE the tied row that page 1 did not show
SELECT 'naive_cursor_loses_a_row | ' || EXISTS (
  SELECT 1 FROM _tied t
   WHERE t.id NOT IN (SELECT id FROM _p1)
     AND t.id NOT IN (SELECT id FROM _p2_naive));

-- the claim: the keyset cursor loses nothing and repeats nothing across the same boundary
SELECT 'keyset_cursor_loses_nothing | ' || NOT EXISTS (
  SELECT 1 FROM _tied t
   WHERE t.id NOT IN (SELECT id FROM _p1)
     AND t.id NOT IN (SELECT id FROM _p2_keyset));
SELECT 'keyset_cursor_repeats_nothing | ' || NOT EXISTS (
  SELECT 1 FROM _p2_keyset k WHERE k.id IN (SELECT id FROM _p1));
ROLLBACK;

-- ★A COUNT-BASED RESTORATION CHECK IS BROKEN BY ANY CONCURRENT WRITER (2026-09-10). Comparing
-- count-at-start with count-at-end reported `false` in a sibling recipe while its rollbacks had
-- worked perfectly - an archetype walk had written two real rows between the readings. A probe
-- that fails when the platform is BUSY teaches people to re-run reds until they go green. The
-- assertions below are about THIS probe's own residue, or about the invariant itself, so another
-- writer cannot move them.
-- the teeth UPDATE timestamps rather than inserting, so restoration means the manufactured TIE is
-- gone - which is exactly the live-data precondition asserted at the top.
SELECT 'rows_restored_after_rollback | ' || (
  (SELECT count(*) - count(DISTINCT created_at) FROM community_posts) = 0);
DROP TABLE _kfix;
