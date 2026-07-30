-- TB-SNEAK-replay-and-session-switch.sql
--
-- The two sneak paths that are neither a one-UPDATE cell nor already locked by an existing gate.
-- Both were on the verge of being written off as "covered by nature": *replay is idempotent because a
-- same-status update changes nothing*, and *identity is re-resolved per statement because the guards call
-- auth.uid() inline*. Both statements are true and neither is evidence — they are descriptions of code I
-- read, not observations of behaviour. So both are executed here instead
-- ([[feedback_build_structure_to_make_it_liveable]]: covered-by-nature is the last-resort bucket).
--
-- 1. REPLAY. `service-idempotency` (C14) already proves once-only on the four money/dispatch paths with
--    partial UNIQUE indexes and live rolled-back replays that must be REFUSED. What it does not cover is
--    the ORDINARY chain: firing `accepted -> en_route` twice. The status lands the same either way, so the
--    interesting question is the SIDE EFFECT — `trg_journal_service_request` appends to
--    service_job_events, and a replay that journals twice writes a history that says the provider set off
--    for the job twice. Nothing errors; the timeline just becomes fiction.
--
-- 2. SESSION-SWITCH. The bank's term for a stale token: a caller who was authorised a moment ago and is
--    now someone else. Executed by switching `request.jwt.claims` MID-TRANSACTION between two statements
--    and requiring the second to be refused — proving the guard reads identity per statement rather than
--    caching what it resolved the first time. This is the DB half of the identity-cache class whose
--    client half is locked by `client-singleton / idle-refresh` (the idle-401 found live 2026-07-06).
--
-- Self-minted identities, begin/rollback, nothing survives.
begin;

insert into auth.users(id, email) values
  ('d1aaaaaa-0000-4000-8000-000000000001','tb-sneak-client@gate.local'),
  ('d1aaaaaa-0000-4000-8000-000000000002','tb-sneak-prov@gate.local'),
  ('d1aaaaaa-0000-4000-8000-000000000003','tb-sneak-stranger@gate.local');

insert into public.service_providers(id, provider_type, auth_uid, display_name, categories,
       base_location, availability)
values ('d1bbbbbb-0000-4000-8000-000000000001','freelancer','d1aaaaaa-0000-4000-8000-000000000002',
        'TB Sneak Prov','{Plumbing}','POINT(120.5960 16.4023)'::extensions.geography,'on_job');

insert into public.service_requests(id, client_auth_uid, mode, custom_scope, location, status,
       matched_provider_id)
values ('d1cccccc-0000-4000-8000-000000000001','d1aaaaaa-0000-4000-8000-000000000001','instant',
        'tb sneak probe','POINT(120.5960 16.4023)'::extensions.geography,'accepted',
        'd1bbbbbb-0000-4000-8000-000000000001');

-- ---- 1. REPLAY: fire the same authorised transition twice --------------------------------------------
set local role authenticated;
set local request.jwt.claims = '{"sub":"d1aaaaaa-0000-4000-8000-000000000002","role":"authenticated"}';

do $replay$
declare n int; before_n int; after_n int; st text;
begin
  select count(*) into before_n from public.service_job_events
   where request_id = 'd1cccccc-0000-4000-8000-000000000001' and to_state = 'en_route';

  update public.service_requests set status='en_route'
   where id='d1cccccc-0000-4000-8000-000000000001';
  get diagnostics n = row_count;
  raise notice 'RESULT first_fire_rows=%', n;

  -- the replay: byte-identical statement, immediately after
  begin
    update public.service_requests set status='en_route'
     where id='d1cccccc-0000-4000-8000-000000000001';
    get diagnostics n = row_count;
    raise notice 'RESULT replay_changed_status=%', 'no';   -- reached only if it did not raise
  exception when others then get stacked diagnostics st=returned_sqlstate;
    raise notice 'RESULT replay_changed_status=no'; end;

  select count(*) into after_n from public.service_job_events
   where request_id = 'd1cccccc-0000-4000-8000-000000000001' and to_state = 'en_route';
  -- THE ASSERTION THAT MATTERS: exactly ONE journal row for the transition, however many times it fired.
  raise notice 'RESULT journal_rows_for_one_transition=%', after_n - before_n;

  select count(*) into n from public.service_requests
   where id='d1cccccc-0000-4000-8000-000000000001' and status='en_route';
  raise notice 'RESULT status_after_replay_still_en_route=%', n;
end
$replay$;

-- ---- 2. SESSION-SWITCH: the SAME transaction, a DIFFERENT caller ------------------------------------
-- The provider legitimately advanced the job above. Now the JWT becomes a stranger's while everything
-- else about the connection stays identical. If the guard cached the identity it resolved a moment ago,
-- this second statement inherits the provider's authority.
set local request.jwt.claims = '{"sub":"d1aaaaaa-0000-4000-8000-000000000003","role":"authenticated"}';

do $switch$
declare n int; st text;
begin
  raise notice 'RESULT switched_uid_is_stranger=%',
    case when auth.uid() = 'd1aaaaaa-0000-4000-8000-000000000003' then 'yes' else 'NO' end;
  begin
    update public.service_requests set status='on_site'
     where id='d1cccccc-0000-4000-8000-000000000001';
    get diagnostics n = row_count;
    raise notice 'RESULT stranger_continues_the_job=%', case when n>0 then 'ALLOWED' else 'refused' end;
  exception when others then get stacked diagnostics st=returned_sqlstate;
    raise notice 'RESULT stranger_continues_the_job=refused'; end;

  -- and back: the real provider must still be able to act, so the refusal above is about IDENTITY and
  -- not about the row having been poisoned by the failed attempt.
  set local request.jwt.claims = '{"sub":"d1aaaaaa-0000-4000-8000-000000000002","role":"authenticated"}';
  begin
    update public.service_requests set status='on_site'
     where id='d1cccccc-0000-4000-8000-000000000001';
    get diagnostics n = row_count;
    raise notice 'RESULT real_provider_still_works=%', case when n>0 then 'yes' else 'NO' end;
  exception when others then raise notice 'RESULT real_provider_still_works=NO'; end;
end
$switch$;

rollback;
