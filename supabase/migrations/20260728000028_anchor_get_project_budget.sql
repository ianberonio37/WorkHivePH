-- ─────────────────────────────────────────────────────────────────────────────
-- Register get_project_budget in canonical_sources.
--
-- THIS EXISTS BECAUSE I BROKE A RULE. The registration was originally APPENDED to
-- 20260728000023 *after* that migration had already been committed and applied. The
-- migration-immutability gate caught it, correctly: a committed migration may already have run
-- somewhere else, so editing it means two environments silently disagree about what
-- `20260728000023` contains. The fix for "I forgot something in a migration" is always a NEW
-- migration, never an edit to the old one. ...023 has been restored to its first-committed
-- content and the addition lives here.
--
-- The registration itself is the same-change rule from the arc doctrine: a `get_*` RPC is an
-- ENGINE-layer item and the canonical-anchor gate counts it as un-anchored until it is registered.
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO public.canonical_sources
  (domain, source_kind, source_name, owner_skill, freshness, contract, description, notes)
VALUES (
  'get_project_budget_rpc', 'rpc', 'get_project_budget', 'architect', 'on_demand',
  '{"signature": "get_project_budget(p_project_id uuid) RETURNS jsonb", "side_effects": []}'::jsonb,
  'Supervisor-only read of projects.budget_php plus the start/end dates Earned Value needs. Exists '
  'because RLS is ROW-level and cannot withhold one column of a row a member may otherwise read. '
  'Returns {ok:false, reason:''not a supervisor''} with a stated detail rather than a null, so a '
  'refusal is never mistaken for "this project has no budget".',
  'PJ9, 2026-07-28. Paired with 20260728000024, which drops the table-wide SELECT grant and '
  're-grants every column except budget_php - a column-level REVOKE alone is a no-op while a '
  'table-level grant stands.'
)
ON CONFLICT (domain) DO UPDATE
  SET source_kind = EXCLUDED.source_kind, source_name = EXCLUDED.source_name,
      owner_skill = EXCLUDED.owner_skill, freshness = EXCLUDED.freshness,
      contract = EXCLUDED.contract, description = EXCLUDED.description, notes = EXCLUDED.notes;
