INSERT INTO fault_knowledge 
  (hive_id, logbook_id, machine, category, problem, root_cause, action, knowledge, worker_name)
SELECT 
  hive_id, id, machine, category, problem, root_cause, action, knowledge, worker_name
FROM logbook
WHERE hive_id = (SELECT id FROM hives WHERE name = 'Pacific Food Industries Corp.')
  AND (problem IS NOT NULL OR action IS NOT NULL OR root_cause IS NOT NULL)
ON CONFLICT DO NOTHING;
