# Correctness Scoreboard (value-at-the-glass) — anti-drift compass

_Sibling of the bughunt scoreboard: bughunt proves each page is SAFE, this proves each displayed value is RIGHT._

_10 contracted metrics · 10 COVERED · 0 GAP · 6 multi-page (parity-checked)._

WHAT-axis→gate: **a**=canonical-source · **b**=calculation · **c**=cross-surface parity (static) · **d**=db-truth · **e**=provenance. `✓`=covered · `·`=N/A · `GAP`=uncovered.

| Metric (formula) | pages | a src | b calc | c parity | d db | e prov | status |
|---|---:|:---:|:---:|:---:|:---:|:---:|---|
| adoption_risk_score_v1 | 3 | ✓ | ✓ | ✓ | ✓ | ✓ | COVERED |
| pump_total_head_api_610 | 3 | ✓ | ✓ | ✓ | ✓ | ✓ | COVERED |
| achievement_card_level | 2 | ✓ | ✓ | ✓ | ✓ | ✓ | COVERED |
| marketplace_seller_quality_score | 2 | ✓ | ✓ | ✓ | ✓ | ✓ | COVERED |
| risk_score_v2_composite | 2 | ✓ | ✓ | ✓ | ✓ | ✓ | COVERED |
| skill_level_tier | 2 | ✓ | ✓ | ✓ | ✓ | ✓ | COVERED |
| pf_interval_days | 1 | ✓ | ✓ | · | ✓ | ✓ | COVERED |
| platform_health_pct | 1 | ✓ | ✓ | · | ✓ | ✓ | COVERED |
| skill_exam_score | 1 | ✓ | ✓ | · | ✓ | ✓ | COVERED |
| z_score_anomaly_3sigma | 1 | ✓ | ✓ | · | ✓ | ✓ | COVERED |

**✅ No GAPS — every contracted metric has canonical source, a formula, and cross-page parity.**

## Coverage context (reuse-first — these arcs already carry the correctness surface)
- **Arc Q (calc/engine):** `validate_calc_formula_accuracy` 63/63 · `validate_calc_live_value` · `validate_reliability_kpi_faithfulness` · `validate_oee_quality_derivation` · engines 10/10.
- **Value classification:** `audit_displayed_values` — 0 uncontracted · 0 unknown (every display anchor classified).
- **Source/provenance:** `validate_kpi_source_registry` (one metric→one source) · `validate_user_facing_kpi_canonical` · `validate_canonical_anchor` · lineage gates.
- **KNOWN tracked build (not a GAP):** RUNTIME cross-surface parity — a live probe asserting a multi-page hive-level KPI renders the SAME value on each page (contract-parity is proven static above; runtime is the one un-built check).
