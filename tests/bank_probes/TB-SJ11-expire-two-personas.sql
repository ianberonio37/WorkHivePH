-- TB-SJ11-expire-two-personas.sql
--
-- JOURNEY SJ-J11 "expire" — the hail nobody took. Its W phase was PARTIAL: one state walked and ZERO
-- personas, so the board could not call it a walk ([[feedback_a_walked_cell_is_not_a_banked_cell]] — a
-- journey is walked when BOTH sides have been seen in MORE THAN ONE state, not when someone looked once).
--
-- This drives the REAL mechanism, `sweep_service_broadcasts()`, rather than an UPDATE that sets
-- status='expired' by hand. Hand-setting the terminal state would assert nothing about the product: the whole
-- question is whether the sweep expires the right rows, leaves the wrong ones alone, and whether each side
-- SEES the outcome through its own truth view.
--
-- THE SWEEP'S OWN RULES, read from its body rather than assumed:
--   1. a broadcasting request with a NULL TTL gets one stamped (instant = 2 min, quote = 24 h)
--   2. an instant hail past its TTL is WIDENED (radius x2, round+1) while broadcast_round < 2
--   3. only what the widened search still could not place is EXPIRED
-- So a hail must be past TTL *and* out of widening rounds before it may expire — which is exactly the
-- boundary worth asserting, and the reason a naive "set it expired" test would prove nothing.
--
-- TWO PERSONAS, each through the view it actually reads:
--   P-client   reads v_service_request_truth  — their own hail, and must see it reach a terminal state
--   P-provider reads v_service_open_broadcasts — the open-hail feed, where an expired hail must DISAPPEAR
--              (a provider who still sees a dead hail wastes a trip; this is the user-visible half)
-- TWO STATES: S-active (before the sweep) and S-terminal (after it).
--
-- EACH PERSONA IS *ACTED AS*, not merely named. Both views are scoped by auth.uid()
-- (v_service_request_truth: client OR hive member OR matched provider; v_service_open_broadcasts: the
-- calling provider). Reading them with no JWT set returns ZERO rows and would look exactly like "the hail
-- is not there" — the first run of this probe did precisely that and reported 0/0. A persona walk that does
-- not adopt the persona's identity is not a walk ([[feedback_verify_the_instrument_before_the_page]]).
begin;

insert into auth.users(id, email) values
  ('5a000000-0000-4000-8000-00000000000a','tb-sj11-client@gate.local'),
  ('5a000000-0000-4000-8000-00000000000b','tb-sj11-provider@gate.local');

-- The provider persona needs a provider PROFILE: v_service_open_broadcasts resolves the caller through
-- my_service_provider_ids(), so an auth user alone would read an empty feed for the wrong reason.
insert into public.service_providers(id, provider_type, display_name, auth_uid)
values ('5a000000-0000-4000-8000-0000000000f1','freelancer','TB SJ11 Provider',
        '5a000000-0000-4000-8000-00000000000b');

-- Two hails from the same client, planted as postgres (auth.uid() null -> the guards' vetted backend path,
-- which is also what lets a request be BORN broadcasting).
--   d1: past TTL and out of widening rounds  -> the sweep MUST expire it
--   d2: TTL still in the future              -> the sweep MUST leave it alone (the non-vacuity half: a sweep
--       that expired everything would pass a one-row test while destroying live hails)
--
-- broadcast_round is READ FROM THE KNOB, never hardcoded. It was pinned at 2 because
-- broadcast_widen_rounds was 2, so a round of 2 meant "out of rounds". When the knob rose to 3 (the
-- coverage sweep found 15km reached far too few providers, and the widening rounds matter more now that
-- the radius is actually load-bearing), a round of 2 became "one widening still owed" -- so the sweep
-- correctly WIDENED the stale hail instead of expiring it, and this probe reported the product broken.
-- A fixture that encodes a knob's current value silently becomes a test of yesterday's configuration.
insert into public.service_requests
  (id, client_auth_uid, status, mode, custom_scope, broadcast_round, offer_ttl_expires_at, broadcast_radius_m)
values
  ('5a000000-0000-4000-8000-0000000000d1','5a000000-0000-4000-8000-00000000000a','broadcasting','instant',
   'TB SJ11 stale hail',
   public.service_knob((select hive_id from public.service_requests limit 1),'broadcast_widen_rounds'),
   now() - interval '10 minutes', 5000),
  ('5a000000-0000-4000-8000-0000000000d2','5a000000-0000-4000-8000-00000000000a','broadcasting','instant',
   'TB SJ11 live hail',
   public.service_knob((select hive_id from public.service_requests limit 1),'broadcast_widen_rounds'),
   now() + interval '30 minutes', 5000);

select set_config('request.jwt.claims',
  '{"sub":"5a000000-0000-4000-8000-00000000000a","role":"authenticated"}', true);

do $probe$
declare
  v_client_sees_open int; v_provider_sees_open int;
  v_client_sees_expired text; v_provider_still_sees int;
  v_live_survived text;
  CLIENT constant text := '{"sub":"5a000000-0000-4000-8000-00000000000a","role":"authenticated"}';
  PROVIDER constant text := '{"sub":"5a000000-0000-4000-8000-00000000000b","role":"authenticated"}';
begin
  -- ── S-ACTIVE, as the CLIENT ────────────────────────────────────────────────────────────────────────
  perform set_config('request.jwt.claims', CLIENT, true);
  select count(*) into v_client_sees_open from public.v_service_request_truth
   where id = '5a000000-0000-4000-8000-0000000000d1'::uuid and status = 'broadcasting';
  raise notice 'RESULT active_client_sees_hail=%', v_client_sees_open;

  -- ── S-ACTIVE, as the PROVIDER ──────────────────────────────────────────────────────────────────────
  -- The SECOND persona, and the reason this journey was only PARTIAL: the open-hail feed is what a provider
  -- actually looks at, and it is scoped to THEM.
  perform set_config('request.jwt.claims', PROVIDER, true);
  select count(*) into v_provider_sees_open from public.v_service_open_broadcasts
   where request_id = '5a000000-0000-4000-8000-0000000000d1'::uuid;
  raise notice 'RESULT active_provider_feed_has_hail=%', v_provider_sees_open;

  -- ── THE TRANSITION — a SYSTEM operation, and the guard says so ─────────────────────────────────────
  -- Running the sweep while still wearing a user identity is refused: "illegal service request transition
  -- broadcasting -> expired for this caller". That is guard_service_request_status doing its job — expiry is
  -- the platform's decision, never a party's. Clearing the JWT takes the vetted backend path, which is how
  -- pg_cron runs it in production.
  perform set_config('request.jwt.claims', '{}', true);
  perform public.sweep_service_broadcasts();

  -- ── S-TERMINAL, as the CLIENT ──────────────────────────────────────────────────────────────────────
  perform set_config('request.jwt.claims', CLIENT, true);
  select status into v_client_sees_expired from public.v_service_request_truth
   where id = '5a000000-0000-4000-8000-0000000000d1'::uuid;
  raise notice 'RESULT terminal_client_status=%', coalesce(v_client_sees_expired, '(gone)');

  -- ── S-TERMINAL, as the PROVIDER ────────────────────────────────────────────────────────────────────
  -- A dead hail still on the feed is a wasted trip for whoever answers it.
  perform set_config('request.jwt.claims', PROVIDER, true);
  select count(*) into v_provider_still_sees from public.v_service_open_broadcasts
   where request_id = '5a000000-0000-4000-8000-0000000000d1'::uuid;
  raise notice 'RESULT terminal_provider_feed_dropped=%',
    case when v_provider_still_sees = 0 then 'yes' else 'NO' end;

  -- NON-VACUITY: the hail whose TTL has NOT passed survives the same sweep. Without this, a sweep that
  -- expired everything would pass every assertion above while destroying live work.
  select status into v_live_survived from public.service_requests
   where id = '5a000000-0000-4000-8000-0000000000d2'::uuid;
  raise notice 'RESULT live_hail_survived=%', v_live_survived;
end $probe$;

rollback;
