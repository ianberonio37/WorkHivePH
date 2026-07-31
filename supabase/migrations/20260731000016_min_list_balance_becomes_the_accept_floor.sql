-- 20260731000016_min_list_balance_becomes_the_accept_floor.sql
--
-- P2 (M2). `min_list_balance` was the THIRD knob in this family to ship write-only: it existed, validated,
-- was resolvable through `service_knob()` — and the only function in the entire database that mentioned it
-- was the resolver returning it. Nothing read it, so setting it did nothing.
--
-- The roadmap already intended this wiring. P6b shipped the debt-gate as "negative-balance accept block,
-- cold-start-safe threshold 0, **D9 floor Ian-tunable**" — the tunable floor is this knob, and the tuning
-- was never connected. So `accept_service_request` hardcodes `< 0`: a provider is blocked only once they are
-- ALREADY in debt, which is the wrong moment. Failure mode 2 of the sustainability study is precisely "the
-- commission is unpayable exactly when it is owed" — a provider completing a job with an empty wallet. A
-- floor of 0 cannot prevent that; it can only notice it afterwards.
--
-- WHY PHP200 (sustainability study §10): cover ONE job's commission, not one month's. A PHP2,000 job costs
-- PHP100 in commission, so PHP200 covers two average jobs and a provider is never caught empty at
-- completion. PHP500+ stops being a deposit and becomes the entry fee we deliberately rejected — the listing
-- fee wearing a deposit's clothes, suppressing the supply the marketplace needs. It is spendable, not
-- consumed: it pays their own commission.
--
-- SURGERY, NOT A REBUILD. `accept_service_request` is large (identity, category, radius, certified-skill
-- gate, the atomic accept race). Retyping it from a partial read is exactly how a working rule was silently
-- dropped in this repo before — three truncated `substring(prosrc)` reads once produced a "restored"
-- function missing a cast and a guard clause. So this takes the COMPLETE definition via
-- pg_get_functiondef(), substitutes ONE clause, and **asserts the substitution actually happened**. If the
-- target text is not found (a diverged environment, an already-applied migration), it RAISES rather than
-- silently leaving the hardcoded floor in place and reporting success — a silently-failed edit becoming a
-- false report is its own banked lesson.

do $mig$
declare
  v_def   text;
  v_new   text;
  v_from  constant text := 'public.provider_credit_balance(v_provider.id) < 0';
  v_to    constant text :=
    'public.provider_credit_balance(v_provider.id) < public.service_knob(v_req.hive_id, ''min_list_balance'')';
begin
  select pg_get_functiondef(oid) into v_def
    from pg_proc where proname = 'accept_service_request'
    order by oid limit 1;

  if v_def is null then
    raise exception 'accept_service_request not found - nothing to wire the min-balance floor into';
  end if;

  -- Already wired (re-run): leave it alone, but say so rather than pretending to work.
  if position('min_list_balance' in v_def) > 0 then
    raise notice 'accept_service_request already reads min_list_balance - no change';
    return;
  end if;

  if position(v_from in v_def) = 0 then
    raise exception
      'the hardcoded debt-gate clause was not found in accept_service_request; refusing to guess. '
      'Expected: %', v_from;
  end if;

  v_new := replace(v_def, v_from, v_to);

  -- Belt and braces: the replacement must have CHANGED the text and introduced the knob.
  if v_new = v_def or position('min_list_balance' in v_new) = 0 then
    raise exception 'substitution did not apply - refusing to report a change that did not happen';
  end if;

  execute v_new;
  raise notice 'accept_service_request now reads the min_list_balance floor';
end
$mig$;

-- The platform default: 0 -> 200. `service_knob()` falls back to 0 for this key when a hive has no settings
-- row, which is what kept a cold start safe while the floor was meaningless.
--
-- SURGERY AGAIN, AND THE FIRST DRAFT OF THIS BLOCK PROVES WHY. It retyped `service_knob` wholesale from a
-- grepped fragment and got FIVE unrelated defaults wrong — quote_ttl 86400->3600 (a 24-hour quote window
-- cut to one hour), broadcast_radius_max 100000->15000 (100km down to 15km), radius_start 5000->3000,
-- instant_ttl 120->90, widen_rounds 2->3 — and would have shipped all five silently while claiming to
-- change one number. Same class as the truncated-prosrc regression this repo has already paid for. So:
-- take the COMPLETE definition, substitute the ONE default, and assert it applied.
do $mig$
declare
  v_def  text;
  v_new  text;
  -- Unique on purpose: the OTHER mention of this knob is `THEN s.min_list_balance` (the settings lookup),
  -- so anchoring on `THEN 0` targets the platform default and nothing else.
  v_from constant text := 'WHEN ''min_list_balance''         THEN 0';
  v_to   constant text := 'WHEN ''min_list_balance''         THEN 200';
begin
  select pg_get_functiondef(oid) into v_def from pg_proc where proname = 'service_knob' limit 1;
  if v_def is null then
    raise exception 'service_knob not found';
  end if;
  if position(v_to in v_def) > 0 then
    raise notice 'min_list_balance default already 200 - no change';
    return;
  end if;
  if position(v_from in v_def) = 0 then
    raise exception 'the min_list_balance platform default clause was not found; refusing to guess';
  end if;
  v_new := replace(v_def, v_from, v_to);
  if v_new = v_def then
    raise exception 'substitution did not apply';
  end if;
  execute v_new;
  raise notice 'min_list_balance platform default 0 -> 200';
end
$mig$;

comment on function public.service_knob(uuid, text) is
  'D9 knob resolver: the hive''s setting, else the platform default. min_list_balance defaults to 200 - '
  'one job''s commission twice over, per the sustainability study. It is SPENDABLE (it pays the provider''s '
  'own commission), not a fee.';
