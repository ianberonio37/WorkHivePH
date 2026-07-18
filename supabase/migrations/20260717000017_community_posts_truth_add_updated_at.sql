-- Fix (bug-hunt roadmap, 2026-07-18). community.html's feed reads the truth VIEW
-- v_community_posts_truth (not the base table), and the P6 OC guard (mig 000012) needs
-- post.updated_at FROM THE FEED to arm .eq('updated_at', snapshot) on the edit. The view did not
-- expose updated_at, so the OC work caused two failures the live page-battery caught:
--   (a) the feed SELECT (which added `updated_at`) 400'd -> "Could not load posts" (P1/P2 regression);
--   (b) even without the 400, post.updated_at would be undefined -> the OC snapshot never set ->
--       a DEAD optimistic-concurrency guard (the exact class in feedback_dead_oc_guard_missing_updated_at_column).
-- Fix: expose p.updated_at through the view. Added at the END of the column list so CREATE OR REPLACE
-- VIEW is valid (same columns, same order, one appended). security_invoker=on preserved (base-table RLS
-- still applies to the read path — see validate_truth_view_security_invoker).
CREATE OR REPLACE VIEW public.v_community_posts_truth
WITH (security_invoker = on) AS
 SELECT p.id,
    p.hive_id,
    p.author_name,
    p.auth_uid,
    p.content,
    p.category,
    p.pinned,
    p.flagged,
    p.public,
    p.created_at,
    p.edited_at,
    p.mentions,
    p.deleted_at,
    h.name AS hive_name,
    p.deleted_at IS NOT NULL AS is_deleted,
    p.edited_at IS NOT NULL AS is_edited,
    p.updated_at
   FROM community_posts p
     LEFT JOIN hives h ON h.id = p.hive_id;
