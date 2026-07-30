-- TB-RATE-platform-feedback-identity-bucket.sql
--
-- `check_platform_feedback_rate_limit` is the second of the four guards no registered gate names (§12.1), and
-- it now enforces TWO bounds that fail differently:
--
--   per-identity   5/hour on COALESCE(auth_uid::text, worker_name, contact_email, 'anonymous')
--   global anon    20/hour on `auth_uid IS NULL`, regardless of the name supplied  (mig 20260730000008)
--
-- WHY THE SECOND ONE EXISTS. `platform_feedback` is anon-writable, so for an unauthenticated submitter the
-- per-identity key is a field THE CLIENT SUPPLIES. Probed live: six submissions under six different
-- worker_names were all accepted, because each name is its own bucket
-- ([[feedback_free_text_identity_is_a_claim]]). The limit did exactly what it said and protected nothing
-- against anyone willing to type a different name. The ceiling is keyed on `auth_uid IS NULL` precisely
-- because a bound the client can move by changing a string is not a bound.
--
-- BOTH BOUNDS ARE ASSERTED, and the second needs care: it counts EVERY anonymous row in the window, including
-- rows already live in the table. So the probe measures its own starting point instead of assuming zero — a
-- fixture that assumed an empty window would pass or fail depending on unrelated traffic
-- ([[feedback_a_test_asserting_a_state_it_does_not_control]]).
--
-- The sqlstate is asserted, not just the refusal: 23P01 is the code this guard chose so the client can show a
-- friendly toast, and both bounds share it deliberately so no frontend change was needed. A different code
-- would mean something else refused — the mistake this probe made on its first run, when a wrong column name
-- (42703) looked exactly like "the limit is not evadable".
begin;

set local role anon;

do $probe$
declare
  accepted int := 0; refused_code text := '(none)';
  accepted_varying int := 0; ceiling_code text := '(none)';
begin
  -- ── BOUND 1: the per-identity limit, under a STABLE name ──────────────────────────────────────────────
  for i in 1..6 loop
    begin
      insert into public.platform_feedback(worker_name, kind, subject, body, status, is_public)
      values ('TB Rate Stable', 'idea', 'probe', 'stable #' || i, 'new', false);
      accepted := accepted + 1;
    exception when others then refused_code := sqlstate;
    end;
  end loop;
  -- Five, not six: the guard refuses once 5 rows are already present, so the SIXTH is the one that fails.
  raise notice 'RESULT stable_identity_accepted=%', accepted;
  raise notice 'RESULT sixth_refused_sqlstate=%', refused_code;

  -- ── BOUND 2: the global ceiling, under a DIFFERENT name every time ────────────────────────────────────
  -- Asserted BEHAVIOURALLY, without reading the table. The first version measured its own headroom with a
  -- COUNT and got 20 when the true figure was 15: the `anon` role cannot SELECT unpublished feedback (the
  -- read policies expose only `is_public` rows), so the probe was blind to the very rows it had just written
  -- while the guard — SECURITY DEFINER — counted all of them. A fixture that cannot see the state it is
  -- reasoning about will compute a confident wrong number
  -- ([[feedback_a_test_asserting_a_state_it_does_not_control]]).
  --
  -- So the property is stated in a form that needs no visibility: attempt 25 submissions, EVERY ONE under a
  -- fresh name so the per-identity bucket can never be the thing that refuses, and require that renaming does
  -- NOT carry all 25 through. If the ceiling were absent, all 25 would land.
  for i in 1..25 loop
    begin
      insert into public.platform_feedback(worker_name, kind, subject, body, status, is_public)
      values ('TB Rate Varying ' || i, 'idea', 'probe', 'varying #' || i, 'new', false);
      accepted_varying := accepted_varying + 1;
    exception when others then ceiling_code := sqlstate;
    end;
  end loop;

  raise notice 'RESULT renaming_still_evades=%',
    case when accepted_varying >= 25 then 'YES-STILL-EVADABLE' else 'no' end;
  -- And the ceiling must be what refused, not something incidental.
  raise notice 'RESULT ceiling_refused_sqlstate=%', ceiling_code;
  -- 20 is the configured ceiling and the 5 stable rows above already consumed part of the window, so the
  -- accepted count must land at or under it. Asserting the BOUND rather than an exact number keeps the cell
  -- robust to whatever else is in the hour.
  raise notice 'RESULT varying_within_ceiling=%',
    case when accepted_varying <= 20 then 'yes' else 'NO-OVER-CEILING' end;
end
$probe$;

rollback;
