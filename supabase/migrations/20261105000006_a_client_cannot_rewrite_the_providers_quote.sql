-- ★A CLIENT COULD REWRITE THE PROVIDER'S QUOTE (2026-11-05, found reading J6's premise for GJ M9).
--
-- service_offers carried no trigger at all, and its UPDATE policy (service_offers_party_update) lets BOTH parties to a
-- request update an offer: the provider who made it and the client who asked. Nothing said which columns are whose, so a
-- client could PATCH a provider's quote down (price = 1) and then accept it through select_quote - a job agreed at a
-- price the provider never offered. An offer is the provider's statement; the client's only act on it is choosing it.
--
--   price, kind, eta_minutes, message   the provider's, and only while the offer is still 'pending'
--   status                              moved by the platform's own paths (select_quote, accept_service_request - both
--                                       announce workhive.service_system_write) or by its provider withdrawing it
--   request_id, provider_id             never change
-- The service role and the system-write paths are unaffected; a refused change raises 42501 with its sentence.

CREATE OR REPLACE FUNCTION public.guard_service_offer_columns()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public', 'pg_temp'
AS $$
DECLARE
  v_provider boolean;
BEGIN
  IF auth.uid() IS NULL OR coalesce(current_setting('workhive.service_system_write', true), '') = 'on' THEN
    RETURN NEW;
  END IF;

  IF NEW.request_id IS DISTINCT FROM OLD.request_id OR NEW.provider_id IS DISTINCT FROM OLD.provider_id THEN
    RAISE EXCEPTION 'An offer''s request and provider cannot be changed.' USING ERRCODE = '42501';
  END IF;

  v_provider := OLD.provider_id IN (SELECT public.my_service_provider_ids());

  IF NEW.price IS DISTINCT FROM OLD.price OR NEW.kind IS DISTINCT FROM OLD.kind
     OR NEW.eta_minutes IS DISTINCT FROM OLD.eta_minutes OR NEW.message IS DISTINCT FROM OLD.message THEN
    IF NOT v_provider THEN
      RAISE EXCEPTION 'Only the provider who made this offer can change it.' USING ERRCODE = '42501';
    END IF;
    IF OLD.status <> 'pending' THEN
      RAISE EXCEPTION 'This offer can no longer be changed - it has been %.', OLD.status USING ERRCODE = '42501';
    END IF;
  END IF;

  IF NEW.status IS DISTINCT FROM OLD.status
     AND NOT (v_provider AND OLD.status = 'pending' AND NEW.status = 'withdrawn') THEN
    RAISE EXCEPTION 'An offer is chosen by the client choosing a quote, and withdrawn only by the provider who made it.' USING ERRCODE = '42501';
  END IF;

  RETURN NEW;
END $$;

-- a trigger's function: nobody calls it; anon is named because Supabase grants it explicitly (definer-doors Y2)
REVOKE ALL ON FUNCTION public.guard_service_offer_columns() FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS trg_guard_service_offer_columns ON public.service_offers;
CREATE TRIGGER trg_guard_service_offer_columns
  BEFORE UPDATE ON public.service_offers
  FOR EACH ROW EXECUTE FUNCTION public.guard_service_offer_columns();
