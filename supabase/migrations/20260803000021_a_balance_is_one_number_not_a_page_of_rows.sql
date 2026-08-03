-- The confirm sheet read the buyer's ENTIRE ledger to add it up.
--
-- `db.from('service_credit_ledger').select('amount').eq(...)` with no bound: correct on day one, and a
-- growing page of rows over a wallet's lifetime, fetched every time someone opens the confirm sheet just
-- to produce a single number. The unbounded-query gate caught it (baseline 1 -> 2).
--
-- The obvious fix is the wrong one. Adding `.limit(200)` bounds the query and produces a WRONG BALANCE --
-- silently, and only for the heaviest users, which is the worst possible distribution for a money bug.
-- A balance is not a page of rows; it is one number, and it belongs where the rows are.
--
-- This also removes a third derivation of the same rule. The seller's balance already comes from
-- seller_credit_balance() (party-checked, DEFINER, computed in SQL); the buyer's was being re-added in
-- JavaScript. Two implementations of "what do I hold" is exactly the shape that made the spend cap and the
-- confirm sheet disagree earlier today.

create or replace function public.my_credit_balance()
returns numeric
language sql
stable security definer
set search_path to 'pg_catalog', 'public'
as $function$
  -- auth.uid() and nothing else: this function takes no argument precisely so it cannot be pointed at
  -- somebody else's wallet. seller_credit_balance(text) needs an internal party check because it accepts
  -- a name; the safest accessor is the one with nothing to pass.
  select coalesce(sum(amount), 0)::numeric
    from public.service_credit_ledger
   where account_type = 'consumer' and account_id = auth.uid();
$function$;

revoke all on function public.my_credit_balance() from public, anon;
grant execute on function public.my_credit_balance() to authenticated, service_role;

comment on function public.my_credit_balance() is
  'The caller''s own credit balance, as one number. Takes no argument so it cannot be aimed at another '
  'wallet, and replaces a client-side sum over an UNBOUNDED ledger read - where the tempting fix (a LIMIT) '
  'would have produced a quietly wrong balance for exactly the users who hold the most rows.';
