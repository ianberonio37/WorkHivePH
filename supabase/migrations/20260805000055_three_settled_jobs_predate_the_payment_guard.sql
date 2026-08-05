-- THREE SETTLED JOBS CARRY NO PAYMENT ROW — they predate the guard that now forbids it
-- ═══════════════════════════════════════════════════════════════════════════════════════════════
-- Measured 2026-08-05 by tools/verify_money_lifecycle.py :: settlement_requires_a_payment:
--
--   f95d2b11  settled 2026-07-29  agreed base 800.00    no service_payments row
--   e6e26218  settled 2026-07-28  agreed base 4000.00   no service_payments row
--   fbc90892  settled 2026-07-28  agreed base 800.00    no service_payments row
--
-- The guard is working. It was verified in the same run by moving a paymentless job to `settled` and
-- watching the server refuse it ("Record the payment before releasing: a settled job must carry what
-- was actually paid"). A trigger cannot retroactively refuse a write that already happened, so these
-- three are a DATA repair, not a guard hole — and the check now says so in those words rather than
-- reporting a broken rule.
--
-- WHAT THIS DOES NOT CLAIM. Nobody knows what was actually paid on these three; the payment row is
-- the record of that fact and it was never written. So the amount is reconstructed from
-- `service_agreed_base()` — the price both sides agreed — and the row SAYS it was reconstructed, in
-- `variance_reason`, where a person reading the payment will see it. `confirmed_by` stays NULL and
-- `auto_confirmed_at` stays NULL: neither a human nor the sweep confirmed these, and claiming either
-- would be inventing an actor. An honest gap beats a tidy fiction.

do $$
declare
  r record;
  v_base numeric(12,2);
  n int := 0;
begin
  for r in
    select sr.id, sr.hive_id, sr.settled_at
      from public.service_requests sr
     where sr.status = 'settled'
       and not exists (select 1 from public.service_payments p where p.request_id = sr.id)
  loop
    v_base := coalesce(public.service_agreed_base(r.id), 0);
    if v_base <= 0 then
      raise notice 'skipped % — no agreed base to reconstruct from; leaving the gap visible', r.id;
      continue;
    end if;

    -- `method` is CHECK-constrained to cash | gcash | bank | other. 'reconstructed' is not a payment
    -- METHOD, it is a statement about provenance — so the method is the honest 'other' and the
    -- provenance lives in variance_reason, where it belongs and where a reader will actually meet it.
    insert into public.service_payments
      (request_id, hive_id, amount_paid, method, paid_at, variance_reason)
    values (r.id, r.hive_id, v_base, 'other', coalesce(r.settled_at, now()),
            'RECONSTRUCTED by mig 55. This job settled before guard_settle_requires_payment existed, '
            'so no payment was ever recorded. The amount is the agreed base, not an observed receipt; '
            'confirmed_by and auto_confirmed_at are deliberately NULL because neither a person nor '
            'the sweep confirmed it.');
    n := n + 1;
  end loop;
  raise notice 'reconstructed % payment row(s) for jobs that settled before the guard', n;
end $$;
