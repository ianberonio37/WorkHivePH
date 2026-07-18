-- ============================================================================
-- "My people" — same-trade discovery (Community PDDA 7th, U-axis: belonging)
-- ----------------------------------------------------------------------------
-- A new member joins a hive and sees a wall of names, but not WHO shares their
-- trade. Belonging in a community-of-practice starts with "these are MY people —
-- they do what I do." This RPC surfaces hive-mates who share the caller's trade
-- (a discipline the caller holds at Practitioner+ / level >= 2), so community.html
-- can render a "People in your trade" cue with clickable person cards.
--
-- WHY A DEFINER RPC (build-the-structure, not covered-by-nature):
--   skill_badges RLS is `auth_uid = auth.uid()` (self-only) — a hive member
--   CANNOT read a peer's skill levels from the client, and v_worker_skill_truth
--   (SECURITY INVOKER) returns NULL levels for everyone but the caller. So the
--   trade-match is impossible client-side without a curated DEFINER path.
--
-- SAFETY MODEL (mirrors get_community_reputation):
--   * Authorization: the caller must be an ACTIVE member of p_hive_id (matched by
--     auth.uid()); a non-member / unauthenticated caller gets ZERO rows (fail
--     closed) — every CTE hangs off `caller`.
--   * Scope: peers are restricted to ACTIVE members of THIS hive; the join to
--     skill_badges is on the spoof-safe auth_uid key (worker_name is non-unique),
--     so no cross-hive skill data leaks in via a same-named person.
--   * Minimal exposure: returns ONLY worker_name, role, and the SHARED trades
--     (discipline + the peer's level in it) — never emails, never the peer's full
--     unrelated skill set, never a peer with no shared trade. Within-hive only;
--     hive-mates already see each other's names in the roster.
-- ============================================================================

CREATE OR REPLACE FUNCTION public.get_hive_trade_peers(p_hive_id uuid)
RETURNS TABLE (
  worker_name        text,
  role               text,
  shared_disciplines jsonb   -- [{discipline, level}] the caller & peer BOTH hold >= 2
)
LANGUAGE sql
SECURITY DEFINER
SET search_path TO ''
STABLE
AS $$
  WITH caller AS (
    -- authorization gate: the auth'd user must be an active member of this hive
    SELECT hm.auth_uid
    FROM public.hive_members hm
    WHERE hm.hive_id = p_hive_id
      AND hm.auth_uid = auth.uid()
      AND hm.status = 'active'
    LIMIT 1
  ),
  lvl AS (
    -- max badge level per (person, discipline); Practitioner+ only = a real "trade"
    SELECT auth_uid, discipline, max(level) AS level
    FROM public.skill_badges
    WHERE level >= 2 AND auth_uid IS NOT NULL
    GROUP BY auth_uid, discipline
  ),
  my_trades AS (
    SELECT l.discipline
    FROM lvl l JOIN caller c ON l.auth_uid = c.auth_uid
  ),
  peers AS (
    -- other active members of THIS hive (spoof-safe: matched later by auth_uid)
    SELECT hm.worker_name, hm.role, hm.auth_uid
    FROM public.hive_members hm CROSS JOIN caller c
    WHERE hm.hive_id = p_hive_id
      AND hm.status = 'active'
      AND hm.auth_uid IS NOT NULL
      AND hm.auth_uid IS DISTINCT FROM c.auth_uid
  )
  SELECT
    p.worker_name,
    p.role,
    jsonb_agg(jsonb_build_object('discipline', l.discipline, 'level', l.level)
              ORDER BY l.level DESC, l.discipline) AS shared_disciplines
  FROM peers p
  JOIN lvl l       ON l.auth_uid = p.auth_uid          -- peer's Practitioner+ trades
  JOIN my_trades m ON m.discipline = l.discipline       -- ...that overlap MY trades
  GROUP BY p.worker_name, p.role
  ORDER BY max(l.level) DESC, p.worker_name;
$$;

COMMENT ON FUNCTION public.get_hive_trade_peers(uuid) IS
  '"My people" same-trade discovery: hive-mates who share a Practitioner+ discipline with the caller. SECURITY DEFINER (skill_badges RLS is self-only); authz = active member of the hive, fail-closed; returns only worker_name/role/shared trades. Community PDDA 7th (U-axis belonging).';

GRANT EXECUTE ON FUNCTION public.get_hive_trade_peers(uuid) TO anon, authenticated;
