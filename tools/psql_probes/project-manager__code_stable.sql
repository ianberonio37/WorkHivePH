-- code_stable: a project code is a stable identifier — unique within its hive, and every code
-- matches the CODE-#### shape a person can quote.
-- expect: projects \| [1-9][0-9]*
-- expect: duplicate_codes_in_hive \| 0
-- expect: malformed_codes \| 0
SELECT 'projects | ' || count(*) FROM projects;
SELECT 'duplicate_codes_in_hive | ' || count(*) FROM (
  SELECT hive_id, project_code FROM projects GROUP BY hive_id, project_code HAVING count(*) > 1) d;
SELECT 'malformed_codes | ' || count(*) FROM projects
WHERE project_code !~ '^[A-Z]{2,4}-[0-9]{4}-[0-9]{3}$';
