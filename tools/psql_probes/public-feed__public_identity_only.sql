-- public_identity_only (public-feed): the author identity an anonymous visitor can obtain is the
-- author's PUBLIC identity - author_name - and never their internal user id.
--
-- THIS IS A REGRESSION LOCK, NOT A DESCRIPTION. Until 2026-08-31 it was false: anon held a table-wide
-- SELECT on community_posts, so any holder of the publishable key could ask for auth_uid and receive
-- it for every public post - measured, 15 of 15, exposing 7 distinct authors across 2 hives. The PAGE
-- was innocent the whole time (public-feed.html fetches five named columns and auth_uid is not among
-- them), which is exactly why a walk of the rendered page never saw it. The leak was on the API
-- surface the page declines to use.
--
-- The probe asserts the two halves of the fix, because either one alone silently fails:
--   * the table-level grant is GONE and the column is refused (42501) - a column-level revoke is a
--     no-op while a blanket table grant stands, which is how the first attempt at this fix changed
--     nothing at all;
--   * the column is gone from v_community_posts_truth - the view is security_invoker, so its own
--     SELECT list is privilege-checked, and while it still named auth_uid the revoke took the entire
--     public feed down with it (permission denied) rather than hiding one field.
-- And it asserts the feed still WORKS, because a fix that secures a page by breaking it is not a fix:
-- the exact five-column query public-feed.html issues must still return rows to an anonymous session.
-- expect: anon_has_no_table_wide_select \| t
-- expect: view_has_no_auth_uid_column \| t
-- expect: public_name_still_exposed \| t
-- expect: permission denied for table community_posts
-- expect: feed_rows_for_anon \| [1-9][0-9]*
SELECT 'anon_has_no_table_wide_select | ' || NOT EXISTS (
  SELECT 1 FROM information_schema.role_table_grants
   WHERE table_schema='public' AND table_name='community_posts'
     AND grantee='anon' AND privilege_type='SELECT');
SELECT 'view_has_no_auth_uid_column | ' || NOT EXISTS (
  SELECT 1 FROM information_schema.columns
   WHERE table_schema='public' AND table_name='v_community_posts_truth' AND column_name='auth_uid');

BEGIN;
SET LOCAL ROLE anon;
-- the feed's exact query, which must keep working
SELECT 'feed_rows_for_anon | ' || count(*) FROM (
  SELECT id, author_name, content, category, created_at
    FROM v_community_posts_truth WHERE public IS TRUE AND flagged IS FALSE) q;
-- the public identity is still there: a feed with no author name is not the goal
SELECT 'public_name_still_exposed | ' || (count(*) FILTER (WHERE author_name IS NOT NULL) > 0)
  FROM v_community_posts_truth WHERE public IS TRUE;
-- TEETH: the internal id must be refused outright
SELECT count(auth_uid) FROM community_posts;
ROLLBACK;
