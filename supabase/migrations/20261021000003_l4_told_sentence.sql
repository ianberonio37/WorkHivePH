-- SL L4 - the sentence a person saw when something failed is logged, not only the code (2026-10-21).
--
-- Measured before this change: client_errors held 390 rows and 383 were the uncaught net (an exception nobody caught);
-- 7 were caught failures. A failure a person was TOLD about - "The stock was NOT deducted. Nothing changed", "Only a
-- supervisor of this hive can..." - left no row at all: the pages show the sentence and log nothing, and the one logger
-- (utils.js whLogError) records the error's technical message, never what the person read. And the identity on a row
-- was the device's claim: worker_name whatever localStorage held, hive_id a hive the device remembered.
--
-- 1. client_errors gains `shown` (the sentence the person saw, verbatim, capped) and `code` (the cause's code - a SQLSTATE,
--    an HTTP status, an error name).
-- 2. bind_client_errors_reporter() (BEFORE INSERT) decides who: a visitor no account, hive or name; a member their own
--    account, a hive only while an ACTIVE member of it (so a stale device hive no longer gets the row REFUSED by the
--    membership check - the error is kept, without the hive), and their own name. A direct session or the service role
--    states its own fields. RLS WITH CHECK runs on the row as the trigger left it.
-- 3. A visitor's told failure may be logged: the anon policy admits the 'told-*' contexts beside the two uncaught ones,
--    still with no identity and with bounded text.

alter table public.client_errors
  add column if not exists shown text,
  add column if not exists code text;

do $$ begin
  if not exists (select 1 from pg_constraint where conname = 'client_errors_shown_len') then
    alter table public.client_errors add constraint client_errors_shown_len check (shown is null or char_length(shown) <= 400);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'client_errors_code_len') then
    alter table public.client_errors add constraint client_errors_code_len check (code is null or char_length(code) <= 60);
  end if;
end $$;

create or replace function public.bind_client_errors_reporter()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_uid    uuid := auth.uid();
  v_claims text := current_setting('request.jwt.claims', true);
  v_role   text := case when v_claims is null or v_claims = '' then null
                        else coalesce(v_claims::jsonb ->> 'role', '') end;
begin
  if v_role is null or v_role = 'service_role' then
    return new;
  end if;
  if v_uid is null then
    new.auth_uid := null;
    new.hive_id := null;
    new.worker_name := null;
    return new;
  end if;
  new.auth_uid := v_uid;
  if new.hive_id is not null and not exists (
       select 1 from public.hive_members hm
        where hm.hive_id = new.hive_id and hm.auth_uid = v_uid and hm.status = 'active') then
    new.hive_id := null;
  end if;
  new.worker_name := coalesce(
    (select wp.display_name from public.worker_profiles wp where wp.auth_uid = v_uid limit 1),
    (select hm.worker_name from public.hive_members hm
      where hm.auth_uid = v_uid and hm.hive_id = new.hive_id and hm.status = 'active' limit 1));
  return new;
end
$$;
revoke all on function public.bind_client_errors_reporter() from public, anon, authenticated;

drop trigger if exists trg_bind_client_errors_reporter on public.client_errors;
create trigger trg_bind_client_errors_reporter
  before insert on public.client_errors
  for each row execute function public.bind_client_errors_reporter();

drop policy if exists client_errors_insert_anon on public.client_errors;
create policy client_errors_insert_anon on public.client_errors
  for insert to anon
  with check (
    (select auth.uid()) is null
    and hive_id is null and worker_name is null and auth_uid is null
    and (context = any (array['uncaught-error', 'unhandled-rejection']) or context like 'told-%')
    and char_length(context) <= 40
    and (page is null or char_length(page) <= 300)
    and (user_agent is null or char_length(user_agent) <= 300)
  );

create index if not exists idx_client_errors_told_created
  on public.client_errors (created_at desc) where shown is not null;
