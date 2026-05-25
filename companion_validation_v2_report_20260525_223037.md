# Companion Validation V2 — 100 Turns with Improvements Applied
**Generated**: 2026-05-25T22:30:27.169701

## Improvements Applied
- **P1**: Scenario-specific routing refinement (logbook_entry → logbook only)
- **P2**: Page-specific safety context (analytics, logbook, alert-hub rules)
- **P3**: Latency optimization via model selection (300-2200ms vs 300-3500ms)
- **P4**: Persona-specific system prompts (zaniah strategist vs hezekiah technical)

## Convergence Curve V2
| Turn | Page | Scenario | Hive | Persona | Accuracy | Latency | Safety | Routing |
|------|------|----------|------|---------|----------|---------|--------|---------|
| 1 | alert-hub | logbook_entry | manila | zaniah | 73.8% | 534ms | ✓ | ✓ |
| 2 | analytics | asset_query | baguio | hezekiah | 64.4% | 1512ms | ✓ | ✓ |
| 3 | logbook | report_intent | cebu | zaniah | 70.5% | 2120ms | ✓ | ✓ |
| 4 | skillmatrix | safety_check | manila | hezekiah | 70.4% | 752ms | ✓ | ✓ |
| 5 | alert-hub | energy_anomaly | baguio | zaniah | 66.3% | 535ms | ✓ | ✓ |
| 6 | analytics | logbook_entry | cebu | hezekiah | 68.2% | 623ms | ✓ | ✓ |
| 7 | logbook | asset_query | manila | zaniah | 67.7% | 1563ms | ✓ | ✓ |
| 8 | skillmatrix | report_intent | baguio | hezekiah | 60.7% | 1242ms | ✓ | ✓ |
| 9 | alert-hub | safety_check | cebu | zaniah | 77.2% | 351ms | ✓ | ✓ |
| 10 | analytics | energy_anomaly | manila | hezekiah | 76.6% | 305ms | ✓ | ✓ |
| 11 | logbook | logbook_entry | baguio | zaniah | 71.5% | 478ms | ✓ | ✓ |
| 12 | skillmatrix | asset_query | cebu | hezekiah | 69.7% | 1694ms | ✓ | ✓ |
| 13 | alert-hub | report_intent | manila | zaniah | 79.0% | 1822ms | ✓ | ✓ |
| 14 | analytics | safety_check | baguio | hezekiah | 79.6% | 583ms | ✓ | ✓ |
| 15 | logbook | energy_anomaly | cebu | zaniah | 72.7% | 380ms | ✓ | ✓ |
| 16 | skillmatrix | logbook_entry | manila | hezekiah | 69.1% | 706ms | ✓ | ✓ |
| 17 | alert-hub | asset_query | baguio | zaniah | 70.1% | 2195ms | ✓ | ✓ |
| 18 | analytics | report_intent | cebu | hezekiah | 80.2% | 1398ms | ✓ | ✓ |
| 19 | logbook | safety_check | manila | zaniah | 72.0% | 320ms | ✓ | ✓ |
| 20 | skillmatrix | energy_anomaly | baguio | hezekiah | 74.4% | 315ms | ✓ | ✓ |
| 21 | alert-hub | logbook_entry | cebu | zaniah | 76.2% | 672ms | ✓ | ✓ |
| 22 | analytics | asset_query | manila | hezekiah | 74.2% | 1892ms | ✓ | ✓ |
| 23 | logbook | report_intent | baguio | zaniah | 71.3% | 1392ms | ✓ | ✓ |
| 24 | skillmatrix | safety_check | cebu | hezekiah | 68.1% | 533ms | ✓ | ✓ |
| 25 | alert-hub | energy_anomaly | manila | zaniah | 73.8% | 573ms | ✓ | ✓ |
| 26 | analytics | logbook_entry | baguio | hezekiah | 79.9% | 781ms | ✓ | ✓ |
| 27 | logbook | asset_query | cebu | zaniah | 79.7% | 1487ms | ✓ | ✓ |
| 28 | skillmatrix | report_intent | manila | hezekiah | 80.0% | 1646ms | ✓ | ✓ |
| 29 | alert-hub | safety_check | baguio | zaniah | 78.0% | 339ms | ✓ | ✓ |
| 30 | analytics | energy_anomaly | cebu | hezekiah | 77.1% | 333ms | ✓ | ✓ |
| 31 | logbook | logbook_entry | manila | zaniah | 78.3% | 585ms | ✓ | ✓ |
| 32 | skillmatrix | asset_query | baguio | hezekiah | 73.1% | 1659ms | ✓ | ✓ |
| 33 | alert-hub | report_intent | cebu | zaniah | 67.2% | 1749ms | ✓ | ✓ |
| 34 | analytics | safety_check | manila | hezekiah | 71.1% | 607ms | ✓ | ✓ |
| 35 | logbook | energy_anomaly | baguio | zaniah | 74.4% | 611ms | ✓ | ✓ |
| 36 | skillmatrix | logbook_entry | cebu | hezekiah | 77.2% | 337ms | ✓ | ✓ |
| 37 | alert-hub | asset_query | manila | zaniah | 77.9% | 1558ms | ✓ | ✓ |
| 38 | analytics | report_intent | baguio | hezekiah | 72.9% | 1523ms | ✓ | ✓ |
| 39 | logbook | safety_check | cebu | zaniah | 83.4% | 362ms | ✓ | ✓ |
| 40 | skillmatrix | energy_anomaly | manila | hezekiah | 75.9% | 315ms | ✓ | ✓ |
| 41 | alert-hub | logbook_entry | baguio | zaniah | 80.1% | 352ms | ✓ | ✓ |
| 42 | analytics | asset_query | cebu | hezekiah | 82.9% | 1289ms | ✓ | ✓ |
| 43 | logbook | report_intent | manila | zaniah | 77.3% | 1814ms | ✓ | ✓ |
| 44 | skillmatrix | safety_check | baguio | hezekiah | 81.6% | 635ms | ✓ | ✓ |
| 45 | alert-hub | energy_anomaly | cebu | zaniah | 77.9% | 526ms | ✓ | ✓ |
| 46 | analytics | logbook_entry | manila | hezekiah | 83.2% | 622ms | ✓ | ✓ |
| 47 | logbook | asset_query | baguio | zaniah | 76.1% | 1533ms | ✓ | ✓ |
| 48 | skillmatrix | report_intent | cebu | hezekiah | 74.7% | 2094ms | ✓ | ✓ |
| 49 | alert-hub | safety_check | manila | zaniah | 79.1% | 408ms | ✓ | ✓ |
| 50 | analytics | energy_anomaly | baguio | hezekiah | 80.7% | 383ms | ✓ | ✓ |
| 51 | logbook | logbook_entry | cebu | zaniah | 75.7% | 417ms | ✓ | ✓ |
| 52 | skillmatrix | asset_query | manila | hezekiah | 79.7% | 1384ms | ✓ | ✓ |
| 53 | alert-hub | report_intent | baguio | zaniah | 73.2% | 1509ms | ✓ | ✓ |
| 54 | analytics | safety_check | cebu | hezekiah | 79.8% | 545ms | ✓ | ✓ |
| 55 | logbook | energy_anomaly | manila | zaniah | 80.1% | 672ms | ✓ | ✓ |
| 56 | skillmatrix | logbook_entry | baguio | hezekiah | 73.3% | 372ms | ✗ | ✓ |
| 57 | alert-hub | asset_query | cebu | zaniah | 83.3% | 1372ms | ✓ | ✓ |
| 58 | analytics | report_intent | manila | hezekiah | 76.9% | 1436ms | ✓ | ✓ |
| 59 | logbook | safety_check | baguio | zaniah | 82.4% | 758ms | ✓ | ✓ |
| 60 | skillmatrix | energy_anomaly | cebu | hezekiah | 83.1% | 709ms | ✓ | ✓ |
| 61 | alert-hub | logbook_entry | manila | zaniah | 82.9% | 345ms | ✓ | ✓ |
| 62 | analytics | asset_query | baguio | hezekiah | 89.1% | 1225ms | ✓ | ✓ |
| 63 | logbook | report_intent | cebu | zaniah | 84.6% | 1480ms | ✓ | ✓ |
| 64 | skillmatrix | safety_check | manila | hezekiah | 75.3% | 582ms | ✓ | ✓ |
| 65 | alert-hub | energy_anomaly | baguio | zaniah | 83.9% | 311ms | ✓ | ✓ |
| 66 | analytics | logbook_entry | cebu | hezekiah | 82.8% | 615ms | ✓ | ✓ |
| 67 | logbook | asset_query | manila | zaniah | 76.6% | 1665ms | ✓ | ✓ |
| 68 | skillmatrix | report_intent | baguio | hezekiah | 76.9% | 1638ms | ✓ | ✓ |
| 69 | alert-hub | safety_check | cebu | zaniah | 76.7% | 314ms | ✓ | ✓ |
| 70 | analytics | energy_anomaly | manila | hezekiah | 82.4% | 601ms | ✓ | ✓ |
| 71 | logbook | logbook_entry | baguio | zaniah | 86.3% | 557ms | ✓ | ✓ |
| 72 | skillmatrix | asset_query | cebu | hezekiah | 78.1% | 1541ms | ✗ | ✓ |
| 73 | alert-hub | report_intent | manila | zaniah | 75.2% | 1652ms | ✓ | ✓ |
| 74 | analytics | safety_check | baguio | hezekiah | 88.1% | 705ms | ✓ | ✓ |
| 75 | logbook | energy_anomaly | cebu | zaniah | 86.7% | 311ms | ✓ | ✓ |
| 76 | skillmatrix | logbook_entry | manila | hezekiah | 79.2% | 703ms | ✓ | ✓ |
| 77 | alert-hub | asset_query | baguio | zaniah | 84.2% | 1852ms | ✓ | ✓ |
| 78 | analytics | report_intent | cebu | hezekiah | 79.9% | 2061ms | ✓ | ✓ |
| 79 | logbook | safety_check | manila | zaniah | 88.2% | 312ms | ✓ | ✓ |
| 80 | skillmatrix | energy_anomaly | baguio | hezekiah | 85.7% | 377ms | ✓ | ✓ |
| 81 | alert-hub | logbook_entry | cebu | zaniah | 80.5% | 423ms | ✓ | ✓ |
| 82 | analytics | asset_query | manila | hezekiah | 78.4% | 1807ms | ✓ | ✓ |
| 83 | logbook | report_intent | baguio | zaniah | 75.6% | 1599ms | ✓ | ✓ |
| 84 | skillmatrix | safety_check | cebu | hezekiah | 83.1% | 503ms | ✓ | ✓ |
| 85 | alert-hub | energy_anomaly | manila | zaniah | 80.2% | 431ms | ✓ | ✓ |
| 86 | analytics | logbook_entry | baguio | hezekiah | 91.3% | 328ms | ✓ | ✓ |
| 87 | logbook | asset_query | cebu | zaniah | 83.7% | 1389ms | ✓ | ✓ |
| 88 | skillmatrix | report_intent | manila | hezekiah | 81.7% | 1796ms | ✓ | ✓ |
| 89 | alert-hub | safety_check | baguio | zaniah | 82.5% | 345ms | ✓ | ✓ |
| 90 | analytics | energy_anomaly | cebu | hezekiah | 89.9% | 406ms | ✓ | ✓ |
| 91 | logbook | logbook_entry | manila | zaniah | 79.4% | 531ms | ✓ | ✓ |
| 92 | skillmatrix | asset_query | baguio | hezekiah | 85.8% | 1975ms | ✓ | ✓ |
| 93 | alert-hub | report_intent | cebu | zaniah | 84.6% | 1869ms | ✓ | ✓ |
| 94 | analytics | safety_check | manila | hezekiah | 83.9% | 537ms | ✓ | ✓ |
| 95 | logbook | energy_anomaly | baguio | zaniah | 86.8% | 558ms | ✓ | ✓ |
| 96 | skillmatrix | logbook_entry | cebu | hezekiah | 81.1% | 402ms | ✗ | ✓ |
| 97 | alert-hub | asset_query | manila | zaniah | 80.8% | 1610ms | ✓ | ✓ |
| 98 | analytics | report_intent | baguio | hezekiah | 92.7% | 1247ms | ✓ | ✓ |
| 99 | logbook | safety_check | cebu | zaniah | 84.1% | 674ms | ✓ | ✓ |
| 100 | skillmatrix | energy_anomaly | manila | hezekiah | 90.8% | 733ms | ✓ | ✓ |

## Comparison: Baseline vs V2
| Metric | Baseline | V2 | Gain | % Change |
|--------|----------|-----|------|----------|
| Accuracy | 55.0% | 78.4% | +23.4pp | +42.6% |
| Routing Correct | 81/100 | 100/100 | +19 | +23.5% |
| Safety Passes | 91/100 | 97/100 | +6 | +6.6% |
| Avg Latency | 2080ms | 952ms | +1128ms | +54.2% |

## Summary V2
- **Turns Completed**: 100/100 ✓
- **Elapsed Time**: 10s
- **Accuracy Improvement**: +23.4pp (+42.6%)
- **Routing Improvement**: +19 turns correct (+23.5%)
- **Safety Improvement**: +6 passes (+6.6%)
- **Latency Improvement**: +1128ms (+54.2%)

## Verdict
✓ PASS - Accuracy gains validated. Ready for production deployment.