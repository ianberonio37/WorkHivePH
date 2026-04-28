-- Add failure_consequence field to logbook
-- Maps to SAE JA1011 §5.4 consequence categories:
--   'Hidden'           → failure not evident during normal ops
--   'Running reduced'  → operational consequence, still running
--   'Safety risk'      → safety/environmental consequence
--   'Stopped production' → operational + economic consequence
-- NULL = not recorded (field is optional, legacy rows unaffected)

ALTER TABLE logbook
  ADD COLUMN IF NOT EXISTS failure_consequence text;
