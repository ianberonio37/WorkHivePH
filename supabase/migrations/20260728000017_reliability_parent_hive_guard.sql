-- ─────────────────────────────────────────────────────────────────────────────
-- A reliability row's PARENT must live in the same hive as the row claims to.
--
-- FOUND BY THE AH13 WALK (2026-07-28, ASSET_HUB_DEEPWALK_EXPANSION_ROADMAP):
-- the same child/parent gap PM13 found in pm_completions, now on the four reliability tables. The
-- WITH CHECK validates that `hive_id` is one the caller belongs to, and says nothing about whether
-- the PARENT it points at lives there. Probed live, both accepted:
--
--   rcm_fmea_modes  hive_id = MINE, asset_id      = another hive's asset node
--   rcm_strategies  hive_id = MINE, fmea_mode_id  = another hive's failure mode
--
-- SEVERITY, MEASURED RATHER THAN ASSUMED — and it is genuinely lower than PM13's. There the
-- injected completion CREDITED the foreign hive, because get_pm_compliance_smrp joins by
-- scope_item_id regardless of hive (502 -> 503 measured). Here every reliability view filters by
-- hive_id, so the victim sees nothing: reading v_fmea_truth AS a member of the target hive returns
-- 0 rows for an injected severity-10 mode. What the attacker actually achieves is pollution of
-- THEIR OWN hive with a phantom row pointing at an asset they cannot see.
--
-- SO WHY FIX IT. The containment is real but it is CONSUMER-DEPENDENT: it holds only while every
-- reader — current and future — remembers to filter by hive_id rather than joining through
-- asset_id or fmea_mode_id. That is precisely the assumption that failed in PM13, where one RPC
-- joined by the child key and turned the same "contained" gap into a live cross-tenant defect.
-- Closing it at the write removes the dependence on every future consumer's discipline.
--
-- SAFE TO TIGHTEN, measured before applying: 0 existing rows violate this on any of the four tables
-- (fmea->node, strategy->mode, weibull->node, pf->node), so it rejects nothing that exists.
--
-- RESTRICTIVE so it ANDs with the existing permissive policies and cannot widen anything; the
-- service_role / seeder path (auth.uid() IS NULL) keeps its reach, as everywhere else in this arc.
-- ─────────────────────────────────────────────────────────────────────────────

-- 1. An FMEA mode belongs to an asset node in ITS OWN hive.
DROP POLICY IF EXISTS rcm_fmea_modes_parent_hive_guard ON public.rcm_fmea_modes;
CREATE POLICY rcm_fmea_modes_parent_hive_guard
  ON public.rcm_fmea_modes
  AS RESTRICTIVE
  FOR ALL
  USING (true)
  WITH CHECK (
    auth.uid() IS NULL
    OR asset_id IS NULL
    OR EXISTS (
      SELECT 1 FROM public.asset_nodes n
       WHERE n.id = rcm_fmea_modes.asset_id
         AND n.hive_id IS NOT DISTINCT FROM rcm_fmea_modes.hive_id
    )
  );

-- 2. A strategy belongs to a failure mode in ITS OWN hive.
DROP POLICY IF EXISTS rcm_strategies_parent_hive_guard ON public.rcm_strategies;
CREATE POLICY rcm_strategies_parent_hive_guard
  ON public.rcm_strategies
  AS RESTRICTIVE
  FOR ALL
  USING (true)
  WITH CHECK (
    auth.uid() IS NULL
    OR fmea_mode_id IS NULL
    OR EXISTS (
      SELECT 1 FROM public.rcm_fmea_modes m
       WHERE m.id = rcm_strategies.fmea_mode_id
         AND m.hive_id IS NOT DISTINCT FROM rcm_strategies.hive_id
    )
  );

-- 3. A Weibull fit belongs to an asset node in ITS OWN hive.
DROP POLICY IF EXISTS weibull_fits_parent_hive_guard ON public.weibull_fits;
CREATE POLICY weibull_fits_parent_hive_guard
  ON public.weibull_fits
  AS RESTRICTIVE
  FOR ALL
  USING (true)
  WITH CHECK (
    auth.uid() IS NULL
    OR asset_id IS NULL
    OR EXISTS (
      SELECT 1 FROM public.asset_nodes n
       WHERE n.id = weibull_fits.asset_id
         AND n.hive_id IS NOT DISTINCT FROM weibull_fits.hive_id
    )
  );

-- 4. A P-F interval belongs to an asset node in ITS OWN hive.
DROP POLICY IF EXISTS pf_intervals_parent_hive_guard ON public.pf_intervals;
CREATE POLICY pf_intervals_parent_hive_guard
  ON public.pf_intervals
  AS RESTRICTIVE
  FOR ALL
  USING (true)
  WITH CHECK (
    auth.uid() IS NULL
    OR asset_id IS NULL
    OR EXISTS (
      SELECT 1 FROM public.asset_nodes n
       WHERE n.id = pf_intervals.asset_id
         AND n.hive_id IS NOT DISTINCT FROM pf_intervals.hive_id
    )
  );
