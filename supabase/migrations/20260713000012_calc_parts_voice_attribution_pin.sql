-- 20260713000012_calc_parts_voice_attribution_pin.sql
--
-- engineering_calcs / parts_records / voice_journal_entries authorship-forgery (LOW-MED) — bug-hunt
-- 2026-07-14, the substrate attribution pre-filter's CLOSURE pass (after migs 010/011). Each exposes a
-- client-writable AUTHORSHIP display name (worker_name = who ran the calc / recorded the parts / spoke
-- the journal entry) with no bind_ trigger and a WITH CHECK that (at most) pins auth_uid but NOT the
-- display name. LIVE-CONFIRMED on voice_journal_entries (attacker stored worker_name='Leandro Marquez').
--
-- DELIBERATELY EXCLUDED after semantic review (pattern != bug):
--  * project_items.owner_name — an ASSIGNMENT field (a PM legitimately assigns a work item to another
--    worker), not authorship. Pinning it would BREAK project assignment. Left unchanged.
--  * hive_audit_log.actor (already server-bound by audit_actor_bind), hive_members/project_roles
--    (founder/supervisor-gated), agent_memory/resume_documents (personal per-user), marketplace_sellers
--    (trg_guard_seller_trust). inventory_transactions.worker_name is handled where the txn is written
--    (the inventory_deduct/inventory_restock RPCs set it server-side) — separate track.
--
-- FIX (mirror bind_pm_asset_submitter): BEFORE INSERT OR UPDATE — INSERT pins the display name (and
-- auth_uid where the column exists) to the caller's hive_members.worker_name; UPDATE preserves the
-- original author (immutable). parts_records has NO auth_uid column (worker_name is its only identity).
-- Service-role/seeder (auth.uid() NULL) bypass = batch trust. RLS unchanged. Idempotent.

BEGIN;

-- 1. engineering_calcs (auth_uid + worker_name) --------------------------------------------------
CREATE OR REPLACE FUNCTION public.bind_engineering_calc_submitter() RETURNS trigger
  LANGUAGE plpgsql SECURITY DEFINER SET search_path TO 'public' AS $fn$
DECLARE v_name text;
BEGIN
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;
  IF TG_OP = 'UPDATE' THEN NEW.auth_uid := OLD.auth_uid; NEW.worker_name := OLD.worker_name; RETURN NEW; END IF;
  NEW.auth_uid := auth.uid();
  IF NEW.hive_id IS NOT NULL THEN
    SELECT worker_name INTO v_name FROM public.hive_members
      WHERE auth_uid = auth.uid() AND hive_id = NEW.hive_id AND status = 'active' LIMIT 1;
    IF v_name IS NOT NULL THEN NEW.worker_name := v_name; END IF;
  END IF;
  RETURN NEW;
END; $fn$;
DROP TRIGGER IF EXISTS trg_bind_submitter_engineering_calc ON public.engineering_calcs;
CREATE TRIGGER trg_bind_submitter_engineering_calc BEFORE INSERT OR UPDATE ON public.engineering_calcs
  FOR EACH ROW EXECUTE FUNCTION public.bind_engineering_calc_submitter();

-- 2. parts_records (worker_name only — NO auth_uid column) ----------------------------------------
CREATE OR REPLACE FUNCTION public.bind_parts_record_submitter() RETURNS trigger
  LANGUAGE plpgsql SECURITY DEFINER SET search_path TO 'public' AS $fn$
DECLARE v_name text;
BEGIN
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;
  IF TG_OP = 'UPDATE' THEN NEW.worker_name := OLD.worker_name; RETURN NEW; END IF;
  IF NEW.hive_id IS NOT NULL THEN
    SELECT worker_name INTO v_name FROM public.hive_members
      WHERE auth_uid = auth.uid() AND hive_id = NEW.hive_id AND status = 'active' LIMIT 1;
    IF v_name IS NOT NULL THEN NEW.worker_name := v_name; END IF;
  END IF;
  RETURN NEW;
END; $fn$;
DROP TRIGGER IF EXISTS trg_bind_submitter_parts_record ON public.parts_records;
CREATE TRIGGER trg_bind_submitter_parts_record BEFORE INSERT OR UPDATE ON public.parts_records
  FOR EACH ROW EXECUTE FUNCTION public.bind_parts_record_submitter();

-- 3. voice_journal_entries (auth_uid + worker_name) ----------------------------------------------
CREATE OR REPLACE FUNCTION public.bind_voice_journal_submitter() RETURNS trigger
  LANGUAGE plpgsql SECURITY DEFINER SET search_path TO 'public' AS $fn$
DECLARE v_name text;
BEGIN
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;
  IF TG_OP = 'UPDATE' THEN NEW.auth_uid := OLD.auth_uid; NEW.worker_name := OLD.worker_name; RETURN NEW; END IF;
  NEW.auth_uid := auth.uid();
  IF NEW.hive_id IS NOT NULL THEN
    SELECT worker_name INTO v_name FROM public.hive_members
      WHERE auth_uid = auth.uid() AND hive_id = NEW.hive_id AND status = 'active' LIMIT 1;
    IF v_name IS NOT NULL THEN NEW.worker_name := v_name; END IF;
  END IF;
  RETURN NEW;
END; $fn$;
DROP TRIGGER IF EXISTS trg_bind_submitter_voice_journal ON public.voice_journal_entries;
CREATE TRIGGER trg_bind_submitter_voice_journal BEFORE INSERT OR UPDATE ON public.voice_journal_entries
  FOR EACH ROW EXECUTE FUNCTION public.bind_voice_journal_submitter();

COMMIT;
