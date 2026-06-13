# Streamlining Survey — Cross-Page IA Redundancy Map (Phase 1)

> **Deterministic. SURFACES redundancy — disposes nothing.** This is the grounded
> _map_ (Brad Frost Interface Inventory + NN/g Content Inventory). The
> keep/consolidate/move/remove recommendation, the canonical home, the UX-law
> citation and the severity are **Phase 2's rubric** — not in this map.

- Pages surveyed: **28**  ·  info-units catalogued: **95**  ·  min-pages threshold: **2**
- Live-inventory dumps merged: **28** (`.tmp/ia_inventory/*.json` from `__UFAI.inventory()`; 0 = static-only run)
- Complements `clone_debt_baseline.json` (jscpd = textual code clones). This map = user-facing **semantic** redundancy.

## 1. Information redundancy — the SAME info-unit on N pages

### 1a. Exact-label matches (high confidence)

| Info-unit (label) | Pages | Where |
|---|---|---|
| Pending approval | 2 | asset-hub, inventory |

### 1b. Same tile-key suffix across pages (high confidence)

_The `page:KEY` convention — an identical KEY suffix = the same unit replicated._

| Tile key | Pages | Where |
|---|---|---|
| `detail_panel` | 15 | achievements, alert-hub, analytics, asset-hub, dayplanner, hive, integrations, inventory, marketplace, ph-intelligence, pm-scheduler, predictive, report-sender, shift-brain, skillmatrix |
| `pending_approval` | 2 | asset-hub, inventory |

### 1c. Semantic theme clusters (CANDIDATES — different labels, same job)

_Lower confidence: keyword-bucketed families. A human confirms each is true redundancy vs. legitimately distinct (e.g. PM-overdue ≠ project-overdue)._

| Theme | Pages | Member units (label · page) |
|---|---|---|
| detail breakdown panel | 15 | Achievements detail (achievements); Alert detail breakdown (alert-hub); Analytics detail breakdown (analytics); Asset detail breakdown (asset-hub); Day planner detail (dayplanner); Hive supervisor detail (hive); Integrations detail (integrations); Inventory detail breakdown (inventory); Marketplace  |
| risk / hot / critical | 4 | High-severity alerts (alert-hub); Anomaly signals (alert-hub); AMC parts at risk (alert-hub); Critical assets (asset-hub); Top risk this shift (shift-brain); Hot assets (predictive); Risk ranking table (predictive); Risk heatmap (predictive) |
| due soon / upcoming | 3 | Tasks today (dayplanner); Tasks this week (dayplanner); Due soon (14d) (pm-scheduler); Due this week (pm-scheduler); PMs due (shift-brain) |
| healthy / on-track | 3 | On track (pm-scheduler); On target workers (skillmatrix); Healthy assets (predictive) |
| late / overdue | 3 | Overdue tasks (dayplanner); Overdue PMs (pm-scheduler); Past end date (project-manager) |
| pending approval | 2 | Pending assets (asset-hub); Pending approval (asset-hub); Pending parts (inventory); Pending approval (inventory) |

## 2. Affordance overlap — the same action reachable from N places (Hick's law)

_Page-BODY cross-links only; the global nav-hub is excluded (it links everywhere by design). A body link to a page that ALSO sits in the nav = an extra path._

| Destination | Linked from (bodies) | Where |
|---|---|---|
| hive | 9 | alert-hub, asset-hub, audit-log, engineering-design, index, integrations, logbook, project-manager, shift-brain |
| index | 9 | audit-log, community, dayplanner, engineering-design, hive, inventory, logbook, pm-scheduler, voice-journal |
| analytics-report | 2 | analytics, report-sender |
| inventory | 2 | hive, index |
| ph-intelligence | 2 | analytics, integrations |
| plant-connections | 2 | hive, integrations |
| pm-scheduler | 2 | hive, index |
| report-sender | 2 | analytics-report, analytics |
| skillmatrix | 2 | achievements, index |
| voice-journal | 2 | index, logbook |

<details><summary>Shared inline onclick handlers (informational — mostly shell utilities like toggles/modals; not a redundancy verdict)</summary>

| Handler | Pages |
|---|---|
| `switchTab()` | 3 |

</details>

## 3. Presentational clones — same block, copy-pasted

- **jscpd (textual):** 70 clones · 5242 duplicated lines · 27.5% (see `clone_debt_baseline.json`). Tracked separately; this map adds the SEMANTIC layer below.
- **`:detail_panel` family:** the same "detail breakdown" panel structure on **14** pages — achievements, alert-hub, analytics, asset-hub, dayplanner, hive, integrations, inventory, marketplace, ph-intelligence, pm-scheduler, report-sender, shift-brain, skillmatrix.
- **`.sum-card` 4-tile summary block:** on **1** pages — ai-quality.
- **`.simple-card` KPI block density (≥3 per page):** achievements=3, ai-quality=3, alert-hub=3, analytics=3, asset-hub=3, dayplanner=3, hive=3, integrations=3, inventory=3, ph-intelligence=3, pm-scheduler=3, project-manager=3, report-sender=3, shift-brain=3, skillmatrix=3.

---
### Next: Phase 2 (rubric)
Read `ia_inventory_corpus.json` (no re-parse) and, per redundant unit, score **keep / consolidate / move / remove** + the ONE canonical home (single source of truth, deep-link elsewhere) + the UX-law citation (Hick / Tesler / Jakob / Miller / progressive-disclosure) + severity → `streamlining_plan.md` + critic candidates into `sweep_critiques.json`. **No UI is collapsed without your sign-off.**
