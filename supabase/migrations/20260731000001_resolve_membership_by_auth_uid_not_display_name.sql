-- 20260731000001_resolve_membership_by_auth_uid_not_display_name.sql
--
-- CROSS-TENANT PRIVILEGE ESCALATION — the canonical identity view resolved MEMBERSHIP by a
-- user-mutable string.
--
-- `v_worker_truth` is the membership anchor that `_shared/tenant-context.ts::resolveTenancy` trusts, and
-- through it 30 service-role edge functions decide which hive a caller belongs to. Its membership join was:
--
--     LEFT JOIN public.hive_members hm ON hm.worker_name = wp.display_name AND hm.status = 'active'
--
-- `worker_name`/`display_name` is a DISPLAY string, not an identity. `worker_profiles.display_name` is
-- UPDATE-grantable to `authenticated`/`anon` and the RLS policy `profiles update own` (USING auth.uid() =
-- auth_uid, no WITH CHECK) lets a user set it to ANY value. There is no UNIQUE constraint on display_name.
-- So a member of hive A can rename their own profile to the display name of a member of hive B, and the view
-- then joins their auth_uid to hive B's membership row.
--
-- PROVEN (2026-07-31, rolled back): Pablo Aguilar (a member of Manila Electronics, NOT of Baguio Textile
-- Mills) runs, as himself under RLS:
--     update worker_profiles set display_name='Leandro Marquez' where auth_uid = <pablo>;   -- allowed
-- and then resolveTenancy(<pablo>, <baguio-hive>), run service-role exactly as the edge functions run it,
-- returns { ok:true, role:'supervisor' } for Baguio — a hive he was never invited to. The helper itself is
-- correct: it filters v_worker_truth on auth_uid AND hive_id AND hive_status='active'. The view lied to it,
-- because the view resolved WHO is a member by a string the attacker controls.
--
-- Why the anon/authenticated path did not already leak this: v_worker_truth is security_invoker, so under
-- the caller's own role RLS on hive_members hides other hives' rows. But the edge functions call it on a
-- SERVICE-ROLE client (RLS bypassed) scoped only by the client-supplied hive_id — that is the whole reason
-- resolveTenancy exists — so for them the phantom membership row is fully visible.
--
-- THE FIX: resolve membership by the immutable `auth_uid`, which the signup trigger owns and no user can
-- change, instead of the mutable display_name. Proven behaviour-identical on current data: all 17 active
-- memberships carry a non-null auth_uid, and the name-keyed and auth_uid-keyed joins return the SAME 17 rows
-- today (0-row delta). So no legitimate resolution changes; only the rename attack is closed. The
-- active_hive_count subquery is re-keyed the same way for the same reason.
--
-- security_invoker is re-asserted explicitly: Arc G G4 set it via ALTER VIEW, and CREATE OR REPLACE must not
-- silently drop it (validate_view_security_invoker.py also guards this).

BEGIN;

CREATE OR REPLACE VIEW public.v_worker_truth
  WITH (security_invoker = true) AS
SELECT
  wp.auth_uid,
  wp.username,
  wp.display_name              AS worker_name,
  wp.email,
  wp.preferred_persona,
  wp.created_at                AS registered_at,
  hm.hive_id,
  hm.role,
  hm.joined_at                 AS hive_joined_at,
  hm.status                    AS hive_status,
  (hm.hive_id IS NULL)         AS is_solo,
  -- Count the caller's OWN active memberships, keyed on the immutable auth_uid. Keying this on
  -- display_name let a rename inflate someone else's account into it too.
  (SELECT count(*) FROM public.hive_members hm2
     WHERE hm2.auth_uid = wp.auth_uid AND hm2.status = 'active') AS active_hive_count
FROM public.worker_profiles wp
LEFT JOIN public.hive_members hm
       ON hm.auth_uid = wp.auth_uid
      AND hm.status    = 'active';

COMMENT ON VIEW public.v_worker_truth IS
  'Canonical worker identity + preferred_persona. Membership is resolved by auth_uid (immutable), NEVER by '
  'display_name (user-mutable) — see 20260731000001: the name-keyed join was a cross-tenant escalation a '
  'self-rename could drive. preferred_persona feeds every conversational AI surface per '
  'WORKHIVE_PERSONA_CONTRACT.md.';

COMMIT;
