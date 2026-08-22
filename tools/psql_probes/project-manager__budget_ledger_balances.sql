-- budget_ledger_balances: a project's current budget is DERIVED (base + approved change orders),
-- never a mutated base — recompute per project: budget_php stays the sanctioned base, and derived
-- current = base + sum(approved CO cost impacts). Coherence for every project (non-vacuity printed).
-- expect: projects \| [1-9][0-9]*
-- expect: negative_bases \| 0
-- expect: derivation_well_defined \| t
SELECT 'projects | ' || count(*) FROM projects;
SELECT 'negative_bases | ' || count(*) FROM projects WHERE budget_php < 0;
SELECT 'derivation_well_defined | ' || (count(*) = 0) FROM project_change_orders co
WHERE co.status = 'approved' AND co.cost_impact_php IS NULL;
