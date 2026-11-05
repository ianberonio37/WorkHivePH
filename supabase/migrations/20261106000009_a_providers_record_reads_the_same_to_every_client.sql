-- ★A PROVIDER'S TRACK RECORD WAS THE READER'S OWN SLICE OF IT (2026-11-06, GJ M9 J6 hop 3: "the provider's quote is on the
-- client's request to choose").
--
-- The quote card is where a client decides who to let into their plant, and it shows the provider's "N jobs done" and
-- "★rating (count)" from v_service_provider_truth. That view is security_invoker, and both figures were counted over
-- service_requests - which RLS shows a person only for the jobs they are party to (their own, their hive's, their own
-- provider work). So the figure was the VIEWER's slice of the provider. Measured as a client (Christine Dizon) against the
-- database: Hector Salvador Mechanical Works 2 jobs done -> read as 0; Leandro Marquez HVAC 1 -> 0. Every provider read
-- "0 jobs done" to every client who had not hired them already, the exact people the number is for. This is the fourth
-- instance of one root ([[feedback_a_figure_about_someone_else_is_the_viewers_rls_slice]]).
--
-- And the review the client writes ("A sentence for other clients", the field's own words) reached no one: no page reads a
-- service review's comment, only its star count, and that count was sliced the same way.
--
-- One SECURITY DEFINER function returns the provider's AGGREGATES and their latest client review - no job row, no client
-- account, no address - computed exactly as the view computed them; the view joins it, so every reader (a signed-out
-- visitor included) reads the same record. The latest review carries the reviewer's name as marketplace reviews already
-- publish it (marketplace_reviews.reviewer_name is readable to anyone, as on the seller profile).

BEGIN;

CREATE OR REPLACE FUNCTION public.service_provider_record(p_provider_id uuid)
 RETURNS TABLE(completed_jobs bigint, rating_avg numeric, rating_count bigint,
               latest_review_rating integer, latest_review_comment text, latest_review_by text, latest_review_at timestamptz)
 LANGUAGE sql
 STABLE
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  SELECT
    (SELECT count(*) FROM public.service_requests sr
      WHERE sr.matched_provider_id = p_provider_id AND sr.status = ANY (ARRAY['completed', 'settled'])),
    (SELECT round(avg(mr.rating), 2) FROM public.marketplace_reviews mr JOIN public.service_requests r ON r.id = mr.request_id
      WHERE r.matched_provider_id = p_provider_id AND mr.direction = 'client_to_provider'),
    (SELECT count(*) FROM public.marketplace_reviews mr JOIN public.service_requests r ON r.id = mr.request_id
      WHERE r.matched_provider_id = p_provider_id AND mr.direction = 'client_to_provider'),
    lr.rating, lr.comment, lr.reviewer_name, lr.created_at
  FROM (SELECT 1) one
  LEFT JOIN LATERAL (
    SELECT mr.rating, mr.comment, mr.reviewer_name, mr.created_at
      FROM public.marketplace_reviews mr JOIN public.service_requests r ON r.id = mr.request_id
     WHERE r.matched_provider_id = p_provider_id AND mr.direction = 'client_to_provider'
     ORDER BY mr.created_at DESC, mr.id DESC
     LIMIT 1) lr ON true;
$function$;

-- signed-in readers only: anon holds no SELECT on service_providers, so a visitor's read of the view stops there before
-- it could reach this body - and Supabase grants anon EXECUTE on every new function explicitly, so it is revoked by name
REVOKE ALL ON FUNCTION public.service_provider_record(uuid) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.service_provider_record(uuid) TO authenticated, service_role;

CREATE OR REPLACE VIEW public.v_service_provider_truth WITH (security_invoker = on) AS
 SELECT sp.id,
    sp.provider_type,
    sp.worker_name,
    sp.hive_id,
    sp.display_name,
    sp.contact,
    sp.categories,
    sp.service_areas,
    sp.base_lat,
    sp.base_lng,
    sp.availability,
    sp.verified,
    sp.verified_at,
    sp.created_at,
    COALESCE(rec.completed_jobs, (0)::bigint) AS completed_jobs,
    rec.rating_avg,
    COALESCE(rec.rating_count, (0)::bigint) AS rating_count,
        CASE
            WHEN ((COALESCE(rec.completed_jobs, (0)::bigint) >= 25) AND (COALESCE(rec.rating_avg, (0)::numeric) >= 4.5)) THEN 'gold'::text
            WHEN (COALESCE(rec.completed_jobs, (0)::bigint) >= 10) THEN 'silver'::text
            ELSE 'bronze'::text
        END AS tier,
    1 AS _source_count,
    sp.updated_at AS _freshness_ts,
    'service_provider_truth:v3'::text AS _canonical_version,
    rec.latest_review_rating,
    rec.latest_review_comment,
    rec.latest_review_by,
    rec.latest_review_at
   FROM (service_providers sp
     LEFT JOIN LATERAL service_provider_record(sp.id) rec(completed_jobs, rating_avg, rating_count, latest_review_rating,
       latest_review_comment, latest_review_by, latest_review_at) ON (true));

COMMIT;
