-- =====================================================================
-- SERVICE HAILING · the MONEY tables get their Engine views
-- =====================================================================
-- The user-facing-KPI-canonical gate caught the arc breaking its OWN §1 rule
-- ("Dashboard NEVER reads Fuel raw"): the founder queue read `service_credit_topups`
-- directly and the provider wallet read `service_credit_ledger` directly. Two readers
-- on topups is exactly the gate's option (2) - build the wrapper - and for MONEY the
-- wrapper is worth more than a `canonical-allow` marker anyway: it re-asserts the
-- boundary in one place instead of trusting every page's filter.
--
-- House pattern (mig 40): views are WITH (security_invoker = false) - owner's rights -
-- so each view MUST re-assert the row boundary its base table's RLS would have applied.
-- Both predicates below are copied from the base policies in mig 39 verbatim:
--   ledger_own:  consumer=auth.uid() OR provider in my_service_provider_ids() OR admin
--   topups_own:  payer_auth_uid = auth.uid() OR admin
-- Writes are UNCHANGED and still go to the Fuel tables (topup intake insert, admin
-- verify update) - a view is a READ path only; the mint stays on the guard trigger.

-- =============================================
-- 1. v_service_credit_topups_truth - the GCash verification queue + a payer's own filings
-- =============================================
drop view if exists public.v_service_credit_topups_truth;
create view public.v_service_credit_topups_truth
with (security_invoker = false) as
select
  t.id,
  t.account_type,
  t.account_id,
  t.payer_auth_uid,
  t.amount,
  t.gcash_ref,
  t.status,
  t.verified_at,
  t.verified_by,
  t.note,
  t.created_at,
  -- provider display name folded in so the founder queue stops N+1-ing the directory
  sp.display_name as provider_display_name,
  -- canonical truth-view signal-trust contract
  1 as _source_count,
  t.created_at as _freshness_ts,
  'service_credit_topups_truth:v1' as _canonical_version
from public.service_credit_topups t
left join public.service_providers sp
  on t.account_type = 'provider' and sp.id = t.account_id
where t.payer_auth_uid = auth.uid()
   or public.is_marketplace_admin();
comment on view public.v_service_credit_topups_truth is
  'Top-up truth: a payer sees only their own filings; a marketplace admin sees the whole verification queue (mirrors service_credit_topups_own). Read path only - intake INSERT and the admin verify UPDATE stay on the Fuel table so the mint trigger keeps firing.';

-- =============================================
-- 2. v_service_credit_ledger_truth - append-only money history, own account only
-- =============================================
drop view if exists public.v_service_credit_ledger_truth;
create view public.v_service_credit_ledger_truth
with (security_invoker = false) as
select
  l.id,
  l.account_type,
  l.account_id,
  l.entry_type,
  l.amount,
  l.ref_kind,
  l.ref_id,
  l.note,
  l.created_at,
  -- canonical truth-view signal-trust contract
  1 as _source_count,
  l.created_at as _freshness_ts,
  'service_credit_ledger_truth:v1' as _canonical_version
from public.service_credit_ledger l
where (l.account_type = 'consumer' and l.account_id = auth.uid())
   or (l.account_type = 'provider' and l.account_id in (select public.my_service_provider_ids()))
   or public.is_marketplace_admin();
comment on view public.v_service_credit_ledger_truth is
  'Credit ledger truth: own account only (mirrors service_credit_ledger_own). The ledger is append-only with NO client write path - balance is SUM(ledger) via provider_credit_balance(); this view is history display only.';

-- =============================================
-- 3. Grants (authenticated only - money is never anon-readable)
-- =============================================
grant select on public.v_service_credit_topups_truth to authenticated;
grant select on public.v_service_credit_ledger_truth to authenticated;

-- =============================================
-- 4. Canonical registry anchors (mig 41 pattern)
-- =============================================
INSERT INTO public.canonical_sources
  (domain, source_kind, source_name, owner_skill, freshness, contract, description)
VALUES
  ('service_hailing', 'view', 'v_service_credit_topups_truth', 'marketplace', 'on_demand',
   '{"key": ["id"], "boundary": "payer_auth_uid = auth.uid() OR is_marketplace_admin() — re-asserted because the view is security_invoker=false", "writes": "none; intake INSERT + admin verify UPDATE stay on service_credit_topups so the mint trigger fires"}'::jsonb,
   'GCash top-up verification queue (admin) + a payer''s own filings, with the provider display name folded in.'),
  ('service_hailing', 'view', 'v_service_credit_ledger_truth', 'marketplace', 'on_demand',
   '{"key": ["id"], "append_only": true, "boundary": "own consumer account OR own provider ids OR admin", "balance": "NOT from this view — provider_credit_balance() is the balance truth"}'::jsonb,
   'Credit ledger history for the owning account; display-only read path over the append-only money ledger.')
ON CONFLICT DO NOTHING;
