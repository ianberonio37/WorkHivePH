-- Q1 (2026-07-05): FLIP hive_quotas.enforce_blocking on — the cumulative per-hive
-- row-quota that holds the DB line against sustained runaway growth.
--
-- GROUNDED framing (2026-07-05, Step 0): 500 MB ÷ ~300 hives can't be BOTH generous
-- per-hive AND tight enough to hold the line, so the two jobs split:
--   * cumulative caps here = GENEROUS ABUSE ceilings (a runaway integration/loop that
--     the per-DAY caps (Q2) don't catch because it stays under the daily rate for weeks).
--     No honest team hits 20k lifetime logbook rows; a broken loop does.
--   * steady-state 500 MB line = RETENTION (Q5-b: archive-to-Parquet + prune hot rows,
--     esp. the embedding tables — voice_journal_entries measured 45 MB).
-- F2 fork ("enforce vs warn first?") is resolved in the roadmap: enforce-generous from
-- day 1 + warn-at-80%. This migration is LOCAL; the prod deploy is Ian-gated.
--
-- THREE fixes bundled (all needed to make the flip safe):
--   1. BUG: the 5 existing quota fns log over-quota to automation_log with status 'warn',
--      but automation_log CHECK allows only success/failed/skipped -> a constraint
--      violation the moment any hive with a quota row hits its cap. Masked today only
--      because hive_quotas has 0 rows. Also the log-then-RAISE was FUTILE (the RAISE rolls
--      back the same statement, incl. the log — the Q0 lesson). Restructured: RAISE with
--      SQLSTATE 54000 (the frontend's existing daily-cap handler catches it) when
--      enforcing; log with a VALID status only in warn-only mode.
--   2. Every hive gets a generous quota row (backfill + a new-hive trigger) so the flip
--      actually covers the platform (a NULL cap = pass, so no-row hives were unbounded).
--   3. enforce_blocking default flips to true for any future direct inserts.

-- ── 0. Self-heal schema drift (live-apply caught it) ───────────────────────────────
-- The live hive_quotas (000003) was created via CREATE TABLE IF NOT EXISTS against a
-- pre-existing, differently-shaped table, so max_rows_inv_tx + max_storage_mb never
-- landed even though the migration FILE declares them (files-are-truth drift). ADD IF
-- NOT EXISTS makes this migration correct on both the drifted local DB and a clean one —
-- and repairs check_hive_quota_inv_tx, which SELECTs max_rows_inv_tx.
ALTER TABLE public.hive_quotas ADD COLUMN IF NOT EXISTS max_rows_inv_tx integer;
ALTER TABLE public.hive_quotas ADD COLUMN IF NOT EXISTS max_storage_mb  integer;

-- ── 1. Generous abuse-ceiling caps + enforce ON, backfilled for every existing hive ──
-- max_storage_mb is a column with no trigger yet (future MB-quota lever); set for context.
INSERT INTO public.hive_quotas (hive_id, max_rows_logbook, max_rows_logbook_per_user,
                                max_rows_inv_tx, max_rows_pm_comp, max_rows_community,
                                max_rows_ai_reports, max_storage_mb, enforce_blocking)
SELECT h.id, 20000, 8000, 50000, 20000, 10000, 5000, 400, true
  FROM public.hives h
ON CONFLICT (hive_id) DO UPDATE SET
  max_rows_logbook          = COALESCE(public.hive_quotas.max_rows_logbook, EXCLUDED.max_rows_logbook),
  max_rows_logbook_per_user = COALESCE(public.hive_quotas.max_rows_logbook_per_user, EXCLUDED.max_rows_logbook_per_user),
  max_rows_inv_tx           = COALESCE(public.hive_quotas.max_rows_inv_tx, EXCLUDED.max_rows_inv_tx),
  max_rows_pm_comp          = COALESCE(public.hive_quotas.max_rows_pm_comp, EXCLUDED.max_rows_pm_comp),
  max_rows_community        = COALESCE(public.hive_quotas.max_rows_community, EXCLUDED.max_rows_community),
  max_rows_ai_reports       = COALESCE(public.hive_quotas.max_rows_ai_reports, EXCLUDED.max_rows_ai_reports),
  max_storage_mb            = COALESCE(public.hive_quotas.max_storage_mb, EXCLUDED.max_storage_mb),
  enforce_blocking          = true,
  updated_at                = now();

-- Future direct inserts default to enforcing.
ALTER TABLE public.hive_quotas ALTER COLUMN enforce_blocking SET DEFAULT true;

-- ── 2. New hives auto-get a generous, enforcing quota row ──────────────────────────
-- SECURITY DEFINER so it can write through the service-role-only RLS on hive_quotas.
CREATE OR REPLACE FUNCTION public.seed_hive_quota_defaults()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public
AS $$
BEGIN
  INSERT INTO public.hive_quotas (hive_id, max_rows_logbook, max_rows_logbook_per_user,
                                  max_rows_inv_tx, max_rows_pm_comp, max_rows_community,
                                  max_rows_ai_reports, max_storage_mb, enforce_blocking)
  VALUES (NEW.id, 20000, 8000, 50000, 20000, 10000, 5000, 400, true)
  ON CONFLICT (hive_id) DO NOTHING;
  RETURN NEW;
END; $$;

DROP TRIGGER IF EXISTS trg_seed_hive_quota_defaults ON public.hives;
CREATE TRIGGER trg_seed_hive_quota_defaults
  AFTER INSERT ON public.hives
  FOR EACH ROW EXECUTE FUNCTION public.seed_hive_quota_defaults();

-- ── 3. Fix all 5 cumulative-quota fns: valid-status log + non-futile enforce ────────
-- logbook
CREATE OR REPLACE FUNCTION public.check_hive_quota_logbook()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public
AS $$
DECLARE q_max integer; q_enforce boolean; current_n integer;
BEGIN
  SELECT max_rows_logbook, enforce_blocking INTO q_max, q_enforce
    FROM public.hive_quotas WHERE hive_id = NEW.hive_id;
  IF q_max IS NULL OR NEW.hive_id IS NULL THEN RETURN NEW; END IF;
  SELECT COUNT(*) INTO current_n FROM public.logbook WHERE hive_id = NEW.hive_id;
  IF current_n >= q_max THEN
    IF q_enforce THEN
      RAISE EXCEPTION 'logbook cumulative quota exceeded for hive % (% >= %)', NEW.hive_id, current_n, q_max
        USING ERRCODE = '54000', HINT = 'Old records can be archived; contact your supervisor to raise the cap.';
    ELSE
      INSERT INTO public.automation_log (job_name, status, detail, triggered_at)
      VALUES ('hive_quota_logbook_over', 'skipped',
              format('WARN-ONLY hive %s logbook %s >= cap %s', NEW.hive_id, current_n, q_max), now());
    END IF;
  END IF;
  RETURN NEW;
END; $$;

-- inventory_transactions
CREATE OR REPLACE FUNCTION public.check_hive_quota_inv_tx()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public
AS $$
DECLARE q_max integer; q_enforce boolean; current_n integer;
BEGIN
  SELECT max_rows_inv_tx, enforce_blocking INTO q_max, q_enforce
    FROM public.hive_quotas WHERE hive_id = NEW.hive_id;
  IF q_max IS NULL OR NEW.hive_id IS NULL THEN RETURN NEW; END IF;
  SELECT COUNT(*) INTO current_n FROM public.inventory_transactions WHERE hive_id = NEW.hive_id;
  IF current_n >= q_max THEN
    IF q_enforce THEN
      RAISE EXCEPTION 'inventory_transactions cumulative quota exceeded for hive % (% >= %)', NEW.hive_id, current_n, q_max
        USING ERRCODE = '54000', HINT = 'Old records can be archived; contact your supervisor to raise the cap.';
    ELSE
      INSERT INTO public.automation_log (job_name, status, detail, triggered_at)
      VALUES ('hive_quota_inv_tx_over', 'skipped',
              format('WARN-ONLY hive %s inv_tx %s >= cap %s', NEW.hive_id, current_n, q_max), now());
    END IF;
  END IF;
  RETURN NEW;
END; $$;

-- pm_completions
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
    IF q_enforce THEN
      RAISE EXCEPTION 'pm_completions cumulative quota exceeded for hive % (% >= %)', NEW.hive_id, current_n, q_max
        USING ERRCODE = '54000', HINT = 'Old records can be archived; contact your supervisor to raise the cap.';
    ELSE
      INSERT INTO public.automation_log (job_name, status, detail, triggered_at)
      VALUES ('hive_quota_pm_completions_over', 'skipped',
              format('WARN-ONLY hive %s pm_completions %s >= cap %s', NEW.hive_id, current_n, q_max), now());
    END IF;
  END IF;
  RETURN NEW;
END; $$;

-- ai_reports
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
    IF q_enforce THEN
      RAISE EXCEPTION 'ai_reports cumulative quota exceeded for hive % (% >= %)', NEW.hive_id, current_n, q_max
        USING ERRCODE = '54000', HINT = 'Old reports can be archived; contact your supervisor to raise the cap.';
    ELSE
      INSERT INTO public.automation_log (job_name, status, detail, triggered_at)
      VALUES ('hive_quota_ai_reports_over', 'skipped',
              format('WARN-ONLY hive %s ai_reports %s >= cap %s', NEW.hive_id, current_n, q_max), now());
    END IF;
  END IF;
  RETURN NEW;
END; $$;

-- community_posts
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
    IF q_enforce THEN
      RAISE EXCEPTION 'community cumulative quota exceeded for hive % (% >= %)', NEW.hive_id, current_n, q_max
        USING ERRCODE = '54000', HINT = 'Old posts can be archived; contact your supervisor to raise the cap.';
    ELSE
      INSERT INTO public.automation_log (job_name, status, detail, triggered_at)
      VALUES ('hive_quota_community_over', 'skipped',
              format('WARN-ONLY hive %s community %s >= cap %s', NEW.hive_id, current_n, q_max), now());
    END IF;
  END IF;
  RETURN NEW;
END; $$;

-- ── 4. (RE)ATTACH all 5 triggers ───────────────────────────────────────────────────
-- Live-apply caught that 000003's logbook + inv_tx triggers had DRIFTED OFF the live DB
-- (only 000007's pm/community/ai_reports were still attached) — so those two cumulative
-- caps were silently no-ops. Re-attach all 5 idempotently so enforcement is real
-- regardless of drift.
DROP TRIGGER IF EXISTS trg_hive_quota_logbook ON public.logbook;
CREATE TRIGGER trg_hive_quota_logbook BEFORE INSERT ON public.logbook
  FOR EACH ROW EXECUTE FUNCTION public.check_hive_quota_logbook();

DROP TRIGGER IF EXISTS trg_hive_quota_inv_tx ON public.inventory_transactions;
CREATE TRIGGER trg_hive_quota_inv_tx BEFORE INSERT ON public.inventory_transactions
  FOR EACH ROW EXECUTE FUNCTION public.check_hive_quota_inv_tx();

DROP TRIGGER IF EXISTS trg_hive_quota_pm_completions ON public.pm_completions;
CREATE TRIGGER trg_hive_quota_pm_completions BEFORE INSERT ON public.pm_completions
  FOR EACH ROW EXECUTE FUNCTION public.check_hive_quota_pm_completions();

DROP TRIGGER IF EXISTS trg_hive_quota_ai_reports ON public.ai_reports;
CREATE TRIGGER trg_hive_quota_ai_reports BEFORE INSERT ON public.ai_reports
  FOR EACH ROW EXECUTE FUNCTION public.check_hive_quota_ai_reports();

DROP TRIGGER IF EXISTS trg_hive_quota_community_posts ON public.community_posts;
CREATE TRIGGER trg_hive_quota_community_posts BEFORE INSERT ON public.community_posts
  FOR EACH ROW EXECUTE FUNCTION public.check_hive_quota_community();
