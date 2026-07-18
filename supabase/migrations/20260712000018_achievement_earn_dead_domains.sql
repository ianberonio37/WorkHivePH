-- 20260712000018_achievement_earn_dead_domains.sql
-- Dayplanner/Growth PDDA arc (2026-07-12) — Ext-3 honesty: MAKE the 4 dead achievement domains
-- EARNABLE (Ian: "just make it earnable" — build the structure, don't downgrade to "coming soon").
--
-- These 4 achievement_definitions rendered as earnable but had NO XP trigger (0 rows ever earned by
-- anyone, all workers). Each is now wired to a REAL existing action + backfilled from existing data:
--   blueprint_master ← engineering_calcs INSERT      (run an engineering calculation)  +40
--   shift_keeper     ← shift_plans publish           (publish/hand over the shift plan) +40
--   hive_architect   ← hive_members role=supervisor  (lead/build a team)                +50
--   iron_worker      ← worker_achievements meta-check (Level 50 in any 5 domains)       +500 unlock
-- All award via the existing SECURITY DEFINER award_achievement_xp() (client EXECUTE already revoked),
-- so XP stays server-awarded + event-sourced. Backfill is idempotent (NOT EXISTS on achievement_xp_log
-- source_id), so re-applying the migration never double-awards. published_by is a worker_name (text).

-- ── blueprint_master ← engineering_calcs ──────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION trg_engcalc_achievement_xp() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  IF NEW.worker_name IS NOT NULL THEN
    PERFORM award_achievement_xp(NEW.worker_name, 'blueprint_master', 40, 'calc_run', NEW.id::text);
  END IF;
  RETURN NEW;
END; $$;
DROP TRIGGER IF EXISTS trg_engcalc_achievement ON engineering_calcs;
CREATE TRIGGER trg_engcalc_achievement AFTER INSERT ON engineering_calcs
  FOR EACH ROW EXECUTE FUNCTION trg_engcalc_achievement_xp();

-- ── shift_keeper ← shift_plans publish (published_by set) ──────────────────────────────────────
CREATE OR REPLACE FUNCTION trg_shiftplan_achievement_xp() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  IF NEW.published_by IS NOT NULL
     AND (OLD.published_by IS NULL OR OLD.published_by IS DISTINCT FROM NEW.published_by) THEN
    PERFORM award_achievement_xp(NEW.published_by, 'shift_keeper', 40, 'shift_publish', NEW.id::text);
  END IF;
  RETURN NEW;
END; $$;
DROP TRIGGER IF EXISTS trg_shiftplan_achievement ON shift_plans;
CREATE TRIGGER trg_shiftplan_achievement AFTER UPDATE ON shift_plans
  FOR EACH ROW EXECUTE FUNCTION trg_shiftplan_achievement_xp();

-- ── hive_architect ← becoming/leading as a supervisor ─────────────────────────────────────────
CREATE OR REPLACE FUNCTION trg_hivemember_achievement_xp() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  IF NEW.role = 'supervisor' AND NEW.worker_name IS NOT NULL
     AND (TG_OP = 'INSERT' OR OLD.role IS DISTINCT FROM 'supervisor') THEN
    PERFORM award_achievement_xp(NEW.worker_name, 'hive_architect', 50, 'team_lead', NEW.id::text);
  END IF;
  RETURN NEW;
END; $$;
DROP TRIGGER IF EXISTS trg_hivemember_achievement ON hive_members;
CREATE TRIGGER trg_hivemember_achievement AFTER INSERT OR UPDATE ON hive_members
  FOR EACH ROW EXECUTE FUNCTION trg_hivemember_achievement_xp();

-- ── iron_worker ← Level 50 in any 5 domains (legendary unlock, meta on worker_achievements) ────
-- Recursion-safe: skips the iron_worker row itself + no-ops once unlocked. Fires on every XP write
-- but the count query is cheap and XP writes are low-frequency.
CREATE OR REPLACE FUNCTION trg_iron_worker_check() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v_cnt int;
BEGIN
  IF NEW.achievement_id = 'iron_worker' THEN RETURN NEW; END IF;
  IF EXISTS (SELECT 1 FROM worker_achievements
             WHERE worker_name = NEW.worker_name AND achievement_id = 'iron_worker') THEN
    RETURN NEW;
  END IF;
  SELECT count(*) INTO v_cnt FROM worker_achievements
   WHERE worker_name = NEW.worker_name AND achievement_id <> 'iron_worker' AND current_level >= 50;
  IF v_cnt >= 5 THEN
    PERFORM award_achievement_xp(NEW.worker_name, 'iron_worker', 500, 'legendary_unlock', NULL);
  END IF;
  RETURN NEW;
END; $$;
DROP TRIGGER IF EXISTS trg_iron_worker ON worker_achievements;
CREATE TRIGGER trg_iron_worker AFTER INSERT OR UPDATE ON worker_achievements
  FOR EACH ROW EXECUTE FUNCTION trg_iron_worker_check();

-- ── Idempotent backfill from existing data (so the domains are earnable AND already show progress) ──
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT ec.id, ec.worker_name FROM engineering_calcs ec
           WHERE ec.worker_name IS NOT NULL
             AND NOT EXISTS (SELECT 1 FROM achievement_xp_log l
                             WHERE l.achievement_id='blueprint_master' AND l.source_id = ec.id::text)
  LOOP PERFORM award_achievement_xp(r.worker_name, 'blueprint_master', 40, 'calc_run', r.id::text); END LOOP;

  FOR r IN SELECT sp.id, sp.published_by FROM shift_plans sp
           WHERE sp.published_by IS NOT NULL
             AND NOT EXISTS (SELECT 1 FROM achievement_xp_log l
                             WHERE l.achievement_id='shift_keeper' AND l.source_id = sp.id::text)
  LOOP PERFORM award_achievement_xp(r.published_by, 'shift_keeper', 40, 'shift_publish', r.id::text); END LOOP;

  FOR r IN SELECT hm.id, hm.worker_name FROM hive_members hm
           WHERE hm.role='supervisor' AND hm.worker_name IS NOT NULL
             AND NOT EXISTS (SELECT 1 FROM achievement_xp_log l
                             WHERE l.achievement_id='hive_architect' AND l.source_id = hm.id::text)
  LOOP PERFORM award_achievement_xp(r.worker_name, 'hive_architect', 50, 'team_lead', r.id::text); END LOOP;
END $$;
