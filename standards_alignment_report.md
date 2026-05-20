# Standards Alignment Audit (Tier S — Layer -1.5)

Cross-checks every formula in `canonical/formula_contracts.json`
against its cited entry in `canonical/standards.json`. Catches the
OEE-class bug: a formula that says it implements a standard but is
actually missing required inputs.

## Summary

- Total formulas:  **15**
- Pass:            **15**
- Fail:            **0**
- Partial honest:  **3** (declared with reason + label)
- Partial silent:  **0** ❌ (labelled as full)

## ⚠️ Declared partial variants (6)

These formulas honestly declare themselves partial relative to
their cited standard. They are CORRECT per the contract but
should be promoted to full implementations as the missing fuel
fields / RPCs land.

| Formula | Standard clause | Missing | Reason |
|---|---|---|---|
| `mtbf_iso_14224` | iso_14224_2016 §9.3_mtbf | — | Uses CALENDAR time intervals (logbook.created_at) rather than OPERATING time per ISO 14224 §9.3. Operating-time mode req |
| `mttr_iso_14224` | iso_14224_2016 §9.4_mttr | — | Uses logbook.downtime_hours which is TOTAL downtime (active repair + logistic + admin). ISO 14224 §9.4 specifies ACTIVE  |
| `pm_compliance_30d` | smrp_metrics_v5 §2.1.1_pm_compliance | ['pms_scheduled'] | 30-day threshold is a PLATFORM convention, not the SMRP standard. SMRP 2.1.1 is per-asset-per-PM-cycle on the asset's ac |
| `risk_score_v2_composite` | sae_ja1011 §5.4_consequence_buckets | ['failure_mode', 'operating_context'] | Composite weighting (0.30/0.30/0.20/0.20/0.15/0.10) is a PLATFORM heuristic blending SAE JA1011 consequence-class + IEC  |
| `pump_total_head_api_610` | api_610_2018 §pump_head | — | Bernoulli velocity term (v_d² - v_s²)/(2g) is OMITTED in the platform's quick calc — acceptable when discharge and sucti |
| `oee_iso_22400_partial` | iso_22400_2_2014 §5.5_oee | ['performance_pct'] | Performance factor excluded: requires per-asset ideal_cycle_time_seconds (Tier F capture asset_ideal_cycle_time) which i |

## All results (full alignment ranking)

| Formula | Standard | Clause | Partial | OK |
|---|---|---|:---:|:---:|
| `mtbf_iso_14224` | iso_14224_2016 | 9.3_mtbf | ✓ | ✅ |
| `mttr_iso_14224` | iso_14224_2016 | 9.4_mttr | ✓ | ✅ |
| `pm_compliance_30d` | smrp_metrics_v5 | 2.1.1_pm_compliance | ✓ | ✅ |
| `risk_score_v2_composite` | sae_ja1011 | 5.4_consequence_buckets | ✓ | ✅ |
| `oee_iso_22400` | iso_22400_2_2014 | 5.5_oee |  | ✅ |
| `bearing_life_iso_281` | iso_281_2007 | 5_l10_hours |  | ✅ |
| `pipe_pressure_drop_darcy` | darcy_weisbach | pressure_drop |  | ✅ |
| `pump_total_head_api_610` | api_610_2018 | pump_head | ✓ | ✅ |
| `motor_output_power_nema` | nema_mg_1_2021 | motor_power |  | ✅ |
| `rpn_iec_60812` | iec_60812_2018 | rpn |  | ✅ |
| `z_score_anomaly_3sigma` | z_score_anomaly | z_score |  | ✅ |
| `spi_pmbok` | pmbok_evm | spi |  | ✅ |
| `cpi_pmbok` | pmbok_evm | cpi |  | ✅ |
| `hive_stair_composite` | platform_maturity_stair | stair_composite |  | ✅ |
| `oee_iso_22400_partial` | iso_22400_2_2014 | 5.5_oee | ✓ | ✅ |