-- ─────────────────────────────────────────────────────────────────────────────
-- SERVICE HAILING P6/P6b: the client CONFIRMS settlement, and settling MINTS the
-- commission — the founder-income mechanic (D6/D9) on the already-proven guards.
--   * guard amendment: completed → settled becomes CLIENT-legal ("I paid the
--     provider") — everything else stays exactly as adversarially proven;
--   * settle mint (AFTER trigger, DEFINER): one commission ledger row per request
--     (unique index = idempotent), amount = selected-offer price, else the catalog
--     rate, else 0; rate 10% consumer / 5% industrial (D9, Ian tunes);
--   * settlement truth = the LEDGER row + the journal — one money-truth, no
--     marketplace_orders mirror (C7 wording updated in the roadmap).
-- ─────────────────────────────────────────────────────────────────────────────
create unique index if not exists service_credit_ledger_one_commission_per_request
  on public.service_credit_ledger (ref_id) where entry_type = 'commission';

create or replace function public.mint_settlement_commission()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
declare
  v_base numeric(12,2);
  v_rate numeric(4,3);
begin
  if new.status <> 'settled' or old.status = 'settled' or new.matched_provider_id is null then
    return new;
  end if;
  select coalesce(
           (select o.price from public.service_offers o
             where o.request_id = new.id and o.status = 'selected' and o.price is not null
             order by o.updated_at desc limit 1),
           (select c.base_rate from public.service_catalog c where c.id = new.catalog_item_id),
           0)
    into v_base;
  v_rate := case when new.segment = 'consumer' then 0.100 else 0.050 end;
  insert into public.service_credit_ledger (account_type, account_id, entry_type, amount, ref_kind, ref_id, note)
  values ('provider', new.matched_provider_id, 'commission',
          round(-(v_base * v_rate), 2), 'request', new.id,
          'Commission ' || (v_rate * 100)::int || '% on ' || to_char(v_base, 'FM999,999,990.00') || ' (settled job)')
  on conflict (ref_id) where entry_type = 'commission' do nothing;
  return new;
exception when unique_violation then
  return new; -- concurrent double-settle race: the first mint stands
end $$;

drop trigger if exists trg_mint_settlement_commission on public.service_requests;
create trigger trg_mint_settlement_commission
  after update of status on public.service_requests
  for each row execute function public.mint_settlement_commission();
