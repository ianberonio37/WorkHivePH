-- ─────────────────────────────────────────────────────────────────────────────
-- SERVICE HAILING P6b: the credit-balance accept gate (D6/D9, Grab-PH precedent).
-- A provider whose ledger balance is NEGATIVE (unpaid commissions) cannot accept
-- new jobs until they top up — the enforcement that makes commission-in-credits
-- COLLECTIBLE. Threshold 0 (not ₱100) for cold-start fairness: a brand-new
-- provider with zero credits can take their first jobs; the debt those jobs mint
-- is what forces the first GCash top-up. Ian tunes the floor in D9.
-- ─────────────────────────────────────────────────────────────────────────────
create or replace function public.provider_credit_balance(p_provider_id uuid)
returns numeric
language sql
stable
security definer
set search_path to 'pg_catalog', 'public'
as $$
  select coalesce(sum(amount), 0)
    from public.service_credit_ledger
   where account_type = 'provider' and account_id = p_provider_id;
$$;
grant execute on function public.provider_credit_balance(uuid) to authenticated;

insert into public.canonical_sources (domain, source_kind, source_name, owner_skill, freshness, contract, description)
values ('service_hailing', 'rpc', 'provider_credit_balance', 'marketplace', 'on_demand',
        '{"signature": "provider_credit_balance(p_provider_id uuid) RETURNS numeric", "side_effects": []}'::jsonb,
        'Ledger balance = SUM(amount); powers the accept gate + the wallet card.')
on conflict do nothing;
