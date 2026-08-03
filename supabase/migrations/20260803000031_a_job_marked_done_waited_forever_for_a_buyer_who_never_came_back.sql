-- ============================================================================
-- THE COMPLETION WINDOW — a job marked done must not wait forever
--
-- Today a provider drives a job to `completed` and then nothing happens until
-- the BUYER presses Confirm. If the buyer never comes back, the job sits in
-- `completed` forever: the provider is unpaid on the platform's record, the
-- 10% reward never moves, and no one is told. The buyer holds a veto they may
-- not even know they hold.
--
-- 500 adversarial simulations measured three designs (plan §3b):
--
--   OFF     buyer confirms alone (today)          P344.3M scam loss   0 stalled
--   STRICT  both must sign off, no timeout        P69.3M  (-80%)      170,388 stalled (15%)
--   WINDOW  provider marks done -> buyer has N     P146.1M (-58%)      0 stalled
--           days to object -> auto-confirms
--
-- STRICT is safest and strands 15% of HONEST jobs, which is unshippable.
-- WINDOW costs nothing and captures most of it; with a push at the moment the
-- provider marks done it reaches P55.3M (-84%), beating STRICT on BOTH axes.
-- So: not a mutual checklist -- provider declares, buyer has a window to
-- object, and silence settles it.
--
-- THIS MIGRATION IS THE MECHANISM ONLY: the knob, the deadline, and the sweep.
-- The push fan-out and the buyer-facing "object by <date>" state ride on top
-- of it and land next; they need this clock to exist first.
--
-- WHAT AUTO-CONFIRM MAY NOT DO. `guard_settle_requires_payment` means a job
-- cannot reach `settled` without a payment row -- correctly, because the whole
-- money spine bills against what was actually paid. But at window expiry NO
-- ONE HAS TOLD US what was paid: the buyer pays the provider directly, off
-- platform, and never came back to say so. So the sweep records the AGREED
-- price and marks the row `auto_confirmed_at`, with `confirmed_by` left NULL.
-- That distinction is the point: an assumed payment must never be
-- indistinguishable from one a human attested to. Every downstream reader can
-- tell the difference, and a dispute can still reverse it.
--
-- A job with no agreed price at all is NOT auto-settled -- amount_paid > 0 is
-- a CHECK, and inventing a number to satisfy it would be the worst outcome
-- here. Those jobs stay `completed` and are counted in the sweep's return so
-- they are visible rather than silently skipped.
-- ============================================================================

-- ── 1. The knob ─────────────────────────────────────────────────────────────
-- A window, not a constant: every other timing value on this platform is
-- hive-tunable and this one is the most likely to need tuning by trade (a
-- 3-day window suits a repair; a commissioning job may want longer).
ALTER TABLE public.hive_service_settings
  ADD COLUMN IF NOT EXISTS completion_window_days integer NOT NULL DEFAULT 3;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                  WHERE conrelid = 'public.hive_service_settings'::regclass
                    AND conname  = 'hive_service_settings_completion_window_sane') THEN
    -- Floor 1 day: a zero/negative window would auto-settle the instant the
    -- provider marks done, which is OFF wearing WINDOW's name. Ceiling 30:
    -- past a month the provider is effectively unpaid on our record anyway.
    ALTER TABLE public.hive_service_settings
      ADD CONSTRAINT hive_service_settings_completion_window_sane
      CHECK (completion_window_days BETWEEN 1 AND 30);
  END IF;
END $$;

-- ── 2. Teach service_knob the new key ───────────────────────────────────────
-- ZERO hives currently hold a settings row, so the FALLBACK is what actually
-- governs -- this is exactly what made the commission knob a no-op in mig 30
-- (the rate was hiding in the trigger's own fallback). The column default and
-- the function fallback must agree, and both say 3.
CREATE OR REPLACE FUNCTION public.service_knob(p_hive uuid, p_key text)
 RETURNS integer
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
  SELECT COALESCE(
    (SELECT CASE p_key
              WHEN 'instant_ttl_seconds'      THEN s.instant_ttl_seconds
              WHEN 'quote_ttl_seconds'        THEN s.quote_ttl_seconds
              WHEN 'broadcast_radius_start_m' THEN s.broadcast_radius_start_m
              WHEN 'broadcast_radius_max_m'   THEN s.broadcast_radius_max_m
              WHEN 'broadcast_widen_rounds'   THEN s.broadcast_widen_rounds
              WHEN 'tier_silver_sales'        THEN s.tier_silver_sales
              WHEN 'tier_gold_sales'          THEN s.tier_gold_sales
              WHEN 'min_list_balance'         THEN s.min_list_balance
              WHEN 'reward_max_per_listing'   THEN s.reward_max_per_listing
              WHEN 'reward_min_per_listing'   THEN s.reward_min_per_listing
              WHEN 'starter_grant'            THEN s.starter_grant
              WHEN 'completion_window_days'   THEN s.completion_window_days
            END
       FROM public.hive_service_settings s WHERE s.hive_id = p_hive),
    CASE p_key
      WHEN 'instant_ttl_seconds'      THEN 120
      WHEN 'quote_ttl_seconds'        THEN 86400
      WHEN 'broadcast_radius_start_m' THEN 15000
      WHEN 'broadcast_radius_max_m'   THEN 100000
      WHEN 'broadcast_widen_rounds'   THEN 3
      WHEN 'tier_silver_sales'        THEN 11
      WHEN 'tier_gold_sales'          THEN 51
      WHEN 'min_list_balance'         THEN 200
      WHEN 'reward_max_per_listing'   THEN 500   -- 4.9x throughput at scale vs a flat rate (measured)
      WHEN 'reward_min_per_listing'   THEN 0     -- a PHP200 floor was the most harmful knob tested
      WHEN 'starter_grant'            THEN 500   -- +8 pts health; removes STALLED entirely (measured)
      WHEN 'completion_window_days'   THEN 3     -- plan §3b: start at 3, Ian tunes
    END);
$function$;

-- ── 3. Mark an auto-confirmed payment as auto-confirmed ─────────────────────
-- NOT a boolean: the TIMESTAMP says when the platform assumed it, which is the
-- fact a dispute needs. NULL = a human confirmed it (see confirmed_by).
ALTER TABLE public.service_payments
  ADD COLUMN IF NOT EXISTS auto_confirmed_at timestamptz;

COMMENT ON COLUMN public.service_payments.auto_confirmed_at IS
  'Set when the completion-window sweep settled this job because the buyer did '
  'not respond. The amount is the AGREED price, not an attested one, and '
  'confirmed_by is NULL. A buyer-attested payment leaves this NULL.';

-- ── 4. The deadline, as a readable function ─────────────────────────────────
-- A function rather than a stored column: the knob may change, and a deadline
-- baked into a row at completion time would silently ignore the new value. The
-- buyer-facing "object by <date>" copy reads THIS, so the screen and the sweep
-- can never disagree about when the window closes.
CREATE OR REPLACE FUNCTION public.service_objection_deadline(p_request_id uuid)
 RETURNS timestamptz
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
  SELECT r.completed_at
       + (public.service_knob(r.hive_id, 'completion_window_days') * interval '1 day')
    FROM public.service_requests r
   WHERE r.id = p_request_id AND r.completed_at IS NOT NULL;
$function$;

REVOKE ALL ON FUNCTION public.service_objection_deadline(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.service_objection_deadline(uuid) TO authenticated;

-- ── 5. The sweep ────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.sweep_service_completions()
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  n_settled   integer := 0;
  n_unpriced  integer := 0;
  r           record;
  v_price     numeric;
BEGIN
  -- Jobs whose window has closed, oldest first so a backlog drains in order.
  FOR r IN
    SELECT sr.id, sr.hive_id
      FROM public.service_requests sr
     WHERE sr.status = 'completed'
       AND sr.completed_at IS NOT NULL
       AND sr.completed_at
           + (public.service_knob(sr.hive_id, 'completion_window_days') * interval '1 day')
           <= now()
     ORDER BY sr.completed_at
     FOR UPDATE SKIP LOCKED
  LOOP
    v_price := public.service_request_price(r.id);

    -- No agreed price => nothing honest to record. amount_paid > 0 is a CHECK
    -- and inventing a figure to clear it would put a fabricated number in the
    -- money spine. Leave it completed and COUNT it, so it shows up rather than
    -- vanishing into a skipped branch.
    IF v_price IS NULL OR v_price <= 0 THEN
      n_unpriced := n_unpriced + 1;
      CONTINUE;
    END IF;

    -- The assumed payment. confirmed_by stays NULL: nobody attested to this.
    INSERT INTO public.service_payments
      (request_id, hive_id, amount_paid, method, confirmed_by, paid_at, auto_confirmed_at,
       variance_reason)
    VALUES
      (r.id, r.hive_id, v_price, 'other', NULL, now(), now(),
       'Auto-confirmed: the objection window closed with no response from the buyer. '
       'Amount is the agreed price, not a buyer-attested figure.');

    UPDATE public.service_requests
       SET status = 'settled', settled_at = now(), updated_at = now()
     WHERE id = r.id;

    INSERT INTO public.service_job_events (request_id, actor_role, from_state, to_state, note)
    VALUES (r.id, 'system', 'completed', 'settled',
            'auto-confirmed after the '
            || public.service_knob(r.hive_id, 'completion_window_days')
            || '-day objection window closed with no response');

    n_settled := n_settled + 1;
  END LOOP;

  RETURN jsonb_build_object(
    'settled',  n_settled,
    'unpriced', n_unpriced,   -- completed, past the window, but with no agreed price to record
    'swept_at', now()
  );
END;
$function$;

-- The sweep is infrastructure, exactly like sweep_service_broadcasts: a
-- SECURITY DEFINER function that settles other people's jobs must not be
-- callable by a user who could aim it. Cron/service-role only.
REVOKE ALL ON FUNCTION public.sweep_service_completions() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.sweep_service_completions() FROM authenticated;
REVOKE ALL ON FUNCTION public.sweep_service_completions() FROM anon;
