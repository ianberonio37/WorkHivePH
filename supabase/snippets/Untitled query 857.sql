-- Fix 1: Closed entries missing closed_at (use created_at as fallback)
UPDATE logbook
SET closed_at = created_at
WHERE status = 'Closed' AND closed_at IS NULL;

-- Fix 2: Open entries with closed_at accidentally set
UPDATE logbook
SET closed_at = NULL
WHERE status = 'Open' AND closed_at IS NOT NULL;

-- Fix 3: Clear <think>-leaked alerts (re-scan will regenerate clean)
DELETE FROM failure_signature_alerts
WHERE alert_detail ILIKE '%<think>%';
