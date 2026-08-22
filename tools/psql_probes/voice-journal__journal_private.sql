-- journal_private: the journal is PRIVATE to its author — even a supervisor sees only their own
-- entries. Control proves foreign entries exist; under an author's ROLE + claims, zero foreign
-- rows are visible.
-- expect: control_sees_foreign \| t
-- expect: author_sees_none_foreign \| t
CREATE TEMP TABLE _jp AS
SELECT v.auth_uid,
       (SELECT count(*) FROM voice_journal_entries x WHERE x.auth_uid <> v.auth_uid) AS foreign_n
FROM voice_journal_entries v GROUP BY v.auth_uid ORDER BY count(*) DESC LIMIT 1;
GRANT SELECT ON _jp TO authenticated;
SELECT 'control_sees_foreign | ' || ((SELECT foreign_n FROM _jp) > 0);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT auth_uid FROM _jp)::text, 'role', 'authenticated')::text, true);
SELECT 'author_sees_none_foreign | ' ||
  ((SELECT count(*) FROM voice_journal_entries
     WHERE auth_uid <> (SELECT auth_uid FROM _jp)) = 0);
ROLLBACK;
DROP TABLE _jp;
