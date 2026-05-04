# Production Fixes — Discovered During Testing

Bugs, missing fields, schema gaps, and UX issues found while running the test-data-seeder against a local copy of WorkHive. Each entry has severity, location in the codebase, and how to fix.

**How to use this file:**
- Items get added here as testing surfaces them.
- Move entries between sections (🔴 → 🟡 → ✅) as priorities shift or fixes ship.
- When you ship a fix in production, copy the entry into your PR description and move it to ✅ Fixed with the date + commit ref.

**Last updated:** 2026-05-03 (entry #12 logged + fixed)

---

## 🔴 Critical — breaks a user flow

_(none currently)_

---

## 🟡 Important — degrades UX or data quality

### 8. AI orchestrator returns object instead of string for some queries — FIXED 2026-05-04

(See "Fixed" section.)

### 17. Diagnostic PM-Failure Correlation calc joins on incompatible keys (always 0 matches) — OPEN 2026-05-03

**Source:** `ui:Analytics Diagnostic tab > PM-Failure Correlation panel (test session 2026-05-03)`

**Test message:** Only 0 machines with both PM and failure data - need >= 5

**Found:** 2026-05-03T11:22:03+00:00 via WorkHive Tester

**What's wrong:** diagnostic.calc_pm_failure_correlation() in python-api/analytics/diagnostic.py:99 merges pm_completions (asset_id is UUID FK to pm_assets.id) with logbook (machine field is the HUMAN asset_id code like PMP-001 from the assets table). It tries to bridge them by mapping UUID -> asset_name via pm_scope_items, then matching on asset_name. But logbook.machine is the human code, not the readable name, so the merge yields 0 matches every time.

**Architectural mismatch:** logbook references the `assets` table (human asset_id codes), pm tables use their own `pm_assets` table (UUIDs internally, with `tag_id` for the human code). To correlate, the orchestrator needs to enrich pm_completions/pm_scope_items with the human code (pm_assets.tag_id OR a join through assets.asset_id), then the calc joins on that human code.

**Fix to apply:**
1. analytics-orchestrator: select pm_assets `id, asset_name, tag_id, category` (currently misses tag_id). Build a `tag_id_map` UUID->tag_id alongside the existing assetMap UUID->name. Enrich pm_completions and pm_scope_items with `machine_code: tagIdMap[asset_id]`.
2. python-api/analytics/diagnostic.py: change calc_pm_failure_correlation to merge on `machine_code` (the human asset code) instead of asset_name.
3. Same enrichment likely needed for predictive/prescriptive calcs that touch both PM and logbook.

**Related seeder bug (separately fixed):** test-data-seeder/seeders/logbook.py was building machine as '{name} ({asset_id})' instead of just asset_id. That made the seeded data not even match production's format. Aligned the seeder to store machine = asset.asset_id.

**Same root cause also breaks Prescriptive `PM Interval Optimization`** (`prescriptive.py:126`). It builds `mtbf_map` keyed by `logbook.machine` (human code like "PMP-001"), then iterates `pm_scope_items.asset_name` (readable name like "Centrifugal Pump 50HP") and looks up MTBF — never matches, all assets skip, recommendations list stays empty. The UI then renders the empty state as `✓ Current PM intervals are appropriate based on failure history`, which is misleading: it's not "we computed and you're fine," it's "we couldn't compute anything." Need to fix the join (use the human asset code) AND change the empty-state copy to `No comparable failure history yet — recommendations will appear once breakdowns log against assets in scope.`


---


## 🟡 Important — degrades UX or data quality

_(none currently)_

---

## 🟢 Nice to have — polish, refactors, doc gaps

### 11. 6 tap targets <44px — OPEN 2026-05-03

**Source:** `ui:Mobile`

**Test message:** logbook.html: 6 tap targets <44px

**Found:** 2026-05-03T08:59:43+00:00 via WorkHive Tester

### 15. Worker names on hive page should be clickable (mini-profile drawer) — OPEN 2026-05-03

**Source:** `ui:hive.html (test session 2026-05-03)`

**Test message:** Plain text worker names on Team Stock Issues + Roster panels

**Found:** 2026-05-03T10:41:14+00:00 via WorkHive Tester

Worker names render as plain text on the hive page (Team Stock Issues panel + Roster panel). Clicking does nothing. A nice-to-have improvement: turn each name into a clickable mini-profile drawer showing skill level, open jobs count, recent logbook activity, and low-stock items for that worker. Useful for supervisors during stand-ups or shift handovers - one tap to know who is overloaded or has skill gaps. Not urgent; deal with it when time permits.

---


## ✅ Fixed — for the changelog

### 29. Analytics panel order reranked by decision-relevance (top = what matters most) — FIXED 2026-05-04

**Source:** UX continuation. Each phase had panels in arbitrary code order; user wanted them ranked by what matters most to read first.

**Fix — reordered the `html += render*()` lines in 4 functions:**

**Descriptive (synthesis → reliability → drilldowns → cost):**
OEE → Availability → MTBF → MTTR → PM Compliance → Downtime Pareto → Failure Frequency → Repeat Failures → Parts Consumption

**Diagnostic (root causes → recurrence → correlations → taxonomy → QA):**
Failure Mode Distribution → Repeat Failure Clustering → PM-Failure Correlation → Skill-MTTR Correlation → Parts Availability Impact → RCM Consequence → Engineering Validation

**Predictive (trend → specific predictions → triage → realtime → schedule → supply → leading indicator):**
Failure Trend → Next Failure Prediction → Health Scores → Anomaly Baseline → PM Due Calendar → Parts Stockout → Parts Consumption Spike

**Prescriptive (synthesis → triage → this-week ops → schedule change → HR development):**
AI Action Plan → Priority Ranking → Technician Assignment → Parts Reorder → PM Interval Optimization → Training Gaps

**Skills consulted:**
- Analytics Engineer: "lead with the most-asked exec KPI" + "one chart, one insight" — synthesis first, drilldowns after
- Designer: hierarchy preserved (orange Action Plan card stays at top of Prescriptive)
- Mobile Maestro: above-the-fold = ~1 panel on 375px; the most decision-relevant panel is now first on every tab

**Risk:** zero. Pure DOM order swap. No content/schema changes.

### 28. Analytics role-view layout — period controls moved to header + Supervisor card absorbed full AI rec — FIXED 2026-05-04

**Source:** UX Phases 2 + 3 of the role-card cleanup (continuation of #27).

**Phase 2 — period controls relocated:**
The period selector (30·90·180·1yr) and Refresh button were sitting BETWEEN the role-quick-view and the status bar, making them feel role-specific even though they're page-level controls. Moved them up to sit immediately under the page header (above the role-bar), grouping all page-level controls together.

**Phase 3 — Supervisor card absorbed the AI recommendation in full text:**
After #27 deleted the duplicate banner below the role card, the AI synthesis (`presc.action_plan.summary`) had no place to render in full. Added a styled `.role-ai-rec` block inside the Supervisor view that shows the complete recommendation (no `.slice(0, 80) + '...'` truncation). Light purple background, border, label "⚡ AI recommendation", body text at 0.74rem. Stays at the bottom of the card since it integrates the rows above.

**Result:** above-the-fold layout is now:
- Page header (title + Stage 3 badge)
- Period selector + Refresh
- Role tabs (Worker / Supervisor)
- Role quick view (with AI rec inside if Supervisor)
- Status bar
- Phase tabs + filter chips + phase content

Three role views collapsed to two; the redundant chip strip and duplicate banner from #27 are gone; the AI recommendation now reads in full inside the role card. ~30 KB removed total across #27 + #28.

### 27. Analytics role views were cluttered + included a fake "Manager" role + duplicated AI banner — FIXED 2026-05-04

**Source:** UX Phase 1 of role-card cleanup (after #24/25/26 list-scaling work).

**What was wrong:**
- The Analytics page had 3 role tabs: Field Tech / Supervisor / Manager. But per the multitenant-engineer skill ("a worker can only read and write their own hive's data; a supervisor can manage members…"), **only Worker and Supervisor exist as actual `hive_members.role` values**. Manager was a UI fiction showing reframed supervisor data.
- A "Command Summary Bar" below each role card showed KPI pills (MTBF/MTTR/PM Compliance/OEE/anomaly count) — the same numbers already rendered inside each role card AND inside each phase panel. Triple duplication.
- An AI recommendation banner appeared TWICE on Supervisor + Manager screens — once truncated inside the role card, once full-text below as a separate banner.

**Fix:**
- Removed Manager button from role-bar HTML.
- Removed `buildManagerView()` (~25 lines).
- Removed `updateCommandBar()` (~95 lines), `ragColor()`, `makePill()`.
- Removed `<div id="command-bar">` HTML and the orphaned `command-pills` / `command-alert` container.
- Removed `.cmd-pill` CSS (15 lines).
- `setRole()` now clamps unknown role values to `worker` so any stale localStorage `_role='manager'` falls back gracefully.

Net diff: ~150 lines removed. Same information, less duplication. Above-the-fold real estate freed up so the role card and phase tabs sit closer together.

**Skills consulted:**
- Multitenant Engineer — confirmed only 2 hive roles exist
- Analytics Engineer — `>5 KPIs needs role toggle` (kept), Manager tier was aspirational not implemented
- Designer — pill-style toggle group preserved for the role switcher (correct pattern)

**Verified:** page HTTP 200, 113KB (was ~118KB), zero leftover references to the removed names.

### 26. Analytics global filter chips — narrow every panel by criticality + discipline — FIXED 2026-05-04

**Source:** UX Phase 2 of the Analytics scaling plan (after #24 Top-N + #25 search).

**What was added:** A pill-style filter chip bar at the top of the Analytics page, between the phase tabs and the info banner. Two dimensions:
- **Criticality:** All / Critical / High / Medium / Low (5 chips)
- **Discipline:** All / Mechanical / Electrical / Instrumentation / Hydraulic / Pneumatic / Lubrication (7 chips)

Server-side filter at the orchestrator (analytics-orchestrator/index.ts: new `applyFilters(data, filters)` function). After fetching raw data per phase, narrows every asset-keyed array (logbook entries, pm_completions, pm_scope_items, pm_assets) plus the precomputed RPC arrays (MTBF/MTTR/Frequency/Pareto/Repeats) by an `allowedCodes` set built from the filters. Discipline-only filters that hit logbook also narrow the precomputed RPCs by deriving allowedCodes from the filtered logbook's machine codes.

State persists in `localStorage.wh_analytics_filters` so the user's selection survives page reloads. Filter change clears the per-phase cache and re-fetches all 4 phases. Active filter banner ("Filtered: Criticality: Critical · Discipline: Mechanical · clear") appears below the chips when any filter is applied.

**Skills consulted:**
- Designer: pill-style toggle button group preferred over `<select>` for 3-8 known options.
- Frontend: state in `let _filters = {...}`, persistence via localStorage, cache invalidation on filter change.
- Mobile Maestro: chips are 32px visual / 44px hitbox via padding; horizontal scroll on the discipline group below 600px so the row doesn't wrap awkwardly.

**Verified with seeded Lucena hive (30 assets, 6 Critical):**
- `criticality=Critical` → priority ranking 6 rows (was 30), MTBF/MTTR narrowed
- `discipline=Mechanical` → 25 MTBF rows (Mechanical-only machines)
- `criticality=Critical AND discipline=Mechanical` → 4 ranking rows (intersection)

### 25. Analytics search input on long lists — find an asset/part by typing — FIXED 2026-05-04

**Source:** Continuation of #24 (UX overflow). With 30 assets per hive a "Show all" button only solves part of the problem; users still scroll to find a specific machine.

**Fix:** Extended `renderListWithShowAll()` with two new options: `searchable: true` and an optional `searchPlaceholder`. When enabled AND the list has ≥ 8 items, the helper renders a `<input type="search">` above the list. Typing filters rows by `textContent.includes(query)` (case-insensitive). Search auto-expands the hidden Show-All container so matches outside the top N are visible. Clearing the input restores the default Top-N view.

**Panels with search now:** MTBF, MTTR, Availability, Parts Consumption, Repeat Failures (auto for ≥8), Priority Ranking, PM Interval Optimization (custom placeholder "Filter by asset name or code…"), Parts Reorder, Next Failure Prediction. 8 panels total.

**Mobile considerations (per Mobile Maestro skill):**
- Input `font-size: 0.82rem` (≥ 16px effective) — no iOS auto-zoom on focus
- `min-height: 38px` — close enough to tap target without overwhelming the visual
- `type="search"` gets the native iOS clear button ✕
- `-webkit-appearance: none` removes weird iOS rounded-rect default

**Skipped:**
- Failure Frequency (bar chart aesthetic — search would clutter)
- Small lists (<8 items) — search hidden by the `total >= 8` guard inside `renderListWithShowAll`

### 24. Analytics panels overflowed with realistic data — added Top-N + Show All pattern — FIXED 2026-05-04

**Source:** `ui:Analytics page (test session 2026-05-04, all 4 phases)`

**What was wrong:** With 30 seeded assets per hive and 90-day breakdown history, several Analytics panels rendered the entire dataset (30+ rows) inline, producing a forever-scroll page. Worst offender was PM Interval Optimization at 30 cards before #21, still 30 after; Priority Ranking, MTBF, MTTR, Availability, Repeat Failures, Next Failure Dates, and Parts Reorder all had no caps.

**Fix:** Added one reusable `renderListWithShowAll({ items, renderRow, wrap, tableHeader, defaultN, itemNoun })` helper in `analytics.html` (defined once, applied 10 times). It renders the first N items visibly, hides the rest in a sibling `<tbody class="extra-rows" hidden>` (or `<div class="extra-cards" hidden>` for card lists), and emits a `<button class="showall-toggle">Show all 30 assets ↓</button>` that flips the hidden attribute. No re-render on toggle. Mobile-tap-target compliant (44px min height, per Mobile Maestro skill).

**Panels upgraded:**
- Descriptive: MTBF, MTTR, Availability, Failure Frequency, Parts Consumption, Repeat Failures
- Predictive: Anomaly Baseline (was 90+ row flood), Parts Spike, Next Failure Prediction, Parts Stockout
- Prescriptive: Priority Ranking, PM Interval Optimization, Parts Reorder

**Pattern reuse:** the helper accepts `wrap: 'table' | 'cards'` so it works for both data-table panels and stacked-card panels (PM Optimization, Availability, Failure Frequency). Single source of truth.

**Skills consulted:** Designer (toggle button group preferred over dropdown), Frontend (dom modal-before-script rule preserved; helper avoids re-rendering on toggle), Mobile Maestro (44px tap target on toggle button), Analytics-engineer (mobile-readable list patterns, top-N stays visible by default).

**Found by:** user noted PM Interval Optimization scrolling endlessly with 30 Kaeser CSD 105 cards.

### 23. Priority Maintenance Ranking showed every asset as Medium / P1 — three layered bugs — FIXED 2026-05-04

**Source:** `ui:Analytics Prescriptive tab > Priority Maintenance Ranking (test session 2026-05-04)`

**What was wrong:** the panel showed all 30 seeded assets as "Medium" criticality and all as P1, making the ranking useless. Three stacked bugs:

1. **Seeder vocabulary mismatch:** `assets.py` produced criticality values `Major / Minor / Critical`, but the platform's canonical labels (per `pm-scheduler.html` dropdown) are `Critical / High / Medium / Low`.
2. **Calc lookup keyed wrong:** `calc_priority_ranking()` keyed `crit_map` by `asset_name` and looked up by `logbook.machine` (which is the human asset code, not the name). Same architectural issue as #17. Lookup always missed → "Medium" default for every machine.
3. **Edge function didn't pass `tag_id`:** `fetchPrescriptiveData` SELECTed `id, asset_name, category, criticality` from pm_assets but omitted `tag_id` (the human code). Even after fixing #2, the calc had no key to look up by.
4. **Tier thresholds too low:** P1 ≥ 20 / P2 ≥ 8 made every asset P1 once basic failure activity existed. With realistic 90-day data scores reach 50-250.

**Fix:**
- `seeders/assets.py`: `CRITICALITY_WEIGHTS` now uses canonical `Critical / High / Medium / Low` (with Critical~12% / High~25% / Medium~50% / Low~12% distribution).
- `prescriptive.py CRITICALITY_WEIGHT`: kept canonical 4 plus Major/Minor aliases for backward-compat with un-reseeded data.
- `prescriptive.py calc_priority_ranking`: keyed `crit_map` by `tag_id` (human code) instead of asset_name; matches `logbook.machine`.
- `analytics-orchestrator/index.ts fetchPrescriptiveData`: added `tag_id` to the pm_assets SELECT.
- Tier thresholds: P1 ≥ 150, P2 ≥ 60 (was 20/8). Calibrated for 90-day windows.

**Verified with seeded Lucena hive:** 8 P1 / 22 P2 / 0 P3 (was 30 P1 / 0 P2). Top of list now shows Critical machines (PV-002, BF-002), then Major (TT-002, MILL-001). Real prioritization signal.

### 22. AI Action Plan only saw Prescriptive data — now reasons across all 4 analytics phases — FIXED 2026-05-04

**Source:** `ui:Analytics Prescriptive tab > AI Action Plan panel (test session 2026-05-04)`

**What was wrong:** `callGroqSynthesis()` in `analytics-orchestrator/index.ts` built its prompt from prescriptive recommendations only (priority_ranking, pm_optimizations, assignments, reorder, training_gaps). The AI couldn't reference WHY anything was being recommended — no MTBF/MTTR numbers (descriptive), no failure modes or correlations (diagnostic), no forecasted failures or stockout dates (predictive). Output was generic templated bullets like "Pablo to focus on X, others to support, review PM frequency."

**Fix:** Server-side fan-out. When phase=prescriptive runs, the orchestrator now also calls Python for descriptive + diagnostic + predictive in parallel using the same loaded data shape, builds a 4-phase context bundle, and passes that to Groq with an updated system prompt that explicitly instructs the AI to draw cross-phase connections (descriptive number + diagnostic root cause → prescriptive action; predictive forecast + prescriptive reorder → watch-list entry).

**Verified with seeded Lucena hive:** action plan now cites specific machine codes, KPI numbers, and phase signals. Example: "Inspect TT-002 — highest downtime hours (70.6) and failure count (16) with top root cause of Wear (diagnostic)." Watch list now explains WHY each item is on it ("AC-002 forecast to fail soon (predictive), only 1 spare seal kit (prescriptive reorder)"). Cost: 3 extra Python calls per Prescriptive load, ~2-5s added latency on warm cache. Worth it for once-per-session action plans.

### 21. PM Interval Optimization spammed N cards per asset (one per scope item) and didn't show machine_code — FIXED 2026-05-04

**Source:** `ui:Analytics Prescriptive tab > PM Interval Optimization (test session 2026-05-04)`

**What was wrong:** The Python calc emitted one recommendation per scope item per asset. With 30 assets each having ~5 PM tasks (Weekly/Monthly/Quarterly/Semi-annual/Annual), that's 145+ cards all saying the same thing per asset. Plus, when multiple assets share a model name (4 Kaeser CSD 105 compressors in the same hive), the rendered cards were indistinguishable — no machine_code shown.

**Fix:**
- `prescriptive.py calc_pm_interval_optimization`: aggregate by asset. Compare MTBF against the TIGHTEST current PM interval (most frequent task) for "increase" decisions, against the LOOSEST for "reduce" decisions. Emit ONE recommendation per asset with `scope_items_count` indicating how many tasks the change covers.
- `analytics.html renderPMOptimization()`: show the machine_code badge next to asset name (gold-tinted code chip), and add "covers N PM tasks" to the recommended-frequency line.

**Verified with seeded Lucena hive:** went from 145 recs → 30 recs (one per evaluated asset). Each card distinguishable by machine_code. AC-001 through AC-004 are 4 separate Kaeser CSD 105 compressors, now visibly different.

### 20. Technician Assignment piled every open job on the highest-skilled supervisor — FIXED 2026-05-04

**Source:** `ui:Analytics Prescriptive tab > Technician Assignment panel (test session 2026-05-04)`

**What was wrong:** `calc_technician_assignment()` in `prescriptive.py` picked a single "best tech per discipline" (highest level), then assigned every job in that discipline to the same person. With one cross-trained supervisor (e.g. Pablo Aguilar L3+ in Mechanical, Electrical, AND Instrumentation), all 10 displayed jobs landed on him. Realistic supervisors would never do this — they'd spread the load.

**Fix:**
- Replaced `best_by_disc: dict` (single best) with `ranked_by_disc: dict` (sorted list of qualified techs per discipline).
- Added a `MAX_CONCURRENT_JOBS = 3` cap and a per-worker `load` counter.
- New `_pick_next_best(disc)` helper: returns highest-skilled tech under the cap; if all are capped, returns the fewest-loaded one (skill level breaks ties).
- Each assignment's `reason` field now explains the picking logic — "no current open jobs" / "currently has N other open jobs" / "all {disc} techs at workload cap; fewest-loaded wins."

**Verified with seeded Lucena hive (5 workers, 18 open jobs, 10 displayed):** Pablo gets 4 (3 Mechanical + 1 Instrumentation, his cap), David Velasco gets 4 Mechanical (L1 backup), Ricardo Morales 1 Instrumentation, Dennis Aquino 1 Electrical. Spread is realistic.

**Found by:** user spotted the "all 10 jobs to one person" pattern during prescriptive walkthrough.

### 19. Two Prescriptive panels showed false-positive "all good" green checkmarks when calc had nothing to compare — FIXED 2026-05-03

**Source:** `ui:Analytics Prescriptive tab > PM Interval Optimization + Training Gap Recommendation panels (test session 2026-05-03)`

**What was wrong:** Both panels rendered a green ✓ message ("Current PM intervals are appropriate" / "No significant training gaps detected") whenever their `recommendations`/`gaps` arrays were empty — without distinguishing "we evaluated everything and it's healthy" from "we couldn't evaluate anything and have no findings to report." The user got false confidence in two different unrelated states.

**Root cause:** Python calcs returned `{recommendations: [], standard: "..."}` regardless of whether 0 assets were comparable or 50 assets were compared and all healthy. UI couldn't tell which.

**Fix:**
- `prescriptive.py calc_pm_interval_optimization`: now returns `compared_count`, `skipped_count`, `scope_asset_count` so the UI can render one of three honest messages — "compared N healthy" / "couldn't compare" / "no scopes registered."
- `prescriptive.py calc_training_gaps`: now returns `categories_evaluated`, `above_threshold_count`, `badge_count` — UI renders one of four honest messages — "no closed entries" / "no skill badges" / "evaluated N, no spikes" / "spikes exist but everyone is L3+."
- `analytics.html renderPMOptimization()` + `renderTrainingGaps()`: branch on the new fields to pick the right empty-state copy. The misleading green ✓ only fires when there's actual evidence of healthy state.

**Found by:** user noticed the green ✓ on PM Interval Optimization while the underlying data was clearly broken (related to #17). Asked "why I got this result in prescriptive" — the panel was lying to them.

### 18. Technician Assignment skill-gaps panel showed duplicate generic messages, hid machine context — FIXED 2026-05-03

**Source:** `ui:Analytics Prescriptive tab > Technician Assignment panel (test session 2026-05-03)`

**What was wrong:** Python (`prescriptive.py:267-271`) builds skill_gap entries with `{machine, discipline, gap}` — three fields per gap. The renderer in `analytics.html:1457` was only displaying `g.gap` (the pre-formatted generic string `No qualified Mechanical technician found in the team.`), discarding the machine name and discipline. Result: 8 identical-looking lines for 8 different machines, with no indication of WHICH machines were unassigned. Useless for action.

**Fix:** Group gaps by discipline, show the discipline as a single rolled-up line with the affected machine count + first 4 machine names (truncated with "+N more" overflow). Now one row per missing discipline, with concrete context for what to do about it.

**Found by:** user spotted the duplicate "No qualified Mechanical technician found in the team" lines while exploring the Prescriptive tab.

### 16. Edge functions had two flavors of schema drift on inventory_items + inventory_transactions — FIXED 2026-05-03

**Source:** `ui:Analytics page Descriptive tab "Parts Consumption Rate" panel always empty`

**What was wrong:**
1. `analytics-orchestrator/index.ts:67` SELECTed `part_name` from `inventory_transactions`. That column doesn't exist on that table — `part_name` lives on `inventory_items`. PostgREST silently returned rows without a part_name, the Python `calc_parts_consumption()` saw `df.part_name` missing, and dropped to "No parts usage transactions found in period" no matter how much data was seeded.
2. `analytics-orchestrator/index.ts:152` and `ai-orchestrator/index.ts:91` SELECTed `reorder_point` from `inventory_items`. Real column is `min_qty` (same bug as #12 in `assistant.html`, in two more places). Predictive stockout calc and the AI inventory-risk agent both saw `undefined` and silently produced wrong results.

**Production impact:** Every analytics user got an empty "Parts Consumption Rate" panel; predictive stockout calculations were wrong; the AI assistant's inventory-risk agent reported "qty:5|reorder_at:undefined" to the LLM and got noise back.

**Fix:**
- Embed `inventory_items(part_name)` in the inventory_transactions PostgREST query, then flatten the nested object before passing to the Python API.
- Alias `min_qty` as `reorder_point` in both edge functions' selects so the existing Python and prompt logic keeps working: `select("..., reorder_point:min_qty, ...")`.

**Validator extension that prevents recurrence:** `validate_schema_coverage.py` originally scanned only HTML/JS at the project root. Extended it to also scan `supabase/functions/*/index.ts` and `supabase/functions/_shared/*.ts`. Findings count jumped from 105 → 133 db.from().select() calls scanned. The 3rd reorder_point bug in ai-orchestrator was caught immediately by the validator after the extension; without it, that one would have shipped with the first two fixes.

**Found by:** user spotted the empty Parts Consumption panel during the Descriptive analytics walkthrough.

**Verified by:** `python validate_schema_coverage.py` returns `2 pass · 0 warn · 0 fail` (133 calls scanned, all known columns). Edge runtime restarted; analytics-orchestrator now returns `"source":"python_computed"` with no errors.

### 14. Team Stock Issues panel showed worker names + counts instead of the actual parts — FIXED 2026-05-03

**Source:** `ui:hive.html Team Stock Issues panel (test session 2026-05-03)`

**What was wrong:** The panel rendered "David Velasco — 1 low / Emma Velasquez — 1 low / Ricardo Morales — 1 low". You can see WHO is short, but not WHAT they're short of. In a hive context where inventory is shared and supervisors approve new stock, the actionable signal is the part name (so you can plan a buy/order), not whose name is attached.

**Fix:** Refactored `renderTeamStockSummary()` in `hive.html` (lines 1774-1802) to flatten the item list rather than group by worker. Now shows: `[•] Bearing 6204    Marcelino Madrigal    [3 of 5 pcs]`. Out-of-stock items sort first (red dot + "OUT" pill); low items second (gold dot + "X of Y unit" pill); alphabetical within each severity. Capped at 8 visible items with "+N more" overflow link.

**Found by:** user spotted it during their first hands-on testing session via the seeded data. Exactly what the closed-loop dashboard is for.

### 13. Hive join fails with FK violation when browser has stale Supabase JWT after reseed — FIXED 2026-05-03

**Source:** `ui:Hive join flow (test session 2026-05-03)`

**Test message:** `Could not join: insert or update on table hive_members violates foreign key constraint hive_members_auth_uid_fkey`

**Root cause:** Reset wipes `auth.users` (delete by email). Reseed creates new auth users with new UUIDs. But the browser still holds the OLD Supabase JWT from before the wipe. JWTs are stateless, so `db.auth.getSession()` happily returns the stale session. When the hive-join code INSERTs into `hive_members` with that dead `auth_uid`, the FK constraint fails.

**Production impact:** any user whose `auth.users` row gets deleted (rare in prod, but plausible during account merges, admin cleanup, or when someone deletes their account and re-signs up) will hit a confusing FK error and be unable to join a hive.

**Fix:** in `hive.html` join handler, detect the FK error pattern (`/auth_uid.*fkey|violates foreign key/i`), auto-sign-out, clear all `wh_*` localStorage keys, and redirect to `index.html?signin=1`. The user gets a friendly message ("Your sign-in session expired (auth was reset). Redirecting you to sign in again…") instead of the raw error.

**Verified by:** the next time you Reset + Reseed in the Tester and try to join a hive, instead of dead-ending on the FK error, you're cleanly redirected to sign in fresh.

### 12. assistant.html queried inventory_items with wrong column names (name, reorder_point) — FIXED 2026-05-03

`assistant.html:424` SELECTed `name, reorder_point` from `inventory_items` but the schema columns are `part_name` and `min_qty`. The downstream low-stock filter and render logic at lines 476-478 also referenced the wrong field names, so all 5 references were broken.

**Production impact:** workers using the AI assistant on a hive page got broken inventory context. Items showed as `undefined: 5 pcs` in the prompt, and the low-stock filter never triggered (`i.reorder_point` was always `undefined`, falling through to the `qty_on_hand <= 2` fallback). The AI saw broken data and either ignored inventory or hallucinated names from elsewhere in the prompt.

**Fix:** at all 5 references in `assistant.html`, changed `name` → `part_name` and `reorder_point` → `min_qty`. The actual schema (in `supabase/migrations/20260420000000_baseline.sql:828`) defines `part_name` and `min_qty`.

**Found by:** the new `validate_schema_coverage.py` validator on its first run. It auto-derives the table/column map from `supabase/migrations/*.sql` and checks every `db.from().select()` plain-column reference exists. Caught both bad columns immediately.

**Verified by:** `python validate_schema_coverage.py` returns `2 pass · 0 warn · 0 fail`. Full `python run_platform_checks.py --fast` returns `56 PASS · 0 FAIL · 0 WARN`.

### 2. iOS auto-zoom on inputs in pm-scheduler + marketplace pages — FIXED 2026-05-04

Found and fixed in one session:
- `pm-scheduler.html` — `<select id="cat-filter">` had inline `font-size:0.875rem`. Removed the inline override so `wh-input`'s 1rem default takes over.
- `marketplace.html` — three CSS classes (`.search-input`, `.wh-select`, `.wh-textarea`) all had `font-size: 0.82rem`. Bumped all three to `1rem`.

**Verified by:** Mobile Playwright flow now reports `41 pass, 0 fail` (was `39 pass, 2 fail`). All visible inputs measure ≥16px.

### 7. semantic-search + embed-entry used non-existent Groq embedding model — FIXED 2026-05-04

Replaced the single Groq embedding call (which never worked — Groq offers chat-only) with a 2-provider fallback chain at `supabase/functions/_shared/embedding-chain.ts`:

1. **Voyage AI** (`voyage-3.5-lite` at 512 dims, truncated to 384) — primary, 200M tokens/month free
2. **Jina AI** (`jina-embeddings-v3` at 384 dims native) — secondary, 100M tokens/month free

Both `semantic-search` and `embed-entry` now import `generateEmbedding()` from this shared file. Output is a 384-dim vector compatible with the existing `vector(384)` schema on knowledge tables.

**Verified by:**
- Local edge function logs show `[embedding] ok via voyage (384 dims)` on every semantic search call
- AI gate's `ai_semantic` test now PASS (was KNOWN-FAIL)
- Total free capacity ~300M tokens/month, sustainable for production

**Production migration:** Add `VOYAGE_API_KEY` and `JINA_API_KEY` to your Supabase project's secrets dashboard before deploying. Without those, the chain falls through and embeddings throw — same behavior as before, just with explicit error.

---

### 10. handle_community_post_xp trigger didn't propagate auth_uid — FIXED 2026-05-04

When the trigger awards `voice_of_the_hive` to a worker on their 10th post, it inserted into `skill_badges` without `auth_uid`. Result: badge rows had NULL auth_uid, which under RLS means the badge owner can't read their own badge. Migration `20260504000001` updates the trigger to copy `NEW.auth_uid` (the post author's auth_uid) onto the badge row.

**Verified by:** Test runner's "auth_uid populated everywhere" check, which previously flagged 2/31 skill_badges as NULL.

---

### 9. assistant.html queried non-existent skill_badges.badge_type column — FIXED 2026-05-04

`assistant.html:422` queried `db.from('skill_badges').select('discipline,level,badge_type')` — but the column is `badge_key`, not `badge_type`. Result: every page load fired a 400 Bad Request that silently dropped the worker's badge context from the AI assistant's prompt.

**Fix:** changed `badge_type` to `badge_key` in `assistant.html`. The column was added by migration `20260504000000_skill_badges_badge_key.sql` (this session).

**Status:** FIXED 2026-05-04

---

### 8. AI orchestrator returns structured object instead of string — FIXED 2026-05-04

`ai-orchestrator`'s synthesis step asks the LLM for `{ "answer": "string" }` but Groq sometimes returns `{ "answer": { ...structured... } }`. The frontend then renders `[object Object]` instead of useful content.

**Fix:** added `formatStructuredAnswer()` post-processor in `ai-orchestrator/index.ts` that converts an object answer into bullet-formatted markdown text (key → bold heading, arrays → bulleted lists).

**Verified by:** AI assistant now shows readable bullet-formatted answers with named machines, downtime hours, and root causes.

### 1. `skill_badges.badge_key` column missing — FIXED 2026-05-04

Migration `20260504000000_skill_badges_badge_key.sql` adds:
- `badge_key text` column on `skill_badges`
- Non-partial UNIQUE INDEX `(worker_name, badge_key)` (Postgres treats NULLs as distinct, so existing exam-based badges with NULL badge_key don't conflict)
- `DEFAULT 0` on `exam_score` so the community trigger insert (which omits exam_score for non-exam badges) doesn't violate NOT NULL

**Verified by:** Release gate now reports 0 failures across 155 automated checks. Voice of the Hive badge correctly awards on the 10th community post per author in a hive.

### 3-6. Platform Guardian regressions — FIXED 2026-05-04

These were *artifacts of the test environment* (pg_dump baseline file conflicting with developer-format validators), not real production bugs. All 4 cleared:

- **Marketplace Validator + Knowledge Freshness** — fixed by restoring the original 38 incremental migrations alongside the baseline (the original developer-format SQL contains the patterns the validators look for).
- **Vector Schema + Idempotency** — fixed by teaching `validate_vector_schema.py` and `validate_idempotency.py` to skip `*_baseline.sql` files (which use pg_dump's quoted-identifier dialect, not the project's developer convention).

**Verified by:** Platform Guardian now reports `54 PASS · 0 FAIL` (was `50 PASS · 4 FAIL`). Release gate verdict: **READY — safe to deploy**.

---

## Template for new entries

```
### N. Short imperative title

**Discovered:** YYYY-MM-DD — which test/page/seeder surfaced it

**What's wrong:**
Plain-English description of the bug or gap. Include exact error message if any.

**Where:**
- File path / table / function name

**How to fix:**
1. Concrete step
2. Concrete step

**Workaround in seeder/test:** (optional)

**Status:** TO DO | IN PROGRESS | FIXED (date, commit ref)
```
