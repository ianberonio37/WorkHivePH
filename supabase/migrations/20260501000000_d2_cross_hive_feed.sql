-- D Phase 2: Cross-hive feed — authenticated workers read public posts from all hives
-- ====================================================================================
-- Adds RLS for reading hive names (needed to show "From: [Hive Name]" in global feed)
-- and allows authenticated workers to react to public posts from any hive.

-- ── hives: open read (workers need hive names in global feed) ────────────────
GRANT SELECT ON hives TO anon, authenticated;
ALTER TABLE hives ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "hives_open_read" ON hives;
CREATE POLICY "hives_open_read" ON hives FOR SELECT USING (true);

-- ── community_reactions: allow cross-hive reactions on public posts ───────────
-- Authenticated workers can react to public posts from any hive (D Phase 2).
-- Own-hive reactions remain unchanged.

DROP POLICY IF EXISTS "community_reactions_read"  ON community_reactions;
DROP POLICY IF EXISTS "community_reactions_write" ON community_reactions;

CREATE POLICY "community_reactions_read" ON community_reactions FOR SELECT USING (
  -- Public post reactions: readable by anyone authenticated
  (auth.uid() IS NOT NULL AND EXISTS (
    SELECT 1 FROM community_posts cp
    WHERE cp.id = community_reactions.post_id AND cp.public = true
  ))
  OR
  -- Own-hive post reactions
  (auth.uid() IS NOT NULL AND hive_id IN (
    SELECT hm.hive_id FROM hive_members hm
    WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
  ))
);

CREATE POLICY "community_reactions_write" ON community_reactions FOR ALL USING (
  auth.uid() IS NOT NULL AND (
    -- React to public posts from any hive (D Phase 2 cross-hive)
    EXISTS (
      SELECT 1 FROM community_posts cp
      WHERE cp.id = community_reactions.post_id AND cp.public = true
    )
    OR
    -- React to own-hive posts
    hive_id IN (
      SELECT hm.hive_id FROM hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  )
);
