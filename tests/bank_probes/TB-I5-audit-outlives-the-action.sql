-- TB-I5-audit-outlives-the-action
--
-- UFAI I5 (auditability). ufai_pillar_map.json records this cell as `pct: null` on marketplace.html —
-- unmeasured by the UFAI walk — and the platform has already been burned by its opposite twin, where
-- an audit row, a ledger row and a knowledge row all OUTLIVED an action that was reversed
-- ([[feedback_records_that_outlive_the_action]]). Both directions matter and they pull against each
-- other:
--
--   THE TRAIL MUST SURVIVE. A job that is cancelled still happened. Every state it passed through
--   stays in service_job_events, attributed to the identity that caused it, or there is no way to
--   answer "who moved this, and when" after the fact — which is the whole point of an audit log.
--
--   A CLAIM MUST NOT. Anything that only makes sense if the job COMPLETED — a settlement commission,
--   a released payout — must not exist for a job that was cancelled. A surviving claim is not an audit
--   trail, it is a wrong number that will be believed because it sits in a ledger.
--
-- The distinction is the cell: history is append-only, consequences are not.
begin;

insert into auth.users(id, email) values
  ('d6aaaaaa-0000-4000-8000-000000000001', 'tb-i5-client@gate.local'),
  ('d6aaaaaa-0000-4000-8000-000000000002', 'tb-i5-provider@gate.local');

insert into public.service_providers
  (id, provider_type, auth_uid, display_name, categories, base_location, availability)
values ('d6bbbbbb-0000-4000-8000-000000000001', 'freelancer', 'd6aaaaaa-0000-4000-8000-000000000002',
        'TB I5 Provider', '{Plumbing}', 'POINT(120.5960 16.4023)'::extensions.geography, 'on_job');

insert into public.service_requests
  (id, client_auth_uid, mode, custom_scope, location, status, matched_provider_id)
values ('d6cccccc-0000-4000-8000-000000000001', 'd6aaaaaa-0000-4000-8000-000000000001', 'instant',
        'tb i5 probe', 'POINT(120.5960 16.4023)'::extensions.geography, 'accepted',
        'd6bbbbbb-0000-4000-8000-000000000001');

-- Walk the job forward as the real parties, so every event carries a real actor rather than 'system'.
set local role authenticated;
set local request.jwt.claims = '{"sub":"d6aaaaaa-0000-4000-8000-000000000002","role":"authenticated"}';
update public.service_requests set status = 'en_route'
 where id = 'd6cccccc-0000-4000-8000-000000000001';
update public.service_requests set status = 'on_site'
 where id = 'd6cccccc-0000-4000-8000-000000000001';

-- Then the CLIENT cancels. This is the reversal the cell is about.
reset role;
set local role authenticated;
set local request.jwt.claims = '{"sub":"d6aaaaaa-0000-4000-8000-000000000001","role":"authenticated"}';
update public.service_requests set status = 'cancelled_by_client'
 where id = 'd6cccccc-0000-4000-8000-000000000001';

reset role;

-- THE TRAIL SURVIVES: insert + en_route + on_site + cancelled = 4 events, none removed by the cancel.
select 'RESULT events_after_cancel=' || count(*)::text
  from public.service_job_events
 where request_id = 'd6cccccc-0000-4000-8000-000000000001';

-- ATTRIBUTED, not anonymous. An audit row that cannot name the actor answers nothing six months later.
select 'RESULT events_with_actor=' || count(*)::text
  from public.service_job_events
 where request_id = 'd6cccccc-0000-4000-8000-000000000001' and actor_uid is not null;

-- The PROVIDER's moves are recorded as the provider's, and the CLIENT's cancel as the client's. A
-- trail that attributes every row to 'system' is a log, not an audit.
select 'RESULT provider_events=' || count(*)::text
  from public.service_job_events
 where request_id = 'd6cccccc-0000-4000-8000-000000000001' and actor_role = 'provider';

select 'RESULT cancel_actor_role=' ||
       coalesce((select actor_role from public.service_job_events
                  where request_id = 'd6cccccc-0000-4000-8000-000000000001'
                    and to_state = 'cancelled_by_client' limit 1), 'NONE');

-- THE CLAIM DOES NOT SURVIVE: a cancelled job earns no settlement commission. mint_settlement_commission
-- fires on the status transition, so this asserts it never fired for a job that did not complete.
-- mint_settlement_commission writes into service_credit_ledger, keyed by ref_id, not a settlements
-- table. Reading the table the trigger ACTUALLY writes matters: a probe pointed at a table that does
-- not exist errors loudly here, but a probe pointed at the WRONG existing table would have returned a
-- confident 0 and asserted nothing.
select 'RESULT commission_rows_for_cancelled=' || count(*)::text
  from public.service_credit_ledger
 where ref_id = 'd6cccccc-0000-4000-8000-000000000001';

-- ...and the same ledger must NOT be empty by construction: prove the query can see a row at all, or
-- the zero above is meaningless.
insert into public.service_credit_ledger (account_type, account_id, entry_type, amount, ref_kind, ref_id, note)
values ('provider', 'd6bbbbbb-0000-4000-8000-000000000001', 'adjustment', 1, 'probe',
        'd6cccccc-0000-4000-8000-000000000001', 'tb i5 visibility control');
select 'RESULT ledger_query_can_see_rows=' || count(*)::text
  from public.service_credit_ledger
 where ref_id = 'd6cccccc-0000-4000-8000-000000000001';

rollback;
