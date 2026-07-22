## DIM -> LAYER map
- **F Frontend**: D1, D3, D4, D5, D15, D17, D22, D23
- **A APIs/Edge**: (no grid dim — DEPTH GAP: add a walked cell)
- **D Database**: D2
- **AU Auth**: D19
- **H Hosting/Multitenancy**: D8, D9
- **C Cloud/LLM**: D10, D11, D13, D24, D25, D26
- **CI CI-CD**: (no grid dim — DEPTH GAP: add a walked cell)
- **S Security**: D7
- **RL Rate-Limit**: D12
- **CA Caching/CDN**: (no grid dim — DEPTH GAP: add a walked cell)
- **LB Load/Perf**: D6
- **L Logs/Observability**: D21
- **AV Availability/Recovery**: D18, D20

## Per-LAYER platform-wide % (avg across pages, grid-measured)
- F Frontend: 100.0%  (528 cells)
- A APIs/Edge: n/a (no grid dim)  (0 cells)
- D Database: 100.0%  (27 cells)
- AU Auth: 100.0%  (42 cells)
- H Hosting/Multitenancy: 100.0%  (84 cells)
- C Cloud/LLM: n/a (no grid dim)  (0 cells)
- CI CI-CD: n/a (no grid dim)  (0 cells)
- S Security: 100.0%  (90 cells)
- RL Rate-Limit: n/a (no grid dim)  (0 cells)
- CA Caching/CDN: n/a (no grid dim)  (0 cells)
- LB Load/Perf: 100.0%  (90 cells)
- L Logs/Observability: n/a (no grid dim)  (0 cells)
- AV Availability/Recovery: 100.0%  (84 cells)

## Per-PAGE x per-LAYER % (90 pages)
| Page | F | A | D | AU | H | C | CI | S | RL | CA | LB | L | AV |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| about | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| achievements | 100 | · | · | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| agentic-rag-observability | 100 | · | · | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| ai-quality | 100 | · | · | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| alert-hub | 100 | · | 100 | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| analytics | 100 | · | 100 | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| analytics-report | 100 | · | · | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| architecture | 100 | · | · | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| asset-hub | 100 | · | 100 | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| assistant | 100 | · | 100 | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| audit-log | 100 | · | 100 | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| community | 100 | · | 100 | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| dayplanner | 100 | · | 100 | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| design-system | 100 | · | · | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| engineering-design | 100 | · | · | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| founder-console | 100 | · | 100 | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| hive | 100 | · | 100 | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| index | 100 | · | 100 | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| integrations | 100 | · | 100 | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| inventory | 100 | · | 100 | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| learn/ai-companion-hezekiah-zaniah-personas | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/ai-quality-and-roi-stage-2-plants | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/ai-work-assistant-maintenance-technicians | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/asset-brain-360-one-machine-history-philippine-plant | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/autonomous-shift-planning-philippine-plants | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/bms-facilities-maintenance-peza-buildings | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/building-asset-register-zero-budget | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/connecting-workhive-to-sap-maximo-cmms | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/dilo-wilo-day-planner-supervisors | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/dole-iso-audit-trail-from-logbook | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/fmea-worked-example-philippine-bottling-line | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/food-beverage-plant-maintenance-philippines | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/four-phases-maintenance-analytics-philippine-plants | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/free-engineering-calculators-philippine-plants | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/free-pm-checklist-templates | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/gamifying-maintenance-for-engagement | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/industrial-community-of-practice-philippines | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/industrial-marketplace-philippine-specialists | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/joining-and-growing-your-hive | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/loto-procedures-dole-oshs-template | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/maintenance-project-planning-template | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/maintenance-shift-handover-template | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/mtbf-vs-mttr-for-supervisors | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/ofw-engineer-portable-portfolio | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/ph-industrial-benchmarks-intelligence | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/plant-alert-inbox-amc-daily-brief | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/power-plant-reliability-metrics-philippines | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/predictive-alert-thresholds-plants | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/predictive-maintenance-on-a-budget-philippines | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/print-ready-maintenance-analytics-report | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/psme-iiee-piche-which-association-to-join | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/ra-11285-energy-efficiency-plant-checklist | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/reliability-centered-maintenance-philippine-plants | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/resume-builder-for-filipino-industrial-workers | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/sensor-cmms-gateway-operations | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/skill-matrix-for-maintenance-technicians | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/spare-parts-inventory-philippine-plants | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/start-digital-logbook-philippine-factory | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/tesda-nc-mapping-to-skill-matrix | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/thermography-for-pm-philippine-plants | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/vibration-analysis-on-a-phone-budget | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/voice-to-text-maintenance-philippine-plant-floor | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/what-is-oee-how-to-calculate | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/what-is-workhive-complete-platform-guide | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| learn/workhive-ai-companion-complete-capabilities | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| llm-observability | 100 | · | · | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| logbook | 100 | · | 100 | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| marketplace | 100 | · | 100 | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| marketplace-admin | 100 | · | 100 | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| marketplace-seller | 100 | · | 100 | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| marketplace-seller-profile | 100 | · | 100 | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| offline-fallback | 100 | · | · | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| ph-intelligence | 100 | · | 100 | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| plant-connections | 100 | · | · | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| platform-actions | 100 | · | 100 | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| pm-scheduler | 100 | · | 100 | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| privacy-policy | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| project-manager | 100 | · | 100 | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| project-report | 100 | · | 100 | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| promo-poster | 100 | · | · | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| public-feed | 100 | · | · | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| report-sender | 100 | · | 100 | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| resume | 100 | · | 100 | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| shift-brain | 100 | · | 100 | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| skillmatrix | 100 | · | 100 | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| status | 100 | · | · | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| symbol-gallery | 100 | · | · | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| terms-of-service | 100 | · | · | · | · | · | · | 100 | · | · | 100 | · | · |
| validator-catalog | 100 | · | · | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
| voice-journal | 100 | · | 100 | 100 | 100 | · | · | 100 | · | · | 100 | · | 100 |
