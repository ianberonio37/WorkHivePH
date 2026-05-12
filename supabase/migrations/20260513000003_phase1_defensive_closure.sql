-- Phase 1 of STRATEGIC_ROADMAP — Defensive Closure (security + DT hygiene).
--
-- Closes 3 long-standing gaps the Guardian validators have flagged:
--
--   1. Knowledge-base RLS (data_governance WARN)
--      fault_knowledge / skill_knowledge / pm_knowledge had zero RLS
--      policies, meaning the anon key could read every hive's knowledge
--      OR inject poison rows. This is the single highest-leverage
--      security fix in the platform.
--
--   2. Asset lifecycle state machine (digital_twin WARN)
--      asset_nodes lacked a lifecycle column. MTBF and predictive
--      models therefore silently included decommissioned equipment in
--      the population. Add 'active' | 'inactive' | 'decommissioned'
--      with default 'active' so existing rows stay live.
--
--   3. Asset FK on pm_knowledge (digital_twin WARN)
--      pm_knowledge.asset_id had no REFERENCES, so orphan rows could
--      accumulate as assets were deleted. Add a NOT VALID FK to
--      asset_nodes(id) ON DELETE SET NULL. NOT VALID skips backfill
--      validation; future writes are enforced. A follow-on VALIDATE
--      pass can run when the operator confirms data is clean.
--
-- Skills consulted:
--   security (RLS hive-membership-join pattern from validate_tenant_boundary)
--   multitenant-engineer (hive_members JOIN, never raw hive_id eq)
--   architect (lifecycle CHECK constraint, NOT VALID FK pattern)
--   data-engineer (default 'active' so all existing rows are valid;
--     no migration backfill required)
--   knowledge-manager (knowledge tables are read by RAG; RLS must allow
--     hive-scoped read by active members only, never anon)
--   enterprise-compliance (audit-log gap for member_joined is in hive.html,
--     not here — see Phase 1.2 JS edit)

BEGIN;

-- ────────────────────────────────────────────────────────────────────────────
-- 1. Knowledge-base RLS lock-down
-- ────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.fault_knowledge  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.skill_knowledge  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pm_knowledge     ENABLE ROW LEVEL SECURITY;

-- Read: any active hive member can read their hive's knowledge corpus
DROP POLICY IF EXISTS fault_knowledge_read ON public.fault_knowledge;
CREATE POLICY fault_knowledge_read ON public.fault_knowledge FOR SELECT
  USING (
    auth.uid() IS NOT NULL
    AND hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  );

DROP POLICY IF EXISTS skill_knowledge_read ON public.skill_knowledge;
CREATE POLICY skill_knowledge_read ON public.skill_knowledge FOR SELECT
  USING (
    auth.uid() IS NOT NULL
    AND hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  );

DROP POLICY IF EXISTS pm_knowledge_read ON public.pm_knowledge;
CREATE POLICY pm_knowledge_read ON public.pm_knowledge FOR SELECT
  USING (
    auth.uid() IS NOT NULL
    AND hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  );

-- Insert: client cannot directly insert. The embed-entry edge function
-- writes as service-role (bypasses RLS). Anon / authenticated insert is
-- blocked at the policy layer.
DROP POLICY IF EXISTS fault_knowledge_insert_locked ON public.fault_knowledge;
CREATE POLICY fault_knowledge_insert_locked ON public.fault_knowledge FOR INSERT
  WITH CHECK (false);

DROP POLICY IF EXISTS skill_knowledge_insert_locked ON public.skill_knowledge;
CREATE POLICY skill_knowledge_insert_locked ON public.skill_knowledge FOR INSERT
  WITH CHECK (false);

DROP POLICY IF EXISTS pm_knowledge_insert_locked ON public.pm_knowledge;
CREATE POLICY pm_knowledge_insert_locked ON public.pm_knowledge FOR INSERT
  WITH CHECK (false);

-- Update / Delete: locked entirely for non-service-role.
DROP POLICY IF EXISTS fault_knowledge_update_locked ON public.fault_knowledge;
CREATE POLICY fault_knowledge_update_locked ON public.fault_knowledge FOR UPDATE
  USING (false) WITH CHECK (false);

DROP POLICY IF EXISTS fault_knowledge_delete_locked ON public.fault_knowledge;
CREATE POLICY fault_knowledge_delete_locked ON public.fault_knowledge FOR DELETE
  USING (false);

DROP POLICY IF EXISTS skill_knowledge_update_locked ON public.skill_knowledge;
CREATE POLICY skill_knowledge_update_locked ON public.skill_knowledge FOR UPDATE
  USING (false) WITH CHECK (false);

DROP POLICY IF EXISTS skill_knowledge_delete_locked ON public.skill_knowledge;
CREATE POLICY skill_knowledge_delete_locked ON public.skill_knowledge FOR DELETE
  USING (false);

DROP POLICY IF EXISTS pm_knowledge_update_locked ON public.pm_knowledge;
CREATE POLICY pm_knowledge_update_locked ON public.pm_knowledge FOR UPDATE
  USING (false) WITH CHECK (false);

DROP POLICY IF EXISTS pm_knowledge_delete_locked ON public.pm_knowledge;
CREATE POLICY pm_knowledge_delete_locked ON public.pm_knowledge FOR DELETE
  USING (false);

-- GRANT SELECT explicitly so authenticated role can read through RLS.
-- INSERT/UPDATE/DELETE intentionally NOT granted at the GRANT layer
-- (extra defence; the policies above already block them).
GRANT SELECT ON public.fault_knowledge TO anon, authenticated;
GRANT SELECT ON public.skill_knowledge TO anon, authenticated;
GRANT SELECT ON public.pm_knowledge    TO anon, authenticated;

-- ────────────────────────────────────────────────────────────────────────────
-- 2. Asset lifecycle state machine on asset_nodes
-- ────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.asset_nodes
  ADD COLUMN IF NOT EXISTS lifecycle text NOT NULL DEFAULT 'active'
  CHECK (lifecycle IN ('active', 'inactive', 'decommissioned'));

COMMENT ON COLUMN public.asset_nodes.lifecycle IS
  'Asset lifecycle state. Default ''active''. Predictive analytics, MTBF, OEE, and the AMC daily brief should filter to lifecycle=''active'' to avoid including retired equipment in the population.';

-- Index so the dominant query "active assets per hive" stays fast as
-- the inactive / decommissioned set grows.
CREATE INDEX IF NOT EXISTS idx_asset_nodes_hive_lifecycle
  ON public.asset_nodes (hive_id, lifecycle)
  WHERE lifecycle = 'active';

-- ────────────────────────────────────────────────────────────────────────────
-- 3. pm_knowledge.asset_id FK to asset_nodes(id)
-- ────────────────────────────────────────────────────────────────────────────
-- NOT VALID skips the backfill check, so existing dangling rows don't
-- break the migration. Future inserts are enforced. A separate VALIDATE
-- pass can run later when the operator confirms data is clean.

ALTER TABLE public.pm_knowledge
  DROP CONSTRAINT IF EXISTS pm_knowledge_asset_id_fkey;

ALTER TABLE public.pm_knowledge
  ADD CONSTRAINT pm_knowledge_asset_id_fkey
  FOREIGN KEY (asset_id) REFERENCES public.asset_nodes(id) ON DELETE SET NULL
  NOT VALID;

-- ────────────────────────────────────────────────────────────────────────────
-- 4. Canonical-source registration: knowledge tables are now hardened
-- ────────────────────────────────────────────────────────────────────────────
-- Document the lock-down in canonical_sources so any AI agent asking
-- "where is fault history stored?" gets the contract that says
-- "fault_knowledge, hive-scoped, anon CANNOT insert."

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES
  ('fault_knowledge_corpus', 'table', 'fault_knowledge',
   'knowledge-manager', 'realtime',
   'RAG knowledge base for fault history. Read by semantic-search edge function for fault recall. Lock down 2026-05-13 (Phase 1.1): hive-membership read, anon cannot insert/update/delete.',
   jsonb_build_object(
     'key', jsonb_build_array('id'),
     'hive_scoped', true,
     'read_policy', 'auth.uid() in active hive_members',
     'write_policy', 'service-role only (embed-entry edge fn)',
     'phase_1_hardened', true
   ),
   'Phase 1.1 of STRATEGIC_ROADMAP — RLS lock-down closes the data_governance WARN.'),

  ('skill_knowledge_corpus', 'table', 'skill_knowledge',
   'knowledge-manager', 'realtime',
   'RAG knowledge base for worker skill profiles. Read by semantic-search edge function for "best worker for this job" recall. Lock down 2026-05-13 (Phase 1.1).',
   jsonb_build_object(
     'key', jsonb_build_array('id'),
     'hive_scoped', true,
     'read_policy', 'auth.uid() in active hive_members',
     'write_policy', 'service-role only',
     'phase_1_hardened', true
   ),
   'Phase 1.1 of STRATEGIC_ROADMAP — RLS lock-down.'),

  ('pm_knowledge_corpus', 'table', 'pm_knowledge',
   'knowledge-manager', 'realtime',
   'RAG knowledge base for PM health snapshots. Read by semantic-search edge function for PM-related recall. Lock down 2026-05-13 (Phase 1.1). Asset FK added in same migration.',
   jsonb_build_object(
     'key', jsonb_build_array('id'),
     'hive_scoped', true,
     'read_policy', 'auth.uid() in active hive_members',
     'write_policy', 'service-role only',
     'asset_id_fk', 'asset_nodes(id) NOT VALID',
     'phase_1_hardened', true
   ),
   'Phase 1.1 + 1.4 of STRATEGIC_ROADMAP — RLS lock-down + asset FK.')
ON CONFLICT (domain) DO UPDATE
  SET source_kind   = EXCLUDED.source_kind,
      source_name   = EXCLUDED.source_name,
      owner_skill   = EXCLUDED.owner_skill,
      freshness     = EXCLUDED.freshness,
      description   = EXCLUDED.description,
      contract      = EXCLUDED.contract,
      notes         = EXCLUDED.notes,
      registered_at = now();

COMMIT;
