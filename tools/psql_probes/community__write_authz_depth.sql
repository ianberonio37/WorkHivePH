-- write_authz_depth (community, P-B, generated 2026-09-05 by tools/gen_write_authz_recipes.py): the hive-scoped
-- tables this page WRITES (community_posts, community_reactions, community_replies, hive_audit_log) must refuse a foreign hive in the DATABASE. A USING clause on
-- UPDATE/DELETE filters, so a no-op UPDATE (pk = pk) and a DELETE on a foreign hive's row must touch 0 rows; the
-- own-hive control must touch >= 1 where the write policy is hive-member ALL (owner/supervisor-scoped tables keep
-- only the refusal half and say so). Everything runs inside a rolled-back transaction; counts are re-checked after.
-- expect: community_posts_fixture \| t
-- expect: community_posts_foreign_update_touched \| (0\b|refused)
-- expect: community_posts_foreign_delete_touched \| (0\b|refused)
-- expect: community_posts_own_update_touched_gt0 \| t
-- expect: community_posts_move_into_foreign \| (0\b|refused|pinned)
-- forbid: community_posts_move_into_foreign \| [1-9]
-- expect: community_posts_rows_restored \| t
-- expect: community_reactions_fixture \| t
-- expect: community_reactions_foreign_update_touched \| (0\b|refused)
-- expect: community_reactions_foreign_delete_touched \| (0\b|refused)
-- expect: community_reactions_own_update_touched_gt0 \| t
-- expect: community_reactions_move_into_foreign \| (0\b|refused|pinned)
-- forbid: community_reactions_move_into_foreign \| [1-9]
-- expect: community_reactions_rows_restored \| t
-- expect: community_replies_fixture \| t
-- expect: community_replies_foreign_update_touched \| (0\b|refused)
-- expect: community_replies_foreign_delete_touched \| (0\b|refused)
-- expect: community_replies_own_update_touched_gt0 \| t
-- expect: community_replies_move_into_foreign \| (0\b|refused|pinned)
-- forbid: community_replies_move_into_foreign \| [1-9]
-- expect: community_replies_rows_restored \| t
-- expect: hive_audit_log_fixture \| t
-- expect: hive_audit_log_foreign_update_touched \| (0\b|refused)
-- expect: hive_audit_log_foreign_delete_touched \| (0\b|refused)
-- expect: hive_audit_log_move_into_foreign \| (0\b|refused|pinned)
-- forbid: hive_audit_log_move_into_foreign \| [1-9]
-- expect: hive_audit_log_rows_restored \| t

CREATE TEMP TABLE _wx_community_posts AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM community_posts x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM community_posts x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT x.hive_id FROM community_posts x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM community_posts) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM community_posts x WHERE x.hive_id = m.hive_id)
  -- a VALID foreign row exists for this member (an empty one manufactured a 'move into NULL', 2026-10-27)
  AND EXISTS (SELECT 1 FROM community_posts x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active'))
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.auth_uid = m.auth_uid)   -- by account, never by display name
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_community_posts TO authenticated;
SELECT 'community_posts_fixture | ' || ((SELECT me FROM _wx_community_posts) IS NOT NULL AND (SELECT foreign_row FROM _wx_community_posts) IS NOT NULL);
-- every write probe runs through ONE exception-safe function (2026-10-14): a refused write (42501, a missing grant, a
-- guard trigger) returns 'refused <SQLSTATE>' instead of aborting the rolled-back transaction and every probe after it
CREATE FUNCTION pg_temp.wx_try_community_posts(op text) RETURNS text LANGUAGE plpgsql AS $wx$
DECLARE n int;
BEGIN
  IF op = 'foreign_update' THEN UPDATE community_posts SET id = id WHERE id = (SELECT foreign_row FROM _wx_community_posts);
  ELSIF op = 'foreign_delete' THEN DELETE FROM community_posts WHERE id = (SELECT foreign_row FROM _wx_community_posts);
  ELSIF op = 'own_update' THEN UPDATE community_posts SET id = id WHERE id = (SELECT own_row FROM _wx_community_posts);
  ELSIF op = 'move' THEN UPDATE community_posts SET hive_id = (SELECT foreign_hive FROM _wx_community_posts) WHERE id = (SELECT own_row FROM _wx_community_posts);
    GET DIAGNOSTICS n = ROW_COUNT;
    -- ★A PINNING GUARD SAYS "1 ROW" AND MOVES NOTHING (2026-11-05): community_replies' authorship trigger keeps
    -- OLD.hive_id, so the UPDATE succeeds, touches the row, and the reply stays home - the row count was a stand-in
    -- for "the row landed in the foreign hive" that a BEFORE trigger breaks. The invariant is where the row SITS.
    -- Read as the member: still visible in their own hive = positively stayed. Invisible (moved, RLS-hidden) keeps
    -- the count and fails - so a hidden row can never read as safe. No RETURNING (a SELECT grant would refuse it).
    IF n > 0 AND EXISTS (SELECT 1 FROM community_posts x WHERE x.id = (SELECT own_row FROM _wx_community_posts) AND x.hive_id = (SELECT mine FROM _wx_community_posts)) THEN
      RETURN 'pinned (the row stayed in its own hive)';
    END IF;
    RETURN n::text;
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n::text;
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused 42501';
  WHEN others THEN RETURN 'refused ' || SQLSTATE;
END $wx$;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_community_posts)::text, 'role','authenticated')::text, true);
SELECT 'community_posts_foreign_update_touched | ' || pg_temp.wx_try_community_posts('foreign_update');
SELECT 'community_posts_foreign_delete_touched | ' || pg_temp.wx_try_community_posts('foreign_delete');
SELECT 'community_posts_move_into_foreign | ' || pg_temp.wx_try_community_posts('move');
SELECT 'community_posts_own_update_touched_gt0 | ' || (pg_temp.wx_try_community_posts('own_update') ~ '^[1-9]');
ROLLBACK;
SELECT 'community_posts_rows_restored | ' || ((SELECT count(*) FROM community_posts) = (SELECT n0 FROM _wx_community_posts));

CREATE TEMP TABLE _wx_community_reactions AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM community_reactions x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM community_reactions x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT x.hive_id FROM community_reactions x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM community_reactions) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM community_reactions x WHERE x.hive_id = m.hive_id)
  -- a VALID foreign row exists for this member (an empty one manufactured a 'move into NULL', 2026-10-27)
  AND EXISTS (SELECT 1 FROM community_reactions x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active'))
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.auth_uid = m.auth_uid)   -- by account, never by display name
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_community_reactions TO authenticated;
SELECT 'community_reactions_fixture | ' || ((SELECT me FROM _wx_community_reactions) IS NOT NULL AND (SELECT foreign_row FROM _wx_community_reactions) IS NOT NULL);
-- every write probe runs through ONE exception-safe function (2026-10-14): a refused write (42501, a missing grant, a
-- guard trigger) returns 'refused <SQLSTATE>' instead of aborting the rolled-back transaction and every probe after it
CREATE FUNCTION pg_temp.wx_try_community_reactions(op text) RETURNS text LANGUAGE plpgsql AS $wx$
DECLARE n int;
BEGIN
  IF op = 'foreign_update' THEN UPDATE community_reactions SET id = id WHERE id = (SELECT foreign_row FROM _wx_community_reactions);
  ELSIF op = 'foreign_delete' THEN DELETE FROM community_reactions WHERE id = (SELECT foreign_row FROM _wx_community_reactions);
  ELSIF op = 'own_update' THEN UPDATE community_reactions SET id = id WHERE id = (SELECT own_row FROM _wx_community_reactions);
  ELSIF op = 'move' THEN UPDATE community_reactions SET hive_id = (SELECT foreign_hive FROM _wx_community_reactions) WHERE id = (SELECT own_row FROM _wx_community_reactions);
    GET DIAGNOSTICS n = ROW_COUNT;
    -- ★A PINNING GUARD SAYS "1 ROW" AND MOVES NOTHING (2026-11-05): community_replies' authorship trigger keeps
    -- OLD.hive_id, so the UPDATE succeeds, touches the row, and the reply stays home - the row count was a stand-in
    -- for "the row landed in the foreign hive" that a BEFORE trigger breaks. The invariant is where the row SITS.
    -- Read as the member: still visible in their own hive = positively stayed. Invisible (moved, RLS-hidden) keeps
    -- the count and fails - so a hidden row can never read as safe. No RETURNING (a SELECT grant would refuse it).
    IF n > 0 AND EXISTS (SELECT 1 FROM community_reactions x WHERE x.id = (SELECT own_row FROM _wx_community_reactions) AND x.hive_id = (SELECT mine FROM _wx_community_reactions)) THEN
      RETURN 'pinned (the row stayed in its own hive)';
    END IF;
    RETURN n::text;
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n::text;
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused 42501';
  WHEN others THEN RETURN 'refused ' || SQLSTATE;
END $wx$;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_community_reactions)::text, 'role','authenticated')::text, true);
SELECT 'community_reactions_foreign_update_touched | ' || pg_temp.wx_try_community_reactions('foreign_update');
SELECT 'community_reactions_foreign_delete_touched | ' || pg_temp.wx_try_community_reactions('foreign_delete');
SELECT 'community_reactions_move_into_foreign | ' || pg_temp.wx_try_community_reactions('move');
SELECT 'community_reactions_own_update_touched_gt0 | ' || (pg_temp.wx_try_community_reactions('own_update') ~ '^[1-9]');
ROLLBACK;
SELECT 'community_reactions_rows_restored | ' || ((SELECT count(*) FROM community_reactions) = (SELECT n0 FROM _wx_community_reactions));

CREATE TEMP TABLE _wx_community_replies AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM community_replies x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM community_replies x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT x.hive_id FROM community_replies x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM community_replies) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM community_replies x WHERE x.hive_id = m.hive_id)
  -- a VALID foreign row exists for this member (an empty one manufactured a 'move into NULL', 2026-10-27)
  AND EXISTS (SELECT 1 FROM community_replies x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active'))
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.auth_uid = m.auth_uid)   -- by account, never by display name
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_community_replies TO authenticated;
SELECT 'community_replies_fixture | ' || ((SELECT me FROM _wx_community_replies) IS NOT NULL AND (SELECT foreign_row FROM _wx_community_replies) IS NOT NULL);
-- every write probe runs through ONE exception-safe function (2026-10-14): a refused write (42501, a missing grant, a
-- guard trigger) returns 'refused <SQLSTATE>' instead of aborting the rolled-back transaction and every probe after it
CREATE FUNCTION pg_temp.wx_try_community_replies(op text) RETURNS text LANGUAGE plpgsql AS $wx$
DECLARE n int;
BEGIN
  IF op = 'foreign_update' THEN UPDATE community_replies SET id = id WHERE id = (SELECT foreign_row FROM _wx_community_replies);
  ELSIF op = 'foreign_delete' THEN DELETE FROM community_replies WHERE id = (SELECT foreign_row FROM _wx_community_replies);
  ELSIF op = 'own_update' THEN UPDATE community_replies SET id = id WHERE id = (SELECT own_row FROM _wx_community_replies);
  ELSIF op = 'move' THEN UPDATE community_replies SET hive_id = (SELECT foreign_hive FROM _wx_community_replies) WHERE id = (SELECT own_row FROM _wx_community_replies);
    GET DIAGNOSTICS n = ROW_COUNT;
    -- ★A PINNING GUARD SAYS "1 ROW" AND MOVES NOTHING (2026-11-05): community_replies' authorship trigger keeps
    -- OLD.hive_id, so the UPDATE succeeds, touches the row, and the reply stays home - the row count was a stand-in
    -- for "the row landed in the foreign hive" that a BEFORE trigger breaks. The invariant is where the row SITS.
    -- Read as the member: still visible in their own hive = positively stayed. Invisible (moved, RLS-hidden) keeps
    -- the count and fails - so a hidden row can never read as safe. No RETURNING (a SELECT grant would refuse it).
    IF n > 0 AND EXISTS (SELECT 1 FROM community_replies x WHERE x.id = (SELECT own_row FROM _wx_community_replies) AND x.hive_id = (SELECT mine FROM _wx_community_replies)) THEN
      RETURN 'pinned (the row stayed in its own hive)';
    END IF;
    RETURN n::text;
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n::text;
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused 42501';
  WHEN others THEN RETURN 'refused ' || SQLSTATE;
END $wx$;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_community_replies)::text, 'role','authenticated')::text, true);
SELECT 'community_replies_foreign_update_touched | ' || pg_temp.wx_try_community_replies('foreign_update');
SELECT 'community_replies_foreign_delete_touched | ' || pg_temp.wx_try_community_replies('foreign_delete');
SELECT 'community_replies_move_into_foreign | ' || pg_temp.wx_try_community_replies('move');
SELECT 'community_replies_own_update_touched_gt0 | ' || (pg_temp.wx_try_community_replies('own_update') ~ '^[1-9]');
ROLLBACK;
SELECT 'community_replies_rows_restored | ' || ((SELECT count(*) FROM community_replies) = (SELECT n0 FROM _wx_community_replies));

CREATE TEMP TABLE _wx_hive_audit_log AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM hive_audit_log x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM hive_audit_log x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT x.hive_id FROM hive_audit_log x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM hive_audit_log) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM hive_audit_log x WHERE x.hive_id = m.hive_id)
  -- a VALID foreign row exists for this member (an empty one manufactured a 'move into NULL', 2026-10-27)
  AND EXISTS (SELECT 1 FROM hive_audit_log x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active'))
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.auth_uid = m.auth_uid)   -- by account, never by display name
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_hive_audit_log TO authenticated;
SELECT 'hive_audit_log_fixture | ' || ((SELECT me FROM _wx_hive_audit_log) IS NOT NULL AND (SELECT foreign_row FROM _wx_hive_audit_log) IS NOT NULL);
-- every write probe runs through ONE exception-safe function (2026-10-14): a refused write (42501, a missing grant, a
-- guard trigger) returns 'refused <SQLSTATE>' instead of aborting the rolled-back transaction and every probe after it
CREATE FUNCTION pg_temp.wx_try_hive_audit_log(op text) RETURNS text LANGUAGE plpgsql AS $wx$
DECLARE n int;
BEGIN
  IF op = 'foreign_update' THEN UPDATE hive_audit_log SET id = id WHERE id = (SELECT foreign_row FROM _wx_hive_audit_log);
  ELSIF op = 'foreign_delete' THEN DELETE FROM hive_audit_log WHERE id = (SELECT foreign_row FROM _wx_hive_audit_log);
  ELSIF op = 'own_update' THEN UPDATE hive_audit_log SET id = id WHERE id = (SELECT own_row FROM _wx_hive_audit_log);
  ELSIF op = 'move' THEN UPDATE hive_audit_log SET hive_id = (SELECT foreign_hive FROM _wx_hive_audit_log) WHERE id = (SELECT own_row FROM _wx_hive_audit_log);
    GET DIAGNOSTICS n = ROW_COUNT;
    -- ★A PINNING GUARD SAYS "1 ROW" AND MOVES NOTHING (2026-11-05): community_replies' authorship trigger keeps
    -- OLD.hive_id, so the UPDATE succeeds, touches the row, and the reply stays home - the row count was a stand-in
    -- for "the row landed in the foreign hive" that a BEFORE trigger breaks. The invariant is where the row SITS.
    -- Read as the member: still visible in their own hive = positively stayed. Invisible (moved, RLS-hidden) keeps
    -- the count and fails - so a hidden row can never read as safe. No RETURNING (a SELECT grant would refuse it).
    IF n > 0 AND EXISTS (SELECT 1 FROM hive_audit_log x WHERE x.id = (SELECT own_row FROM _wx_hive_audit_log) AND x.hive_id = (SELECT mine FROM _wx_hive_audit_log)) THEN
      RETURN 'pinned (the row stayed in its own hive)';
    END IF;
    RETURN n::text;
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n::text;
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused 42501';
  WHEN others THEN RETURN 'refused ' || SQLSTATE;
END $wx$;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_hive_audit_log)::text, 'role','authenticated')::text, true);
SELECT 'hive_audit_log_foreign_update_touched | ' || pg_temp.wx_try_hive_audit_log('foreign_update');
SELECT 'hive_audit_log_foreign_delete_touched | ' || pg_temp.wx_try_hive_audit_log('foreign_delete');
SELECT 'hive_audit_log_move_into_foreign | ' || pg_temp.wx_try_hive_audit_log('move');
ROLLBACK;
SELECT 'hive_audit_log_rows_restored | ' || ((SELECT count(*) FROM hive_audit_log) = (SELECT n0 FROM _wx_hive_audit_log));
