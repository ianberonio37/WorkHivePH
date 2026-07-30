-- TB-FIELD-nonstatus-edits-and-hive-party.sql
--
-- THE SECOND HALF OF THE SAME BLIND SPOT. The bank derives its cells from the authorised-TRANSITION set, so
-- every cell changes `status`. `guard_service_request_status` also enforces three rules that have nothing to
-- do with status, and the mutation score found all three unasserted across 107 cells:
--
--     SURVIVED reassignment_allowed        matching may be reassigned by a direct write, not the accept RPC
--     SURVIVED ownership_transfer_allowed  a request's OWNERSHIP may be moved to another account
--     SURVIVED stranger_field_edit_allowed a stranger may edit a request's fields if status is untouched
--     SURVIVED hive_provider_branch_removed a HIVE provider's members stop counting as a party
--
-- These are the rules that hold when `new.status IS NOT DISTINCT FROM old.status` — the branch a
-- transition-shaped test suite can never enter, because entering it means NOT changing status. A suite
-- organised around one axis is blind along every other, and no amount of adding cells on that axis fixes it.
--
-- THE HIVE ONE IS THE SHARPEST, AND IT IS A SELF-DEAL HOLE, NOT A FIELD RULE. `v_is_party` is computed from
-- two things: the caller owning the provider outright (`sp.auth_uid = auth.uid()`) OR the provider being a
-- HIVE profile the caller is an active member of. TB-I2 covers the first. Nothing covered the second — so if
-- the hive branch were dropped, an admin who is a party only THROUGH hive membership would compute as a
-- non-party, take the admin bypass, and drive transitions on a job their own hive is performing. That is the
-- exact hole mig 20260730000003 closed, reachable by a second route that had no test.
--
-- It is also why the mutation operator is worth reading carefully: it rewrites the FIRST occurrence of the
-- hive branch, which is the one inside `v_is_party` (used ONLY by the admin bypass), not the copy inside
-- `v_is_matched_provider` further down. So the mutant is invisible to every non-admin caller, and the only
-- cell that can kill it is one where an ADMIN is a party via hive membership. Asserting a mutant is
-- "untested" is easy; working out which caller can even observe it is the actual work.
--
-- WHAT IS ASSERTED AS MASKED, WITH EVIDENCE. `service_requests_party_update` is
-- `USING (client_auth_uid = auth.uid() OR matched_provider_id IN my_service_provider_ids())` with no admin
-- clause. A USING clause filters row VISIBILITY, so a stranger's UPDATE matches zero rows and the trigger
-- never fires — the guard's stranger rule is genuinely unreachable from a client, and case 3 records which
-- layer answered rather than asserting a refusal the guard did not produce. This is the real distinction
-- against TB-BIRTH, where the same reasoning was WRONG: WITH CHECK runs AFTER a BEFORE trigger, USING runs
-- before it. Same policy, opposite ordering, and only executing it tells you which one you are in.
begin;

insert into auth.users(id, email) values
  ('c1111111-0000-4000-8000-00000000000a','tb-field-client@gate.local'),
  ('c1111111-0000-4000-8000-00000000000b','tb-field-provider@gate.local'),
  ('c1111111-0000-4000-8000-00000000000c','tb-field-stranger@gate.local'),
  ('c1111111-0000-4000-8000-00000000000d','tb-field-hiveadmin@gate.local');

-- The admin is a party ONLY through hive membership: they do not own the provider profile, they are an
-- active member of the hive that does. That is the whole point of the case.
insert into public.hive_members(hive_id, worker_name, role, status, auth_uid) values
  ((select id from public.hives order by id limit 1),'TB Field HiveAdmin','worker','active',
   'c1111111-0000-4000-8000-00000000000d');
insert into public.marketplace_platform_admins(worker_name, granted_by)
  values ('TB Field HiveAdmin','tb-probe');

insert into public.service_providers(id, provider_type, auth_uid, hive_id, display_name, categories,
       base_location, availability) values
  -- a freelancer the client is matched with, and a second one to attempt a reassignment TO
  ('c2222222-0000-4000-8000-00000000000a','freelancer','c1111111-0000-4000-8000-00000000000b',null,
   'TB Field Provider','{Plumbing}','POINT(120.5960 16.4023)'::extensions.geography,'online'),
  ('c2222222-0000-4000-8000-00000000000b','freelancer','c1111111-0000-4000-8000-00000000000b',null,
   'TB Field Provider 2','{Plumbing}','POINT(120.5960 16.4023)'::extensions.geography,'online'),
  -- the HIVE profile: owned (auth_uid) by the provider account, NOT by the admin. The admin's party-ness can
  -- therefore only come from the hive branch.
  ('c2222222-0000-4000-8000-00000000000c','hive','c1111111-0000-4000-8000-00000000000b',
   (select id from public.hives order by id limit 1),
   'TB Field Hive Co','{Plumbing}','POINT(120.5960 16.4023)'::extensions.geography,'online');

-- Planted as postgres: auth.uid() is null, so the guard's vetted backend path allows the fixture. The rules
-- under test are all on the raw-client path, which the DO blocks below enter deliberately.
insert into public.service_requests(id, client_auth_uid, mode, status, custom_scope, matched_provider_id)
values
  ('c3333333-0000-4000-8000-00000000000a','c1111111-0000-4000-8000-00000000000a','instant','accepted',
   'TB field scope','c2222222-0000-4000-8000-00000000000a'),
  ('c3333333-0000-4000-8000-00000000000b','c1111111-0000-4000-8000-00000000000a','instant','requested',
   'TB field scope','c2222222-0000-4000-8000-00000000000c'),
  ('c3333333-0000-4000-8000-00000000000c','c1111111-0000-4000-8000-00000000000a','instant','accepted',
   'TB field scope','c2222222-0000-4000-8000-00000000000c'),
  -- a finished, PAID job, for the cancel-window case below
  ('c3333333-0000-4000-8000-00000000000d','c1111111-0000-4000-8000-00000000000a','instant','settled',
   'TB field scope','c2222222-0000-4000-8000-00000000000a');

-- ── the request's own client ────────────────────────────────────────────────────────────────────────────
set local role authenticated;
set local request.jwt.claims = '{"sub":"c1111111-0000-4000-8000-00000000000a","role":"authenticated"}';

do $client$
declare n int;
begin
  -- 1. Reassigning the match by a direct write. Status is deliberately UNCHANGED: this is the branch a
  --    transition-shaped cell cannot reach, and the accept/select RPC is the only legitimate route.
  begin
    update public.service_requests set matched_provider_id='c2222222-0000-4000-8000-00000000000b'
     where id='c3333333-0000-4000-8000-00000000000a';
    get diagnostics n = row_count;
    raise notice 'RESULT client_reassigns_matching=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT client_reassigns_matching=blocked'; end;

  -- 2. Moving the request to another account. An owner who can hand ownership away can also hand away the
  --    audit trail of who asked for the work.
  --
  --    ASSERTED BY LAYER, and it had to be: the first version of this case asserted `blocked` and the
  --    mutation score reported `ownership_transfer_allowed` as STILL SURVIVING. It was right. Deleting the
  --    guard's rule lets the write reach RLS, whose UPDATE check (there is no WITH CHECK, so USING is reused)
  --    rejects a row whose client_auth_uid is no longer the caller — so the write still fails, the exception
  --    handler still writes `blocked`, and the assertion cannot tell the two layers apart. A refusal is not
  --    evidence about WHO refused. This is the same discriminator case 2 of TB-BIRTH is built on, and I had
  --    just written that reasoning out one file earlier before reproducing the mistake here.
  begin
    update public.service_requests set client_auth_uid='c1111111-0000-4000-8000-00000000000c'
     where id='c3333333-0000-4000-8000-00000000000a';
    get diagnostics n = row_count;
    raise notice 'RESULT client_transfers_ownership_layer=%',
      case when n>0 then 'ALLOWED' else 'silently-filtered' end;
  exception when others then
    raise notice 'RESULT client_transfers_ownership_layer=%',
      case sqlstate when '42501' then 'rls' when '23514' then 'guard' else 'other:'||sqlstate end;
  end;

  -- 2b. THE CANCEL WINDOW'S FAR EDGE. A client may cancel while the job is still live
  --     (requested/broadcasting/accepted/en_route/on_site) and not after: `settled` means the work is done
  --     AND the client has confirmed payment, which mints the commission. Cancelling from there would
  --     retroactively undo a paid job.
  --
  --     This is the cell the `state_list_widened` mutant demanded. That operator appends one extra state to
  --     the first authorised from-state list in the guard, which is this cancel window, and it SURVIVED 109
  --     cells: the derived grid walks the transitions the product allows and the illegal origins it thinks
  --     to enumerate, and `settled -> cancelled_by_client` was in neither set. A boundary is only tested
  --     from BOTH sides, and the outside of this one was missing.
  begin
    update public.service_requests set status='cancelled_by_client'
     where id='c3333333-0000-4000-8000-00000000000d';
    get diagnostics n = row_count;
    raise notice 'RESULT client_cancels_settled_job=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT client_cancels_settled_job=blocked'; end;

  -- The positive control for this whole lane: an ordinary field edit by the actual client must still work,
  -- or "every field edit is refused" would satisfy both negatives above while breaking the product.
  begin
    update public.service_requests set custom_scope='TB field scope edited'
     where id='c3333333-0000-4000-8000-00000000000a';
    get diagnostics n = row_count;
    raise notice 'RESULT client_edits_own_field=%', case when n>0 then 'works' else 'BROKEN' end;
  exception when others then raise notice 'RESULT client_edits_own_field=BROKEN'; end;
end
$client$;

-- ── a stranger ─────────────────────────────────────────────────────────────────────────────────────────
set local request.jwt.claims = '{"sub":"c1111111-0000-4000-8000-00000000000c","role":"authenticated"}';

do $stranger$
declare n int;
begin
  -- 3. Recorded by LAYER, not as a refusal. The USING clause hides the row from a non-party, so the write
  --    affects 0 rows and the guard never speaks. Writing this as `blocked` would credit the guard with a
  --    refusal RLS produced, and would keep reading green if the guard's rule were deleted.
  begin
    update public.service_requests set custom_scope='TB stranger edit'
     where id='c3333333-0000-4000-8000-00000000000a';
    get diagnostics n = row_count;
    raise notice 'RESULT stranger_edits_field_layer=%',
      case when n>0 then 'ALLOWED' else 'rls-filtered' end;
  exception when others then
    raise notice 'RESULT stranger_edits_field_layer=%',
      case sqlstate when '42501' then 'rls-error' when '23514' then 'guard' else 'other:'||sqlstate end;
  end;
end
$stranger$;

-- ── an admin who is a party ONLY through hive membership ───────────────────────────────────────────────
set local request.jwt.claims = '{"sub":"c1111111-0000-4000-8000-00000000000d","role":"authenticated"}';

do $hiveadmin$
declare n int;
begin
  -- Both halves of the branch, in one identity. If either notice is wrong the branch is broken in a
  -- different direction, which is why they are asserted together rather than in separate cells.
  raise notice 'RESULT hiveadmin_is_admin=%', public.is_marketplace_admin();

  -- 4a. THE SELF-DEAL. This admin's hive is performing the job, so they are a PARTY and the bypass must not
  --     apply — leaving them with the ordinary party rules, under which requested -> completed is illegal for
  --     everyone. Drop the hive branch from v_is_party and this admin computes as a non-party moderator,
  --     takes the bypass, and this write succeeds.
  begin
    update public.service_requests set status='completed'
     where id='c3333333-0000-4000-8000-00000000000b';
    get diagnostics n = row_count;
    raise notice 'RESULT hive_party_admin_illegal_transition=%',
      case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then
    raise notice 'RESULT hive_party_admin_illegal_transition=blocked'; end;

  -- 4b. THE PERMISSION THE BRANCH EXISTS TO GRANT: acting for the hive's provider profile on a job that hive
  --     accepted. accepted -> en_route is the matched provider's own transition, and an active member of the
  --     hive IS that provider. A "fix" that broke this would close the hole by removing the feature.
  begin
    update public.service_requests set status='en_route'
     where id='c3333333-0000-4000-8000-00000000000c';
    get diagnostics n = row_count;
    raise notice 'RESULT hive_member_acts_for_provider=%', case when n>0 then 'works' else 'BROKEN' end;
  exception when others then
    raise notice 'RESULT hive_member_acts_for_provider=BROKEN'; end;
end
$hiveadmin$;

rollback;
