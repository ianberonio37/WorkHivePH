-- =============================================================
-- Achievement Milestone System
-- Tables: achievement_definitions, worker_achievements,
--         achievement_xp_log
-- Central function: award_achievement_xp()
-- Triggers: logbook (4 domains), pm_completions,
--           community_posts, skill_badges
-- pg_cron: weekly XP log purge
-- =============================================================


-- ── 1. Static definitions (seeded once) ──────────────────────
CREATE TABLE IF NOT EXISTS achievement_definitions (
  id          text PRIMARY KEY,
  name        text NOT NULL,
  description text,
  icon        text,
  domain      text,
  pillar      text,
  max_level   int NOT NULL DEFAULT 100
);

INSERT INTO achievement_definitions
  (id, name, description, icon, domain, pillar)
VALUES
  ('wrench_chronicle',
   'Wrench Chronicle',
   'Log jobs, close them with detail, and build a record of your craft.',
   '🔧', 'logbook', 'competence'),

  ('uptime_guardian',
   'Uptime Guardian',
   'Complete PM tasks on time and keep machines running.',
   '🛡️', 'pm', 'competence'),

  ('parts_warden',
   'Parts Warden',
   'Manage inventory, restock proactively, and link parts to jobs.',
   '📦', 'inventory', 'competence'),

  ('blueprint_master',
   'Blueprint Master',
   'Run engineering calculations and generate design reports.',
   '📐', 'engineering', 'competence'),

  ('failure_hunter',
   'Failure Hunter',
   'Close breakdown jobs with root causes. Understand failure, prevent repeats.',
   '🎯', 'diagnostic', 'competence'),

  ('safety_sentinel',
   'Safety Sentinel',
   'Log safety events, flag hazards, and champion safe work practices.',
   '⚠️', 'safety', 'autonomy'),

  ('skill_climber',
   'Skill Climber',
   'Complete skill assessments and unlock competency badges.',
   '📈', 'skill', 'autonomy'),

  ('knowledge_forger',
   'Knowledge Forger',
   'Write detailed entries and submit shift handover reports.',
   '📝', 'knowledge', 'autonomy'),

  ('hive_architect',
   'Hive Architect',
   'Build and sustain your team. Invite members and approve submissions.',
   '🏗️', 'team', 'relatedness'),

  ('voice_of_hive',
   'Voice of the Hive',
   'Post, reply, and contribute to your hive community.',
   '🗣️', 'community', 'relatedness'),

  ('shift_keeper',
   'Shift Keeper',
   'Submit shift handover reports on time with no gaps.',
   '🕐', 'shift', 'relatedness'),

  ('iron_worker',
   'Iron Worker',
   'Legendary composite achievement. Reach Level 50 in any 5 domains.',
   '⚙️', 'composite', 'legendary')

ON CONFLICT (id) DO NOTHING;


-- ── 2. Per-worker progress (worker-wide, not hive-scoped) ─────
CREATE TABLE IF NOT EXISTS worker_achievements (
  id              uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  auth_uid        uuid        REFERENCES auth.users(id) ON DELETE CASCADE,
  worker_name     text        NOT NULL,
  achievement_id  text        NOT NULL REFERENCES achievement_definitions(id),
  current_level   int         NOT NULL DEFAULT 0,
  xp_total        bigint      NOT NULL DEFAULT 0,
  last_action_at  timestamptz,
  UNIQUE (worker_name, achievement_id)
);

-- For "load all for one worker" (profile page, achievement page)
CREATE INDEX IF NOT EXISTS idx_achievements_worker
  ON worker_achievements (worker_name);

-- For "leaderboard per domain" (top N workers by level in Wrench Chronicle, etc.)
CREATE INDEX IF NOT EXISTS idx_achievements_ranking
  ON worker_achievements (achievement_id, current_level DESC);

-- Realtime: level-up events fan out to every open page
ALTER PUBLICATION supabase_realtime ADD TABLE worker_achievements;


-- ── 3. XP audit log (append-only) ────────────────────────────
CREATE TABLE IF NOT EXISTS achievement_xp_log (
  id              uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  worker_name     text        NOT NULL,
  achievement_id  text        NOT NULL,
  xp_earned       int         NOT NULL,
  source_action   text        NOT NULL,
  source_id       text,
  earned_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_xp_log_worker
  ON achievement_xp_log (worker_name, earned_at DESC);


-- ── 4. RLS ────────────────────────────────────────────────────
ALTER TABLE achievement_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE worker_achievements      ENABLE ROW LEVEL SECURITY;
ALTER TABLE achievement_xp_log       ENABLE ROW LEVEL SECURITY;

-- Definitions: read-only for all
DROP POLICY IF EXISTS "ach_def_read" ON achievement_definitions;
CREATE POLICY "ach_def_read"
  ON achievement_definitions FOR SELECT USING (true);

-- Achievements: everyone can read (leaderboards, profile frames)
-- No INSERT/UPDATE/DELETE from the client — writes come from triggers only
DROP POLICY IF EXISTS "ach_worker_read" ON worker_achievements;
CREATE POLICY "ach_worker_read"
  ON worker_achievements FOR SELECT USING (true);

-- XP log: anyone can read (history tab on achievements page)
DROP POLICY IF EXISTS "ach_log_read" ON achievement_xp_log;
CREATE POLICY "ach_log_read"
  ON achievement_xp_log FOR SELECT USING (true);

-- Explicit grants for client queries
GRANT SELECT ON achievement_definitions TO anon, authenticated;
GRANT SELECT ON worker_achievements      TO anon, authenticated;
GRANT SELECT ON achievement_xp_log       TO anon, authenticated;


-- ── 5. Central award function ─────────────────────────────────
-- SECURITY DEFINER: runs as postgres, bypasses RLS for writes.
-- Triggers call this. Clients cannot call it (REVOKE below).
CREATE OR REPLACE FUNCTION award_achievement_xp(
  p_worker    text,
  p_ach_id    text,
  p_xp        int,
  p_action    text,
  p_source_id text DEFAULT NULL
) RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_old_level int := 0;
  v_new_xp    bigint;
  v_new_level int;
BEGIN
  -- Capture current level before the upsert
  SELECT current_level INTO v_old_level
  FROM   worker_achievements
  WHERE  worker_name = p_worker AND achievement_id = p_ach_id;

  -- Atomic upsert: add XP, update timestamp
  INSERT INTO worker_achievements
    (worker_name, achievement_id, xp_total, last_action_at)
  VALUES
    (p_worker, p_ach_id, p_xp, now())
  ON CONFLICT (worker_name, achievement_id) DO UPDATE
    SET xp_total       = worker_achievements.xp_total + p_xp,
        last_action_at = now()
  RETURNING xp_total INTO v_new_xp;

  -- Quadratic 1.8 level curve: level = floor((xp / 100) ^ (1 / 1.8))
  -- Level 1 = 100 XP, Level 10 = 6,310 XP, Level 50 = 107,652 XP, Level 100 = 398,107 XP
  v_new_level := LEAST(
    floor(power(v_new_xp::float / 100.0, 1.0 / 1.8))::int,
    100
  );

  -- Persist level only if it improved
  IF v_new_level > COALESCE(v_old_level, 0) THEN
    UPDATE worker_achievements
    SET    current_level = v_new_level
    WHERE  worker_name = p_worker AND achievement_id = p_ach_id;
  END IF;

  -- Audit log (fire-and-forget: failure is acceptable, never block the action)
  BEGIN
    INSERT INTO achievement_xp_log
      (worker_name, achievement_id, xp_earned, source_action, source_id)
    VALUES
      (p_worker, p_ach_id, p_xp, p_action, p_source_id);
  EXCEPTION WHEN OTHERS THEN NULL;
  END;
END;
$$;

-- Block direct client calls: XP must come from DB triggers only
REVOKE EXECUTE ON FUNCTION award_achievement_xp(text, text, int, text, text)
  FROM anon, authenticated;


-- ── 6. Logbook trigger (4 domains fired per row) ──────────────
-- Domains: wrench_chronicle, failure_hunter, safety_sentinel, knowledge_forger
-- Note: logbook.id is type TEXT (not uuid)
CREATE OR REPLACE FUNCTION trg_logbook_achievement_xp()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_xp      int;
  v_content text;
BEGIN
  -- INSERT: entry submitted
  IF TG_OP = 'INSERT' THEN
    v_xp := 20;

    -- Knowledge Forger: combined text > 200 chars signals a detailed entry
    v_content := coalesce(NEW.problem, '') || coalesce(NEW.action, '') || coalesce(NEW.knowledge, '');
    IF char_length(v_content) > 200 THEN
      v_xp := v_xp + 20;
      PERFORM award_achievement_xp(
        NEW.worker_name, 'knowledge_forger', 20, 'detailed_entry', NEW.id);
    END IF;

    PERFORM award_achievement_xp(
      NEW.worker_name, 'wrench_chronicle', v_xp, 'logbook_submit', NEW.id);

    -- Safety Sentinel: safety-category entry
    IF NEW.category ILIKE '%safety%' THEN
      PERFORM award_achievement_xp(
        NEW.worker_name, 'safety_sentinel', 60, 'safety_entry', NEW.id);
    END IF;
  END IF;

  -- UPDATE: status transition to Closed
  IF TG_OP = 'UPDATE'
     AND NEW.status = 'Closed'
     AND (OLD.status IS DISTINCT FROM 'Closed') THEN

    v_xp := 50;

    IF NEW.root_cause IS NOT NULL AND trim(NEW.root_cause) <> '' THEN
      v_xp := v_xp + 30;
    END IF;

    IF NEW.machine IS NOT NULL AND NEW.downtime_hours IS NOT NULL THEN
      v_xp := v_xp + 15;
    END IF;

    -- Closed within 24 h of submission
    IF NEW.closed_at IS NOT NULL AND NEW.created_at IS NOT NULL
       AND (NEW.closed_at - NEW.created_at) < interval '24 hours' THEN
      v_xp := v_xp + 25;
    END IF;

    PERFORM award_achievement_xp(
      NEW.worker_name, 'wrench_chronicle', v_xp, 'logbook_close', NEW.id);

    -- Failure Hunter: breakdown/corrective entry closed with root cause
    IF (NEW.maintenance_type ILIKE '%corrective%'
        OR NEW.maintenance_type ILIKE '%breakdown%'
        OR NEW.category        ILIKE '%breakdown%')
       AND NEW.root_cause IS NOT NULL
       AND trim(NEW.root_cause) <> '' THEN
      PERFORM award_achievement_xp(
        NEW.worker_name, 'failure_hunter', 100, 'breakdown_root_cause', NEW.id);
    END IF;
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_logbook_achievement ON logbook;
CREATE TRIGGER trg_logbook_achievement
  AFTER INSERT OR UPDATE ON logbook
  FOR EACH ROW
  EXECUTE FUNCTION trg_logbook_achievement_xp();


-- ── 7. PM completion trigger (Uptime Guardian) ────────────────
-- pm_completions.id is uuid — cast to text for source_id
CREATE OR REPLACE FUNCTION trg_pm_achievement_xp()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    PERFORM award_achievement_xp(
      NEW.worker_name, 'uptime_guardian', 60, 'pm_complete', NEW.id::text);
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_pm_achievement ON pm_completions;
CREATE TRIGGER trg_pm_achievement
  AFTER INSERT ON pm_completions
  FOR EACH ROW
  EXECUTE FUNCTION trg_pm_achievement_xp();


-- ── 8. Community post trigger (Voice of the Hive) ─────────────
-- community_posts uses author_name, not worker_name
-- id is uuid — cast to text
CREATE OR REPLACE FUNCTION trg_community_achievement_xp()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_xp int;
BEGIN
  IF TG_OP = 'INSERT' THEN
    v_xp := 20;
    IF NEW.category = 'safety' THEN
      v_xp := v_xp + 40;
    END IF;
    PERFORM award_achievement_xp(
      NEW.author_name, 'voice_of_hive', v_xp, 'community_post', NEW.id::text);
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_community_achievement ON community_posts;
CREATE TRIGGER trg_community_achievement
  AFTER INSERT ON community_posts
  FOR EACH ROW
  EXECUTE FUNCTION trg_community_achievement_xp();


-- ── 9. Skill badge trigger (Skill Climber) ────────────────────
-- skill_badges.id is uuid — cast to text
CREATE OR REPLACE FUNCTION trg_skill_badge_achievement_xp()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    PERFORM award_achievement_xp(
      NEW.worker_name, 'skill_climber', 250, 'skill_badge_earned', NEW.id::text);
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_skill_badge_achievement ON skill_badges;
CREATE TRIGGER trg_skill_badge_achievement
  AFTER INSERT ON skill_badges
  FOR EACH ROW
  EXECUTE FUNCTION trg_skill_badge_achievement_xp();


-- ── 10. pg_cron: purge XP log older than 90 days ─────────────
-- Runs every Sunday at 03:00 UTC.
-- The XP total on worker_achievements is the durable record;
-- the log is for recent history display only.
SELECT cron.schedule(
  'achievement-xp-log-purge',
  '0 3 * * 0',
  $$DELETE FROM achievement_xp_log WHERE earned_at < now() - interval '90 days'$$
);
