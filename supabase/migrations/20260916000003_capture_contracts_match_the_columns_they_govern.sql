-- Two capture contracts describe a vocabulary their own column cannot hold. Neither has ever fired,
-- because no page calls whValidateCapture for them - which is the only reason this has gone
-- unnoticed, and exactly why it must be fixed BEFORE anyone wires one, not after.
--
-- Found by tools/prove_capture_enums_cover_the_data.py on its first live run (2026-09-16), which
-- compares every contract enum against SELECT DISTINCT on the column it governs. Five mismatches;
-- these are the two the gate classifies LATENT (no caller). The other three are on
-- schedule_item_v1 / logbook_add_entry_v1 and are handled by 20260916000001 and 20260916000002.
--
-- ─────────────────────────────────────────────────────────────────────────────────────────────
-- 1. asset_wizard_v1.criticality - AN UNSATISFIABLE CONTRACT.
--
-- The contract declares:      ["Critical", "High", "Medium", "Low"]
-- The table enforces:         CHECK (criticality = ANY (ARRAY['low','medium','high','critical']))
--                             (constraint asset_nodes_criticality_check)
--
-- These do not merely disagree about today's data - they cannot BOTH be satisfied by any value.
-- A payload the contract accepts is rejected by the database with 23514; a payload the database
-- accepts is rejected by the contract. Wiring the validator onto asset-hub.html would make the
-- asset wizard unable to save anything at all, in either direction.
--
-- All 125 rows are lowercase (medium 79, high 17, critical 17, low 12) and not one is Title-case,
-- which is the CHECK constraint doing its job. The seeder chain agrees: test-data-seeder builds the
-- payload with Title-case labels and asset_brain.py maps them down (`crit_map.get(...) -> "medium"`)
-- immediately before the insert. asset-hub.html reads the column case-insensitively throughout
-- (.ilike('criticality','critical'), String(n.criticality).toLowerCase()) and upper-cases only for
-- DISPLAY. So lowercase is the stored truth on every path, and the CHECK constraint is the
-- authority the contract must agree with.
--
-- ─────────────────────────────────────────────────────────────────────────────────────────────
-- 2. cmms_import_v1.system_type - THE CONTRACT FORBIDS WHAT THE SHIPPING PAGE WRITES.
--
-- The contract declares:      ["maximo", "emaint", "fiix", "upkeep", "custom"]
-- integrations.html offers:   <option value="sap_pm">, <option value="maximo">, <option value="generic">
--                             and writes `_systemType === 'auto' ? 'generic' : _systemType`
--
-- Two of the three values the page can actually produce - `sap_pm` and `generic` - are absent from
-- the contract, while three vendors it does list (emaint, fiix, upkeep) appear in no <option> on any
-- page. A contract that forbids what a shipping surface writes is wrong regardless of what one
-- thinks of the vendor list, so the two the page emits are ADDED. The three unused vendor names are
-- KEPT: they cost nothing, they are already reported as "declares ... with no rows yet (fine)", and
-- removing them would decide a roadmap question this migration has no business deciding.
--
-- NOT FIXED HERE, AND DELIBERATELY LEFT VISIBLE: external_sync holds 14 rows spelled `SAP_PM` (9)
-- and `Fiix` (5) - fixture casing from the CMMS import test path, not from the page, which writes
-- lowercase. Normalising them is a separate question about test data, and there is no CHECK
-- constraint on system_type to arbitrate it. The gate will keep reporting them as LATENT, which is
-- the correct state for a real mismatch nobody is blocked by: visible, counted, and not quietly
-- absorbed by widening an enum until the board turns green.
--
-- Forward-only and idempotent: both statements set an absolute array, so re-running writes the same
-- value. Each touches exactly one row of canonical_capture_contracts and no application row.

-- 1. criticality: agree with asset_nodes_criticality_check, which is the real gate.
UPDATE public.canonical_capture_contracts
SET
  contract_schema = jsonb_set(
    contract_schema,
    '{properties,criticality,enum}',
    '["low","medium","high","critical"]'::jsonb
  ),
  fields = (
    SELECT jsonb_agg(
      CASE WHEN elem->>'name' = 'criticality'
        THEN elem || '{"values":["low","medium","high","critical"]}'::jsonb
        ELSE elem
      END
    )
    FROM jsonb_array_elements(fields) elem
  )
WHERE capture_id = 'asset_wizard_v1';

-- 2. system_type: cover the two values integrations.html can actually emit.
UPDATE public.canonical_capture_contracts
SET
  contract_schema = jsonb_set(
    contract_schema,
    '{properties,system_type,enum}',
    '["sap_pm","maximo","generic","emaint","fiix","upkeep","custom"]'::jsonb
  ),
  fields = (
    SELECT jsonb_agg(
      CASE WHEN elem->>'name' = 'system_type'
        THEN elem || '{"values":["sap_pm","maximo","generic","emaint","fiix","upkeep","custom"]}'::jsonb
        ELSE elem
      END
    )
    FROM jsonb_array_elements(fields) elem
  )
WHERE capture_id = 'cmms_import_v1';

-- Proof the unsatisfiable contract is gone: every value the CHECK constraint permits must now be a
-- member of the contract enum. This is the assertion that would have caught the original defect.
DO $$
DECLARE missing text;
BEGIN
  SELECT string_agg(v, ', ') INTO missing
  FROM unnest(ARRAY['low','medium','high','critical']) AS v
  WHERE NOT (to_jsonb(v) <@ (
    SELECT contract_schema->'properties'->'criticality'->'enum'
    FROM public.canonical_capture_contracts WHERE capture_id = 'asset_wizard_v1'
  ));
  IF missing IS NOT NULL THEN
    RAISE EXCEPTION 'asset_wizard_v1 still forbids criticality value(s) the table permits: %', missing;
  END IF;
END $$;
