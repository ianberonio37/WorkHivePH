-- Adds asset_nodes.ideal_cycle_time_seconds — the Performance-factor
-- fuel field that unlocks full OEE (Availability × Performance × Quality)
-- per ISO 22400-2:2014 / Nakajima TPM.
--
-- Capture contract: asset_ideal_cycle_time (Tier F).
-- Consumed by: get_oee_by_machine RPC, python-api descriptive.calc_oee,
--              analytics.html renderOEE.
--
-- The field is NULLable on purpose — assets that don't have a planned
-- rate (e.g. job-shop equipment with variable cycle times) keep returning
-- the partial OEE (A × Q). When the value lands, the RPC flips to full.
--
-- Unit: seconds-per-unit produced. The cycle-time convention matches
-- ISO 22400-2 §3.4.18 (planned operation cycle time). A canning line
-- doing 600 cans/hour has ideal_cycle_time_seconds = 6.

BEGIN;

ALTER TABLE public.asset_nodes
  ADD COLUMN IF NOT EXISTS ideal_cycle_time_seconds numeric
  CHECK (ideal_cycle_time_seconds IS NULL OR ideal_cycle_time_seconds > 0);

COMMENT ON COLUMN public.asset_nodes.ideal_cycle_time_seconds IS
  'Seconds per unit at planned (ideal) cycle. NULL = no planned rate captured; OEE falls back to partial (Availability x Quality). When set, get_oee_by_machine returns full OEE (A x P x Q) per ISO 22400-2:2014.';

COMMIT;
