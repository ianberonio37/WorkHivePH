-- DB Hygiene Batch -- 2026-05-11
-- Closes PRODUCTION_FIXES entries:
--   #50 SQL function security (DEFINER + search_path lockdown)
--   #45 Cascade behavior (2 FKs without explicit ON DELETE)
--   #42 Index coverage (13 high-frequency unindexed columns)
--
-- Postgres last-writer-wins per (table, name) for ALTER TABLE constraints
-- and per function name for CREATE OR REPLACE FUNCTION, so this single
-- migration supersedes all prior vulnerable definitions in one shot.

-- ==========================================================================
-- Part A: SECURITY DEFINER + search_path lockdown (closes #50)
-- ==========================================================================
-- Each fn re-declared with `SET search_path = pg_catalog, public` so an
-- attacker cannot shadow built-in names via a writeable schema.

CREATE OR REPLACE FUNCTION public.increment_community_xp(
  p_worker_name text,
  p_hive_id     uuid,
  p_amount      integer
) RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
  INSERT INTO community_xp (worker_name, hive_id, xp_total, updated_at)
  VALUES (p_worker_name, p_hive_id, p_amount, now())
  ON CONFLICT (worker_name, hive_id) DO UPDATE
  SET xp_total   = community_xp.xp_total + p_amount,
      updated_at = now();
END;
$$;


CREATE OR REPLACE FUNCTION public.handle_community_post_xp()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  post_count integer;
BEGIN
  SELECT COUNT(*) INTO post_count
  FROM community_posts
  WHERE author_name = NEW.author_name AND hive_id = NEW.hive_id;

  IF post_count = 1 THEN
    PERFORM increment_community_xp(NEW.author_name, NEW.hive_id, 50);
  END IF;

  IF NEW.category = 'safety' THEN
    PERFORM increment_community_xp(NEW.author_name, NEW.hive_id, 25);
  END IF;

  IF post_count = 10 THEN
    INSERT INTO skill_badges (worker_name, discipline, level, badge_key, earned_at, auth_uid)
    VALUES (NEW.author_name, 'Community', 1, 'voice_of_the_hive', now(), NEW.auth_uid)
    ON CONFLICT (worker_name, badge_key) DO NOTHING;
  END IF;

  RETURN NEW;
END;
$$;


CREATE OR REPLACE FUNCTION public.handle_community_reply_xp()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
  PERFORM increment_community_xp(NEW.author_name, NEW.hive_id, 10);
  RETURN NEW;
END;
$$;


CREATE OR REPLACE FUNCTION public.handle_community_reaction_xp()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  reaction_count integer;
  v_author       text;
  v_hive_id      uuid;
BEGIN
  SELECT COUNT(*) INTO reaction_count
  FROM community_reactions WHERE post_id = NEW.post_id;

  IF reaction_count = 3 THEN
    SELECT author_name, hive_id INTO v_author, v_hive_id
    FROM community_posts WHERE id = NEW.post_id;
    IF v_author IS NOT NULL THEN
      PERFORM increment_community_xp(v_author, v_hive_id, 20);
    END IF;
  END IF;

  RETURN NEW;
END;
$$;


CREATE OR REPLACE FUNCTION public.sync_auth_uid_on_signup()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
  UPDATE public.hive_members           SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.logbook                SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.inventory_items        SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.inventory_transactions SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.assets                 SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.pm_assets              SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.pm_completions         SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.schedule_items         SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.skill_profiles         SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.skill_badges           SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.skill_exam_attempts    SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.engineering_calcs      SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.asset_nodes            SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  RETURN NEW;
END;
$$;


CREATE OR REPLACE FUNCTION public.increment_listing_view(p_listing_id uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
  UPDATE public.marketplace_listings
  SET view_count = view_count + 1
  WHERE id = p_listing_id AND status = 'published';
END;
$$;


-- ==========================================================================
-- Part B: Explicit ON DELETE cascade behavior (closes #45)
-- ==========================================================================
-- parts_records.asset_ref_id -> assets : SET NULL (parts history survives asset deletion)
-- worker_achievements.achievement_id -> achievement_definitions : CASCADE (no achievement = no record)

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'parts_records_asset_ref_id_fkey'
  ) THEN
    ALTER TABLE public.parts_records DROP CONSTRAINT parts_records_asset_ref_id_fkey;
  END IF;
END
$$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'parts_records' AND column_name = 'asset_ref_id'
  )
  AND EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'assets' AND column_name = 'asset_id'
  )
  -- Guard: Postgres requires the FK target column to have a UNIQUE or PRIMARY KEY
  -- constraint. Fresh-clone local stacks may not have that on assets.asset_id yet;
  -- skip the FK in that case so `supabase start` does not fail. The check looks
  -- for any unique/PK constraint that covers exactly the asset_id column.
  AND EXISTS (
    SELECT 1
    FROM pg_constraint c
    JOIN pg_class      t ON t.oid = c.conrelid
    JOIN pg_attribute  a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
    WHERE t.relname = 'assets'
      AND a.attname = 'asset_id'
      AND c.contype IN ('u', 'p')
      AND array_length(c.conkey, 1) = 1
  ) THEN
    EXECUTE 'ALTER TABLE public.parts_records
             ADD CONSTRAINT parts_records_asset_ref_id_fkey
             FOREIGN KEY (asset_ref_id) REFERENCES public.assets(asset_id)
             ON DELETE SET NULL';
  END IF;
END
$$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'worker_achievements_achievement_id_fkey'
  ) THEN
    ALTER TABLE public.worker_achievements DROP CONSTRAINT worker_achievements_achievement_id_fkey;
  END IF;
END
$$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'worker_achievements' AND column_name = 'achievement_id'
  ) THEN
    EXECUTE 'ALTER TABLE public.worker_achievements
             ADD CONSTRAINT worker_achievements_achievement_id_fkey
             FOREIGN KEY (achievement_id) REFERENCES public.achievement_definitions(id)
             ON DELETE CASCADE';
  END IF;
END
$$;


-- ==========================================================================
-- Part C: Index coverage (closes #42 L1; 13 high-frequency unindexed columns)
-- ==========================================================================
-- All use IF NOT EXISTS so re-apply on environments that already have any
-- of these indexes is a no-op.

CREATE INDEX IF NOT EXISTS idx_hive_members_hive_id          ON public.hive_members          (hive_id);
CREATE INDEX IF NOT EXISTS idx_hive_members_worker_name      ON public.hive_members          (worker_name);
CREATE INDEX IF NOT EXISTS idx_hive_members_status           ON public.hive_members          (status);
CREATE INDEX IF NOT EXISTS idx_logbook_created_at            ON public.logbook               (created_at);
CREATE INDEX IF NOT EXISTS idx_logbook_maintenance_type      ON public.logbook               (maintenance_type);
CREATE INDEX IF NOT EXISTS idx_inventory_items_worker_name   ON public.inventory_items       (worker_name);
CREATE INDEX IF NOT EXISTS idx_marketplace_listings_status   ON public.marketplace_listings  (status);
CREATE INDEX IF NOT EXISTS idx_assets_worker_name            ON public.assets                (worker_name);
CREATE INDEX IF NOT EXISTS idx_assets_hive_id                ON public.assets                (hive_id);
CREATE INDEX IF NOT EXISTS idx_pm_completions_status         ON public.pm_completions        (status);
CREATE INDEX IF NOT EXISTS idx_pm_completions_hive_id        ON public.pm_completions        (hive_id);
CREATE INDEX IF NOT EXISTS idx_pm_assets_hive_id             ON public.pm_assets             (hive_id);
CREATE INDEX IF NOT EXISTS idx_external_sync_entity_type     ON public.external_sync         (entity_type);
