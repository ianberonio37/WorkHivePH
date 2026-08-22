-- weibull_reproducible: every Weibull fit carries what it takes to REPRODUCE it — sample size,
-- method, window, pattern — and eta names its unit in the column itself (eta_days). Population
-- printed (non-vacuity).
-- expect: fits \| [1-9][0-9]*
-- expect: unreproducible_fits \| 0
-- expect: eta_unit_in_name \| t
SELECT 'fits | ' || count(*) FROM v_weibull_truth;
SELECT 'unreproducible_fits | ' || count(*) FROM v_weibull_truth
WHERE n_failures IS NULL OR fit_method IS NULL OR source_window_days IS NULL OR failure_pattern IS NULL;
SELECT 'eta_unit_in_name | ' || EXISTS (
  SELECT 1 FROM information_schema.columns
  WHERE table_name='v_weibull_truth' AND column_name='eta_days');
