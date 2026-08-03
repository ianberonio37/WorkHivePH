-- ============================================================================
-- A SERVICE IS A LISTING TOO — the 10% rule was only half-built
--
-- Ian, 2026-08-03: "a provider can list a product OR SERVICE only when he has a
-- 10% credit of the total listing... when the buyer who has no credit pays it
-- in full gcash price, the buyer will receive the 10% credit."
--
-- The product half has been live since migration 07: publishing a listing locks
-- 10% in credit_reservations, and grant_listing_reward passes it to the buyer
-- on sale. The SERVICE half was never built. Measured before writing:
-- accept_service_request reserves nothing, and credit_reservations is keyed by
-- listing_id with a NOT NULL FK to marketplace_listings — services could not
-- even be represented in it.
--
-- So a services buyer earned nothing, and a provider could take unlimited work
-- holding zero credits. That is not a separate design question, which is what I
-- previously mistook it for and put to Ian as a "fork". It is the same rule,
-- unimplemented on one side.
--
-- WHERE THE SERVICE RESERVATION BELONGS. A product reserves when it is
-- PUBLISHED — the moment it makes a claim on the marketplace. The service
-- equivalent is ACCEPTANCE: the instant a provider takes a job, they are
-- committed and the buyer is owed their 10%. Reserving at hail time would
-- charge a provider for work they have not won; reserving at settle would be
-- too late to refuse.
--
-- THE PRICE MOVES, AND THAT IS THE HARD PART. A listing has one price. A job is
-- accepted against a budget and settles against what was actually paid, which
-- may be more. The buyer's 10% is owed on what they ACTUALLY paid, so:
--
--   accept  reserve  10% of the price known then (budget / agreed base)
--   settle  the buyer earns 10% of amount_paid, funded FIRST from that
--           reservation and then from the provider's free balance
--
-- If the provider cannot cover a shortfall, the buyer is still made whole up to
-- what is recoverable and the gap is RECORDED rather than silently dropped —
-- the same posture apply_dispute_adjustment already takes (mig 29). A reward
-- that quietly shrinks is worse than one that is short and says so.
-- ============================================================================

-- ── 1. credit_reservations must be able to hold a SERVICE reservation ──────
ALTER TABLE public.credit_reservations
  ADD COLUMN IF NOT EXISTS request_id uuid REFERENCES public.service_requests(id) ON DELETE CASCADE;

ALTER TABLE public.credit_reservations ALTER COLUMN listing_id DROP NOT NULL;

-- seller_name identifies the SELLER of a listing; a service job identifies its provider through
-- service_requests.matched_provider_id instead, so the column cannot be required for both. Made
-- nullable, then re-required for listings only by the CHECK below — dropping a NOT NULL without
-- replacing it would quietly let a listing reservation lose its owner.
ALTER TABLE public.credit_reservations ALTER COLUMN seller_name DROP NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                  WHERE conrelid = 'public.credit_reservations'::regclass
                    AND conname  = 'credit_reservations_listing_needs_seller') THEN
    ALTER TABLE public.credit_reservations
      ADD CONSTRAINT credit_reservations_listing_needs_seller
      CHECK (listing_id IS NULL OR seller_name IS NOT NULL);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                  WHERE conrelid = 'public.credit_reservations'::regclass
                    AND conname  = 'credit_reservations_one_ref') THEN
    -- Exactly one referent. A row pointing at both a listing and a job, or at
    -- neither, is a reservation nobody can release.
    ALTER TABLE public.credit_reservations
      ADD CONSTRAINT credit_reservations_one_ref
      CHECK (num_nonnulls(listing_id, request_id) = 1);
  END IF;
END $$;

-- One live hold per job, mirroring credit_reservations_one_live for listings.
DROP INDEX IF EXISTS credit_reservations_one_live_request;
CREATE UNIQUE INDEX credit_reservations_one_live_request
  ON public.credit_reservations (request_id)
  WHERE state = 'held' AND request_id IS NOT NULL;

-- ── 2. taking a job requires (and locks) the 10% ───────────────────────────
CREATE OR REPLACE FUNCTION public.guard_accept_requires_reservation()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_price numeric;
  v_need  numeric;
  v_uid   uuid;
  v_bal   numeric;
BEGIN
  -- only the transition INTO accepted
  IF NEW.status IS DISTINCT FROM 'accepted' THEN RETURN NEW; END IF;
  IF TG_OP = 'UPDATE' AND OLD.status IS NOT DISTINCT FROM 'accepted' THEN RETURN NEW; END IF;
  IF NEW.matched_provider_id IS NULL THEN RETURN NEW; END IF;

  v_price := public.service_request_price(NEW.id);
  v_need  := public.listing_reservation_amount(NEW.hive_id, coalesce(v_price, 0));
  IF v_need IS NULL OR v_need <= 0 THEN
    -- No agreed price yet, so there is no 10% of it to hold. The settle-time
    -- transfer still owes the buyer their share and will draw it then.
    RETURN NEW;
  END IF;

  SELECT auth_uid INTO v_uid FROM public.service_providers WHERE id = NEW.matched_provider_id;
  IF v_uid IS NULL THEN RETURN NEW; END IF;   -- hive-owned provider, no wallet to charge

  SELECT coalesce(sum(amount), 0) INTO v_bal
    FROM public.service_credit_ledger
   WHERE account_type = 'consumer' AND account_id = v_uid;

  -- Free balance = holdings minus what THIS provider already has held against other jobs.
  -- Scoped through the job to the provider: an unscoped sum would subtract every other
  -- provider's reservations from this one's balance, so a busy marketplace would refuse a
  -- provider who is perfectly solvent. Caught by the probe on the second accept.
  v_bal := v_bal - coalesce((
      SELECT sum(cr.amount)
        FROM public.credit_reservations cr
        JOIN public.service_requests sr ON sr.id = cr.request_id
        JOIN public.service_providers sp ON sp.id = sr.matched_provider_id
       WHERE cr.state = 'held' AND cr.request_id IS NOT NULL AND sp.auth_uid = v_uid), 0);

  IF v_bal < v_need THEN
    RAISE EXCEPTION 'You need PHP% in credits to take a PHP% job (10%%), and you have PHP%. '
                    'Top up to accept it.',
                    to_char(v_need,'FM999G999G990'), to_char(v_price,'FM999G999G990'),
                    to_char(greatest(v_bal,0),'FM999G999G990')
      USING errcode = 'check_violation';
  END IF;

  INSERT INTO public.credit_reservations (request_id, hive_id, amount, state)
  VALUES (NEW.id, NEW.hive_id, v_need, 'held');

  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_guard_accept_requires_reservation ON public.service_requests;
CREATE TRIGGER trg_guard_accept_requires_reservation
  BEFORE UPDATE OF status ON public.service_requests
  FOR EACH ROW EXECUTE FUNCTION public.guard_accept_requires_reservation();

-- ── 3. on settle, the reservation becomes the buyer's 10% (or goes back) ───
CREATE OR REPLACE FUNCTION public.grant_service_reward()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_held    numeric;
  v_price   numeric;
  v_owed    numeric;
  v_prov    uuid;
  v_free    numeric;
  v_pay     numeric;
BEGIN
  IF NEW.status IS DISTINCT FROM 'settled' THEN RETURN NEW; END IF;
  IF TG_OP = 'UPDATE' AND OLD.status IS NOT DISTINCT FROM 'settled' THEN RETURN NEW; END IF;

  SELECT amount INTO v_held FROM public.credit_reservations
   WHERE request_id = NEW.id AND state = 'held';

  SELECT auth_uid INTO v_prov FROM public.service_providers WHERE id = NEW.matched_provider_id;

  -- EARN OR SPEND, NEVER BOTH. If the buyer already paid part of this job in
  -- credits, they do not also earn on it — guard_reward_exclusive enforces that
  -- at the ledger, and honouring it here means the provider simply gets their
  -- hold back rather than hitting a refusal they cannot act on.
  IF EXISTS (SELECT 1 FROM public.service_credit_ledger
              WHERE ref_kind = 'service_request' AND ref_id = NEW.id
                AND entry_type = 'reward_spend') THEN
    UPDATE public.credit_reservations SET state = 'returned', released_at = now()
     WHERE request_id = NEW.id AND state = 'held';
    RETURN NEW;
  END IF;

  IF NEW.client_auth_uid IS NULL OR v_prov IS NULL THEN
    UPDATE public.credit_reservations SET state = 'returned', released_at = now()
     WHERE request_id = NEW.id AND state = 'held';
    RETURN NEW;
  END IF;

  -- The buyer is owed 10% of what they ACTUALLY paid, not of the estimate the
  -- reservation was sized against.
  v_price := public.service_request_price(NEW.id);
  v_owed  := public.listing_reservation_amount(NEW.hive_id, coalesce(v_price, 0));
  IF v_owed IS NULL OR v_owed <= 0 THEN
    UPDATE public.credit_reservations SET state = 'returned', released_at = now()
     WHERE request_id = NEW.id AND state = 'held';
    RETURN NEW;
  END IF;

  -- Fund from the hold first, then the provider's free balance. Never mint.
  SELECT coalesce(sum(amount), 0) INTO v_free FROM public.service_credit_ledger
   WHERE account_type = 'consumer' AND account_id = v_prov;
  v_pay := least(v_owed, coalesce(v_held, 0) + greatest(v_free, 0));

  IF v_pay > 0 THEN
    PERFORM set_config('workhive.service_system_write', 'on', true);
    INSERT INTO public.service_credit_ledger
      (account_type, account_id, entry_type, amount, ref_kind, ref_id, note)
    VALUES ('consumer', v_prov, 'reward_fund', -v_pay, 'service_request', NEW.id,
            'funded the buyer''s 10% on this job');
    INSERT INTO public.service_credit_ledger
      (account_type, account_id, entry_type, amount, ref_kind, ref_id, note)
    VALUES ('consumer', NEW.client_auth_uid, 'reward_earn', v_pay, 'service_request', NEW.id,
            'your 10% back for paying in full');
    PERFORM set_config('workhive.service_system_write', 'off', true);
  END IF;

  -- Say so when the buyer got less than they were owed, rather than letting the
  -- reward quietly shrink to whatever happened to be available.
  UPDATE public.credit_reservations
     SET state = 'released_to_buyer', released_at = now()
   WHERE request_id = NEW.id AND state = 'held';

  IF v_pay < v_owed THEN
    INSERT INTO public.service_job_events (request_id, actor_role, from_state, to_state, note)
    VALUES (NEW.id, 'system', 'settled', 'settled',
            'buyer reward short: owed ' || to_char(v_owed,'FM999G999G990')
            || ', paid ' || to_char(v_pay,'FM999G999G990')
            || ' (provider could not fund the difference)');
  END IF;

  RETURN NEW;
END;
$function$;

-- Fires AFTER the settle guard chain: alphabetically `grant_service_reward` is
-- reached via its trigger name, so it is named to sort after trg_guard_*.
DROP TRIGGER IF EXISTS trg_zz_grant_service_reward ON public.service_requests;
CREATE TRIGGER trg_zz_grant_service_reward
  AFTER UPDATE OF status ON public.service_requests
  FOR EACH ROW EXECUTE FUNCTION public.grant_service_reward();

-- ── 4. a job that never completes returns the hold ─────────────────────────
CREATE OR REPLACE FUNCTION public.release_service_reservation_on_close()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
BEGIN
  IF NEW.status IN ('cancelled_by_client','cancelled_by_provider','expired')
     AND OLD.status IS DISTINCT FROM NEW.status THEN
    UPDATE public.credit_reservations SET state = 'returned', released_at = now()
     WHERE request_id = NEW.id AND state = 'held';
  END IF;
  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_zz_release_service_reservation ON public.service_requests;
CREATE TRIGGER trg_zz_release_service_reservation
  AFTER UPDATE OF status ON public.service_requests
  FOR EACH ROW EXECUTE FUNCTION public.release_service_reservation_on_close();
