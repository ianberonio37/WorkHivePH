-- Arc I · I7/A — server-side brute-force lockout for the login path (Ian's pick: edge login-proxy).
--
-- ★ WHY THIS, NOT A CLIENT CHECK: a client-side "lock after N tries" is security theater — an attacker
-- ignores index.html and POSTs /auth/v1/token directly with the public anon key. Real brute-force
-- protection must be SERVER-SIDE. The `login` edge function is the single front door all sign-ins route
-- through; it calls these RPCs (as the service role) to gate by a real failed-attempt counter, then forwards
-- to GoTrue. Local GoTrue has no password-attempt limiter (proven: 12 bad logins -> all 400, no 429), so this
-- closes the gap locally AND in prod (prod ALSO gets Supabase's hosted GoTrue/Cloudflare limits = defense in depth).
--
-- ENUMERATION-SAFE: attempts are recorded for ANY identifier (existing or not) and the lockout response is
-- generic, so an attacker cannot distinguish "valid user, locked" from "unknown user". The counter keys on
-- (identifier, ip) so one user's lockout never locks out a whole shared NAT/office IP's other users, and a
-- single attacker IP hammering many usernames still trips per-(id,ip).
--
-- All three RPCs: SECURITY DEFINER (write a table the client can't), SET search_path (CVE-2018-1058 class),
-- and GRANTed to service_role ONLY (the edge fn calls them; no client can reach them). Idempotent.

create table if not exists public.login_attempts (
  identifier    text        not null,
  ip            text        not null default '',
  fail_count    integer     not null default 0,
  window_start  timestamptz not null default now(),
  locked_until  timestamptz,
  updated_at    timestamptz not null default now(),
  primary key (identifier, ip)
);
alter table public.login_attempts enable row level security;  -- no policies = service_role-only (BYPASSRLS); clients see nothing
revoke all on public.login_attempts from anon, authenticated;

-- thresholds are env-overridable in the edge fn; the DB carries sane defaults via the args.
create or replace function public.check_login_lockout(p_identifier text, p_ip text default '')
returns table(locked boolean, locked_until timestamptz, retry_after_seconds integer)
language plpgsql security definer set search_path = public, pg_temp as $$
declare r public.login_attempts%rowtype;
begin
  select * into r from public.login_attempts where identifier = lower(p_identifier) and ip = coalesce(p_ip,'');
  if found and r.locked_until is not null and r.locked_until > now() then
    return query select true, r.locked_until, ceil(extract(epoch from (r.locked_until - now())))::integer;
  else
    return query select false, null::timestamptz, 0;
  end if;
end $$;

create or replace function public.record_login_failure(p_identifier text, p_ip text default '',
                                                       p_max_attempts integer default 5,
                                                       p_window_minutes integer default 15,
                                                       p_lockout_minutes integer default 15)
returns table(fail_count integer, locked boolean, locked_until timestamptz)
language plpgsql security definer set search_path = public, pg_temp as $$
declare r public.login_attempts%rowtype; v_count integer; v_lock timestamptz;
begin
  insert into public.login_attempts(identifier, ip, fail_count, window_start, updated_at)
    values (lower(p_identifier), coalesce(p_ip,''), 1, now(), now())
  on conflict (identifier, ip) do update set
    -- reset the window if it has elapsed, else increment
    fail_count   = case when public.login_attempts.window_start < now() - make_interval(mins => p_window_minutes)
                        then 1 else public.login_attempts.fail_count + 1 end,
    window_start = case when public.login_attempts.window_start < now() - make_interval(mins => p_window_minutes)
                        then now() else public.login_attempts.window_start end,
    updated_at   = now()
  returning * into r;
  v_count := r.fail_count;
  if v_count >= p_max_attempts then
    v_lock := now() + make_interval(mins => p_lockout_minutes);
    update public.login_attempts set locked_until = v_lock, updated_at = now()
      where identifier = lower(p_identifier) and ip = coalesce(p_ip,'');
    return query select v_count, true, v_lock;
  else
    return query select v_count, false, null::timestamptz;
  end if;
end $$;

create or replace function public.clear_login_attempts(p_identifier text, p_ip text default '')
returns void language plpgsql security definer set search_path = public, pg_temp as $$
begin
  delete from public.login_attempts where identifier = lower(p_identifier) and ip = coalesce(p_ip,'');
end $$;

revoke all on function public.check_login_lockout(text, text)             from public, anon, authenticated;
revoke all on function public.record_login_failure(text, text, integer, integer, integer) from public, anon, authenticated;
revoke all on function public.clear_login_attempts(text, text)            from public, anon, authenticated;
grant execute on function public.check_login_lockout(text, text)             to service_role;
grant execute on function public.record_login_failure(text, text, integer, integer, integer) to service_role;
grant execute on function public.clear_login_attempts(text, text)            to service_role;
