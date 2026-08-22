-- pf_interval_actionable: every P-F row is ACTIONABLE — the basis is stated, the monitored
-- parameter named, the recommended inspection interval derived from its own stated basis
-- (P-F/2 or P-F/3) and STRICTLY inside the P-F window (an interval at/over pf_days inspects too
-- late to catch the failure developing).
-- expect: pf_rows \| [1-9][0-9]*
-- expect: basis_or_parameter_missing \| 0
-- expect: interval_at_or_over_pf \| 0
SELECT 'pf_rows | ' || count(*) FROM v_pf_truth;
SELECT 'basis_or_parameter_missing | ' || count(*) FROM v_pf_truth
WHERE basis IS NULL OR parameter IS NULL;   -- the column is `basis` (viewdef), not interval_basis
SELECT 'interval_at_or_over_pf | ' || count(*) FROM v_pf_truth
WHERE recommended_interval_days >= pf_days;
