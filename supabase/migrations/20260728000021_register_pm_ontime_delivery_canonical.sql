-- ─────────────────────────────────────────────────────────────────────────────
-- Register get_pm_ontime_delivery in canonical_sources. It shipped un-anchored.
--
-- The canonical-anchor gate caught this on the release run (2026-07-28): the engine layer's
-- un-anchored count went 2 -> 3, and the new item was `get_pm_ontime_delivery`, added by
-- 20260728000005 during the PM Scheduler arc. The arc's own rule — "new DB functions, validators,
-- RPCs and write tables need their registration in the SAME change" — was not followed for it.
--
-- WHY THIS ONE MATTERS MORE THAN MOST. It exists because the platform's PM compliance number was
-- answering a different question than its label implied: `get_pm_compliance_smrp` reports the share
-- of PMs COMPLETED, and 27% of intervals ran LATE while that figure read 85-87%. This RPC is the
-- missing half — on-time DELIVERY — so an un-anchored engine function here is precisely the kind
-- that drifts away from the number it was built to correct.
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO public.canonical_sources
  (domain, source_kind, source_name, owner_skill, freshness, contract, description, notes)
VALUES (
  'get_pm_ontime_delivery_rpc',
  'rpc',
  'get_pm_ontime_delivery',
  'maintenance-expert',
  'on_demand',
  -- contract is JSONB (verified against the column type and a sibling row), and the signature is
  -- the REAL one from pg_get_function_identity_arguments, not one written from memory.
  '{"signature": "get_pm_ontime_delivery(p_hive_id uuid, p_period_days integer) RETURNS jsonb",
    "side_effects": []}'::jsonb,
  'On-time PM DELIVERY: the share of scheduled PM intervals whose completion landed on or before '
  'the interval''s due date. Distinct from get_pm_compliance_smrp, which reports the share COMPLETED '
  'regardless of when — measured during the PM Scheduler deepwalk, 27% of intervals ran late while '
  'the compliance figure read 85-87%, so the two are answering different questions and both are '
  'needed to describe a programme honestly.',
  'Added by 20260728000005 (PM deepwalk PM7/PMK1); registered here 2026-07-28 after the '
  'canonical-anchor gate caught it shipping un-anchored.'
)
ON CONFLICT (domain) DO UPDATE
  SET source_kind = EXCLUDED.source_kind,
      source_name = EXCLUDED.source_name,
      owner_skill = EXCLUDED.owner_skill,
      freshness   = EXCLUDED.freshness,
      contract    = EXCLUDED.contract,
      description = EXCLUDED.description,
      notes       = EXCLUDED.notes;
