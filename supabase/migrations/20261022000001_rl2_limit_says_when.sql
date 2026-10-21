-- SL RL2 (2026-10-22): a limit the database enforces tells the person, in one sentence, that it was reached and when
-- it clears. Surveyed from the live definitions (pg_proc) of every trigger that refuses a write for a limit:
--   * the marketplace's listing limit said "Daily listing limit of 20 reached" and stopped - the window is a rolling 24
--     hours, so the honest "when" is when the oldest listing in it turns a day old;
--   * the AI-answer rating limit said "Daily AI reply feedback limit reached" - a rolling day, the same reading;
--   * the review limit said its earlier reviews were saved but not when another could be left - its day starts at the
--     database's midnight (UTC: 8 AM in Manila), so that is when it clears;
--   * the feedback limit ended "Try again later." and put the identity it counted under into the sentence - for a
--     signed-in person that is their account id, a UUID read back to them; the visitors' ceiling said "shortly";
--   * the five cumulative hive quotas (logbook, completed PM checks, stock movements, community posts, saved AI
--     reports) answered with a table name, a hive id and two counts: "logbook cumulative quota exceeded for hive
--     1f2e... (5000 >= 5000)". Nothing in that sentence is a person's word; the HINT already held the remedy.
-- Each sentence now names the limit and when it clears (or, for a quota, what clears it). Only the RAISE lines and the
-- MIN(created_at) each "when" is read from change; every count, window, boundary, branch, code (54000, 23P01,
-- check_violation) and HINT is as it was, so the guards hold exactly what they held (validate_guard_mutation_score's
-- operators still find every line they mutate). The daily row caps (check_daily_row_cap) and the logbook's own limit
-- already said "Resets at midnight." (Manila) and are unchanged. LOCAL: applied to the local stack only.

CREATE OR REPLACE FUNCTION public.check_hive_quota_logbook()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE q_max integer; q_enforce boolean; current_n integer;
BEGIN
  SELECT max_rows_logbook, enforce_blocking INTO q_max, q_enforce
    FROM public.hive_quotas WHERE hive_id = NEW.hive_id;
  IF q_max IS NULL OR NEW.hive_id IS NULL THEN RETURN NEW; END IF;
  SELECT COUNT(*) INTO current_n FROM public.logbook WHERE hive_id = NEW.hive_id;
  IF current_n >= q_max THEN
    IF q_enforce THEN
      RAISE EXCEPTION 'This hive has reached its limit of % logbook entries, so this one was not saved. A supervisor can archive older entries or raise the limit.', q_max
        USING ERRCODE = '54000', HINT = 'Old records can be archived; contact your supervisor to raise the cap.';
    ELSE
      INSERT INTO public.automation_log (job_name, status, detail, triggered_at)
      VALUES ('hive_quota_logbook_over', 'skipped',
              format('WARN-ONLY hive %s logbook %s >= cap %s', NEW.hive_id, current_n, q_max), now());
    END IF;
  END IF;
  RETURN NEW;
END; $function$;

CREATE OR REPLACE FUNCTION public.check_hive_quota_pm_completions()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE q_max integer; q_enforce boolean; current_n integer;
BEGIN
  SELECT max_rows_pm_comp, enforce_blocking INTO q_max, q_enforce
    FROM public.hive_quotas WHERE hive_id = NEW.hive_id;
  IF q_max IS NULL OR NEW.hive_id IS NULL THEN RETURN NEW; END IF;
  SELECT COUNT(*) INTO current_n FROM public.pm_completions WHERE hive_id = NEW.hive_id;
  IF current_n >= q_max THEN
    IF q_enforce THEN
      RAISE EXCEPTION 'This hive has reached its limit of % completed PM checks, so this one was not saved. A supervisor can archive older records or raise the limit.', q_max
        USING ERRCODE = '54000', HINT = 'Old records can be archived; contact your supervisor to raise the cap.';
    ELSE
      INSERT INTO public.automation_log (job_name, status, detail, triggered_at)
      VALUES ('hive_quota_pm_completions_over', 'skipped',
              format('WARN-ONLY hive %s pm_completions %s >= cap %s', NEW.hive_id, current_n, q_max), now());
    END IF;
  END IF;
  RETURN NEW;
END; $function$;

CREATE OR REPLACE FUNCTION public.check_hive_quota_inv_tx()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE q_max integer; q_enforce boolean; current_n integer;
BEGIN
  SELECT max_rows_inv_tx, enforce_blocking INTO q_max, q_enforce
    FROM public.hive_quotas WHERE hive_id = NEW.hive_id;
  IF q_max IS NULL OR NEW.hive_id IS NULL THEN RETURN NEW; END IF;
  SELECT COUNT(*) INTO current_n FROM public.inventory_transactions WHERE hive_id = NEW.hive_id;
  IF current_n >= q_max THEN
    IF q_enforce THEN
      RAISE EXCEPTION 'This hive has reached its limit of % stock movements, so this one was not saved. A supervisor can archive older records or raise the limit.', q_max
        USING ERRCODE = '54000', HINT = 'Old records can be archived; contact your supervisor to raise the cap.';
    ELSE
      INSERT INTO public.automation_log (job_name, status, detail, triggered_at)
      VALUES ('hive_quota_inv_tx_over', 'skipped',
              format('WARN-ONLY hive %s inv_tx %s >= cap %s', NEW.hive_id, current_n, q_max), now());
    END IF;
  END IF;
  RETURN NEW;
END; $function$;

CREATE OR REPLACE FUNCTION public.check_hive_quota_community()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE q_max integer; q_enforce boolean; current_n integer;
BEGIN
  SELECT max_rows_community, enforce_blocking INTO q_max, q_enforce
    FROM public.hive_quotas WHERE hive_id = NEW.hive_id;
  IF q_max IS NULL OR NEW.hive_id IS NULL THEN RETURN NEW; END IF;
  SELECT COUNT(*) INTO current_n FROM public.community_posts WHERE hive_id = NEW.hive_id;
  IF current_n >= q_max THEN
    IF q_enforce THEN
      RAISE EXCEPTION 'This hive has reached its limit of % community posts, so this one was not saved. A supervisor can archive older posts or raise the limit.', q_max
        USING ERRCODE = '54000', HINT = 'Old posts can be archived; contact your supervisor to raise the cap.';
    ELSE
      INSERT INTO public.automation_log (job_name, status, detail, triggered_at)
      VALUES ('hive_quota_community_over', 'skipped',
              format('WARN-ONLY hive %s community %s >= cap %s', NEW.hive_id, current_n, q_max), now());
    END IF;
  END IF;
  RETURN NEW;
END; $function$;

CREATE OR REPLACE FUNCTION public.check_hive_quota_ai_reports()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE q_max integer; q_enforce boolean; current_n integer;
BEGIN
  SELECT max_rows_ai_reports, enforce_blocking INTO q_max, q_enforce
    FROM public.hive_quotas WHERE hive_id = NEW.hive_id;
  IF q_max IS NULL OR NEW.hive_id IS NULL THEN RETURN NEW; END IF;
  SELECT COUNT(*) INTO current_n FROM public.ai_reports WHERE hive_id = NEW.hive_id;
  IF current_n >= q_max THEN
    IF q_enforce THEN
      RAISE EXCEPTION 'This hive has reached its limit of % saved AI reports, so this one was not saved. A supervisor can archive older reports or raise the limit.', q_max
        USING ERRCODE = '54000', HINT = 'Old reports can be archived; contact your supervisor to raise the cap.';
    ELSE
      INSERT INTO public.automation_log (job_name, status, detail, triggered_at)
      VALUES ('hive_quota_ai_reports_over', 'skipped',
              format('WARN-ONLY hive %s ai_reports %s >= cap %s', NEW.hive_id, current_n, q_max), now());
    END IF;
  END IF;
  RETURN NEW;
END; $function$;

CREATE OR REPLACE FUNCTION public.check_listing_rate()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'public', 'extensions', 'pg_temp'
AS $function$
DECLARE daily_count integer; v_oldest timestamptz; v_mins integer; v_when text;
BEGIN
  IF NEW.hive_id IS NOT NULL THEN
    SELECT COUNT(*), MIN(created_at) INTO daily_count, v_oldest
      FROM public.marketplace_listings
      WHERE hive_id = NEW.hive_id
        AND created_at > NOW() - INTERVAL '24 hours';
  ELSE
    -- solo/no-hive seller: cap by the (INSERT-RLS-enforced) seller identity so a NULL hive_id
    -- cannot bypass the anti-spam limit.
    SELECT COUNT(*), MIN(created_at) INTO daily_count, v_oldest
      FROM public.marketplace_listings
      WHERE seller_name = NEW.seller_name
        AND created_at > NOW() - INTERVAL '24 hours';
  END IF;
  IF daily_count >= 20 THEN
    v_mins := GREATEST(1, CEIL(EXTRACT(EPOCH FROM (v_oldest + INTERVAL '24 hours' - now())) / 60.0))::int;
    v_when := CASE WHEN v_mins < 60 THEN 'in about ' || v_mins || CASE WHEN v_mins = 1 THEN ' minute' ELSE ' minutes' END
                   WHEN v_mins < 90 THEN 'in about an hour'
                   ELSE 'in about ' || ROUND(v_mins / 60.0)::int || ' hours' END;
    RAISE EXCEPTION 'Daily listing limit of 20 reached. You can post another listing %.', v_when;
  END IF;
  RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION public.enforce_ai_reply_feedback_daily_limit()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
DECLARE
  day_count integer;
  daily_cap constant integer := 200;
  v_oldest timestamptz;
  v_mins integer;
  v_when text;
BEGIN
  IF NEW.auth_uid IS NULL THEN
    RETURN NEW;
  END IF;
  SELECT count(*), min(created_at) INTO day_count, v_oldest
  FROM public.ai_reply_feedback
  WHERE auth_uid = NEW.auth_uid
    AND created_at >= now() - interval '1 day';
  IF day_count >= daily_cap THEN
    v_mins := GREATEST(1, CEIL(EXTRACT(EPOCH FROM (v_oldest + interval '1 day' - now())) / 60.0))::int;
    v_when := CASE WHEN v_mins < 60 THEN 'in about ' || v_mins || CASE WHEN v_mins = 1 THEN ' minute' ELSE ' minutes' END
                   WHEN v_mins < 90 THEN 'in about an hour'
                   ELSE 'in about ' || ROUND(v_mins / 60.0)::int || ' hours' END;
    RAISE EXCEPTION 'Daily AI reply feedback limit reached. You can rate answers again %.', v_when
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION public.enforce_marketplace_review_daily_cap()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  REVIEW_DAILY_CAP CONSTANT integer := 10;
  v_today integer;
  v_mins integer;
  v_when text;
BEGIN
  -- Service-role / seeder writes carry no auth.uid(); they are not the spam surface this guards.
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;

  SELECT COUNT(*) INTO v_today
    FROM public.marketplace_reviews
   WHERE reviewer_name = NEW.reviewer_name
     AND created_at >= date_trunc('day', now());

  IF v_today >= REVIEW_DAILY_CAP THEN
    v_mins := GREATEST(1, CEIL(EXTRACT(EPOCH FROM (date_trunc('day', now()) + interval '1 day' - now())) / 60.0))::int;
    v_when := CASE WHEN v_mins < 60 THEN 'in about ' || v_mins || CASE WHEN v_mins = 1 THEN ' minute' ELSE ' minutes' END
                   WHEN v_mins < 90 THEN 'in about an hour'
                   ELSE 'in about ' || ROUND(v_mins / 60.0)::int || ' hours' END;
    RAISE EXCEPTION 'Daily review limit reached (% per day). Your earlier reviews are saved. You can leave another review %.', REVIEW_DAILY_CAP, v_when
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END; $function$;

CREATE OR REPLACE FUNCTION public.check_platform_feedback_rate_limit()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_recent_count integer;
  v_identity     text;
  v_anon_count   integer;
  v_oldest       timestamptz;
  v_mins         integer;
  v_when         text;
BEGIN
  v_identity := COALESCE(
    NEW.auth_uid::text,
    NEW.worker_name,
    NEW.contact_email,
    'anonymous'
  );

  SELECT COUNT(*), MIN(created_at) INTO v_recent_count, v_oldest
  FROM public.platform_feedback
  WHERE created_at > now() - interval '1 hour'
    AND COALESCE(
      auth_uid::text, worker_name, contact_email, 'anonymous'
    ) = v_identity;

  IF v_recent_count >= 5 THEN
    v_mins := GREATEST(1, CEIL(EXTRACT(EPOCH FROM (v_oldest + interval '1 hour' - now())) / 60.0))::int;
    v_when := CASE WHEN v_mins < 60 THEN 'in about ' || v_mins || CASE WHEN v_mins = 1 THEN ' minute' ELSE ' minutes' END
                   WHEN v_mins < 90 THEN 'in about an hour'
                   ELSE 'in about ' || ROUND(v_mins / 60.0)::int || ' hours' END;
    RAISE EXCEPTION 'Feedback rate limit reached: 5 messages an hour. You can send more %.', v_when
      USING ERRCODE = '23P01';   -- exclusion_violation; client can show friendly toast
  END IF;

  -- ── THE GLOBAL ANONYMOUS CEILING (mig 20260730000008) ─────────────────────────────────────────────
  -- The per-identity limit above buckets on
  --     COALESCE(NEW.auth_uid::text, NEW.worker_name, NEW.contact_email, 'anonymous')
  -- and `platform_feedback` is anon-writable, so for an unauthenticated submitter the bucket key is a field
  -- THE CLIENT SUPPLIES. Probed live 2026-07-30: six submissions under six different worker_names were ALL
  -- accepted, because each name is its own bucket. The limit worked exactly as written and protected nothing
  -- against anyone willing to type a different name ([[feedback_free_text_identity_is_a_claim]]).
  --
  -- Two fixes were possible and they trade differently, so Ian chose rather than me:
  --   * bucket every anonymous submitter as 'anonymous'  -> spam-proof, but ALL anonymous users then share one
  --     5/hour bucket and a busy hour turns away legitimate feedback;
  --   * keep the per-name bucket AND add a platform-wide anonymous ceiling  -> chosen. An honest anonymous
  --     user is unaffected (they would need >5 of their own to notice anything), while a spammer minting fresh
  --     names hits the global wall.
  --
  -- 20/hour is 4 distinct anonymous submitters at their full individual allowance. It is deliberately keyed on
  -- `auth_uid IS NULL` and NOT on the coalesced identity: the whole point is a bound the client cannot move by
  -- changing a string. Signed-in users are untouched by it — their bucket is already an id they cannot forge.
  IF NEW.auth_uid IS NULL THEN
    SELECT COUNT(*), MIN(created_at) INTO v_anon_count, v_oldest
      FROM public.platform_feedback
     WHERE created_at > now() - interval '1 hour'
       AND auth_uid IS NULL;
    IF v_anon_count >= 20 THEN
      v_mins := GREATEST(1, CEIL(EXTRACT(EPOCH FROM (v_oldest + interval '1 hour' - now())) / 60.0))::int;
      v_when := CASE WHEN v_mins < 60 THEN 'in about ' || v_mins || CASE WHEN v_mins = 1 THEN ' minute' ELSE ' minutes' END
                     WHEN v_mins < 90 THEN 'in about an hour'
                     ELSE 'in about ' || ROUND(v_mins / 60.0)::int || ' hours' END;
      RAISE EXCEPTION 'Feedback rate limit reached: feedback from people who are not signed in is full for this hour. Sign in to send yours now, or try again %.', v_when
        USING ERRCODE = '23P01';   -- same code as the per-identity limit, so the client's existing toast works
    END IF;
  END IF;

  RETURN NEW;
END;
$function$;
