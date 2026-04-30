-- D Phase 1: Public post flag
-- ============================
-- Supervisors can mark individual posts as public.
-- Public posts are readable by anyone (no auth required) and appear
-- in the global read-only public feed (public-feed.html).
-- No cross-hive writes — only the originating hive's supervisor can
-- make posts public or private.

ALTER TABLE community_posts ADD COLUMN IF NOT EXISTS public boolean NOT NULL DEFAULT false;
CREATE INDEX IF NOT EXISTS idx_community_posts_public ON community_posts (public) WHERE public = true;

-- ── Update community_posts_read RLS to allow public posts ─────────────────────
-- Public posts: readable by anyone (anon + authenticated)
-- Non-public: auth required + hive membership (unchanged from C4)

DROP POLICY IF EXISTS "community_posts_read" ON community_posts;
CREATE POLICY "community_posts_read" ON community_posts FOR SELECT USING (
  -- D Phase 1: public posts readable by everyone
  (public = true AND flagged = false)
  OR
  -- Non-public: authenticated hive member
  (auth.uid() IS NOT NULL AND hive_id IN (
    SELECT hm.hive_id FROM hive_members hm
    WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
  ))
);

-- ── Allow anon to read hive names (for public feed display) ───────────────────
-- hives table is the source of truth for hive names
GRANT SELECT ON hives TO anon;
