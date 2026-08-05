# Per-Article Optimization Map (Pillar 3.5)

The 45 `/learn` articles + 3 new pillars, mapped to their **primary target query** with a **title/H2/refresh flag**. Answer-first + statistic + citation are already enforced platform-wide by `tools/extractability_gate.py` (all pass), so this map covers the layer *beyond* the binary gates: query alignment and refresh cadence.

**Refresh cadence** (until GSC data lands): pillars on a rolling 30-day cycle so Perplexity always sees <30-day content (it cites <30-day-fresh 82% of the time `[external-chatgpt-vs-perplexity-ai-visibility-citations-tr]`); cluster articles refreshed after their pillar. Once GSC is wired, re-rank by position — refresh positions 3-20 first `[external-content-refresh-cadence-topical-authority-freshn]`.

**Flag key:** `PILLAR` = cluster hub · `title✓` = title already carries the target query · `title△` = tighten title toward the query · `H2△` = add an H2 matching a demand phrasing · `refresh30` = keep <30-day fresh.

## Cluster 1 — Reliability & Metrics
| Article | Primary target query | Flag |
|---|---|---|
| **maintenance-metrics-reliability-guide** | maintenance metrics OEE MTBF MTTR | **PILLAR** · refresh30 |
| what-is-oee-how-to-calculate | how to calculate OEE | title✓ |
| mtbf-vs-mttr-for-supervisors | MTBF vs MTTR explained | title✓ |
| reliability-centered-maintenance-philippine-plants | what is RCM reliability centered maintenance | title✓ |
| fmea-worked-example-philippine-bottling-line | FMEA worked example | title✓ |
| predictive-alert-thresholds-plants | ISO 10816 vibration thresholds | title△ (add "ISO 10816") |
| four-phases-maintenance-analytics-philippine-plants | maintenance analytics maturity | H2△ (add "OEE benchmarks") |
| power-plant-reliability-metrics-philippines | power plant reliability metrics | title✓ |

## Cluster 2 — Getting Started / Digital Maintenance
| Article | Primary target query | Flag |
|---|---|---|
| **start-digital-maintenance-guide** | how to start digital maintenance | **PILLAR** · refresh30 |
| start-digital-logbook-philippine-factory | digital logbook for factory | title✓ |
| building-asset-register-zero-budget | how to build an asset register ISO 14224 | title✓ |
| maintenance-shift-handover-template | shift handover template | title✓ |
| free-pm-checklist-templates | free PM checklist template | title✓ |
| maintenance-project-planning-template | turnaround planning template | title△ |
| dilo-wilo-day-planner-supervisors | DILO WILO planning | title✓ |
| autonomous-shift-planning-philippine-plants | shift planning software | H2△ |

## Cluster 3 — PH Compliance
| Article | Primary target query | Flag |
|---|---|---|
| **ph-plant-compliance-guide** | DOLE OSHS LOTO RA 11285 compliance | **PILLAR** · refresh30 |
| dole-iso-audit-trail-from-logbook | DOLE audit trail digital logbook | title✓ |
| loto-procedures-dole-oshs-template | lockout tagout template Philippines | title✓ |
| ra-11285-energy-efficiency-plant-checklist | RA 11285 energy efficiency checklist | title✓ |

## Cluster 4 — Predictive & Condition-Monitoring
| Article | Primary target query | Flag |
|---|---|---|
| predictive-maintenance-on-a-budget-philippines | predictive maintenance on a budget | title✓ |
| vibration-analysis-on-a-phone-budget | vibration analysis on a phone | title✓ |
| thermography-for-pm-philippine-plants | thermography for preventive maintenance | title✓ |
| sensor-cmms-gateway-operations | sensor CMMS gateway | title△ |

## Cluster 5 — Skills & Career (OFW)
| Article | Primary target query | Flag |
|---|---|---|
| skill-matrix-for-maintenance-technicians | how to build a skill matrix | title✓ |
| tesda-nc-mapping-to-skill-matrix | TESDA NC skill matrix | title✓ |
| ofw-engineer-portable-portfolio | OFW engineer portfolio | title✓ |
| resume-builder-for-filipino-industrial-workers | resume builder industrial worker | title✓ |
| psme-iiee-piche-which-association-to-join | PSME IIEE PIChE which to join | title✓ |

## Cluster 6 — AI Companion
| Article | Primary target query | Flag |
|---|---|---|
| ai-work-assistant-maintenance-technicians | AI assistant for maintenance technicians | title✓ |
| ai-companion-hezekiah-zaniah-personas | AI maintenance assistant personas | H2△ |
| workhive-ai-companion-complete-capabilities | AI maintenance companion capabilities | title✓ |
| ai-quality-and-roi-stage-2-plants | AI maintenance ROI | H2△ |
| voice-to-text-maintenance-philippine-plant-floor | voice to text maintenance Tagalog | title✓ |

## Cluster 7 — Platform / Ecosystem
| Article | Primary target query | Flag |
|---|---|---|
| what-is-workhive-complete-platform-guide | what is WorkHive / free CMMS Philippines | **PILLAR** · title✓ |
| industrial-marketplace-philippine-specialists | industrial parts marketplace Philippines | title✓ |
| industrial-community-of-practice-philippines | industrial community of practice | title✓ |
| joining-and-growing-your-hive | how to join WorkHive | title△ |
| gamifying-maintenance-for-engagement | gamifying maintenance | title✓ |
| plant-alert-inbox-amc-daily-brief | plant alert inbox daily brief | H2△ |

## Cluster 8 — Engineering Calculators
| Article | Primary target query | Flag |
|---|---|---|
| free-engineering-calculators-philippine-plants | free engineering calculators Philippines | **PILLAR** · links all 58 /tools/ · title✓ |
| *(58 /tools/`<calc>`-calculator/ pages)* | `<calc>` calculator | built + gate-green |

## Verticals / Benchmarks (cross-cluster)
| Article | Primary target query | Flag |
|---|---|---|
| food-beverage-plant-maintenance-philippines | food beverage plant maintenance | title✓ |
| bms-facilities-maintenance-peza-buildings | BMS facilities maintenance PEZA | title✓ |
| connecting-workhive-to-sap-maximo-cmms | integrate free CMMS to SAP Maximo | title✓ |
| ph-industrial-benchmarks-intelligence | Philippine OEE benchmarks by sector | **→ upgrade to linkable-asset study** (offsite §4) |
| print-ready-maintenance-analytics-report | maintenance analytics report | H2△ |
| asset-brain-360-one-machine-history-philippine-plant | asset history one machine | title△ |
| spare-parts-inventory-philippine-plants | ABC analysis spare parts inventory | title✓ |

**Highest-priority title/H2 tweaks (the △ rows):** ~10 articles. Low-effort, low-risk; batch when convenient. The PILLARs + `ph-industrial-benchmarks` (→ original-research study) are the highest-leverage on-site moves and are already built or specced.
