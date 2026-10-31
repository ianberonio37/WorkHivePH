-- HS W2 (2026-10-30, tools/prove_hive_scale_burst.mjs): a shift of thirty members writing in the same minutes.
--
-- 1. The marketplace's daily listing limit counted the WHOLE HIVE's listings: twenty listings by any members of a hive
--    and the next member's first listing of the day was refused - "Daily listing limit of 20 reached. You can post
--    another listing ..." - a sentence about their own limit, which they had not touched. The limit is an anti-spam
--    stop, and spam is one account's behaviour, so it now counts that member's own listings in the hive (twenty a day
--    each); the solo branch was already per seller. It runs as SECURITY DEFINER now: as the member, its count passed
--    through RLS (a teammate's draft is invisible, so the old hive-wide count only ever bit on a busy day of PUBLISHED
--    listings - walked: twenty published by teammates, and all 29 members refused), and the per-member count must read
--    auth_uid, a column members may no longer read (the auth_uid-hide release) - as the member it refused every listing
--    with "permission denied". It only counts; no caller may execute it directly.
-- 2. The logbook's per-HIVE free daily cap stays as the plan sets it (hive_quotas, default 200), but its refusal said
--    "You have logged today's free limit" to a member refused because of everyone else's entries. It now says it was the
--    hive's. (The per-USER cap below it keeps "You have logged", which is true there.)
-- Both functions are rewritten from their live definitions with exactly these changes (the listing limit also becomes
-- SECURITY DEFINER, its EXECUTE revoked from every caller).

CREATE OR REPLACE FUNCTION public.check_listing_rate()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'extensions', 'pg_temp'
AS $function$
DECLARE daily_count integer; v_oldest timestamptz; v_mins integer; v_when text;
BEGIN
  IF NEW.hive_id IS NOT NULL THEN
    -- per MEMBER within the hive (HS W2): the hive's other members' listings never spend this person's allowance
    SELECT COUNT(*), MIN(created_at) INTO daily_count, v_oldest
      FROM public.marketplace_listings
      WHERE hive_id = NEW.hive_id
        AND ((NEW.auth_uid IS NOT NULL AND auth_uid = NEW.auth_uid)
             OR (NEW.auth_uid IS NULL AND seller_name = NEW.seller_name))
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
REVOKE ALL ON FUNCTION public.check_listing_rate() FROM PUBLIC, anon, authenticated;

CREATE OR REPLACE FUNCTION public.check_logbook_rate_limit()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  hive_cap   integer;
  user_cap   integer;
  hive_n     integer;
  user_n     integer;
  -- Manila calendar-day window [day_start, day_start + 1 day) as a sargable
  -- created_at range (matches the "Resets at midnight" UX message).
  day_start  timestamptz := (date_trunc('day', now() AT TIME ZONE 'Asia/Manila')) AT TIME ZONE 'Asia/Manila';
  day_end    timestamptz := (date_trunc('day', now() AT TIME ZONE 'Asia/Manila') + INTERVAL '1 day') AT TIME ZONE 'Asia/Manila';
BEGIN
  -- Per-HIVE/day cap. Solo (no-hive) entries skip this but still get the user cap.
  IF NEW.hive_id IS NOT NULL THEN
    SELECT max_rows_logbook INTO hive_cap
      FROM public.hive_quotas WHERE hive_id = NEW.hive_id;
    hive_cap := COALESCE(hive_cap, 200);  -- no row OR NULL cap => default 200

    SELECT COUNT(*) INTO hive_n
      FROM public.logbook
      WHERE hive_id = NEW.hive_id
        AND created_at >= day_start AND created_at < day_end;

    IF hive_n >= hive_cap THEN
      -- No automation_log write here: this RAISE aborts the statement, which would
      -- roll the log row back anyway (and 'warn' isn't an allowed status). The 54000
      -- + friendly message IS the signal; durable over-quota telemetry is a separate
      -- non-blocking path (Q5).
      RAISE EXCEPTION 'Your hive has logged today''s free limit of % entries, so this one was not saved. It resets at midnight.', hive_cap
        USING ERRCODE = '54000', HINT = 'logbook_daily_hive';
    END IF;
  END IF;

  -- Per-USER/day cap -- the real abuse stop (F1). Key on auth_uid, else worker_name.
  SELECT max_rows_logbook_per_user INTO user_cap
    FROM public.hive_quotas WHERE hive_id = NEW.hive_id;
  user_cap := COALESCE(user_cap, 100);

  SELECT COUNT(*) INTO user_n
    FROM public.logbook
    WHERE created_at >= day_start AND created_at < day_end
      AND (
        (NEW.auth_uid IS NOT NULL AND auth_uid = NEW.auth_uid)
        OR (NEW.auth_uid IS NULL AND worker_name = NEW.worker_name)
      );

  IF user_n >= user_cap THEN
    RAISE EXCEPTION 'You have logged today''s free limit (%). Resets at midnight.', user_cap
      USING ERRCODE = '54000', HINT = 'logbook_daily_user';
  END IF;

  RETURN NEW;
END;
$function$;
