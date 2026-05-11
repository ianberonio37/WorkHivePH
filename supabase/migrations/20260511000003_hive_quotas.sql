-- Per-Hive Resource Quota -- closes PRODUCTION_FIXES #56
--
-- One row per hive. NULL caps mean "no limit". Caps are tracked but
-- not yet enforced -- the trigger fns log over-quota writes to
-- automation_log for now so we can observe usage before turning
-- them into hard blocks. Flip enforce_blocking to true on a per-hive
-- basis when ready (paid-tier customers, abuse mitigation, etc.).

CREATE TABLE IF NOT EXISTS public.hive_quotas (
  hive_id              uuid PRIMARY KEY REFERENCES public.hives(id) ON DELETE CASCADE,
  max_rows_logbook     integer,
  max_rows_inv_tx      integer,
  max_rows_pm_comp     integer,
  max_rows_community   integer,
  max_rows_ai_reports  integer,
  max_storage_mb       integer,
  enforce_blocking     boolean NOT NULL DEFAULT false,
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now()
);

GRANT SELECT, INSERT, UPDATE, DELETE ON public.hive_quotas TO anon, authenticated;

ALTER TABLE public.hive_quotas ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS hive_quotas_read  ON public.hive_quotas;
DROP POLICY IF EXISTS hive_quotas_write ON public.hive_quotas;

-- Members of the hive can read their quota (visibility into limits).
CREATE POLICY hive_quotas_read ON public.hive_quotas
  FOR SELECT USING (
    auth.uid() IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = hive_quotas.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.status = 'active'
    )
  );

-- Writes go through service role only (admin / billing layer).
CREATE POLICY hive_quotas_write ON public.hive_quotas
  FOR ALL USING (false) WITH CHECK (false);


-- Quota enforcement function. SECURITY DEFINER + search_path lockdown
-- (per PRODUCTION_FIXES #50). Returns NEW unchanged when under quota
-- or when no quota row exists; logs to automation_log if over quota.
-- Only blocks the insert when enforce_blocking = true.

CREATE OR REPLACE FUNCTION public.check_hive_quota_logbook()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  q_max      integer;
  q_enforce  boolean;
  current_n  integer;
BEGIN
  SELECT max_rows_logbook, enforce_blocking
    INTO q_max, q_enforce
    FROM public.hive_quotas
    WHERE hive_id = NEW.hive_id;

  IF q_max IS NULL OR NEW.hive_id IS NULL THEN
    RETURN NEW;     -- no quota row OR no cap = pass
  END IF;

  SELECT COUNT(*) INTO current_n
    FROM public.logbook
    WHERE hive_id = NEW.hive_id;

  IF current_n >= q_max THEN
    INSERT INTO public.automation_log (job_name, status, detail, triggered_at)
    VALUES (
      'hive_quota_logbook_over',
      'warn',
      format('hive %s logbook count %s >= cap %s', NEW.hive_id, current_n, q_max),
      now()
    );
    IF q_enforce THEN
      RAISE EXCEPTION 'logbook quota exceeded for hive %', NEW.hive_id
        USING HINT = 'Contact your hive supervisor to increase the cap.';
    END IF;
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_hive_quota_logbook ON public.logbook;
CREATE TRIGGER trg_hive_quota_logbook
  BEFORE INSERT ON public.logbook
  FOR EACH ROW EXECUTE FUNCTION public.check_hive_quota_logbook();


-- Same pattern for inventory_transactions
CREATE OR REPLACE FUNCTION public.check_hive_quota_inv_tx()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  q_max      integer;
  q_enforce  boolean;
  current_n  integer;
BEGIN
  SELECT max_rows_inv_tx, enforce_blocking
    INTO q_max, q_enforce
    FROM public.hive_quotas
    WHERE hive_id = NEW.hive_id;

  IF q_max IS NULL OR NEW.hive_id IS NULL THEN
    RETURN NEW;
  END IF;

  SELECT COUNT(*) INTO current_n
    FROM public.inventory_transactions
    WHERE hive_id = NEW.hive_id;

  IF current_n >= q_max THEN
    INSERT INTO public.automation_log (job_name, status, detail, triggered_at)
    VALUES ('hive_quota_inv_tx_over', 'warn',
            format('hive %s inv_tx count %s >= cap %s', NEW.hive_id, current_n, q_max), now());
    IF q_enforce THEN
      RAISE EXCEPTION 'inventory_transactions quota exceeded for hive %', NEW.hive_id;
    END IF;
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_hive_quota_inv_tx ON public.inventory_transactions;
CREATE TRIGGER trg_hive_quota_inv_tx
  BEFORE INSERT ON public.inventory_transactions
  FOR EACH ROW EXECUTE FUNCTION public.check_hive_quota_inv_tx();
