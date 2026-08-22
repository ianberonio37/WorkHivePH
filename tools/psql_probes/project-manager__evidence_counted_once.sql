-- evidence_counted_once: a linked record counts toward a project ONCE — the partial unique index
-- (project_id, link_type, link_id) refuses the duplicate (23505) while a distinct link is accepted;
-- rollback restores the count.
-- expect: dedup_index_live \| t
-- expect: duplicate key value violates unique constraint
-- expect: distinct_link_accepted \| t
-- expect: restored \| t
SELECT 'dedup_index_live | ' || EXISTS (
  SELECT 1 FROM pg_indexes WHERE indexname = 'project_links_target_uidx');
CREATE TEMP TABLE _ec AS
SELECT pl.project_id, pl.hive_id, pl.link_type, pl.link_id,
       (SELECT count(*) FROM project_links) AS n0
FROM project_links pl WHERE pl.link_id IS NOT NULL LIMIT 1;
BEGIN;
INSERT INTO project_links (project_id, hive_id, link_type, link_id)
SELECT project_id, hive_id, link_type, link_id FROM _ec;
ROLLBACK;
BEGIN;
INSERT INTO project_links (project_id, hive_id, link_type, link_id)
SELECT project_id, hive_id, link_type, gen_random_uuid() FROM _ec;
SELECT 'distinct_link_accepted | ' || ((SELECT count(*) FROM project_links) = (SELECT n0 + 1 FROM _ec));
ROLLBACK;
SELECT 'restored | ' || ((SELECT count(*) FROM project_links) = (SELECT n0 FROM _ec));
DROP TABLE _ec;
