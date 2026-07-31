-- 20260731000012_consumer_cashback.sql
--
-- CONSUMER CASHBACK (MARKETPLACE_CREDIT_ECONOMY.md §7.2). Ian: a consumer who avails a service gets 1% back
-- as credits. This is model-agnostic — the cashback mints on VERIFIED COMPLETION whether the platform's 5%
-- is charged at listing or at completion — so it is buildable without pre-empting that decision.
--
-- WHY IT IS A LEDGER ENTRY AND NOT A BALANCE COLUMN: cashback is a LIABILITY the moment it is minted. This
-- platform has been bitten by trust numbers standing on nothing (a rating with no producer, a tier with no
-- source), and money is the least forgiving place to repeat it. Every credit a consumer holds must trace to
-- a row that says where it came from.
--
-- ONLY ON VERIFIED COMPLETION. 'settled' is the state where the CLIENT has confirmed they paid — the same
-- event guard_service_request_status reserves for the client and mig 47 mints the commission on. Minting on
-- creation or acceptance would let a self-dealt request print credits, which is the exact shape the
-- marketplace trust guards already refuse.
--
-- IDEMPOTENCY IS STRUCTURAL, NOT PROCEDURAL. A partial unique index means a second call cannot double-mint
-- even under a race or a retry — PH mobile networks retry constantly, and this platform already learned that
-- an index enforces once-only where a code path only hopes to. The function is therefore safe to call from a
-- trigger, a sweep, or a manual repair.

ALTER TABLE public.service_credit_ledger
  DROP CONSTRAINT IF EXISTS service_credit_ledger_entry_type_check;
ALTER TABLE public.service_credit_ledger
  ADD CONSTRAINT service_credit_ledger_entry_type_check
  CHECK (entry_type = ANY (ARRAY['topup','commission','voucher_grant','voucher_reimburse','adjustment','cashback']));

-- One cashback per request, enforced by the DATABASE.
CREATE UNIQUE INDEX IF NOT EXISTS service_credit_ledger_one_cashback_per_request
  ON public.service_credit_ledger (ref_id)
  WHERE entry_type = 'cashback';

CREATE OR REPLACE FUNCTION public.mint_service_cashback(p_request_id uuid)
RETURNS numeric
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $fn$
DECLARE
  r        public.service_requests%rowtype;
  v_pct    numeric;
  v_amount numeric;
BEGIN
  SELECT * INTO r FROM public.service_requests WHERE id = p_request_id;
  IF r.id IS NULL THEN
    RETURN 0;                       -- nothing to reward
  END IF;

  -- VERIFIED completion only. Anything earlier is a promise, not a payment.
  IF r.status <> 'settled' THEN
    RETURN 0;
  END IF;

  IF r.client_auth_uid IS NULL THEN
    RETURN 0;                       -- no consumer account to credit
  END IF;

  v_pct := public.service_knob(r.hive_id, 'cashback_pct');
  IF v_pct IS NULL OR v_pct <= 0 THEN
    RETURN 0;                       -- the hive has cashback switched off
  END IF;

  v_amount := round(coalesce(r.budget, 0) * v_pct / 100.0, 2);
  IF v_amount <= 0 THEN
    RETURN 0;                       -- a zero-value job earns nothing; do not mint dust rows
  END IF;

  -- ON CONFLICT DO NOTHING against the partial unique index: a retry is a no-op rather than a second mint.
  INSERT INTO public.service_credit_ledger
    (account_type, account_id, entry_type, amount, ref_kind, ref_id, note)
  VALUES ('consumer', r.client_auth_uid, 'cashback', v_amount, 'service_request', r.id,
          v_pct || '% cashback on a settled service request')
  ON CONFLICT DO NOTHING;

  RETURN v_amount;
END
$fn$;

COMMENT ON FUNCTION public.mint_service_cashback(uuid) IS
  'Mints the consumer cashback for a SETTLED service request as a service_credit_ledger entry (a liability '
  'with provenance, never a balance column). Rate comes from the hive D9 knob cashback_pct. Idempotent by a '
  'partial unique index, so a retry or race cannot double-mint. Returns the amount, or 0 when the request is '
  'not settled, has no consumer, or the hive has cashback off.';

REVOKE ALL ON FUNCTION public.mint_service_cashback(uuid) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.mint_service_cashback(uuid) TO service_role;
