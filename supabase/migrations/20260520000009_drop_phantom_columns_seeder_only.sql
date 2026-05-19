-- Drop 7 phantom columns whose only references are test seeders / static
-- schema validators — no application read or production write path.
--
-- Vetted 2026-05-20 via grep (excluding tools/ test-results/ node_modules):
--   approved_notes:  only test-data-seeder/seeders/amc.py writes
--   actual_start:    only test-data-seeder/seeders/projects.py writes
--   actual_end:      only test-data-seeder/seeders/projects.py writes
--   offset_value:    only test-data-seeder/seed_plant_connections_walkthrough.py
--   reserved_at:     only validate_schema_phantom.py allowlist (no reader)
--   screenshot_url:  zero references anywhere
--   sensor_type:     only test-data-seeder/seeders/sensor_readings.py writes
--
-- Each is a write-only / never-read phantom from a never-completed
-- feature (AMC approval notes UI, project actual-start/end tracking,
-- sensor classification, screenshot-attached feedback). Dropping them
-- recovers storage and removes confusing nullable columns from the
-- platform schema.

BEGIN;

ALTER TABLE IF EXISTS public.amc_briefings              DROP COLUMN IF EXISTS approved_notes;
ALTER TABLE IF EXISTS public.project_items              DROP COLUMN IF EXISTS actual_start;
ALTER TABLE IF EXISTS public.project_items              DROP COLUMN IF EXISTS actual_end;
ALTER TABLE IF EXISTS public.sensor_topic_map           DROP COLUMN IF EXISTS offset_value;
ALTER TABLE IF EXISTS public.parts_staged_reservations  DROP COLUMN IF EXISTS reserved_at;
ALTER TABLE IF EXISTS public.platform_feedback          DROP COLUMN IF EXISTS screenshot_url;
ALTER TABLE IF EXISTS public.sensor_readings            DROP COLUMN IF EXISTS sensor_type;

COMMIT;
