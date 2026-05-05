# Project Manager — Roadmap

A unified industrial-project-tracking page for WorkHive. Four flavours sharing one schema:
**workorder** (bundle existing work) · **shutdown** (turnaround) · **capex** (improvement) · **contractor** (vendor job folder).

Standards basis: PMBOK 7th ed., ISO 21500, AACE 17R-97, IDCON 6-Phase Shutdown Model, NSCP for contractor scope.

---

## Phase 0 — Foundation (SHIPPED 2026-05-04 / 05)

What's already live in the codebase.

| Deliverable | Status |
|---|---|
| Migration `20260505000000_project_manager.sql` (4 tables + RPC + realtime) | ✓ |
| Edge function `project-progress` (TS, hand-rolled CPM + EVM) | ✓ (will be replaced in Phase 2) |
| `project-manager.html` v1 — list, create, 7 detail tabs | ✓ (skeletal — Phase 1 makes it usable) |
| 9-place wizard registration (nav, floating-ai, assistant, validators, all 4 Tester flows) | ✓ |
| Client-side rollup fallback when edge fn is unavailable locally | ✓ |
| Tester `/brand_assets/` route (so manifest icons resolve in test mode) | ✓ |
| Platform Guardian: 57 PASS · 0 FAIL · 0 WARN | ✓ |

**Exit criterion met:** schema lives, page registered, no validator regressions.

---

## Phase 1 — Make it Friendly (UX redesign — NEXT)

This phase fixes the "rigid and boring" feedback. Pattern: pre-populated content the user toggles, mirroring `pm-scheduler.html` `PM_TEMPLATES` and `engineering-design.html`'s discipline tabs.

Split into 3 commits, each verified in Tester before moving on.

### Phase 1A — Templates + 3-step wizard
- Add `PROJECT_TEMPLATES` JS literal (4 types × 3-5 templates each = ~15 starter packs)
  - **shutdown:** Centrifugal Pump Overhaul · Boiler Annual Inspection · Electrical Substation Shutdown · Heat Exchanger Cleaning
  - **capex:** CAPEX with FEL Stage Gates (Class 5→1) · Equipment Replacement · DCS / PLC Instrumentation Upgrade · Greenfield Install
  - **contractor:** Fabrication + Install · Specialised OEM Repair · Annual Service Contract · Painting / Insulation
  - **workorder:** Breakdown Repair Bundle · PM Campaign (multi-asset) · Asset Reliability Study
- 3-step new-project flow: Type tile → Template card → Tweak items checklist (uncheck what doesn't apply, add custom rows, set dates)
- Each scope item carries `freq_phase` so Phase 1B can group them
- Each template carries default `duration_days`, `est_h_per_item`, `discipline` so date/hour fields auto-fill
- "Blank project" link at bottom of Step 2 for power users

**Exit criterion:** create a shutdown project from the Pump Overhaul template in <30 seconds with all 7 scope items, planned dates auto-distributed across the duration, predecessors auto-set sequentially.

### Phase 1B — List view: recents + grouping
- Recent chips at top of list view (last 5 projects you opened) — same pattern as engineering-design recent chips
- Group cards by `status` with auto-expand on Active, collapsed on others
- Empty state shows the 4 type tiles directly (not "+ Create your first project")
- Top-N + Show All on completed/archived (>10 projects)
- Per-type counts on tab strip ("Active 4 · Planning 2 · On hold 1")

**Exit criterion:** at 20 projects across 4 statuses, list stays scan-able on mobile (375px) without scrolling past the active set.

### Phase 1C — Detail view: smart defaults
- Scope tab grouped by `freq_phase` (pre / execute / commission / close) with collapsible headers
- Inline status pill cycling on scope rows (click pill: pending → in_progress → done) — no Edit modal for status-only changes
- Smart predecessor suggestion: default predecessor for item N is item N-1 in WBS order (user can change)
- Field hints on every form input per Designer skill (e.g., "Estimated hours = 8h × crew × days")
- Daily log auto-fill: date=today, %=latest rollup, hours=8 (default shift)
- Linked work auto-suggest: open logbook entries on the same asset within 30 days → "Link these 4 related WOs?" banner

**Exit criterion:** field worker can log daily progress in <15 seconds (open project → daily log → submit, all defaults pre-filled).

---

## Phase 2 — Python Backend Swap

Move the math from hand-rolled TS to the existing `python-api` stack so it's testable, reusable, and matches the `analytics-orchestrator` pattern. Internal-only — no UX change.

### Phase 2A — networkx + project module skeleton
- `pip add networkx` to `python-api/requirements.txt`
- Create `python-api/projects/__init__.py`
- Create `python-api/projects/descriptive.py` — current state (rollup, status mix, hours)
- Create `python-api/projects/diagnostic.py` — variance decomposition (why behind/over budget)
- Create `python-api/projects/predictive.py` — EAC forecast via statsmodels trend on progress logs
- Create `python-api/projects/prescriptive.py` — fast-track recommendations + slack analysis
- Add `/project/progress` and `/project/forecast` endpoints to `main.py` handler registry

**Exit criterion:** `python-api/projects/` test fixture round-trip produces same numbers as the current TS edge function on a known project.

### Phase 2B — Critical Path via networkx
- Replace hand-rolled forward/backward pass with `nx.DiGraph` + `nx.dag_longest_path()`
- Add slack/float per node, schedule conflict detection, cycle detection (`nx.find_cycle()` raises a clean error if predecessors form a loop)
- Surface a `cycle_warning` field if predecessors form a cycle (current TS code silently falls back to original order)

**Exit criterion:** CPM matches Microsoft Project on a 12-item test project; cycles produce an actionable error not a silent miscompute.

### Phase 2C — Edge function thin proxy
- Refactor `supabase/functions/project-progress/index.ts` to mirror `analytics-orchestrator/index.ts`: HMAC-validate payload, forward to `${PYTHON_API_URL}/project/progress`, return the response
- Keep client-side fallback in `project-manager.html` for offline/local Tester use
- Update `validate_edge_contracts.py` REQUIRED_FIELDS if signature changes

**Exit criterion:** local Tester uses Python API via `host.docker.internal:8000`; prod uses Render-hosted Python API. Both produce identical payloads.

### Phase 2D — Project Validator
- Create `validate_project_manager.py` (mirror `validate_analytics.py`):
  - L1: HTML structure (tabs, modals, identity chain)
  - L2: Edge function contract (forwards to Python, error JSON, CORS)
  - L3: Python module purity (no missing imports, all 4 phases present)
  - L4: AST check (every column read in HTML exists in schema)
- Register in `run_platform_checks.py`
- Establish baseline (target: 0 FAIL)

**Exit criterion:** new validator registered, baseline locked in `platform_baseline.json`.

---

## Phase 3 — Platform Integration

Wire the Project Manager into the rest of WorkHive so it's not an island.

### Phase 3A — Notifications
- pg_cron daily 06:00: scope item due today / overdue → toast on owner's next page load
- DB Webhook on `project_progress_logs` INSERT with blockers ≠ null → email to project owner
- DB Webhook on `projects` UPDATE when status crosses to 'on_hold' or 'cancelled' → notify all linked scope item owners
- Budget threshold breach (CPI < 0.85): real-time alert to supervisor

### Phase 3B — Logbook integration
- When worker saves a logbook entry, if the asset is linked to an active project, prompt: "Link this entry to project SHD-2026-001?"
- New logbook field (optional) `project_id` (nullable FK) — surfaces a project pill on entry view
- Add to existing `validate_cross_page.py` so cross-page inserts stay aligned

### Phase 3C — PM scheduler integration
- When supervisor schedules a shutdown project, suggest pulling overdue PMs on linked assets into scope items
- When a PM completion fires inside a shutdown window, optionally mark its corresponding scope item as `done`

### Phase 3D — Analytics page integration
- New tab on `analytics.html`: Projects breakdown (active vs at-risk by SPI/CPI, hours burned by discipline)
- Phase 1-3 fan-out includes project rollup as a context layer

### Phase 3E — Home / index card
- Show "3 active projects · 1 at risk" widget on `index.html` for any worker with an open project assignment
- Click → deep link to filtered Project Manager view

**Exit criterion:** project context shows up in 5 other pages (logbook, pm-scheduler, analytics, index, assistant).

---

## Phase 4 — Reporting & Handover

Print-ready and shareable artefacts mirroring `analytics-report.html`.

### Phase 4A — Project Report PDF
- New page `project-report.html` (single source per project, like Analytics Report)
- Sections: Cover · Executive summary (KPIs + RAG status) · Scope (WBS table + critical path Gantt) · Progress timeline (S-curve) · Linked work · Sign-offs · Lessons learned · Appendix
- Reuses `analytics-report.html` `.doc-panel` light theme + `saveAsPdf()` pattern
- Server-side Gantt via matplotlib `broken_barh` for embedding
- 9-place wizard registration via Tester

### Phase 4B — Lessons Learned archive
- New section in detail view + searchable archive page
- Tag by `project_type`, `discipline`, `lesson_kind` (what went well / what to fix)
- Surfaces in Phase 1A template selector ("3 prior pump overhauls flagged 'alignment took 2x' — add buffer hours?")

### Phase 4C — Weekly digest email (Resend)
- pg_cron Monday 07:00 → Edge fn `project-digest` → Resend
- Per-owner digest: active projects, at-risk SPI/CPI, blockers from last 7 days
- Same delivery stack as Failure Pattern Weekly

### Phase 4D — Contractor handover packet
- For `project_type='contractor'`: print-ready packet (scope · BOM · drawings · inspection checklist · sign-off block)
- Single PDF the project owner gives the contractor at kickoff

---

## Phase 5 — Advanced Features

Deferred from earlier decisions; pull in once Phase 1-4 are stable and real usage validates demand.

### Phase 5A — Resource leveling
- `scipy.optimize.linprog` over scope items × days × workers, respecting daily-hour caps and skill-discipline match
- Visualise as a heatmap below the Gantt
- Decision support, not auto-assignment (worker can override)

### Phase 5B — Multi-role assignments
- New table `project_roles` (project_id, worker_name, role) — owner / planner / safety_officer / cost_engineer
- Replaces single `owner_name` field; FK from project header now points at the `owner` role
- Migration must keep existing `owner_name` populated for backward compat

### Phase 5C — Schedule risk simulation
- Monte Carlo on per-item durations (triangular distribution from min/most-likely/max)
- Produces P50/P80/P95 finish dates
- Surfaces in Critical Path tab + Project Report cover finding

### Phase 5D — Change order tracking
- New table `project_change_orders` — scope changes with approver, cost impact, schedule impact
- Approval workflow gated on supervisor role (per architect skill role guard pattern)
- Audit trail in `hive_audit_log`

---

## Phase 6 — AI Assists

Add intelligence on top of stable foundations. AI is enhancement, not the engine.

### Phase 6A — Natural-language project creation
- Worker types: "Plan a 3-day pump overhaul on PUMP-201 starting Monday"
- AI extracts: type=shutdown · template=pump_overhaul · asset=PUMP-201 · start=next-Monday · duration=3 days
- Pre-fills the 3-step wizard so user just confirms and tweaks

### Phase 6B — AI-suggested templates from logbook
- Looks at last 90 days of logbook for repeated work on same asset
- Suggests: "8 breakdown entries on COMP-3 in 60 days — bundle into a Reliability Study project?"
- Surfaces in Project Manager empty state + monthly digest

### Phase 6C — AI risk flagging
- Analyses progress log free-text for blocker patterns ("waiting on parts", "permit delayed", "scope creep")
- Categorises and counts; flags pattern thresholds to project owner
- Reuses semantic-search embedding stack

### Phase 6D — AI handover narrative
- Generates the narrative section of the Project Report PDF (executive summary, lessons learned synthesis)
- Strict-only mode (refuses to invent data); facts come from rollup + logs only
- Same prompt pattern as analytics-orchestrator narrative phases

---

## Status Tracker

| Phase | Status | Owner | Target |
|---|---|---|---|
| 0 — Foundation | ✓ Done | shipped | 2026-05-05 |
| 1A — Templates + wizard | ✓ Done | local commit 71e5ea0 | 2026-05-05 |
| 1B — List view recents + grouping | ✓ Done | local commit 6daae9b | 2026-05-05 |
| 1C — Detail view smart defaults | ✓ Done | local commit f5fae17 | 2026-05-05 |
| 2A — networkx + module skeleton | ✓ Done | local commit 12d619c | 2026-05-05 |
| 2B — CPM via networkx | ✓ Done | folded into 2A | 2026-05-05 |
| 2C — Edge fn thin proxy | ✓ Done | local commit 12d619c | 2026-05-05 |
| 2D — Project validator | ✓ Done | local commit 12d619c | 2026-05-05 |
| 3A — Notifications | ⬜ Deferred | — | Phase 3.5 — leverage scheduled-agents pattern |
| 3B — Logbook integration | ✓ Done | this commit | 2026-05-05 |
| 3C — PM scheduler integration | ✓ Done | this commit | 2026-05-05 |
| 3D — Analytics integration | ⬜ Deferred | — | Phase 3.5 — needs analytics tab refactor |
| 3E — Home card | ⬜ Deferred | — | Phase 3.5 — index.html is marketing page; need authenticated dashboard target |
| 4A — Project Report PDF | ✓ Done | this commit | 2026-05-05 |
| 4B — Lessons Learned (in-page) | ✓ Done | this commit (textarea on Sign-off) | 2026-05-05 |
| 4B — Lessons Learned archive | ⬜ Deferred | — | dedicated searchable page; Phase 4.5 |
| 4C — Weekly digest email | ⬜ Deferred | — | Phase 4.5 — pairs with 3A notifications |
| 4D — Contractor handover packet | ✓ Done | this commit (Sign-off block adapts when project_type=contractor) | 2026-05-05 |
| 4A — Project Report PDF | ⬜ | — | TBD |
| 4B — Lessons Learned archive | ⬜ | — | TBD |
| 4C — Weekly digest | ⬜ | — | TBD |
| 4D — Contractor handover packet | ⬜ | — | TBD |
| 5A — Resource leveling | ✓ Done | this commit (histogram + overload flagging) | 2026-05-05 |
| 5B — Multi-role assignments | ✓ Done | this commit | 2026-05-05 |
| 5C — Schedule risk simulation | ✓ Done | this commit (Monte Carlo P50/P80/P95) | 2026-05-05 |
| 5D — Change order tracking | ✓ Done | this commit | 2026-05-05 |
| 6A — NL project creation | ⬜ | — | post-1.0 |
| 6B — AI template suggestions | ⬜ | — | post-1.0 |
| 6C — AI risk flagging | ⬜ | — | post-1.0 |
| 6D — AI handover narrative | ⬜ | — | post-1.0 |

---

## Definition of "v1.0 ready"

Phases 0, 1, 2 complete. v1.0 = workers can plan, track, and close out projects across all four flavours with templated starting points and standards-grade math. Phases 3-6 layer integration, reporting, advanced features, and AI on top of a stable foundation.

## Cross-references

- Schema lives in `supabase/migrations/20260505000000_project_manager.sql`
- Edge function lives in `supabase/functions/project-progress/index.ts`
- Page lives in `project-manager.html`
- Future Python module will live in `python-api/projects/`
- Validator will live in `validate_project_manager.py`
- Standards memory: PMBOK 7th, AACE 17R-97, IDCON 6-Phase, ISO 21500
