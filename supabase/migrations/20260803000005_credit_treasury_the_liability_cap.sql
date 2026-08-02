-- The credit treasury: a hard, structural ceiling on how much the platform can ever owe.
--
-- WorkHive Credits are a fixed supply of 10,000,000, at 1 credit = ₱1. Every credit that enters
-- circulation is a peso of service the platform has promised. Most loyalty programmes issue without a
-- ceiling and discover the size of the hole later — Delta's loyalty liability reached $3.9B, roughly 10%
-- of its total liabilities. A capped supply makes that impossible by construction rather than by policy.
--
-- Treasury credits are AUTHORISED BUT UNISSUED, like authorised-but-unissued shares. They are not a
-- balance the platform owns; they are permission to issue, and the CHECK below is what makes "10 million
-- means 10 million" true rather than aspirational.
--
-- ONE ROW, ENFORCED. A second treasury row would let issuance be counted twice and the cap silently
-- doubled, so a unique index on a constant column pins it to exactly one.

create table if not exists public.credit_treasury (
  id                smallint    primary key default 1,
  authorised_credits numeric(14,2) not null,
  issued_credits     numeric(14,2) not null default 0,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  constraint credit_treasury_singleton      check (id = 1),
  constraint credit_treasury_authorised_pos check (authorised_credits > 0),
  constraint credit_treasury_issued_pos     check (issued_credits >= 0),
  -- THE CAP. Issuance may never exceed what was authorised.
  constraint credit_treasury_within_cap     check (issued_credits <= authorised_credits)
);

insert into public.credit_treasury (id, authorised_credits, issued_credits)
values (1, 10000000, 0)
on conflict (id) do nothing;

alter table public.credit_treasury enable row level security;

-- Readable by anyone signed in: the supply and what remains are PUBLISHED figures — a credit whose
-- issuance nobody can audit is a promise, not an instrument. Writable by nobody through PostgREST;
-- issuance happens only inside the SECURITY DEFINER function below.
drop policy if exists credit_treasury_read on public.credit_treasury;
create policy credit_treasury_read on public.credit_treasury for select using (true);

revoke all on public.credit_treasury from anon, authenticated;
grant select on public.credit_treasury to authenticated, anon;
grant all    on public.credit_treasury to service_role;

-- ── issuance ─────────────────────────────────────────────────────────────────────────────────────────
-- The ONLY way credits are created. Raising past the cap is refused here AND by the CHECK above: the
-- function gives a message a human can act on, the constraint makes the rule true even if some future
-- code path forgets to call the function. Belt and braces, because this is the number that bounds the
-- platform's entire downside.
create or replace function public.issue_credits(p_amount numeric)
returns numeric
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $function$
declare v_left numeric;
begin
  if p_amount is null or p_amount <= 0 then
    raise exception 'Issuance must be a positive amount (got %)', p_amount
      using errcode = 'check_violation';
  end if;

  select authorised_credits - issued_credits into v_left from public.credit_treasury where id = 1 for update;

  if v_left < p_amount then
    raise exception 'Only % credits remain unissued; cannot issue %. The supply is capped at 10,000,000 '
                    'and that ceiling is what guarantees every credit in circulation is honourable.',
                    to_char(v_left, 'FM999G999G990'), to_char(p_amount, 'FM999G999G990')
      using errcode = 'check_violation',
            hint = 'Raising the cap is a deliberate governance decision, not an operational one.';
  end if;

  update public.credit_treasury
     set issued_credits = issued_credits + p_amount, updated_at = now()
   where id = 1;

  return v_left - p_amount;
end $function$;

revoke all on function public.issue_credits(numeric) from public, anon, authenticated;

comment on function public.issue_credits(numeric) is
  'The only path that creates credits. Refuses issuance beyond the authorised supply, with the remaining '
  'headroom named in the message. EXECUTE revoked from clients: issuance is a platform act.';

-- ── retirement ───────────────────────────────────────────────────────────────────────────────────────
-- Credits consumed by the listing holding fee return to the treasury as unissued, rather than becoming
-- platform income. They were never revenue: they were a liability that expired, so the honest accounting
-- is that the promise was withdrawn, not that money was earned.
create or replace function public.retire_credits(p_amount numeric)
returns numeric
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $function$
begin
  if p_amount is null or p_amount <= 0 then
    raise exception 'Retirement must be a positive amount' using errcode = 'check_violation';
  end if;
  update public.credit_treasury
     set issued_credits = greatest(0, issued_credits - p_amount), updated_at = now()
   where id = 1;
  return (select authorised_credits - issued_credits from public.credit_treasury where id = 1);
end $function$;

revoke all on function public.retire_credits(numeric) from public, anon, authenticated;

comment on table public.credit_treasury is
  'Fixed supply of WorkHive Credits at 1 credit = PHP1. authorised_credits is a HARD CAP on lifetime '
  'liability, enforced by a CHECK rather than by policy: issued may never exceed authorised. Treasury '
  'credits are authorised-but-unissued, not a balance the platform owns. Singleton by construction.';
