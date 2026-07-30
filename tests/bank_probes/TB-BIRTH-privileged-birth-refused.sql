-- TB-BIRTH-privileged-birth-refused.sql
--
-- WHY THIS EXISTS, AND WHY IT WAS MISSING FOR SO LONG. The bank derives its SQL cells from the
-- authorised-TRANSITION set, so every one of its 247 cells is an UPDATE: `from` -> `to`. Nothing in the bank
-- ever INSERTED a row as a raw client. The guards, however, all have a second half — a `TG_OP = 'INSERT'`
-- branch that decides what state a row is allowed to be BORN in — and that half had zero cells.
--
-- Nobody noticed by reading, because reading a green board tells you what ran, not what it would have caught.
-- The mutation score found it mechanically: `tools/validate_guard_mutation_score.py` deleted each guard's
-- birth rules one at a time and **no cell objected** —
--
--     SURVIVED birth_status_unchecked   a new request may be BORN in any state, including a terminal one
--     SURVIVED born_matched_allowed     a request may be born already MATCHED, bypassing the accept RPC
--     SURVIVED refusal_removed          (top-ups) a top-up may be born `verified` -> credit from nothing
--     SURVIVED refusal_removed          (orders)  an order may be born `released` -> the escrow skipped
--
-- The top-up one is the sharp end. `verified` is what MINTS credit, so a client who may insert a top-up
-- already verified does not need to defeat the verification path at all — they simply never enter it. That is
-- a money bug reachable in one statement, and the only thing standing in front of it was a rule no test
-- exercised.
--
-- REACHABILITY WAS CHECKED FIRST, NOT ASSUMED. A guard rule that RLS already enforces is not a gap, and
-- asserting it here would bank a cell that proves nothing about the guard. `pg_policies` says the three
-- INSERT policies check identity ONLY —
--
--     service_requests_client_insert  WITH CHECK (client_auth_uid = auth.uid())
--     service_credit_topups_intake    WITH CHECK (payer_auth_uid  = auth.uid())
--     mkt_orders_insert               WITH CHECK (buyer_name IN (SELECT auth_worker_names()))
--
-- — and `status` appears in none of them. So the born-privileged rules are the guard's alone: reachable, and
-- genuinely untested.
--
-- The ATTRIBUTION rule looked like the opposite case — a rule RLS also enforces, so arguably masked — and
-- checking it live corrected me: BEFORE ROW triggers fire before WITH CHECK, so the guard speaks first there
-- too. Case 2 below asserts that ORDER rather than merely the refusal, and the reasoning is written out at
-- the assertion because it is the part I got wrong from reading the catalog.
--
-- EVERY REFUSAL IS PAIRED WITH THE LEGITIMATE WRITE, because a birth rule that refuses everything would
-- score identically on the negatives while making the product unusable — the same both-halves discipline
-- TB-I2 uses ([[feedback_gates_lock_refusal_not_permission]]: lock the permission that exists, too).
--
-- Self-minted identities inside begin/rollback; nothing here depends on seeded state and nothing survives.
begin;

insert into auth.users(id, email) values
  ('b1111111-0000-4000-8000-00000000000a','tb-birth-client@gate.local'),
  ('b1111111-0000-4000-8000-00000000000b','tb-birth-other@gate.local');

-- `buyer_name IN auth_worker_names()` is how the order policy resolves identity, so the caller needs a
-- membership row. Deliberately NOT a platform admin: an admin would take the bypass at the top of every
-- guard and every refusal below would vanish, so the probe would pass its positives and fail its negatives
-- for a reason that has nothing to do with birth rules. `is_really_admin=f` below asserts that.
insert into public.hive_members(hive_id, worker_name, role, status, auth_uid) values
  ((select id from public.hives order by id limit 1),'TB Birth Client','worker','active',
   'b1111111-0000-4000-8000-00000000000a'),
  ((select id from public.hives order by id limit 1),'TB Birth Other','worker','active',
   'b1111111-0000-4000-8000-00000000000b');

-- Two providers: one owned by the caller (a legitimate top-up target) and one owned by someone else (the
-- provider a request must not be born matched to).
insert into public.service_providers(id, provider_type, auth_uid, display_name, categories,
       base_location, availability) values
  ('b2222222-0000-4000-8000-00000000000a','freelancer','b1111111-0000-4000-8000-00000000000a',
   'TB Birth Client','{Plumbing}','POINT(120.5960 16.4023)'::extensions.geography,'online'),
  ('b2222222-0000-4000-8000-00000000000b','freelancer','b1111111-0000-4000-8000-00000000000b',
   'TB Birth Other','{Plumbing}','POINT(120.5960 16.4023)'::extensions.geography,'online');

set local role authenticated;
set local request.jwt.claims = '{"sub":"b1111111-0000-4000-8000-00000000000a","role":"authenticated"}';

do $probe$
declare n int;
begin
  -- Two non-vacuity guards. If either flipped, every refusal below would be produced by the bypass at the
  -- top of each guard rather than by the birth rule under test, and this probe would be theatre.
  raise notice 'RESULT is_really_admin=%', public.is_marketplace_admin();
  raise notice 'RESULT system_write_off=%',
    coalesce(current_setting('workhive.service_system_write', true), 'unset') is distinct from 'on';

  -- ── 1. SERVICE REQUESTS ─────────────────────────────────────────────────────────────────────────────
  -- Born in a privileged state. `accepted` is reachable only through the accept RPC, which is atomic and
  -- announces itself through a GUC; arriving there by INSERT skips the RPC entirely.
  begin
    insert into public.service_requests(client_auth_uid, mode, status, custom_scope)
    values ('b1111111-0000-4000-8000-00000000000a','instant','accepted','TB birth scope');
    get diagnostics n = row_count;
    raise notice 'RESULT req_born_accepted=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT req_born_accepted=blocked'; end;

  -- Born already MATCHED to a provider the caller does not own — the same RPC bypass by another route.
  begin
    insert into public.service_requests(client_auth_uid, mode, status, custom_scope, matched_provider_id)
    values ('b1111111-0000-4000-8000-00000000000a','instant','requested','TB birth scope',
            'b2222222-0000-4000-8000-00000000000b');
    get diagnostics n = row_count;
    raise notice 'RESULT req_born_matched=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT req_born_matched=blocked'; end;

  -- THE POSITIVE CONTROL: filing an ordinary request must still work.
  begin
    insert into public.service_requests(client_auth_uid, mode, status, custom_scope)
    values ('b1111111-0000-4000-8000-00000000000a','instant','requested','TB birth scope');
    get diagnostics n = row_count;
    raise notice 'RESULT req_born_legit=%', case when n>0 then 'works' else 'BROKEN' end;
  exception when others then raise notice 'RESULT req_born_legit=BROKEN'; end;

  -- ── 2. ATTRIBUTION — this assertion pins WHICH LAYER SPEAKS FIRST, and it corrected me ──────────────
  -- I wrote this case expecting to prove the OPPOSITE of what it proves. Both the guard
  -- (`client_auth_uid is distinct from auth.uid()`) and RLS (`WITH CHECK (client_auth_uid = auth.uid())`)
  -- refuse a request filed as someone else, so from `pg_policies` alone I concluded RLS speaks first, the
  -- guard's copy is unreachable, and `attribution_pin_removed` should be EXCLUDED from the mutation score as
  -- masked. Running it returned `guard`.
  --
  -- The policy text was right and my ordering was wrong: a BEFORE ROW trigger fires BEFORE the WITH CHECK is
  -- evaluated, so on INSERT the guard always speaks first and RLS is the backstop, not the gatekeeper. That
  -- also draws the real distinction with TB-I2, whose admin-bypass mutants genuinely ARE masked on this
  -- table: those are UPDATEs, and a USING clause filters row VISIBILITY before any trigger can fire, so
  -- there the guard never runs at all. USING pre-empts; WITH CHECK does not
  -- ([[feedback_check_the_premise_before_building_the_pattern]] — I nearly banked an exclusion derived from
  -- reading the catalog instead of executing against it).
  --
  -- So the rule is reachable, and asserting `guard` KILLS the mutant: strip the pin and the insert survives
  -- the trigger, RLS rejects it with 42501, and this value becomes `rls`. The SQLSTATE is the discriminator
  -- because a row count cannot tell the layers apart — the same confusion that once turned a failed read
  -- into six imaginary page defects ([[feedback_error_on_returning_is_not_a_failed_write]]).
  --   42501 insufficient_privilege -> RLS / GRANT refused
  --   23514 check_violation        -> the guard refused
  begin
    insert into public.service_requests(client_auth_uid, mode, status, custom_scope)
    values ('b1111111-0000-4000-8000-00000000000b','instant','requested','TB birth scope');
    get diagnostics n = row_count;
    raise notice 'RESULT req_born_as_other_layer=%', case when n>0 then 'ALLOWED' else 'silently-filtered' end;
  exception when others then
    raise notice 'RESULT req_born_as_other_layer=%',
      case sqlstate when '42501' then 'rls' when '23514' then 'guard' else 'other:'||sqlstate end;
  end;

  -- ── 3. TOP-UPS · the money path ─────────────────────────────────────────────────────────────────────
  -- `verified` is the state that mints credit. Born verified = credit from nothing, without ever entering
  -- the verification path.
  begin
    insert into public.service_credit_topups(id, account_type, account_id, payer_auth_uid, amount,
           gcash_ref, status)
    values ('b3333333-0000-4000-8000-00000000000a','provider','b2222222-0000-4000-8000-00000000000a',
            'b1111111-0000-4000-8000-00000000000a',500,'910000000001','verified');
    get diagnostics n = row_count;
    raise notice 'RESULT topup_born_verified=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT topup_born_verified=blocked'; end;

  -- THE POSITIVE CONTROL: declaring a top-up for the founder to verify must still work.
  begin
    insert into public.service_credit_topups(id, account_type, account_id, payer_auth_uid, amount,
           gcash_ref, status)
    values ('b3333333-0000-4000-8000-00000000000b','provider','b2222222-0000-4000-8000-00000000000a',
            'b1111111-0000-4000-8000-00000000000a',500,'910000000002','pending_verification');
    get diagnostics n = row_count;
    raise notice 'RESULT topup_born_pending=%', case when n>0 then 'works' else 'BROKEN' end;
  exception when others then raise notice 'RESULT topup_born_pending=BROKEN'; end;

  -- ── 4. ORDERS · the escrow path ─────────────────────────────────────────────────────────────────────
  -- `released` is what pays the seller and bumps their tier. Born released = escrow skipped.
  begin
    insert into public.marketplace_orders(id, hive_id, buyer_name, seller_name, price, status)
    values ('b4444444-0000-4000-8000-00000000000a',(select id from public.hives order by id limit 1),
            'TB Birth Client','TB Birth Other',100,'released');
    get diagnostics n = row_count;
    raise notice 'RESULT order_born_released=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT order_born_released=blocked'; end;

  -- THE POSITIVE CONTROL: placing an ordinary order must still work.
  begin
    insert into public.marketplace_orders(id, hive_id, buyer_name, seller_name, price, status)
    values ('b4444444-0000-4000-8000-00000000000b',(select id from public.hives order by id limit 1),
            'TB Birth Client','TB Birth Other',100,'pending_payment');
    get diagnostics n = row_count;
    raise notice 'RESULT order_born_pending=%', case when n>0 then 'works' else 'BROKEN' end;
  exception when others then raise notice 'RESULT order_born_pending=BROKEN'; end;
end
$probe$;

-- THE MONEY ORACLE, read back with the identity dropped. The status column is not the thing that matters:
-- a refused born-verified top-up that nevertheless minted a credit row would be the worst outcome here, and
-- every assertion above would still read `blocked` ([[feedback_records_that_outlive_the_action]] — check
-- what the write LEFT BEHIND, not what it returned).
reset role;
select set_config('request.jwt.claims', '', true);
do $ledger$
declare n_born int;
begin
  select count(*) into n_born from public.service_credit_ledger
   where ref_kind='topup' and ref_id in ('b3333333-0000-4000-8000-00000000000a',
                                         'b3333333-0000-4000-8000-00000000000b');
  raise notice 'RESULT birth_credit_minted=%', n_born;
end
$ledger$;

rollback;
