-- Community XP — WorkHive Platform
-- Tracks XP earned from community actions, hive-scoped.
-- XP is awarded server-side by DB triggers — not client-side — to prevent gaming.
--
-- Rules (from roadmap):
--   First post in hive   +50 XP
--   Safety category post +25 XP
--   Reply to a thread    +10 XP
--   Post gets 3 reactions +20 XP (awarded to post author)
--   10 posts milestone   → Voice of the Hive badge (no XP)

-- ── Table ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS community_xp (
  worker_name text NOT NULL,
  hive_id     uuid NOT NULL REFERENCES hives(id) ON DELETE CASCADE,
  xp_total    integer     NOT NULL DEFAULT 0,
  updated_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (worker_name, hive_id)
);

GRANT SELECT, INSERT, UPDATE ON community_xp TO anon, authenticated;

ALTER TABLE community_xp ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "hive xp open read"  ON community_xp;
CREATE POLICY "hive xp open read"  ON community_xp FOR SELECT USING (true);
DROP POLICY IF EXISTS "hive xp open write" ON community_xp;
CREATE POLICY "hive xp open write" ON community_xp FOR ALL    USING (true);

-- ── Atomic increment RPC ──────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION increment_community_xp(
  p_worker_name text,
  p_hive_id     uuid,
  p_amount      integer
) RETURNS void AS $$
BEGIN
  INSERT INTO community_xp (worker_name, hive_id, xp_total, updated_at)
  VALUES (p_worker_name, p_hive_id, p_amount, now())
  ON CONFLICT (worker_name, hive_id) DO UPDATE
  SET xp_total   = community_xp.xp_total + p_amount,
      updated_at = now();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ── Trigger: community_posts INSERT ──────────────────────────────────────────

CREATE OR REPLACE FUNCTION handle_community_post_xp()
RETURNS trigger AS $$
DECLARE
  post_count integer;
BEGIN
  SELECT COUNT(*) INTO post_count
  FROM community_posts
  WHERE author_name = NEW.author_name AND hive_id = NEW.hive_id;

  -- First post in this hive: +50 XP
  IF post_count = 1 THEN
    PERFORM increment_community_xp(NEW.author_name, NEW.hive_id, 50);
  END IF;

  -- Safety category: +25 XP (stacks with first-post bonus)
  IF NEW.category = 'safety' THEN
    PERFORM increment_community_xp(NEW.author_name, NEW.hive_id, 25);
  END IF;

  -- 10th post milestone: Voice of the Hive badge
  IF post_count = 10 THEN
    INSERT INTO skill_badges (worker_name, discipline, level, badge_key, earned_at)
    VALUES (NEW.author_name, 'Community', 1, 'voice_of_the_hive', now())
    ON CONFLICT (worker_name, badge_key) DO NOTHING;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trg_community_post_xp ON community_posts;
CREATE TRIGGER trg_community_post_xp
  AFTER INSERT ON community_posts
  FOR EACH ROW EXECUTE FUNCTION handle_community_post_xp();

-- ── Trigger: community_replies INSERT ────────────────────────────────────────

CREATE OR REPLACE FUNCTION handle_community_reply_xp()
RETURNS trigger AS $$
BEGIN
  PERFORM increment_community_xp(NEW.author_name, NEW.hive_id, 10);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trg_community_reply_xp ON community_replies;
CREATE TRIGGER trg_community_reply_xp
  AFTER INSERT ON community_replies
  FOR EACH ROW EXECUTE FUNCTION handle_community_reply_xp();

-- ── Trigger: community_reactions INSERT (3-reaction threshold) ────────────────

CREATE OR REPLACE FUNCTION handle_community_reaction_xp()
RETURNS trigger AS $$
DECLARE
  reaction_count integer;
  v_author       text;
  v_hive_id      uuid;
BEGIN
  SELECT COUNT(*) INTO reaction_count
  FROM community_reactions WHERE post_id = NEW.post_id;

  -- Award +20 XP to the post author the moment their post hits exactly 3 reactions
  IF reaction_count = 3 THEN
    SELECT author_name, hive_id INTO v_author, v_hive_id
    FROM community_posts WHERE id = NEW.post_id;
    IF v_author IS NOT NULL THEN
      PERFORM increment_community_xp(v_author, v_hive_id, 20);
    END IF;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trg_community_reaction_xp ON community_reactions;
CREATE TRIGGER trg_community_reaction_xp
  AFTER INSERT ON community_reactions
  FOR EACH ROW EXECUTE FUNCTION handle_community_reaction_xp();
