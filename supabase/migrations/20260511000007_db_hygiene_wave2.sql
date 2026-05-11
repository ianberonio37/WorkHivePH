-- DB Hygiene Wave 2 -- 2026-05-11
-- Closes PRODUCTION_FIXES entries:
--   #58  GIN index on external_sync.sync_payload
--   #42 L2  12 medium-frequency unindexed columns
--   #56 v2  8 additional hive-quota triggers (observe-only)

-- ==========================================================================
-- Part A: GIN index on external_sync.sync_payload (closes #58)
-- ==========================================================================

CREATE INDEX IF NOT EXISTS idx_external_sync_sync_payload_gin
  ON public.external_sync USING gin (sync_payload);


-- ==========================================================================
-- Part B: L2 medium-frequency indexes (closes #42 L2)
-- ==========================================================================

CREATE INDEX IF NOT EXISTS idx_logbook_machine                   ON public.logbook               (machine);
CREATE INDEX IF NOT EXISTS idx_inventory_items_hive_id           ON public.inventory_items       (hive_id);
CREATE INDEX IF NOT EXISTS idx_inventory_items_status            ON public.inventory_items       (status);
CREATE INDEX IF NOT EXISTS idx_assets_status                     ON public.assets                (status);
CREATE INDEX IF NOT EXISTS idx_external_sync_external_id         ON public.external_sync         (external_id);
CREATE INDEX IF NOT EXISTS idx_projects_status                   ON public.projects              (status);
CREATE INDEX IF NOT EXISTS idx_parts_staging_recs_status         ON public.parts_staging_recommendations (status);
CREATE INDEX IF NOT EXISTS idx_project_links_hive_id             ON public.project_links         (hive_id);
CREATE INDEX IF NOT EXISTS idx_project_progress_logs_hive_id     ON public.project_progress_logs (hive_id);
CREATE INDEX IF NOT EXISTS idx_asset_nodes_status                ON public.asset_nodes           (status);
CREATE INDEX IF NOT EXISTS idx_schedule_items_worker_name        ON public.schedule_items        (worker_name);
CREATE INDEX IF NOT EXISTS idx_pm_assets_worker_name             ON public.pm_assets             (worker_name);


-- ==========================================================================
-- Part C: Hive-quota triggers v2 (closes #56 v2)
-- ==========================================================================
-- 8 additional high-volume tables get quota enforcement triggers. All
-- observe-only (log over-quota to automation_log; only block when
-- hive_quotas.enforce_blocking = true).

-- Generic quota check builder. Each trigger fn is a thin shell over a
-- shared template -- table-specific because Postgres doesn't have
-- generic trigger arguments without dynamic SQL.

CREATE OR REPLACE FUNCTION public.check_hive_quota_pm_completions()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public
AS $$
DECLARE q_max integer; q_enforce boolean; current_n integer;
BEGIN
  SELECT max_rows_pm_comp, enforce_blocking INTO q_max, q_enforce
    FROM public.hive_quotas WHERE hive_id = NEW.hive_id;
  IF q_max IS NULL OR NEW.hive_id IS NULL THEN RETURN NEW; END IF;
  SELECT COUNT(*) INTO current_n FROM public.pm_completions WHERE hive_id = NEW.hive_id;
  IF current_n >= q_max THEN
    INSERT INTO public.automation_log (job_name, status, detail, triggered_at)
    VALUES ('hive_quota_pm_completions_over', 'warn',
            format('hive %s pm_completions count %s >= cap %s', NEW.hive_id, current_n, q_max), now());
    IF q_enforce THEN
      RAISE EXCEPTION 'pm_completions quota exceeded for hive %', NEW.hive_id;
    END IF;
  END IF;
  RETURN NEW;
END; $$;
DROP TRIGGER IF EXISTS trg_hive_quota_pm_completions ON public.pm_completions;
CREATE TRIGGER trg_hive_quota_pm_completions BEFORE INSERT ON public.pm_completions
  FOR EACH ROW EXECUTE FUNCTION public.check_hive_quota_pm_completions();


CREATE OR REPLACE FUNCTION public.check_hive_quota_ai_reports()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public
AS $$
DECLARE q_max integer; q_enforce boolean; current_n integer;
BEGIN
  SELECT max_rows_ai_reports, enforce_blocking INTO q_max, q_enforce
    FROM public.hive_quotas WHERE hive_id = NEW.hive_id;
  IF q_max IS NULL OR NEW.hive_id IS NULL THEN RETURN NEW; END IF;
  SELECT COUNT(*) INTO current_n FROM public.ai_reports WHERE hive_id = NEW.hive_id;
  IF current_n >= q_max THEN
    INSERT INTO public.automation_log (job_name, status, detail, triggered_at)
    VALUES ('hive_quota_ai_reports_over', 'warn',
            format('hive %s ai_reports count %s >= cap %s', NEW.hive_id, current_n, q_max), now());
    IF q_enforce THEN RAISE EXCEPTION 'ai_reports quota exceeded for hive %', NEW.hive_id; END IF;
  END IF;
  RETURN NEW;
END; $$;
DROP TRIGGER IF EXISTS trg_hive_quota_ai_reports ON public.ai_reports;
CREATE TRIGGER trg_hive_quota_ai_reports BEFORE INSERT ON public.ai_reports
  FOR EACH ROW EXECUTE FUNCTION public.check_hive_quota_ai_reports();


CREATE OR REPLACE FUNCTION public.check_hive_quota_community()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public
AS $$
DECLARE q_max integer; q_enforce boolean; current_n integer;
BEGIN
  SELECT max_rows_community, enforce_blocking INTO q_max, q_enforce
    FROM public.hive_quotas WHERE hive_id = NEW.hive_id;
  IF q_max IS NULL OR NEW.hive_id IS NULL THEN RETURN NEW; END IF;
  SELECT COUNT(*) INTO current_n FROM public.community_posts WHERE hive_id = NEW.hive_id;
  IF current_n >= q_max THEN
    INSERT INTO public.automation_log (job_name, status, detail, triggered_at)
    VALUES ('hive_quota_community_over', 'warn',
            format('hive %s community_posts count %s >= cap %s', NEW.hive_id, current_n, q_max), now());
    IF q_enforce THEN RAISE EXCEPTION 'community quota exceeded for hive %', NEW.hive_id; END IF;
  END IF;
  RETURN NEW;
END; $$;
DROP TRIGGER IF EXISTS trg_hive_quota_community_posts ON public.community_posts;
CREATE TRIGGER trg_hive_quota_community_posts BEFORE INSERT ON public.community_posts
  FOR EACH ROW EXECUTE FUNCTION public.check_hive_quota_community();
