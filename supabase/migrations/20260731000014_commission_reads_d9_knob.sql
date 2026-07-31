-- 20260731000014_commission_reads_d9_knob.sql
--
-- I BUILT A DUPLICATE AND THEN DELETED IT. Ian decided 5% on completion, so I wrote a
-- `mint_service_commission` — without checking whether the platform already had one. It does:
-- `mint_settlement_commission`, fired by `trg_mint_settlement_commission` on the settled transition, since
-- the service-hailing arc. My version would have written a SECOND commission row per job (different ref_kind,
-- so the unique index would not even have caught it) — a double charge on every completed job, shipped in the
-- name of implementing a decision that was already implemented.
--
-- That is the retrieve-first rule I have applied all session and skipped exactly once. The correct unit was
-- never "write a minter"; it was "teach the EXISTING minter the knob".
--
-- WHAT THE EXISTING ONE ALREADY GETS RIGHT, and which a rewrite would have risked losing:
--   * base price resolves from the SELECTED OFFER first, falling back to the catalog rate — the negotiated
--     price, not the list price
--   * it is idempotent by construction: `old.status = 'settled'` short-circuits a re-settle
--   * it debits the PROVIDER PROFILE (matched_provider_id), which is the account the wallet is keyed on
--   * a NEGATIVE amount, so a balance is SUM(amount) with no per-type sign convention
--
-- THE ONLY DEFECT: the rate was hardcoded `case when segment='consumer' then 0.100 else 0.050 end`, so the
-- D9 commission_pct knob Ian's decision configures was read by NOTHING. That is the fourth unread-knob of
-- this feature, and the reason the integrity gate now enumerates every family.
--
-- THE SEGMENT DEFAULT IS PRESERVED. consumer 10% / industrial 5% remains the platform default; the knob
-- OVERRIDES it only where a hive has actually set one. A hive with no settings row behaves exactly as before,
-- so this migration changes no existing behaviour by itself.

CREATE OR REPLACE FUNCTION public.mint_settlement_commission()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $fn$
DECLARE
  v_base numeric(12,2);
  v_rate numeric(6,4);
  v_knob numeric;
BEGIN
  IF new.status <> 'settled' OR old.status = 'settled' OR new.matched_provider_id IS NULL THEN
    RETURN new;
  END IF;

  SELECT COALESCE(
           (SELECT o.price FROM public.service_offers o
             WHERE o.request_id = new.id AND o.status = 'selected' AND o.price IS NOT NULL
             ORDER BY o.updated_at DESC LIMIT 1),
           (SELECT c.base_rate FROM public.service_catalog c WHERE c.id = new.catalog_item_id),
           0)
    INTO v_base;

  -- The hive's D9 knob wins where one is set; otherwise the platform segment default is unchanged.
  v_knob := public.service_knob_pct(new.hive_id, 'commission_pct');
  v_rate := CASE
              WHEN new.hive_id IS NOT NULL
               AND EXISTS (SELECT 1 FROM public.hive_service_settings s WHERE s.hive_id = new.hive_id)
              THEN v_knob / 100.0
              WHEN new.segment = 'consumer' THEN 0.100
              ELSE 0.050
            END;

  IF v_rate <= 0 OR v_base <= 0 THEN
    RETURN new;                     -- nothing to charge; do not mint a zero row
  END IF;

  INSERT INTO public.service_credit_ledger
    (account_type, account_id, entry_type, amount, ref_kind, ref_id, note)
  VALUES ('provider', new.matched_provider_id, 'commission',
          round(-(v_base * v_rate), 2), 'request', new.id,
          'Commission ' || round(v_rate * 100, 2) || '% on a settled service request');

  RETURN new;
END
$fn$;

COMMENT ON FUNCTION public.mint_settlement_commission() IS
  'Debits the platform commission on the settled transition. Base price is the SELECTED OFFER, falling back '
  'to the catalog rate. The rate is the hive D9 knob commission_pct where a settings row exists, otherwise '
  'the platform segment default (consumer 10%, industrial 5%) - so a hive that has not tuned anything is '
  'unaffected. Idempotent via the old.status guard.';
