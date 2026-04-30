-- Community Tables — WorkHive Platform
-- Hive-scoped discussion threads, replies, and reactions.
-- All tables are hive-isolated: every query must include hive_id.

-- ── Threads ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS community_posts (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id     uuid        NOT NULL REFERENCES hives(id) ON DELETE CASCADE,
  author_name text        NOT NULL,
  content     text        NOT NULL CHECK (char_length(content) BETWEEN 1 AND 2000),
  category    text        NOT NULL DEFAULT 'general'
                          CHECK (category IN ('general','safety','technical','announcement')),
  pinned      boolean     NOT NULL DEFAULT false,
  flagged     boolean     NOT NULL DEFAULT false,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_community_posts_hive_created
  ON community_posts (hive_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_community_posts_pinned
  ON community_posts (hive_id, pinned) WHERE pinned = true;

-- ── Replies ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS community_replies (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  post_id     uuid        NOT NULL REFERENCES community_posts(id) ON DELETE CASCADE,
  hive_id     uuid        NOT NULL,
  author_name text        NOT NULL,
  content     text        NOT NULL CHECK (char_length(content) BETWEEN 1 AND 1000),
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_community_replies_post
  ON community_replies (post_id, created_at ASC);

CREATE INDEX IF NOT EXISTS idx_community_replies_hive
  ON community_replies (hive_id);

-- ── Reactions ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS community_reactions (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  post_id     uuid        NOT NULL REFERENCES community_posts(id) ON DELETE CASCADE,
  hive_id     uuid        NOT NULL,
  worker_name text        NOT NULL,
  emoji       text        NOT NULL DEFAULT 'thumbs_up'
                          CHECK (emoji IN ('thumbs_up','wrench','fire','eyes')),
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (post_id, worker_name, emoji)
);

CREATE INDEX IF NOT EXISTS idx_community_reactions_post
  ON community_reactions (post_id);

-- ── RLS (mirrors hive.html pattern — anon key enforced at app layer until Supabase Auth) ──
ALTER TABLE community_posts      ENABLE ROW LEVEL SECURITY;
ALTER TABLE community_replies    ENABLE ROW LEVEL SECURITY;
ALTER TABLE community_reactions  ENABLE ROW LEVEL SECURITY;

-- Open read within hive (anon can read — hive_id filtering enforced in JS)
DROP POLICY IF EXISTS "anon read community_posts"      ON community_posts;
DROP POLICY IF EXISTS "anon read community_replies"    ON community_replies;
DROP POLICY IF EXISTS "anon read community_reactions"  ON community_reactions;
DROP POLICY IF EXISTS "anon insert community_posts"    ON community_posts;
DROP POLICY IF EXISTS "anon insert community_replies"  ON community_replies;
DROP POLICY IF EXISTS "anon insert community_reactions" ON community_reactions;
DROP POLICY IF EXISTS "anon update community_posts"    ON community_posts;
DROP POLICY IF EXISTS "anon delete community_posts"    ON community_posts;
DROP POLICY IF EXISTS "anon delete community_replies"  ON community_replies;
DROP POLICY IF EXISTS "anon delete community_reactions" ON community_reactions;

CREATE POLICY "anon read community_posts"
  ON community_posts FOR SELECT USING (true);

CREATE POLICY "anon read community_replies"
  ON community_replies FOR SELECT USING (true);

CREATE POLICY "anon read community_reactions"
  ON community_reactions FOR SELECT USING (true);

-- Open insert (anon can write — hive_id required at app layer)
CREATE POLICY "anon insert community_posts"
  ON community_posts FOR INSERT WITH CHECK (true);

CREATE POLICY "anon insert community_replies"
  ON community_replies FOR INSERT WITH CHECK (true);

CREATE POLICY "anon insert community_reactions"
  ON community_reactions FOR INSERT WITH CHECK (true);

-- Allow updates (pin/flag — gated at app layer by HIVE_ROLE check)
CREATE POLICY "anon update community_posts"
  ON community_posts FOR UPDATE USING (true);

-- Allow deletes (mod actions — gated at app layer by HIVE_ROLE check)
CREATE POLICY "anon delete community_posts"
  ON community_posts FOR DELETE USING (true);

CREATE POLICY "anon delete community_replies"
  ON community_replies FOR DELETE USING (true);

-- Allow delete own reaction (toggle off)
CREATE POLICY "anon delete community_reactions"
  ON community_reactions FOR DELETE USING (true);
