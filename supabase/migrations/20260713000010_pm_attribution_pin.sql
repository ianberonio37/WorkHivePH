-- 20260713000010_pm_attribution_pin.sql
--
-- PM Scheduler attribution-forgery (MED — CMMS integrity / who-registered / who-completed) —
-- bug-hunt 2026-07-14, pm-scheduler.html P3/P5. Surfaced by the Platform Knowledge Substrate
-- (pm_assets/pm_completions table-rls chunks showed NO bind_ trigger + a hive-branch WITH CHECK that
-- gates hive membership but NOT the submitter identity), then LIVE-CONFIRMED (rolled back):
--
--  * pm_assets: `pm_assets_write` (ALL) hive branch CHECK is `hive_id IN member_hives` only — auth_uid
--    and worker_name are UNPINNED. Attacker Bryan Garcia (Baguio member) INSERTed a pm_asset with
--    worker_name='Leandro Marquez' + auth_uid=<Leandro> and it STORED the forged registrant. A member
--    can attribute an asset registration to any other worker (and, since the policy is ALL, re-attribute
--    an existing asset on UPDATE).
--  * pm_completions: `pm_completions_write` CHECK pins auth_uid=auth.uid() (so the AUTH row is honest),
--    but worker_name (the DISPLAYED completer) is unpinned — attacker stored worker_name='Leandro
--    Marquez' on a completion they made. The compliance/history UI shows the forged completer.
--
-- Same attribution-pin class as logbook/projects/asset/community (migs 20260713000003/004/005/007) —
-- the pm_* tables were missed by those sweeps.
--
-- FIX (mirror bind_community_reply_submitter / bind_logbook_submitter):
--  1. bind_pm_asset_submitter      BEFORE INSERT OR UPDATE — on INSERT pin auth_uid + worker_name to the
--     caller; on UPDATE PRESERVE the original registrant (attribution is immutable; a member may still
--     edit asset metadata — location/criticality — but cannot re-attribute who registered it).
--  2. bind_pm_completion_submitter BEFORE INSERT — pin auth_uid + worker_name to the caller.
--
-- Service-role/seeder writes (auth.uid() NULL) keep their values + bypass RLS (batch trust). The RLS
-- policies are UNCHANGED — pinning at the trigger layer is sufficient and preserves the shared-asset
-- edit model (any hive member manages the asset registry, as a CMMS expects). Idempotent throughout.

BEGIN;

-- 1. asset registrant pin (INSERT pins to caller; UPDATE preserves original) --------------------
CREATE OR REPLACE FUNCTION public.bind_pm_asset_submitter() RETURNS trigger
  LANGUAGE plpgsql SECURITY DEFINER SET search_path TO 'public' AS $fn$
DECLARE v_name text;
BEGIN
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;          -- service-role / seeder: trust the batch
  IF TG_OP = 'UPDATE' THEN                                -- attribution is immutable
    NEW.auth_uid    := OLD.auth_uid;
    NEW.worker_name := OLD.worker_name;
    RETURN NEW;
  END IF;
  NEW.auth_uid := auth.uid();                             -- INSERT: pin to caller
  IF NEW.hive_id IS NOT NULL THEN
    SELECT worker_name INTO v_name FROM public.hive_members
      WHERE auth_uid = auth.uid() AND hive_id = NEW.hive_id AND status = 'active' LIMIT 1;
    IF v_name IS NOT NULL THEN NEW.worker_name := v_name; END IF;
  END IF;
  RETURN NEW;
END; $fn$;
DROP TRIGGER IF EXISTS trg_bind_submitter_pm_asset ON public.pm_assets;
CREATE TRIGGER trg_bind_submitter_pm_asset BEFORE INSERT OR UPDATE ON public.pm_assets
  FOR EACH ROW EXECUTE FUNCTION public.bind_pm_asset_submitter();

-- 2. completion completer pin (INSERT) ----------------------------------------------------------
CREATE OR REPLACE FUNCTION public.bind_pm_completion_submitter() RETURNS trigger
  LANGUAGE plpgsql SECURITY DEFINER SET search_path TO 'public' AS $fn$
DECLARE v_name text;
BEGIN
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;
  NEW.auth_uid := auth.uid();
  IF NEW.hive_id IS NOT NULL THEN
    SELECT worker_name INTO v_name FROM public.hive_members
      WHERE auth_uid = auth.uid() AND hive_id = NEW.hive_id AND status = 'active' LIMIT 1;
    IF v_name IS NOT NULL THEN NEW.worker_name := v_name; END IF;
  END IF;
  RETURN NEW;
END; $fn$;
DROP TRIGGER IF EXISTS trg_bind_submitter_pm_completion ON public.pm_completions;
CREATE TRIGGER trg_bind_submitter_pm_completion BEFORE INSERT ON public.pm_completions
  FOR EACH ROW EXECUTE FUNCTION public.bind_pm_completion_submitter();

COMMIT;
