# Grounded MCP Sweep — Rollout Roadmap

Living tracker for sweeping every WorkHive page with the **Grounded MCP Sweep**
(Playwright MCP as a grounded observer, scored against **UFAI**: Usability ·
Functionality · Adaptability · Internal Control).

- **The how:** `workflows/grounded_mcp_sweep.md` (SOP) + `workflows/grounded_mcp_sweep_page_template.md` (per-page worksheet).
- **Cadence:** one page per session; finish on the SOP's Definition of Done.
- **Pause/resume:** each session writes `.tmp/sweep/<page>_sweep.md` + lessons writeback; update this file's status each session.
- **Local-first:** deploy stays **PENDING explicit OK** every time.
- **Scope is GROUNDED, not guessed:** the authoritative inventory is
  `test-data-seeder/e2e_roles_runner.py:TIER_PAGES` (**34 pages / 5 tiers** — more
  complete than nav-hub's 28; reconcile this table to it as we go). Cross-checked with
  the nav registry (`nav-hub.js`) + the served `*.html` inventory (47 files; 7
  backups/tests excluded). Sub-pages reached only from a parent are swept WITH the parent.
- **Two passes per page — REFEREE then CRITIC:** (1) conformance batteries (pass/fail vs
  the grounded contract → bugs fixed + crystallized); (2) a **harsh-critic** pass that is
  opinionated + prescriptive ("this should be X", "move this to page Y") but ALWAYS cites a
  heuristic/pillar/sibling, flags DEFECT vs TASTE, and routes "should-be" recs to
  `promotion_queue.md` for YOUR judgment (never auto-applied). See SOP Phase 4.6.
- **Identity = role × experience (2-D):** cross the 3 roles (solo/worker/supervisor)
  with a **NOVICE (first-timer)** pass — empty state, blank fields, fat-fingers, flaky
  net. The novice modifier bites ALL FOUR pillars (not just Usability), per role. See
  the SOP "NOVICE axis" + the template's Novice Pass block (N1–N7).
- **REUSE the Layer-2 gate types, don't reinvent:** each page already has L2 hooks —
  Smoke, **Role Permission** (`e2e_roles_runner.py` solo/worker/supervisor vs
  `PERMISSION_MATRIX`), **Concurrent Edit** (`e2e_concurrent_runner.py`), **CRUD
  DB-verified** (`flows/*_crud.py`), **UI Locks** (`journey-*.spec.ts`), **Visual
  Regression** (`visual.py`). The MCP sweep is the EXPLORATORY layer on top; findings
  crystallize back INTO these gates (a new `PERMISSION_MATRIX` row, a concurrent
  scenario, a CRUD assertion, a visual baseline, a journey lock). See the SOP's
  "REUSE the Layer-2 gate TYPES" + "Identity Matrix" sections.

**Sequencing (locked + corrected):**
- **Wave 0 = the shell** (`index.html`) goes FIRST — it is the landing page, the
  authenticated home/dashboard, the nav-hub host, AND the sign-in modal, so its
  nav/identity/`escHtml`/auth is a dependency of EVERY page. This sits UNDER your
  "data-sources first" rule, not against it. (Say the word to defer it after Wave 1.)
- Then **data-sources first** for the tool layer, as locked.

**Status legend:** ☐ todo · ◐ in-progress · ☑ done · ⚠ needs L2 spec created/renamed

---

## Gate integration — the sweep is now part of the self-improving mega gate (2026-06-06)
Not an adjacent ritual; wired into the gate so it self-polices and feeds the promotion engine:
- **`validate_grounded_sweep.py`** (registered G0 `grounded-sweep`) — Standing Rule D for the sweep: every ☑ page here MUST keep its crystallized live lock (named in `grounded_sweep_locks.json`); FAILs if a done page has no lock or its spec/marker vanishes. **Add a manifest entry the same session you mark a page ☑.**
- **`validate_modal_a11y.py`** (registered G0 `modal-a11y`) — critique **C7** promoted to a forward-only DEBT ratchet (baseline `modal_a11y_baseline.json` = 13): blocks any NEW hand-rolled modal lacking role=dialog+aria-modal; ratchet down as retrofits land (`--update-baseline`).
- **`sweep_critiques.json`** → `flywheel_orchestrator.py` surfaces undisposed critiques as a "Grounded MCP Sweep critiques" section in `promotion_queue.md` (same disposition mechanism, NOT recurrence-gated). Mirror: `SWEEP_CRITIQUE_QUEUE.md`.
- Per-page crystallization lives in `journey-*` specs (e.g. `journey-shell-mobile-a11y` + the mobile tap-target tests appended to `journey-logbook`/`journey-inventory`).

---

## Progress

| Wave | Page | Status | L2 spec | Dominant pillar(s) | Notes |
|---|---|---|---|---|---|
| 0 (pilot) | `resume.html` | ☑ **done 2026-06-06** | `journey-resume` 29/29 | Functionality · Internal Control | Award-from-bullets gap fixed; `validate_resume` 52/52. The playbook's pilot. |
| **0 — Shell / Front door** | `index.html` | ☑ **done 2026-06-06** | `journey-shell-mobile-a11y` 3/3 (NEW) + `journey-auth` 8 + `journey-auth-identity` 5 + `calm-dashboard`(+behaviour) + `index` smoke — RECONCILED: shell already had specs, "needs dedicated spec" note was wrong | ALL FOUR | 4 root-cause fixes: auth inputs 14→16px (iOS zoom), header Sign In/#hamburger/Sign Out/persona 34→44px @mobile, sign-in modal a11y (role=dialog+aria-modal+ESC+focus-trap+restore). validate_mobile blind to all 3 (Tailwind text-sm + padding sizing) → documented + live-spec crystallized. 6 critique recs → `SWEEP_CRITIQUE_QUEUE.md`. Cross-page 14/14 green. |
| **1 — Data sources / daily capture** | `logbook.html` | ☑ **done 2026-06-06** | `journey-logbook` ✓ +1 mobile tap-target test (NEW) | Internal Control · Functionality | Logic/DB already strong (35 journey + 23 validator, all green). Sweep targeted the GAP = computed mobile/a11y: inputs all ≥16px ✓, overflow 0 ✓; fixed 1 real tap-target (Voice Journal link missing `min-h-[44px]`, siblings had it). Systemic find: 8 modals lack role/aria/ESC/trap → critique C7 (platform-wide shared-helper rec, not blind-fixed). |
| 1 | `inventory.html` (+ `parts-tracker.html` sub) | ☑ **done 2026-06-06** | `journey-inventory` ✓ +1 mobile tap-target test (NEW) | Internal Control · Functionality | validate_inventory 13/13 + journey green. Fixed primary "Add Part" CTA (inline `min-height:unset` defeated .btn-primary's 44px → 32px on phone). Inputs ≥16px + overflow 0. Modal a11y gap → C7; `min-height:unset` anti-pattern + compact row icons → C9. `parts-tracker.html` = 48-line retired stub (parts moved into logbook/inventory per codebase-integrity) → EXCLUDE from sweep. |
| 1 | `pm-scheduler.html` | ☑ **done 2026-06-07** | `journey-pm` +mobile input-font test (NEW) — RECONCILED: `journey-pm`+`pm-scheduler` specs already existed ("⚠ create" was stale) | Internal Control · Functionality | 4 sub-16px wizard inputs (inline `font-size:0.875rem` + a `text-xs` select = iOS zoom) → 16px at root. validator-blind: validate_mobile parses only the `.wh-input` class, not per-element inline overrides → documented blind-spot #2. validate_pm 13/13; F0 wiring clean (0 dead of 93). |
| 1 | `dayplanner.html` | ☑ **done 2026-06-07** | `journey-dayplanner` +mobile tap-target test (NEW) | Usability · Functionality | Page-local `.btn-primary`/`.btn-ghost` had no min-height → "+ Schedule" 35px, "Today" 32px, modal Save/Cancel <44px. Added min-height:44px + inline-flex centering → all 44px live (CTAs + modal + the full-width card CTA). validator-blind (inline-height only). F0 clean. |
| 1 | `shift-brain.html` | ☑ **done 2026-06-07** | `journey-shift-brain` +mobile tap-target test (NEW) — "⚠ create" was stale (spec existed) | Internal Control · Adaptability | `.btn-primary`/`.btn-ghost` used a FIXED `height:42px` (2px under; same page's `.details-toggle` was already 44px) → `min-height:44px`. Read-only briefing page; buttons live behind the hive-gate so the lock asserts COMPUTED min-height. F0 clean. |
| 1 | `voice-journal.html` | ☑ **done 2026-06-07** | `journey-voice-journal` +mobile persona-chip test (NEW) — "⚠ create" stale (2192-line spec existed) | Adaptability · Usability | Already strong (mic 116px+aria, inputs 16px, `.btn-ghost`/`.filter-chip` have an `@media≤480` 44px bump). ONE gap: the `.persona-chip` radiogroup MISSED that bump → 41px on phones → added `@media≤480 { min-height:44px }` (sibling-consistent). Shared-shell sub-44 (`wh-ai-*` companion overlay, global search) left as cross-cutting critique (platform blast radius), NOT blind-fixed. |
| **2 — Identity / Grow** | `skillmatrix.html` | ☐ | `journey-skillmatrix` ✓ | Usability · Functionality | Feeds resume auto-fill + badges (edge to pilot) |
| 2 | `achievements.html` | ☐ | `journey-achievements` ✓ | Usability · Functionality | Badges / XP |
| **3 — Intelligence reads & reports** | `analytics.html` | ☐ | `journey-analytics` ✓ | Functionality · Adaptability | KPI math == canonical (parity) |
| 3 | `analytics-report.html` | ☐ | ⚠ create | Functionality | Report renderer over analytics data |
| 3 | `asset-hub.html` | ☐ | `journey-asset-hub` ✓ | Functionality | Aggregates assets from truth-views |
| 3 | `alert-hub.html` | ☐ | ⚠ `journey-alerts` (verify/rename) | Adaptability · Internal Control | Alert thresholds |
| 3 | `audit-log.html` | ☐ | ⚠ create | **Internal Control** | The control/compliance surface — reads audit events |
| 3 | `project-report.html` | ☐ | ⚠ create | Functionality | Report renderer (project data) |
| 3 | `report-sender.html` | ☐ | ⚠ create | Internal Control · Adaptability | Export/send (PDF/email) — owner-gated |
| 3 | `ph-intelligence.html` | ☐ | ⚠ create | Functionality | PH industry intelligence aggregate |
| **4 — AI surfaces** | `assistant.html` | ☐ | ⚠ `journey-ai` (verify/extend) | Adaptability · Internal Control | Companion; cross-page context; safety/routing |
| 4 | `predictive.html` | ☐ | `journey-predictive` ✓ | Adaptability · Functionality | ML predictions / risk ranking |
| 4 | `ai-quality.html` | ☐ | ⚠ create | Functionality · Internal Control | AI quality surface (user-facing in nav) |
| **5 — Engineering** | `engineering-design.html` | ☐ | `journey-engineering-design` ✓ | Functionality | Calc vs standards (`validate_calc_formula_accuracy` exists) |
| **6 — Connect / commerce** | `hive.html` | ☐ | `journey-hive` ✓ | Internal Control · Multitenant | Membership / roles / RLS |
| 6 | `community.html` (+ `public-feed.html` sub) | ☐ | `journey-community` ✓ / feed ⚠ | Usability · Internal Control | Forum / profiles / moderation |
| 6 | `marketplace.html` (+ `marketplace-seller.html`, `-seller-profile.html`, `-admin.html` subs) | ☐ | `journey-marketplace` ✓ / subs ⚠ | Internal Control | Listings / payments / trust |
| 6 | `project-manager.html` | ☐ | `journey-project-manager` ✓ | Functionality | Build & projects |
| 6 | `integrations.html` | ☐ | ⚠ create | Internal Control | CMMS / SAP connectors |
| 6 | `plant-connections.html` | ☐ | ⚠ create | Multitenant · Usability | Plant-to-plant networking |

---

## Critic pass — status per swept page (REFEREE ≠ CRITIC)

The Progress table's ☑ tracks the **REFEREE** pass (conformance + deep audit). The
**CRITIC** pass (SOP Phase 4.6 harsh-critic + 4.7 cross-page holistic) is tracked
SEPARATELY here, because it lagged behind. Source of truth: `sweep_critiques.json`
(per-page attribution) + `SWEEP_CRITIQUE_QUEUE.md`.

| Page | REFEREE | CRITIC | Critiques logged |
|---|---|---|---|
| `resume.html` | ☑ | ☑ **2026-06-07** | 1 — pilot is structurally CLEAN (modals already role=dialog+aria-modal, buttons 44px); only a 13px dedupe-toggle label |
| `index.html` | ☑ | ☑ | 6 (full pass) |
| `logbook.html` | ☑ | ◐ | 1 |
| `inventory.html` | ☑ | ◐ | 1 |
| `pm-scheduler.html` | ☑ | ☑ **2026-06-07** | 2 — filter-chips 32px + pm-edit-modal a11y |
| `dayplanner.html` | ☑ | ☑ **2026-06-07** | 3 — btn-icon 28px + view-tab 31px + modal a11y |
| `shift-brain.html` | ☑ | ☑ **2026-06-07** | 2 — shift-pill 37px + back-btn 36px |
| `voice-journal.html` | ☑ | ◐ | 1 |
| (platform-wide / systemic) | — | — | 7 (+nav-hub mode-btn 26px, +the interactive-min-height rule) |

**CRITIC pass — now run on all 8 swept pages (2026-06-07).** The headline cross-page
finding (`sweep:platform-wide:interactive-min-height-rule`): the REFEREE fix bumped
`.btn-primary`/`.btn-ghost` to 44px per page, but each page then shipped a DIFFERENT
secondary control class below 44px (pm `filter-chip`32 · dayplanner `btn-icon`28/`view-tab`31
· shift-brain `shift-pill`37/`back-btn`36 · nav-hub `mode-btn`26). Reactive per-class fixes
will always lag — needs ONE platform rule + validate_mobile per-element box sizing.

**Open critic work:**
1. ~~Run the CRITIC pass on the 4 pages with none~~ ✅ done 2026-06-07 (24 critiques total in `sweep_critiques.json`). Deepen the ◐ partials (`logbook`/`inventory`/`voice-journal`) on their next touch.
2. **Disposition the 24 OPEN critiques** (all `open`) — YOUR call per the SOP (accept→promote / reject→close). Surfaced in `promotion_queue.md` / `SWEEP_CRITIQUE_QUEUE.md`.

## Cross-Page Dedup — backlog (the Phase 4.7 holistic-critic output)

The cross-page holistic critic's headline finding. Measured + gated, collapse deferred (a
human design call — the "judgment fork").
- **Measured:** `jscpd` → 73 clones / 5259 dup lines / **24.65% of platform HTML** (2026-06-07).
- **Gated:** `validate_clone_debt.py` (G0 forward-only ratchet, baseline `clone_debt_baseline.json` = 73) blocks NEW copy-paste; collapsing ratchets it DOWN.
- **Deferred collapse (targets, in order):** (1) the ~530-line `SUPABASE_URL`/script
  boilerplate (`plant-connections` ↔ `shift-brain` + siblings) → a shared include;
  (2) the "verdict + simple-card" block → one component. Each collapse → `--update-baseline` lower.

## Internal / Ops track (lighter "ops" battery, separate cadence — these are founder/admin surfaces, not the public web)
`founder-console.html` · `platform-health.html` · `llm-observability.html` ·
`agentic-rag-observability.html` · `validator-catalog.html` · `architecture.html`
> Sweep with a reduced battery: Functionality (does it read the right truth-views?) +
> Internal Control (owner/founder-gated, no data leakage) + a11y. Skip the consumer-UX
> depth. Do after the user-facing waves, or on demand.

## Explicitly EXCLUDED (throwaway — do NOT sweep)
`index-hive-test.html` · `index-native-test.html` · `index-v3-test.html` ·
`index.backup.html` · `index.backup2.html` · `logbook.backup.html` ·
`engineering-design-test.html` · `symbol-gallery.html` (dev asset gallery)

## After each WAVE — run the cross-surface sentinel
- Wave 0 (shell) → `codebase-integrity` skill + `tests/journey-megagate-cross-page.spec.ts` + `tests/journey-cross-page.spec.ts` (nav/identity/escHtml/auth touch everything)
- Wave 1 → `tests/canonical-lineage.spec.ts`
- Wave 2 → `tests/journey-cross-page.spec.ts`
- Wave 3 → `tests/journey-cross-surface-kpi-parity.spec.ts`
- Wave 6 → `tests/journey-hive-isolation-property.spec.ts`
- Any wave touching nav / identity keys / `escHtml` → `codebase-integrity` + megagate-cross-page

---

## Session log (append one line per sweep)
- 2026-06-06 — `resume.html` — award-miner gap fixed; validate 52/52, journey 29/29; lessons → resume-builder S23 / ai-engineer / qa-tester(×3); zero pollution.
- 2026-06-06 — `index.html` (Wave 0 shell) — 4 root-cause fixes (auth 14→16px iOS-zoom, header tap 34→44px, modal a11y role/aria/ESC/trap/restore); validate_mobile Tailwind blind-spot documented + crystallized live in NEW `journey-shell-mobile-a11y.spec.ts` 3/3; regression auth/auth-identity/calm/index 58/58; cross-page sentinels 14/14; 6 critique recs → `SWEEP_CRITIQUE_QUEUE.md`; lessons → mobile-maestro / qa-tester / frontend; zero pollution; deploy PENDING.
- 2026-06-06 — `logbook.html` (Wave 1) — logic/DB already strong (35 journey + 23 validator green); sweep targeted the mobile/a11y GAP. Fixed 1 tap-target (Voice Journal link `min-h-[44px]`, siblings had it); inputs all ≥16px + overflow 0 (clean). Crystallized: +1 mobile tap-target test in journey-logbook (1/1). validate_logbook 23/23 (no regression). Systemic find (8 modals no role/aria/ESC/trap) → critique C7 platform-wide shared-helper rec (NOT blind-fixed). Zero pollution (read-only sign-in, no saves); deploy PENDING.
- 2026-06-06 — `inventory.html` (Wave 1) — validate_inventory 13/13 + journey green. Fixed primary "Add Part" CTA (`min-height:unset` defeated .btn-primary 44px → 32px); inputs ≥16px + overflow 0. Crystallized: +1 mobile tap-target test in journey-inventory (1/1). Modal a11y → C7; `min-height:unset` anti-pattern + compact row icons → C9. parts-tracker.html = retired 48-line stub → excluded. Zero pollution; deploy PENDING.
- 2026-06-06 — `index.html`+`logbook.html`+`inventory.html` (FULL-MODEL re-audit: WHERE/WHAT/WHEN/per-role/no-phantom, not just alive) — biggest find was ENVIRONMENTAL: parity suite 8/9 RED was a WEDGED Flask dev server + 9-day-stale seed dates, ZERO page bugs (live one-at-a-time every tile == canonical: 18/2/25/3, 27/3/0). Fixed env: restarted Flask + NEW non-destructive `test-data-seeder/refresh_seed_dates.sql` (per-table newest→now, excludes pm_assets/asset_risk_scores → KPIs preserved, time-windows repopulate). PROVEN GREEN: parity+interaction 9/9 fast; `e2e_roles_runner` 15 PASS/0 FAIL + canonical-dims 4/4 (36/36 views reachable). logbook Team-Feed "0" = search-first BY-DESIGN, not a defect. Crystallized: SOP Phase-0 env-health preflight + lessons → qa-tester / data-engineer / devops. Zero pollution; deploy PENDING.
- 2026-06-07 — `pm-scheduler.html`+`dayplanner.html`+`shift-brain.html`+`voice-journal.html` (Wave 1 remainder, autonomous run, user asleep) — SAME sweep as index/logbook/inventory, extended to the 4 tool-layer capture pages. All specs already existed ("⚠ create" notes were stale, like the shell's was). Targeted the computed mobile/a11y GAP + F0 wired-&-alive (all 4 clean). Root-cause fixes, each verified LIVE then crystallized as a per-page computed-value journey lock (**4/4 new locks green, 23.5s**): pm-scheduler 4 sub-16px inputs (inline `font-size:0.875rem`/`text-xs` = iOS zoom) → 16px [validate_mobile blind-spot #2: inline per-element font override, documented]; dayplanner `.btn-primary`/`.btn-ghost` no min-height (35/32px) → 44px (CTAs+modal+card CTA); shift-brain fixed `height:42px` → `min-height:44px`; voice-journal `.persona-chip` missing the `@media≤480` 44px bump its siblings already had (41→44px). Shared-shell sub-44 (`wh-ai-*` companion, global search) left as cross-cutting critique (blast radius), NOT blind-fixed. ALSO fix-forwarded the gate: C5 `ai_eval_baseline.json` froze without `_meta.ai_asset_version` → root-caused `tools/ai_eval_gate.py baseline()` to stamp it (verify exit 0); document.write FAIL was transient. ENV: recovered a post-sleep/wake clock hiccup (Flask down + Supabase auth 502 via Kong) by restarting Flask + auth/kong. Zero pollution (read-only sign-in; date-shift only); deploy PENDING.
