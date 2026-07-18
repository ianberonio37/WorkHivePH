-- P3/P5 attribution-forge SWEEP (bug-hunt roadmap, 2026-07-18). Platform-wide audit for ANY column
-- that records WHO did something (not just worker_name) found 10 more client-writable, hive-scoped
-- accountability fields with NO identity pin — RLS gated the ROLE (member/supervisor of the hive) but
-- never the NAME, so a caller could stamp another person's name on an approval / acknowledgement /
-- review / assignment. Same class as migs 000010/000011/000014, missed because the columns are named
-- approved_by / acknowledged_by / reviewed_by / assigned_by.
--
-- Fix: derive the attribution from the caller's hive_members identity whenever the field is SET to a
-- non-null value this write (INSERT, or an UPDATE that changes it). A status-only update that leaves
-- the field untouched is not affected. Service-role / seeder / edge-fn writes (auth.uid() NULL) are
-- trusted (no-op), so batch/auto-approve flows are unaffected. These actions (approve/ack/review/
-- assign) are always performed BY the caller, so deriving name = caller is the correct semantics.

-- approved_by ----------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.bind_approved_by_from_hive() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE v_name text;
BEGIN
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;
  IF NEW.hive_id IS NULL THEN RETURN NEW; END IF;
  IF NEW.approved_by IS NULL OR NEW.approved_by IS NOT DISTINCT FROM OLD.approved_by THEN RETURN NEW; END IF;
  SELECT worker_name INTO v_name FROM public.hive_members
    WHERE auth_uid = auth.uid() AND hive_id = NEW.hive_id AND status = 'active' LIMIT 1;
  IF v_name IS NOT NULL THEN NEW.approved_by := v_name; END IF;
  RETURN NEW;
END $$;

-- acknowledged_by ------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.bind_acknowledged_by_from_hive() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE v_name text;
BEGIN
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;
  IF NEW.hive_id IS NULL THEN RETURN NEW; END IF;
  IF NEW.acknowledged_by IS NULL OR NEW.acknowledged_by IS NOT DISTINCT FROM OLD.acknowledged_by THEN RETURN NEW; END IF;
  SELECT worker_name INTO v_name FROM public.hive_members
    WHERE auth_uid = auth.uid() AND hive_id = NEW.hive_id AND status = 'active' LIMIT 1;
  IF v_name IS NOT NULL THEN NEW.acknowledged_by := v_name; END IF;
  RETURN NEW;
END $$;

-- reviewed_by ----------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.bind_reviewed_by_from_hive() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE v_name text;
BEGIN
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;
  IF NEW.hive_id IS NULL THEN RETURN NEW; END IF;
  IF NEW.reviewed_by IS NULL OR NEW.reviewed_by IS NOT DISTINCT FROM OLD.reviewed_by THEN RETURN NEW; END IF;
  SELECT worker_name INTO v_name FROM public.hive_members
    WHERE auth_uid = auth.uid() AND hive_id = NEW.hive_id AND status = 'active' LIMIT 1;
  IF v_name IS NOT NULL THEN NEW.reviewed_by := v_name; END IF;
  RETURN NEW;
END $$;

-- assigned_by ----------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.bind_assigned_by_from_hive() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE v_name text;
BEGIN
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;
  IF NEW.hive_id IS NULL THEN RETURN NEW; END IF;
  IF NEW.assigned_by IS NULL OR NEW.assigned_by IS NOT DISTINCT FROM OLD.assigned_by THEN RETURN NEW; END IF;
  SELECT worker_name INTO v_name FROM public.hive_members
    WHERE auth_uid = auth.uid() AND hive_id = NEW.hive_id AND status = 'active' LIMIT 1;
  IF v_name IS NOT NULL THEN NEW.assigned_by := v_name; END IF;
  RETURN NEW;
END $$;

-- approved_by triggers
DROP TRIGGER IF EXISTS tg_bind_approved_by ON public.asset_nodes;
CREATE TRIGGER tg_bind_approved_by BEFORE INSERT OR UPDATE ON public.asset_nodes            FOR EACH ROW EXECUTE FUNCTION public.bind_approved_by_from_hive();
DROP TRIGGER IF EXISTS tg_bind_approved_by ON public.rcm_fmea_modes;
CREATE TRIGGER tg_bind_approved_by BEFORE INSERT OR UPDATE ON public.rcm_fmea_modes         FOR EACH ROW EXECUTE FUNCTION public.bind_approved_by_from_hive();
DROP TRIGGER IF EXISTS tg_bind_approved_by ON public.rcm_strategies;
CREATE TRIGGER tg_bind_approved_by BEFORE INSERT OR UPDATE ON public.rcm_strategies         FOR EACH ROW EXECUTE FUNCTION public.bind_approved_by_from_hive();
DROP TRIGGER IF EXISTS tg_bind_approved_by ON public.inventory_items;
CREATE TRIGGER tg_bind_approved_by BEFORE INSERT OR UPDATE ON public.inventory_items        FOR EACH ROW EXECUTE FUNCTION public.bind_approved_by_from_hive();
DROP TRIGGER IF EXISTS tg_bind_approved_by ON public.project_change_orders;
CREATE TRIGGER tg_bind_approved_by BEFORE INSERT OR UPDATE ON public.project_change_orders  FOR EACH ROW EXECUTE FUNCTION public.bind_approved_by_from_hive();
DROP TRIGGER IF EXISTS tg_bind_approved_by ON public.amc_briefings;
CREATE TRIGGER tg_bind_approved_by BEFORE INSERT OR UPDATE ON public.amc_briefings          FOR EACH ROW EXECUTE FUNCTION public.bind_approved_by_from_hive();

-- acknowledged_by triggers
DROP TRIGGER IF EXISTS tg_bind_acknowledged_by ON public.failure_signature_alerts;
CREATE TRIGGER tg_bind_acknowledged_by BEFORE INSERT OR UPDATE ON public.failure_signature_alerts FOR EACH ROW EXECUTE FUNCTION public.bind_acknowledged_by_from_hive();
DROP TRIGGER IF EXISTS tg_bind_acknowledged_by ON public.project_progress_logs;
CREATE TRIGGER tg_bind_acknowledged_by BEFORE INSERT OR UPDATE ON public.project_progress_logs    FOR EACH ROW EXECUTE FUNCTION public.bind_acknowledged_by_from_hive();

-- reviewed_by / assigned_by triggers
DROP TRIGGER IF EXISTS tg_bind_reviewed_by ON public.ai_quality_escalation;
CREATE TRIGGER tg_bind_reviewed_by BEFORE INSERT OR UPDATE ON public.ai_quality_escalation  FOR EACH ROW EXECUTE FUNCTION public.bind_reviewed_by_from_hive();
DROP TRIGGER IF EXISTS tg_bind_assigned_by ON public.project_roles;
CREATE TRIGGER tg_bind_assigned_by BEFORE INSERT OR UPDATE ON public.project_roles          FOR EACH ROW EXECUTE FUNCTION public.bind_assigned_by_from_hive();
