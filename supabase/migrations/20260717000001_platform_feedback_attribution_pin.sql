-- 20260717000001_platform_feedback_attribution_pin.sql
--
-- platform_feedback attribution-forgery (LOW-MED — feedback-log integrity) — surfaced by the
-- FULLSTACK_COMPONENT_LIBRARY Layer D census (D-P3, 2026-07-17): the substrate rules-engine
-- flagged "has auth_uid + a CLIENT-WRITABLE policy that does NOT self-pin auth_uid AND no
-- bind_* trigger". `feedback anon submit` CHECK gates is_public/status/admin fields but NOT
-- the submitter identity — an AUTHENTICATED user can INSERT feedback carrying another user's
-- auth_uid / worker_name (impersonation in the feedback log an admin later reads).
--
-- Anon submission is BY DESIGN (public feedback box) and stays: auth.uid() IS NULL rows pass
-- through untouched. The pin only makes AUTHENTICATED submissions honest.
--
-- Same attribution-pin class as migs 20260713000003/004/005/007/010/011/012 — this table was
-- missed by those sweeps (it is platform-scoped, not hive-scoped, so the hive sweeps skipped it).
-- Mirror of bind_pm_asset_submitter: INSERT pins to caller; UPDATE (admin-only per policy)
-- preserves the original attribution (immutable).

BEGIN;

CREATE OR REPLACE FUNCTION public.bind_platform_feedback_submitter() RETURNS trigger
  LANGUAGE plpgsql SECURITY DEFINER SET search_path TO 'public' AS $fn$
DECLARE v_name text;
BEGIN
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;          -- anon / service-role: by-design pass-through
  IF TG_OP = 'UPDATE' THEN                                -- attribution is immutable (admin edits status/notes)
    NEW.auth_uid    := OLD.auth_uid;
    NEW.worker_name := OLD.worker_name;
    RETURN NEW;
  END IF;
  NEW.auth_uid := auth.uid();                             -- INSERT: pin to the authenticated caller
  IF NEW.hive_id IS NOT NULL THEN
    SELECT worker_name INTO v_name FROM public.hive_members
      WHERE hive_id = NEW.hive_id AND auth_uid = auth.uid() AND status = 'active'
      LIMIT 1;
    IF v_name IS NOT NULL THEN NEW.worker_name := v_name; END IF;
  END IF;
  RETURN NEW;
END;
$fn$;

DROP TRIGGER IF EXISTS trg_bind_platform_feedback_submitter ON public.platform_feedback;
CREATE TRIGGER trg_bind_platform_feedback_submitter
  BEFORE INSERT OR UPDATE ON public.platform_feedback
  FOR EACH ROW EXECUTE FUNCTION public.bind_platform_feedback_submitter();

COMMIT;
