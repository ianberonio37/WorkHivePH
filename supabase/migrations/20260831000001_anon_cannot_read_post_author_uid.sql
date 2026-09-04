-- An anonymous visitor could read the AUTHOR'S INTERNAL USER ID off every public post.
--
-- FOUND 2026-08-31, while converting public-feed's `public_identity_only` bank row into a permanent
-- psql recipe. The oracle reads: "the author identity shown is the author's PUBLIC identity - never
-- their internal name or hive." The PAGE honours that exactly - public-feed.html fetches
-- `id, author_name, content, category, created_at` and nothing else. The DATA did not: anon held a
-- column-level SELECT grant on community_posts.auth_uid, and PostgREST executes as the anon role, so
-- anyone holding the publishable key could ask for the column the page declines to show.
--
-- Measured before the fix, as role anon: 15 visible posts, auth_uid readable on all 15, revealing
-- 7 distinct author identities across 2 hives. auth_uid is a STABLE identifier, so the exposure is
-- not one id - it is a correlation key: every public post by the same person links together, and
-- links to that person everywhere else their auth_uid appears.
--
-- This is the shape the walk could never catch. A live walk reads the RENDERED page, and the rendered
-- page was innocent; the leak lived one layer down, on the API surface the page happens not to use.
-- The instrument saw what a user sees, and a user is not who exploits this.
--
-- WHY A COLUMN REVOKE AND NOT AN RLS CHANGE. RLS filters ROWS; it cannot hide a COLUMN of a row the
-- viewer is allowed to see, and anon is *supposed* to see public posts. Column privileges are the
-- only mechanism at the right granularity.
--
-- WHY auth_uid ONLY. v_community_posts_truth is security_invoker and LEFT JOINs hives ON h.id =
-- p.hive_id, so every anon read of that view touches hive_id - revoking it would take the public feed
-- down with it. auth_uid is referenced by no predicate and no join, so removing it costs nothing that
-- works today. The hive_id/hive_name half of the same oracle is a live question (should a public post
-- carry visible hive attribution at all?) and is recorded for Ian rather than decided here.
--
-- Writes are NOT the issue and are deliberately left alone: anon does hold INSERT/UPDATE/DELETE grants
-- on this table, but every policy requires auth.uid() IS NOT NULL, so - measured - an anon UPDATE and
-- DELETE each affect 0 rows and an INSERT is refused with 42501. RLS is doing that job correctly.

-- ★A COLUMN-LEVEL REVOKE IS A NO-OP WHILE A TABLE-LEVEL GRANT STANDS (learned here, 2026-08-31).
-- The first version of this migration was exactly `REVOKE SELECT (auth_uid) ... FROM anon`. It ran
-- without error and changed NOTHING: anon still read auth_uid on all 15 posts. The reason is in
-- relacl - anon holds `arwdxtm`, a TABLE-wide grant, and a table-wide SELECT already covers every
-- column present and future. Column privileges only bite once the blanket grant is gone.
-- So: drop the table-level SELECT, then hand back an EXPLICIT column list.
-- The list is an allowlist on purpose. A column added later is NOT granted to anon until someone
-- decides it should be - a new column failing closed is the correct default for the role that belongs
-- to the open internet, and the feed's own query names its columns, so it is unaffected either way.

REVOKE SELECT ON public.community_posts FROM anon;

GRANT SELECT (
  id, hive_id, author_name, content, category,
  pinned, flagged, public, created_at, edited_at, mentions, deleted_at, updated_at
) ON public.community_posts TO anon;

-- ★AND THE REVOKE ALONE TOOK THE PUBLIC FEED DOWN (measured immediately after, same session).
-- v_community_posts_truth is security_invoker, so the VIEW'S OWN query runs as the caller - and that
-- query lists p.auth_uid in its SELECT. The privilege check therefore covers the column even when the
-- caller never asks for it, so the moment anon lost auth_uid, EVERY anon read of the view failed with
-- "permission denied for table community_posts". The feed did not degrade; it stopped.
-- The column has to leave the VIEW as well, and it can: all seven call sites (community.html x6,
-- nav-hub.js, public-feed.html) name their columns explicitly and NOT ONE selects auth_uid. The view
-- has no dependent objects, so this is a drop-and-recreate with the grants restored exactly.
-- CREATE OR REPLACE cannot be used here - it may only APPEND columns, never remove one.

DROP VIEW IF EXISTS public.v_community_posts_truth;

CREATE VIEW public.v_community_posts_truth
WITH (security_invoker = on) AS
SELECT p.id,
       p.hive_id,
       p.author_name,
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
  FROM public.community_posts p
  LEFT JOIN public.hives h ON h.id = p.hive_id;

GRANT SELECT ON public.v_community_posts_truth TO anon, authenticated, grafana_reader;
GRANT ALL    ON public.v_community_posts_truth TO postgres, service_role;
