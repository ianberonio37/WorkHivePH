# Arc C · C0 — Whole-Platform Render-Tier Denominator

_Mined by `tools/mine_render_surfaces.py`. The denominator is **(feature page × `data-rag-tile` cell)** — page-author-declared canonical-value tiles, not a heuristic scrape._

## Totals

- **N = 83 render cells** across 17 pages (47 single-value tiles · 36 panel/list/chart surfaces)
- **Already proven (credited): 13/83 = 15.7%** (§13 V-axis + asset-hub)
- **Value tiles proven: 12/47 = 25.5%** → C1 target = the **35 uncredited value tiles** first

## Per page

| Page | nav | tiles | value | panel | credited |
|---|---|--:|--:|--:|--:|
| achievements.html | – | 7 | 3 | 4 | 0 |
| alert-hub.html | ✓ | 8 | 3 | 5 | 0 |
| analytics.html | ✓ | 5 | 3 | 2 | 1 |
| asset-hub.html | ✓ | 8 | 3 | 5 | 2 |
| dayplanner.html | ✓ | 4 | 3 | 1 | 0 |
| hive.html | ✓ | 4 | 3 | 1 | 1 |
| index.html | ✓ | 1 | 0 | 1 | 0 |
| integrations.html | ✓ | 6 | 3 | 3 | 0 |
| inventory.html | ✓ | 4 | 3 | 1 | 0 |
| marketplace.html | ✓ | 4 | 2 | 2 | 1 |
| ph-intelligence.html | ✓ | 4 | 3 | 1 | 0 |
| pm-scheduler.html | ✓ | 4 | 3 | 1 | 3 |
| predictive.html | – | 7 | 3 | 4 | 2 |
| project-manager.html | ✓ | 5 | 3 | 2 | 0 |
| report-sender.html | – | 4 | 3 | 1 | 0 |
| shift-brain.html | ✓ | 4 | 3 | 1 | 3 |
| skillmatrix.html | ✓ | 4 | 3 | 1 | 0 |

## Non-tile proven pages (credited page-level, outside the tile denominator)

- **ai-quality.html** — T_ai_quality (ai-quality.html)
- **engineering-design.html** — Arc B — 53 calc types render==validated-Python (browser_calc_sweep B1)
- **hive.html** — J5 (hive.html)
- **project-report.html** — T_project_report — wbs/owner/status == v_project_truth (PM print-flow)
- **status.html** — J6 (status.html)
- **voice-journal.html** — J4 (voice-journal.html)

## C1 worklist — uncredited VALUE tiles (read sc-hero, compare to source)

| Page | tile_id | label | sc-hero id |
|---|---|---|---|
| achievements.html | `achievements:xp_this_week` | XP this week | `ac-week-hero` |
| achievements.html | `achievements:active_domains` | Active domains | `ac-active-hero` |
| achievements.html | `achievements:total_level` | Total level | `ac-level-hero` |
| alert-hub.html | `alert-hub:high_severity_alerts` | High-severity alerts | `ah-critical-hero` |
| alert-hub.html | `alert-hub:anomaly_signals` | Anomaly signals | `ah-anomaly-hero` |
| alert-hub.html | `alert-hub:amc_daily_brief` | AMC daily brief | `ah-amc-hero` |
| analytics.html | `analytics:oee` | OEE (avg, partial) | `an-oee-hero` |
| analytics.html | `analytics:mtbf` | Worst MTBF (partial) | `an-mtbf-hero` |
| asset-hub.html | `asset-hub:total_assets` | Total assets | `ah-total-hero` |
| asset-hub.html | `asset-hub:pending_approval` | Pending assets | `ah-pending-hero` |
| dayplanner.html | `dayplanner:today_count` | Tasks today | `dp-today-hero` |
| dayplanner.html | `dayplanner:week_count` | Tasks this week | `dp-week-hero` |
| dayplanner.html | `dayplanner:overdue_count` | Overdue tasks | `dp-overdue-hero` |
| hive.html | `hive:maturity_stair` | Hive maturity stair | `ss-stair-hero` |
| hive.html | `hive:adoption_health` | Adoption health | `ss-adoption-hero` |
| integrations.html | `integrations:active` | Active integrations | `it-active-hero` |
| integrations.html | `integrations:stale` | Stale syncs | `it-stale-hero` |
| integrations.html | `integrations:disabled` | Disabled integrations | `it-disabled-hero` |
| inventory.html | `inventory:out_of_stock` | Out of stock | `inv-out-hero` |
| inventory.html | `inventory:low_stock` | Low stock | `inv-low-hero` |
| inventory.html | `inventory:pending_approval` | Pending parts | `inv-pending-hero` |
| marketplace.html | `marketplace:my_listings` | My listings | `mk-mine-hero` |
| ph-intelligence.html | `ph-intelligence:plants_in_network` | Plants in network | `ph-plants-hero` |
| ph-intelligence.html | `ph-intelligence:top_failure_cause` | Top failure cause | `ph-cause-hero` |
| ph-intelligence.html | `ph-intelligence:report_freshness` | Report freshness | `ph-fresh-hero` |
| predictive.html | `predictive:earliest_forecast` | Earliest forecast failure | `pr-soonest-hero` |
| project-manager.html | `project-manager:active_projects` | Active projects | `pm-active-hero` |
| project-manager.html | `project-manager:past_end_date` | Past end date | `pm-overdue-hero` |
| project-manager.html | `project-manager:on_hold_planning` | On hold or planning | `pm-blocked-hero` |
| report-sender.html | `report-sender:reports_selected` | Reports selected | `rs-reports-hero` |
| report-sender.html | `report-sender:recipients` | Recipients | `rs-recipients-hero` |
| report-sender.html | `report-sender:saved_contacts` | Saved contacts | `rs-contacts-hero` |
| skillmatrix.html | `skillmatrix:on_target` | On target workers | `sm-ontrack-hero` |
| skillmatrix.html | `skillmatrix:quizzes_available` | Quizzes available | `sm-quizzes-hero` |
| skillmatrix.html | `skillmatrix:total_badges` | Total badges earned | `sm-badges-hero` |
