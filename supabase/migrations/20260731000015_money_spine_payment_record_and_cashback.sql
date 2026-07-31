-- 20260731000015_money_spine_payment_record_and_cashback.sql
--
-- THE MONEY SPINE (M1). Ian, 2026-07-31, chose CONFIRM-TO-RELEASE over custody: the consumer pays the
-- provider directly and the platform RECORDS it, the buyer confirms, and only then does commission net from
-- the provider's prepaid wallet and cashback mint. This upholds D13 ("payments client<->provider stay OUTSIDE
-- the platform, record-only") rather than reversing it - it builds the record layer D13 always implied.
--
-- NO CUSTODY IS INTRODUCED HERE. `service_payments` records a payment that happened between two OTHER
-- parties. The platform never holds the money, which is what keeps the light regulatory posture: holding
-- funds in transit would make the founder an Operator of Payment System under RA 11127, and would cap GMV at
-- the ~PHP100k/month a personal GCash wallet accepts - roughly 4 jobs at the PHP25,000 average job here.
--
-- THREE DEFECTS THIS CLOSES, each found by reading the live catalog rather than assumed:
--
--   1. `mint_service_cashback` WAS NEVER CALLED. It existed, was validated, and had NO trigger and no
--      caller - so the 1% cashback the whole economy is designed around minted for NOBODY. That is the
--      fifth write-only artefact in this feature family; "who READS it" is now a standing question.
--
--   2. SETTLING RECORDED NO PAYMENT. The client released, but nothing captured what was ACTUALLY paid or
--      its reference, so commission was billed off the catalogue/offer price. A job settled at a different
--      real price billed the wrong amount, and a dispute had no artefact to argue about.
--
--   3. THE TWO MINTERS USED DIFFERENT BASES. Commission billed the selected offer price; cashback paid on
--      `r.budget` - the client's stated BUDGET, which is a wish, not a transaction. So a consumer could
--      earn cashback on a number no one ever paid. Both now read the same base, preferring what was paid.
--
-- Idempotency is unchanged and structural: the partial unique indexes
-- `service_credit_ledger_one_commission_per_request` / `..._one_cashback_per_request` already guarantee one
-- entry per request, so a double-tapped Release cannot double-mint even if the trigger fires twice.

-- ---------------------------------------------------------------------------------------------------
-- 1. THE RECORD
-- ---------------------------------------------------------------------------------------------------
create table if not exists public.service_payments (
  id            uuid primary key default gen_random_uuid(),
  request_id    uuid not null references public.service_requests(id) on delete cascade,
  hive_id       uuid,
  amount_paid   numeric(12,2) not null check (amount_paid > 0),
  -- Nullable ON PURPOSE. Cash is how a large share of Philippine service work is actually paid, and
  -- forcing a GCash reference would either exclude those jobs or teach people to type a fake one.
  gcash_ref     text,
  method        text not null default 'cash'
                  check (method in ('cash', 'gcash', 'bank', 'other')),
  confirmed_by  uuid,                        -- the CLIENT's auth uid; who attested the payment
  paid_at       timestamptz not null default now(),
  created_at    timestamptz not null default now(),
  -- A GCash reference, when given, is the same 13-digit artefact the top-up queue already verifies.
  constraint service_payments_gcash_ref_shape
    check (gcash_ref is null or gcash_ref ~ '^[0-9]{13}$')
);

-- ONE payment per request. Without this a second confirmation could restate the price after commission was
-- already billed - the record has to be the thing you cannot quietly redo.
create unique index if not exists service_payments_one_per_request
  on public.service_payments (request_id);

create index if not exists service_payments_hive
  on public.service_payments (hive_id, paid_at desc);

alter table public.service_payments enable row level security;

-- Mirrors service_credit_topups: the party who attested it (and admins) may read; the attester may write.
drop policy if exists service_payments_read on public.service_payments;
create policy service_payments_read on public.service_payments
  for select using (
    confirmed_by = auth.uid()
    or public.is_marketplace_admin()
    or exists (select 1 from public.service_requests r
                where r.id = request_id
                  and (r.client_auth_uid = auth.uid() or r.matched_provider_id = auth.uid()))
  );

drop policy if exists service_payments_intake on public.service_payments;
create policy service_payments_intake on public.service_payments
  for insert with check (
    confirmed_by = auth.uid()
    and exists (select 1 from public.service_requests r
                 where r.id = request_id and r.client_auth_uid = auth.uid())
  );

-- DELIBERATELY NO UPDATE OR DELETE POLICY. This is evidence. A payment record that can be edited after
-- commission has been billed is not evidence, it is a draft - the same reason the ledger is append-only.

comment on table public.service_payments is
  'Record-only attestation that a consumer paid a provider DIRECTLY (D13). The platform never holds these '
  'funds; this row is what commission is billed against and what a dispute argues about. Immutable by '
  'design: no UPDATE/DELETE policy exists.';

-- ---------------------------------------------------------------------------------------------------
-- 2. RELEASE REQUIRES THE RECORD
-- ---------------------------------------------------------------------------------------------------
-- A SEPARATE guard rather than an edit to `guard_service_request_status`. That guard is long, is one of the
-- four mutation-scored guards, and rebuilding it from a partial read is exactly how a working rule was once
-- silently dropped here. A distinct concern gets a distinct trigger.
create or replace function public.guard_settle_requires_payment()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
BEGIN
  IF new.status = 'settled' AND old.status IS DISTINCT FROM 'settled' THEN
    IF NOT EXISTS (SELECT 1 FROM public.service_payments p WHERE p.request_id = new.id) THEN
      RAISE EXCEPTION
        'Record the payment before releasing: a settled job must carry what was actually paid'
        USING ERRCODE = 'check_violation';
    END IF;
  END IF;
  RETURN new;
END
$$;

drop trigger if exists trg_guard_settle_requires_payment on public.service_requests;
create trigger trg_guard_settle_requires_payment
  before update of status on public.service_requests
  for each row execute function public.guard_settle_requires_payment();

-- ---------------------------------------------------------------------------------------------------
-- 3. COMMISSION BILLS WHAT WAS PAID
-- ---------------------------------------------------------------------------------------------------
-- Unchanged from the shipped version except for the FIRST term of the COALESCE chain. The knob resolution,
-- the platform segment defaults, the zero-guard and the negative-amount convention are preserved verbatim.
create or replace function public.mint_settlement_commission()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
DECLARE
  v_base numeric(12,2);
  v_rate numeric(6,4);
  v_knob numeric;
BEGIN
  IF new.status <> 'settled' OR old.status = 'settled' OR new.matched_provider_id IS NULL THEN
    RETURN new;
  END IF;

  SELECT COALESCE(
           -- What was ACTUALLY paid wins over what was quoted or catalogued.
           (SELECT p.amount_paid FROM public.service_payments p WHERE p.request_id = new.id),
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
          'Commission ' || round(v_rate * 100, 2) || '% on a settled service request')
  -- ADDED, and it is a real defect fix rather than tidying. The unique index made a second commission
  -- IMPOSSIBLE, but with no conflict clause the second attempt surfaced as a raw 23505 that ABORTED the
  -- whole status update - so a job re-opened and re-closed could not be released at all, and a
  -- double-tapped Release returned a database error instead of doing nothing. Cashback already had this
  -- clause; the two minters sat on the same index and disagreed about what a repeat means. Once-only is
  -- still enforced by the index - this only decides whether the repeat is a no-op or an exception.
  ON CONFLICT DO NOTHING;

  RETURN new;
END
$$;

-- ---------------------------------------------------------------------------------------------------
-- 4. CASHBACK: SAME BASE, AND ACTUALLY WIRED
-- ---------------------------------------------------------------------------------------------------
create or replace function public.mint_service_cashback(p_request_id uuid)
returns numeric
language plpgsql
security definer
set search_path = public, pg_temp
as $$
DECLARE
  r        public.service_requests%rowtype;
  v_pct    numeric;
  v_base   numeric;
  v_amount numeric;
BEGIN
  SELECT * INTO r FROM public.service_requests WHERE id = p_request_id;
  IF r.id IS NULL OR r.status <> 'settled' OR r.client_auth_uid IS NULL THEN
    RETURN 0;                       -- unknown, unsettled, or no consumer to credit
  END IF;

  v_pct := public.service_knob_pct(r.hive_id, 'cashback_pct');
  IF v_pct IS NULL OR v_pct <= 0 THEN
    RETURN 0;                       -- the hive has cashback switched off
  END IF;

  -- SAME base as commission. This previously paid on `r.budget` - the client's stated budget, which is a
  -- wish rather than a transaction - so a consumer could earn cashback on a number nobody ever paid, and
  -- the platform's "net take = commission - cashback" identity did not actually hold on any job where the
  -- budget and the price differed.
  SELECT COALESCE(
           (SELECT p.amount_paid FROM public.service_payments p WHERE p.request_id = r.id),
           (SELECT o.price FROM public.service_offers o
             WHERE o.request_id = r.id AND o.status = 'selected' AND o.price IS NOT NULL
             ORDER BY o.updated_at DESC LIMIT 1),
           (SELECT c.base_rate FROM public.service_catalog c WHERE c.id = r.catalog_item_id),
           r.budget, 0)
    INTO v_base;

  v_amount := round(coalesce(v_base, 0) * v_pct / 100.0, 2);
  IF v_amount <= 0 THEN
    RETURN 0;                       -- a zero-value job earns nothing; do not mint dust rows
  END IF;

  INSERT INTO public.service_credit_ledger
    (account_type, account_id, entry_type, amount, ref_kind, ref_id, note)
  VALUES ('consumer', r.client_auth_uid, 'cashback', v_amount, 'service_request', r.id,
          v_pct || '% cashback on a settled service request')
  ON CONFLICT DO NOTHING;           -- backed by service_credit_ledger_one_cashback_per_request

  RETURN v_amount;
END
$$;

-- THE WIRE. `mint_service_cashback` is an RPC (takes an id, returns the amount), so it cannot be attached
-- as a trigger directly - which is very likely why it was never attached at all. This is the adapter.
create or replace function public.trg_fn_mint_service_cashback()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
BEGIN
  IF new.status = 'settled' AND old.status IS DISTINCT FROM 'settled' THEN
    PERFORM public.mint_service_cashback(new.id);
  END IF;
  RETURN new;
END
$$;

drop trigger if exists trg_mint_service_cashback on public.service_requests;
create trigger trg_mint_service_cashback
  after update of status on public.service_requests
  for each row execute function public.trg_fn_mint_service_cashback();

-- The minter is SECURITY DEFINER and mints money: it must not be callable by a random session. Only the
-- trigger path (and the founder) may reach it.
revoke all on function public.mint_service_cashback(uuid) from public, anon, authenticated;
