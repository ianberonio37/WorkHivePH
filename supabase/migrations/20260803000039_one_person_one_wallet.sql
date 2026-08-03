-- ============================================================================
-- ONE PERSON, ONE WALLET — the money was entering a wallet nothing could spend
--
-- Found while refining the payment flow with Ian (2026-08-03). The credit
-- ledger has TWO account namespaces for the same human being:
--
--   ('provider',  service_providers.id)   <- where every TOP-UP lands
--   ('consumer',  auth.uid())             <- what LISTING, ACCEPTING and every
--                                            reward leg actually read
--
-- Measured before writing: provider-namespace total PHP1,140.00, consumer
-- namespace PHP0.00, and the two namespaces share ZERO ids. So every peso that
-- has ever entered WorkHive sits somewhere the spending machinery cannot see.
-- A provider tops up PHP500 and is still refused a listing, still refused a
-- job, and their wallet card shows a different number from their listing form —
-- both correct, about different wallets.
--
-- It is also why my own migration 37 looked green: its probe seeded
-- ('consumer', auth_uid), the namespace the new guard reads, instead of the
-- ('provider', id) namespace a real top-up credits. The test asserted a state
-- the product does not produce.
--
-- ── THE FIX, AND WHY IT DOES NOT MOVE ANY MONEY ────────────────────────────
-- The ledger is APPEND-ONLY. Rewriting 1,140 pesos of history into a different
-- namespace would be the exact lie the dispute path exists to avoid, so nothing
-- below updates or deletes a single ledger row.
--
-- Instead the READER changes. A person's credits are the sum of both places
-- they can legitimately be:
--
--   person_credit_balance(uid) = SUM('consumer', uid)
--                              + SUM('provider', p.id) for every provider p
--                                that this person OWNS (p.auth_uid = uid)
--
-- No double counting: each provider row belongs to exactly one person, and a
-- HIVE-owned provider (auth_uid IS NULL) belongs to no person at all — its
-- wallet stays its own, which is correct, because those credits are the hive's
-- and not any individual's to spend.
--
-- Going forward the mint also credits the PERSON where there is one, so the
-- split stops widening. Both halves are read, so nothing already banked is
-- stranded and nothing has to be migrated.
-- ============================================================================

CREATE OR REPLACE FUNCTION public.person_credit_balance(p_uid uuid)
 RETURNS numeric
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
  SELECT coalesce((
    -- what the person holds directly
    SELECT coalesce(sum(l.amount), 0) FROM public.service_credit_ledger l
     WHERE l.account_type = 'consumer' AND l.account_id = p_uid
  ), 0) + coalesce((
    -- plus every provider profile they OWN. Hive-owned providers (auth_uid
    -- null) are deliberately absent: those credits are the hive's.
    SELECT coalesce(sum(l.amount), 0)
      FROM public.service_credit_ledger l
      JOIN public.service_providers sp ON sp.id = l.account_id
     WHERE l.account_type = 'provider' AND sp.auth_uid = p_uid
  ), 0);
$function$;

REVOKE ALL ON FUNCTION public.person_credit_balance(uuid) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.person_credit_balance(uuid) TO authenticated;

COMMENT ON FUNCTION public.person_credit_balance(uuid) IS
  'The canonical answer to "how many credits does this human have". Sums the '
  'consumer namespace (auth_uid) and every provider profile they own. Use this, '
  'not a raw ledger sum: reading one namespace was how PHP1,140 of top-ups became '
  'invisible to the listing and acceptance guards (mig 39).';

-- ── the acceptance guard must read the same wallet the top-up funds ────────
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
  IF NEW.status IS DISTINCT FROM 'accepted' THEN RETURN NEW; END IF;
  IF TG_OP = 'UPDATE' AND OLD.status IS NOT DISTINCT FROM 'accepted' THEN RETURN NEW; END IF;
  IF NEW.matched_provider_id IS NULL THEN RETURN NEW; END IF;

  v_price := public.service_request_price(NEW.id);
  v_need  := public.listing_reservation_amount(NEW.hive_id, coalesce(v_price, 0));
  IF v_need IS NULL OR v_need <= 0 THEN RETURN NEW; END IF;

  SELECT auth_uid INTO v_uid FROM public.service_providers WHERE id = NEW.matched_provider_id;
  IF v_uid IS NULL THEN RETURN NEW; END IF;   -- hive-owned provider, no person to charge

  -- BOTH namespaces (mig 39). Reading only 'consumer' meant a provider who had
  -- topped up was still refused, because top-ups land under 'provider'.
  v_bal := public.person_credit_balance(v_uid);

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

-- ── the seller's listing balance, same correction ──────────────────────────
CREATE OR REPLACE FUNCTION public.seller_credit_balance(p_seller text)
 RETURNS TABLE(available numeric, reserved numeric, total numeric)
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
begin
  return query
  with me as (
    select ms.auth_uid from public.marketplace_sellers ms where ms.worker_name = p_seller limit 1
  ), led as (
    -- BOTH namespaces (mig 39). This read 'consumer' alone, so a seller who had
    -- topped up as a PROVIDER saw PHP0 available and could not publish anything.
    select coalesce(public.person_credit_balance((select auth_uid from me)), 0) as bal
  ), res as (
    select coalesce(sum(cr.amount), 0) as held
      from public.credit_reservations cr
     where cr.seller_name = p_seller and cr.state = 'held'
  )
  select (led.bal - res.held)::numeric, res.held::numeric, led.bal::numeric from led, res;
end $function$;

-- ── and the provider card, so every surface agrees ─────────────────────────
CREATE OR REPLACE FUNCTION public.provider_credit_balance(p_provider_id uuid)
 RETURNS numeric
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
  -- A person-owned provider shows the PERSON's balance, because that is what
  -- they can actually spend; a hive-owned provider shows its own, because those
  -- credits belong to the hive. Two cards for one human showing different
  -- numbers is how this defect stayed invisible on screen.
  SELECT CASE
    WHEN sp.auth_uid IS NOT NULL THEN public.person_credit_balance(sp.auth_uid)
    ELSE coalesce((SELECT sum(l.amount) FROM public.service_credit_ledger l
                    WHERE l.account_type = 'provider' AND l.account_id = p_provider_id), 0)
  END
  FROM public.service_providers sp WHERE sp.id = p_provider_id;
$function$;
