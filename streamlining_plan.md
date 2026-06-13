# Streamlining Plan — Phase 2 (rubric)

> **Proposals, not actions.** Every row is scored by a deterministic rubric and awaits your sign-off. The engine PROPOSES; you DISPOSE (via `promotion_dispositions.json`). **No UI is collapsed automatically.**

> Built from `ia_inventory_corpus.json` (Phase 1). Method = NN/g content audit verbs (keep / consolidate / move / remove) + lawsofux severity. The keep/consolidate/relabel/review split exists because *"the same thing on N pages"* is four different situations — and conflating them is how you delete what you needed.

**Tally:** 7× REVIEW (extra path) · 4× DIFFERENTIATE / merge (review) · 2× KEEP (hub link) · 1× RELABEL / keep-distinct · 1× KEEP (consistent pattern)
  ·  **12** rows queued for disposition (KEEP rows are documented here but not queued — no decision needed).

## 2. Relabel — same label, different subject (do NOT collapse)

_same-NAMED ≠ same-derivation, applied to IA._ These are distinct units wearing one label — disambiguate the wording; collapsing them would lose real information.

| Unit | On pages | Canonical home | UX-law | Severity | Why / verify |
|---|---|---|---|---|---|
| **Pending approval** — _RELABEL / keep-distinct_ | asset-hub, inventory | n/a (distinct units) | Nielsen #2 (match real world) + Jakob | Major | Same LABEL "Pending approval" but different SUBJECTS (assets, parts) — same-named ≠ same-derivation. Do NOT consolidate; DISAMBIGUATE the labels (e.g. "Pending approval" → per-page "Pending approval (assets)"). |

## 3. Differentiate / merge — one job served many ways (review)

_Theme candidates (lower confidence)._ A human confirms whether these are one job-to-be-done (merge to a canonical home + deep-links) or legitimately distinct role/context views.

| Unit | On pages | Canonical home | UX-law | Severity | Why / verify |
|---|---|---|---|---|---|
| **theme: risk / hot / critical** — _DIFFERENTIATE / merge (review)_ | alert-hub, asset-hub, predictive, shift-brain | predictive | Hick + Miller (chunking) | Minor | 4 pages answer the "risk / hot / critical" job a different way: High-severity alerts (alert-hub); Anomaly signals (alert-hub); AMC parts at risk (alert-hub); Critical assets (asset-hub); Hot assets (predictive); Risk ranking table (predictive); Risk heatmap (predictive); Top risk this shift (shift-brain). Hick's Law — multiple entry points to one job slow the user. Likely canonical home → predictive, others deep-link. REVIEW: confirm one job (merge) vs legitimately distinct role/context views (e.g. PM-overdue ≠ project-overdue) before acting. |
| **theme: due soon / upcoming** — _DIFFERENTIATE / merge (review)_ | dayplanner, pm-scheduler, shift-brain | pm-scheduler | Hick + Miller (chunking) | Minor | 3 pages answer the "due soon / upcoming" job a different way: Tasks today (dayplanner); Tasks this week (dayplanner); Due this week (pm-scheduler); PMs due (shift-brain). Hick's Law — multiple entry points to one job slow the user. Likely canonical home → pm-scheduler, others deep-link. REVIEW: confirm one job (merge) vs legitimately distinct role/context views (e.g. PM-overdue ≠ project-overdue) before acting. |
| **theme: healthy / on-track** — _DIFFERENTIATE / merge (review)_ | pm-scheduler, predictive, skillmatrix | — (human picks) | Hick + Miller (chunking) | Minor | 3 pages answer the "healthy / on-track" job a different way: On track (pm-scheduler); Healthy assets (predictive); On target workers (skillmatrix). Hick's Law — multiple entry points to one job slow the user. Likely canonical home → — (human picks), others deep-link. REVIEW: confirm one job (merge) vs legitimately distinct role/context views (e.g. PM-overdue ≠ project-overdue) before acting. |
| **theme: late / overdue** — _DIFFERENTIATE / merge (review)_ | dayplanner, pm-scheduler, project-manager | pm-scheduler | Hick + Miller (chunking) | Minor | 3 pages answer the "late / overdue" job a different way: Overdue tasks (dayplanner); Overdue PMs (pm-scheduler); Past end date (project-manager). Hick's Law — multiple entry points to one job slow the user. Likely canonical home → pm-scheduler, others deep-link. REVIEW: confirm one job (merge) vs legitimately distinct role/context views (e.g. PM-overdue ≠ project-overdue) before acting. |

## 4. Affordance paths — review extra routes

_Body links to a deep page beyond the global nav (Hick's Law)._ Confirm each extra path earns its place.

| Unit | On pages | Canonical home | UX-law | Severity | Why / verify |
|---|---|---|---|---|---|
| **link → asset-hub** — _REVIEW (extra path)_ | analytics, index, predictive | asset-hub | Hick's Law | Minor | Deep page "asset-hub" reached from 3 page bodies BEYOND the global nav (analytics, index, predictive). Hick's Law — confirm each extra path earns its place; otherwise rely on the nav + one contextual link. |
| **link → integrations** — _REVIEW (extra path)_ | ph-intelligence, plant-connections | integrations | Hick's Law | Minor | Deep page "integrations" reached from 2 page bodies BEYOND the global nav (ph-intelligence, plant-connections). Hick's Law — confirm each extra path earns its place; otherwise rely on the nav + one contextual link. |
| **link → inventory** — _REVIEW (extra path)_ | hive, index | inventory | Hick's Law | Minor | Deep page "inventory" reached from 2 page bodies BEYOND the global nav (hive, index). Hick's Law — confirm each extra path earns its place; otherwise rely on the nav + one contextual link. |
| **link → ph-intelligence** — _REVIEW (extra path)_ | analytics, integrations | ph-intelligence | Hick's Law | Minor | Deep page "ph-intelligence" reached from 2 page bodies BEYOND the global nav (analytics, integrations). Hick's Law — confirm each extra path earns its place; otherwise rely on the nav + one contextual link. |
| **link → plant-connections** — _REVIEW (extra path)_ | hive, integrations | plant-connections | Hick's Law | Minor | Deep page "plant-connections" reached from 2 page bodies BEYOND the global nav (hive, integrations). Hick's Law — confirm each extra path earns its place; otherwise rely on the nav + one contextual link. |
| **link → pm-scheduler** — _REVIEW (extra path)_ | hive, index | pm-scheduler | Hick's Law | Minor | Deep page "pm-scheduler" reached from 2 page bodies BEYOND the global nav (hive, index). Hick's Law — confirm each extra path earns its place; otherwise rely on the nav + one contextual link. |
| **link → voice-journal** — _REVIEW (extra path)_ | index, logbook | voice-journal | Hick's Law | Minor | Deep page "voice-journal" reached from 2 page bodies BEYOND the global nav (index, logbook). Hick's Law — confirm each extra path earns its place; otherwise rely on the nav + one contextual link. |

## 5. Keep — consistent patterns (documented, no action)

_Replicated BY DESIGN — each instance shows its own page's data, or is an expected hub link (Jakob's Law)._ Not IA defects. Any copy-paste cost is a separate jscpd / Architect component-extraction refactor that does **not** change the IA.

| Unit | On pages | Canonical home | UX-law | Severity | Why / verify |
|---|---|---|---|---|---|
| **detail_panel (family ×15)** — _KEEP (consistent pattern)_ | achievements, alert-hub, analytics, asset-hub, dayplanner, hive, integrations, inventory, marketplace, ph-intelligence, pm-scheduler, predictive, report-sender, shift-brain, skillmatrix | — (each page owns its own) | Jakob + Nielsen #4 (consistency) | Polish | Design-system pattern on 15 pages — each instance renders THAT page's data. Not an IA defect. The copy-paste cost is a separate jscpd/Architect component-extraction job (see clone-debt). |
| **link → hive** — _KEEP (hub link)_ | alert-hub, asset-hub, audit-log, engineering-design, index, integrations, logbook, project-manager, shift-brain | hive | Jakob (expected hub) | Polish | hive is a hub every page reaches by design; body links to it are expected. |
| **link → index** — _KEEP (hub link)_ | audit-log, community, dayplanner, engineering-design, hive, inventory, logbook, pm-scheduler, voice-journal | index | Jakob (expected hub) | Polish | index is a hub every page reaches by design; body links to it are expected. |

---
### How to act on this
1. **Queue the decisions:** `python ufai_ingest.py ia_streamlining_candidates.json` → merges the 12 non-KEEP rows into `sweep_critiques.json` (idempotent), where they flow through `flywheel_orchestrator` → `promotion_queue.md`.
2. **Dispose** each via `promotion_dispositions.json` (accept / defer / reject) — same mechanism as every other sweep finding.
3. **For accepted CONSOLIDATE rows**, the implementation is an Architect/Frontend job (shared component or canonical-source read + deep-link); the **0-math-drift** invariant (`validate_user_facing_kpi_canonical.py`) must stay green.

_Phase 3 (optional): a UXAgent novice×role persona walkthrough to confirm a new user isn't confused by what survives._
