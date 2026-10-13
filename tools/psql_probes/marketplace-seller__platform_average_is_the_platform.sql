-- expect: PASS below five replies there is no platform figure, not a person's own
-- expect: PASS with replies from several sellers the figure is the platform's, the same for every caller
-- expect: PASS the figure is one number and never a row
-- expect: PASS nothing persisted after the rollback
-- forbid: FAIL
-- platform_average_is_the_platform (2026-10-08, migration 20261008000063). The seller dashboard's "platform avg" was
-- computed in the browser from inquiries RLS let the caller read - their own - so a seller was compared with
-- themselves. marketplace_platform_response_hours() answers across the platform, as one number, null below 5 replies.
BEGIN;
CREATE TEMP TABLE _n0 AS SELECT count(*) AS n FROM public.marketplace_inquiries WHERE replied_at IS NOT NULL;
SELECT CASE WHEN (SELECT n FROM _n0) >= 5 OR public.marketplace_platform_response_hours() IS NULL
            THEN 'PASS' ELSE 'FAIL' END || ' below five replies there is no platform figure, not a person''s own';
-- replies on two different sellers' listings, 2 h each, enough to cross the threshold
INSERT INTO public.marketplace_inquiries (listing_id, buyer_name, message, status, created_at, replied_at, reply_text)
SELECT l.id, 'Probe Buyer', 'probe 63 ' || g, 'replied', now() - interval '3 hours', now() - interval '1 hour', 'r'
  FROM (SELECT id FROM public.marketplace_listings WHERE auth_uid IS NOT NULL ORDER BY auth_uid, id LIMIT 2) l, generate_series(1, 3) g;
CREATE TEMP TABLE _calls AS SELECT
  (SELECT public.marketplace_platform_response_hours()) AS as_owner;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', '{"sub":"91e0d1eb-cd96-43ee-af5f-0ff2714b3923","role":"authenticated"}', true);
CREATE TEMP TABLE _bryan AS SELECT public.marketplace_platform_response_hours() AS h;
SELECT set_config('request.jwt.claims', '{"sub":"00000000-0000-4000-8000-00000000f00d","role":"authenticated"}', true);
CREATE TEMP TABLE _stranger AS SELECT public.marketplace_platform_response_hours() AS h;
RESET ROLE;
SELECT CASE WHEN (SELECT as_owner FROM _calls) IS NOT NULL
             AND (SELECT h FROM _bryan) = (SELECT as_owner FROM _calls)
             AND (SELECT h FROM _stranger) = (SELECT as_owner FROM _calls)
            THEN 'PASS' ELSE 'FAIL' END || ' with replies from several sellers the figure is the platform''s, the same for every caller';
SELECT CASE WHEN (SELECT prorettype::regtype::text FROM pg_proc WHERE proname = 'marketplace_platform_response_hours') = 'numeric'
             AND (SELECT prosecdef AND NOT proretset FROM pg_proc WHERE proname = 'marketplace_platform_response_hours')
            THEN 'PASS' ELSE 'FAIL' END || ' the figure is one number and never a row';
ROLLBACK;
SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM public.marketplace_inquiries WHERE message LIKE 'probe 63 %')
            THEN 'PASS' ELSE 'FAIL' END || ' nothing persisted after the rollback';
