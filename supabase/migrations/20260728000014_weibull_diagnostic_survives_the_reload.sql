-- ─────────────────────────────────────────────────────────────────────────────
-- Keep the reason a Weibull fit was REFUSED, so it survives longer than the click.
--
-- FOUND BY THE AH9 WALK (2026-07-28, ASSET_HUB_DEEPWALK_EXPANSION_ROADMAP, class AHK2):
--
-- The engine's refusal path is genuinely well built and stays exactly as it is. Below
-- MIN_FAILURES_FOR_FIT it attempts NO fit and returns beta=NULL, eta_days=NULL,
-- failure_pattern='insufficient_data' and — the useful part — an actionable diagnostic:
--
--     "Need at least 4 corrective events in the lookback window (have 2).
--      Log more breakdowns or widen since_days before refitting."
--
-- That sentence is the whole product of the refusal. It tells a planner why there is no number
-- and what to do to get one, and asset-hub renders it into #weibull-diagnostic.
--
-- BUT IT COULD ONLY EVER BE SEEN ONCE. `weibull_fits` has no `diagnostic` column, `persistFit`
-- therefore never wrote it, and `v_weibull_truth` could not expose it — so `loadLatestWeibull`
-- selects a set of columns that cannot contain it, `fit.diagnostic` is undefined, and
-- `diagEl.textContent = fit.diagnostic || ''` clears the box. The message is visible for the few
-- seconds after you press Compute, and is gone on every page load after that.
--
-- What a planner opening the asset the next day sees instead: beta "--", eta "--", a pill reading
-- "insufficient data", and an empty bordered box where the explanation should be. The number is
-- correctly absent and the REASON is silently absent too — which is the F18 dead-card shape landing
-- on the most important sentence in the reliability workbench.
--
-- ONE DEFINITION, not two: the alternative was to re-derive the wording client-side from
-- n_failures, which would put the same sentence in two places and let them drift (the logbook arc's
-- three-ways-to-say-'corrective'). The engine already writes it; persist what it wrote.
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.weibull_fits
  ADD COLUMN IF NOT EXISTS diagnostic text;

COMMENT ON COLUMN public.weibull_fits.diagnostic IS
  'Human-readable reason the fit was refused or caveated, written by the fitter (python-api '
  'reliability/weibull.py -> weibull-fitter). Persisted so it survives a reload: without it the '
  'refusal explanation was visible only in the response to Compute and blank on every later load.';

-- Re-expose the view with the new column, PRESERVING its existing shape exactly. This view is not a
-- plain projection: `DISTINCT ON (hive_id, asset_id, COALESCE(fmea_mode_id,'_')) ... ORDER BY
-- generated_at DESC` is what makes it the LATEST fit per asset rather than every historical one, and
-- it aliases `id AS fit_id`. Rewriting it from the column list alone would have silently returned
-- the full history to every consumer and renamed a column out from under them.
-- security_invoker stays ON so base-table RLS applies (mig 001 — a view with it OFF runs as owner
-- and leaks across hives).
DROP VIEW IF EXISTS public.v_weibull_truth;
CREATE VIEW public.v_weibull_truth
-- `= true`, matching every other truth view: identical to `on`, but the platform greps
-- for the literal, so a lone `on` would read as unset to a future check.
WITH (security_invoker = true) AS
SELECT DISTINCT ON (hive_id, asset_id, (COALESCE(fmea_mode_id::text, '_'::text)))
       id AS fit_id,
       hive_id,
       asset_id,
       fmea_mode_id,
       beta,
       eta_days,
       failure_pattern,
       n_failures,
       n_censored,
       fit_method,
       log_likelihood,
       source_window_days,
       diagnostic,
       generated_at
FROM public.weibull_fits
ORDER BY hive_id, asset_id, (COALESCE(fmea_mode_id::text, '_'::text)), generated_at DESC;
