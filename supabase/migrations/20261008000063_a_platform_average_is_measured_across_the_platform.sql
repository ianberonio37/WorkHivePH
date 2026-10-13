-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- ★ A "PLATFORM AVERAGE" IS MEASURED ACROSS THE PLATFORM (marketplace-seller.html, 2026-10-08)
-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- The seller dashboard tells a seller "N% faster / slower than platform avg" and shows that average. It computed it
-- in the browser from "the 500 most recent replied inquiries across all sellers" - but RLS (rightly) lets a person read
-- only inquiries they are party to, so the sample was the seller's OWN conversations (plus any they sent as a buyer).
-- The comparison measured a seller against themselves and labelled it the platform. (Found while moving inquiry
-- ownership to accounts, 20261008000061; it was as wrong under the name-keyed policy.)
--
-- The average now comes from the database, over the same definition the page used - the 500 most recent replied
-- inquiries, platform-wide - returned as ONE number and never a row. Below 5 replies it answers NULL: an average of
-- one or two conversations would be a specific seller's response time, not a platform figure, and the page already
-- reads NULL as "no platform figure yet".
BEGIN;
CREATE OR REPLACE FUNCTION public.marketplace_platform_response_hours()
RETURNS numeric LANGUAGE sql STABLE SECURITY DEFINER SET search_path TO 'public' AS $fn$
  SELECT CASE WHEN count(*) >= 5
              THEN round((avg(extract(epoch FROM greatest(replied_at - created_at, interval '0')) / 3600.0))::numeric, 2)
         END
    FROM (SELECT created_at, replied_at FROM public.marketplace_inquiries
           WHERE replied_at IS NOT NULL ORDER BY created_at DESC, id LIMIT 500) s;
$fn$;
REVOKE ALL ON FUNCTION public.marketplace_platform_response_hours() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.marketplace_platform_response_hours() TO anon, authenticated;
COMMIT;
