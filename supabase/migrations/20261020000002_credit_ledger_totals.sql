-- SL LB2 (2026-10-20): THE CREDIT POSITION WAS SUMMED FROM A CAPPED READ.
-- platform-actions.html read v_service_credit_ledger_truth with .limit(2000) and summed the amounts in the browser for the
-- liability and cover a founder acts on. Once the ledger passes 2,000 entries the sums silently stop counting the rest,
-- and the read grows with every entry. The totals now come from the database, one row per entry type, with the count of
-- entries whose amount could not be read (the card treats any such total as unknown, never as zero).
-- SECURITY INVOKER over the security-invoker view: the caller's own RLS applies exactly as it did to the row read - a
-- marketplace admin sees the platform's totals, anyone else only their own accounts' (the card already treats a
-- non-admin as a permission boundary through v_credit_posture).
create or replace function public.get_credit_ledger_totals()
returns table (entry_type text, total numeric, entries bigint, unreadable bigint)
language sql
stable
security invoker
set search_path = public
as $$
  select l.entry_type,
         sum(l.amount)                                  as total,
         count(*)                                       as entries,
         count(*) filter (where l.amount is null)       as unreadable
  from public.v_service_credit_ledger_truth l
  group by l.entry_type
$$;

revoke all on function public.get_credit_ledger_totals() from public, anon;
grant execute on function public.get_credit_ledger_totals() to authenticated;

comment on function public.get_credit_ledger_totals() is
  'SL LB2 2026-10-20: the credit ledger summed by entry type for the platform-actions credit position (was a browser sum over a 2,000-row cap).';
