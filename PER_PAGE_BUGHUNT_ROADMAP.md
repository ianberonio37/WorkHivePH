# Per-Page Full-Stack Bug-Hunt Roadmap

**Mandate (Ian, 2026-07-13):** improve the hunt — go **per page**, hunt each bug through its
**full-stack architectural layers** (UI → client JS → PostgREST/RLS → SQL views/RPCs → triggers →
edge fns), driven **live** by MCPs. Cover every interaction dimension and test type below, and
score each page **per phase as a percentage**. This replaces the ad-hoc "sweep by bug class"
method with a repeatable **per-page battery** that ratchets to 100%.

> Method precedent that carried this session (2026-07-13): live Playwright as a real JWT identity
> + postgres MCP DB verification + two-tenant rolled-back probes; **live-confirm before claiming**
> (2 static findings were false positives); **gate every fix** (Hardening Loop). Reuse
> `tools/live_page_journeys.mjs` sign-in recipe + `validate_hive_write_isolation.py` /
> `validate_display_correctness_fixes.py` as the ratchet pattern. See `BUGHUNT_2026-07-13.md`.

---

## 1 · The 8-phase per-page battery (each maps to a % ratchet)

| # | Phase | What it proves | Primary MCP / tool | The dimensions it covers |
|---|-------|----------------|--------------------|--------------------------|
| **P1** | **Smoke (happy path)** | page loads signed-in, renders real data, primary job completes, **0 console errors** | Playwright: navigate + snapshot + console | happy path · loading states (initial) |
| **P2** | **Console + Network** | no JS errors/warnings; **every** API/network request 2xx (no silent 4xx/5xx); no dead fetch/JWT-drop | Playwright: `browser_console_messages` + `browser_network_requests` | console errors · failed API/network requests |
| **P3** | **CRUD (full-stack)** | create/read/update/delete each entity **verified at the DB** (FK/attribution/`v_*_truth`), not just "UI didn't error" | Playwright drive form → postgres MCP verify | happy path · data integrity |
| **P4** | **Inputs + edge cases** | validation errors, **empty** inputs, **wrong** inputs (type/format/range/XSS/unicode), boundary/overflow, duplicate submit | Playwright fill/submit + console | validation errors · empty inputs · wrong inputs · edge cases |
| **P5** | **Role / Permission** | worker vs supervisor vs anon vs cross-hive; RLS read+write isolation; **UI-only-auth bypass** (call the write directly) | postgres MCP + 2nd auth context (service-role client / 2nd JWT) | permission issues |
| **P6** | **Concurrent-edit** | two contexts edit the same row → last-write/lost-update, stale-read, optimistic-lock, realtime divergence | 2 Playwright contexts OR client + `docker psql` | edge cases (races) |
| **P7** | **UI-locks + loading + recovery** | disabled/locked states honored (e.g. pending-approval locks), skeletons, optimistic rollback, **offline/degraded**, empty-state-vs-error | Playwright: throttle/offline + state assertions | loading states · UI locks · permission (locked actions) |
| **P8** | **Visual regression** | screenshot baseline @ 390px + desktop; no layout break/overflow/contrast regressions across states | Playwright `browser_take_screenshot` (baseline set) | visual regression · responsive |
| **P9** | **Accessibility** *(v2)* | WCAG 2.2 AA: axe **0 serious/critical** (measure `incomplete` too), keyboard-reachable, focus-visible, contrast ≥4.5, ARIA on every control | axe-core live-inject + `validate_aria_*` gates | accessibility *(was untracked → inflated the %)* |
| **P10** | **Performance** *(v2)* | Core Web Vitals (LCP/INP/CLS) in budget, no N+1, render-budget honored, bundle size | CWV probe + `render-budget` gate | performance *(was untracked)* |
| **P11** | **i18n / localization** *(v2)* | every visible string translated EN+FIL, no text-expansion overflow, `_t()` re-render on `wh-locale-change` | i18n-coverage gate + Playwright locale-swap | i18n *(was untracked)* |
| **P12** | **Error-handling & exceptional conditions** *(v2 · OWASP A10:2025)* | no stack/PII leak on error, fail-**closed**, unhandled-rejection-free; **upload/file-safety** (CWE-434 file-upload / CWE-22 path-traversal) where a file surface exists | Playwright error-injection + SAST | exceptional conditions · file-upload/path-traversal *(was untracked)* |

**Test-type → phase crosswalk (Ian's list):** Smoke=P1 · Role-Permission=P5 · Concurrent-Edit=P6 ·
CRUD=P3 · UI-Locks=P7 · Visual-Regression=P8. (P2 console/network + P4 input-edge are the connective
tissue the list implies.) **P9–P12 = the 2026-07-17 denominator v2 extension** (§3b) — dimensions the
8-phase battery silently omitted, so a page's % was measured against a truncated class-space.

**Platform SECURITY track (Instrument B — composes, not a per-page column):** the OWASP Top-10 security
axes are hunted **platform-wide** by `sast_scan.py` (VERIFIED **10/10 OWASP-2021, 26 scanners, PASS**) +
~150 `validate_*.py`, so they are NOT per-page cells (that would double-count). Per-page security lives
in P4 (injection/XSS) + P5 (access-control); the rest is platform-gated. See §3b for its open backlog
(2025 relabel · CSRF · the per-page upload/traversal surfaces folded into P12).

## 2 · Scoring rubric (per page, per phase)

- **0%** not started · **25%** attempted, findings unverified · **50%** happy+primary paths verified
  live · **75%** edge/negative paths verified · **100%** all paths verified **AND locked by a gate**
  (live probe or static marker) so a regression FAILs the suite.
- A phase only reaches 100% when its gate is registered in `run_platform_checks.py`. "Verified but
  ungated" caps at 75% ([[feedback_gate_green_is_part_of_done]] + the "gate every finding" lesson).
- **Page % = mean of its 12 phase %s** (v2, 2026-07-17 — extended from 8; see §3b). Roadmap % = mean
  of page %s. Report MEASURED %, never qualitative "done" ([[feedback_measured_percent_not_qualitative_done]]).

## 3 · Page scoreboard (seed = what THIS session verified; the rest is the backlog)

Legend per cell = phase %. Seed reflects 2026-07-13 work (security/RLS deep pass + targeted display
fixes on ~12 pages); most P3/P4/P6/P7/P8 are still 0 — that IS the roadmap.

Cells raised to the **page-battery gated floor** (2026-07-13 session 2) are the P1/P2/P4/P8 columns:
`validate_page_battery.py` (registered gate) now proves + LOCKS across ALL 30 pages — P1 loads clean
signed-in (0 console errors, non-blank, no error banner) = **85**; P2 no 5xx on load = **75**;
P8 no @390 overflow, gated = **85**. Applied as `max(old, floor)` so deeper prior work is never lowered.

**P4 floor raised 50 → 75 (session 3, 2026-07-14):** BOTH XSS vectors are gated platform-wide, not just
the reflected probe — the stored-XSS ratchet `innerhtml-eschtml` (every template-literal `innerHTML`
interpolation must pass through `escHtml`/`e()`, forward-only) + `dom-xss-fields` + the SQL-injection
`like-escape` ratchet + the page-battery reflected-XSS probe together lock the full input-XSS surface.
So the input axis is edge/negative-path gated = **75**; the residual 25 is per-page **business-rule**
validation (range/format/duplicate-submit semantics), which stays MCP-interactive.

**Live-MCP frontier sweep (session 3, 2026-07-14) — P3/P5/P7 driven up via the db-client round-trip
method** ([[reference_live_dbclient_roundtrip_method]]): signed in as a real WORKER, `window.db` batch-
verifies from one page. **P5 (UI-only-auth-bypass, the hardest P5 check) — ALL blocked live (42501/RLS):**
asset + inventory self-approve (`wh_guard_supervisor_approval`), project_roles grant, api_keys mint,
integration_configs add, hive_retention_config change, shift_plans create, marketplace listing create —
so no worker can perform a supervisor action by calling the write directly, platform-wide. **P3 (CRUD-at-
DB) verified live** (create persists · attribution PINNED to caller · read renders · delete cleans up) for
voice_journal, engineering_calcs, community_posts, pm_assets, asset_nodes, parts_records, schedule_items,
resume_documents, skill_profiles, report_contacts. **P7 (empty-state/skeleton/lock) verified clean on 10
pages** (inventory, logbook, community, pm-scheduler, achievements, marketplace, alert-hub, dayplanner,
project-manager, skillmatrix): 0 error-states, 0 stuck skeletons, correct per-section empty-states,
achievements shows "Locked" for unearned, community realtime connected (3 channels). **Finding: the
platform's P7 mechanical floor + P5 role-gate are UNIFORMLY well-built** — no bugs surfaced in the sweep;
the ~10 real bugs this session were all in the DB-layer attribution/security classes (now closed). NEXT:
read-correctness (rendered==DB) for the read-heavy pages + gate the live P3/P5 round-trips (a headless
`validate_page_crud.py`) to lift the verified-75 cells toward 100.

> **Scoreboard sync note (2026-07-17):** the **Page %** column below is the **8-phase** score (P1–P8).
> The v2 **12-phase** measured re-baseline (P9=75 / P10=75 / P11=60 / **P12=65** per §3b, uniform
> pending per-page differentiation) gives each page a 12-phase % of `(shown × 8 + 275) / 12`; All 12
> phases are now MEASURED; per-page P9–P12 columns get appended as each cell is driven up.
> **P12 floor 50→65 (2026-07-18):** gate-backed — `validate_frontend_floor_cells` GREEN (D17 console-clean
> + D15 degraded-states across 35 pages) + `page_battery.mjs --gate` confirmed 0 console errors / no
> unhandled rejection on load across ALL 30 pages + `validate_file_upload_safety` (CWE-434 size caps).
> Not higher: full P12 (fail-closed, no stack/PII leak on error, submit-path error-injection) is not yet
> per-page-probed. P12 stays the biggest remaining v2 lever.

| Page | P1 Smoke | P2 Con/Net | P3 CRUD | P4 Inputs | P5 Role | P6 Concur | P7 Locks | P8 Visual | **Page %** |
|------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| index.html (landing/ops-home) | 85 | 80 | 75 | 75 | 75 | 75 | 75 | 85 | **78** |
| hive.html | 100 | 100 | 65 | 80 | 100 | 75 | 70 | 85 | **84** |
| logbook.html | 85 | 80 | 70 | 75 | 75 | 100 | 75 | 85 | **81** |
| inventory.html | 85 | 80 | 70 | 75 | 85 | 85 | 75 | 85 | **80** |
| pm-scheduler.html | 85 | 80 | 100 | 75 | 90 | 75 | 75 | 85 | **83** |
| asset-hub.html | 85 | 80 | 65 | 75 | 90 | 100 | 75 | 85 | **82** |
| alert-hub.html | 85 | 80 | 75 | 75 | 75 | 75 | 75 | 85 | **78** |
| analytics.html | 85 | 85 | 100 | 75 | 75 | 100 | 75 | 85 | **85** |
| analytics-report.html | 85 | 80 | 100 | 75 | 75 | 100 | 75 | 85 | **84** |
| achievements.html | 85 | 80 | 100 | 75 | 75 | 100 | 75 | 85 | **84** |
| ai-quality.html | 85 | 80 | 100 | 75 | 75 | 100 | 75 | 85 | **84** |
| skillmatrix.html | 85 | 80 | 100 | 75 | 75 | 65 | 75 | 85 | **80** |
| resume.html | 85 | 80 | 55 | 75 | 75 | 75 | 75 | 85 | **76** |
| community.html | 85 | 80 | 100 | 75 | 90 | 100 | 75 | 85 | **86** |
| public-feed.html | 85 | 80 | 100 | 75 | 75 | 100 | 75 | 85 | **84** |
| marketplace.html | 85 | 80 | 75 | 75 | 75 | 65 | 75 | 85 | **77** |
| marketplace-seller*.html (×3) | 85 | 80 | 65 | 75 | 80 | 75 | 75 | 85 | **78** |
| dayplanner.html | 85 | 80 | 85 | 75 | 75 | 75 | 75 | 85 | **79** |
| engineering-design.html | 85 | 80 | 100 | 75 | 80 | 100 | 75 | 85 | **85** |
| assistant.html | 85 | 80 | 75 | 75 | 68 | 100 | 75 | 85 | **80** |
| report-sender.html | 85 | 80 | 55 | 75 | 75 | 100 | 75 | 85 | **79** |
| project-manager.html | 85 | 80 | 100 | 75 | 85 | 100 | 75 | 85 | **86** |
| project-report.html | 85 | 80 | 100 | 75 | 75 | 100 | 75 | 85 | **84** |
| integrations.html | 85 | 80 | 75 | 75 | 82 | 75 | 75 | 85 | **79** |
| ph-intelligence.html | 85 | 80 | 100 | 75 | 75 | 100 | 75 | 85 | **84** |
| ~~predictive.html~~ RETIRED 2026-06-10 (Phase 4; risk-360 absorbed into asset-hub; no live dead-link, 'predictive' is an assistant routing keyword) | — | — | — | — | — | — | — | — | **n/a** |
| plant-connections.html | 85 | 80 | 100 | 75 | 75 | 100 | 75 | 85 | **84** |
| shift-brain.html | 85 | 80 | 75 | 75 | 80 | 75 | 75 | 85 | **79** |
| audit-log.html | 85 | 80 | 90 | 75 | 75 | 100 | 75 | 85 | **83** |
| voice-journal.html | 85 | 80 | 100 | 75 | 80 | 75 | 75 | 85 | **82** |
| founder-console.html | 85 | 80 | 75 | 75 | 82 | 100 | 75 | 85 | **82** |

**Roadmap total ≈ 81.1%** *(8-phase, 2026-07-18 session 6 — **P6-partials CLOSED** (4 pages 40–60→100, OC-guarded + live-verified, migs 000012/000013); **P7 FRONTIER LIFTED** (mean 62→74: P7=0 cleared 6 pages 0→75 + fixed report-sender saveContact dup-insert; write pages verified via the shared `withButtonLock` finally-re-enable helper + try/finally idiom; asset-hub 10→60 approval-lock gap noted); **P3 drive** (achievements 25→100 pure-read + gated; alert-hub/marketplace-seller/founder-console/skillmatrix/dayplanner/logbook driven up); **ATTRIBUTION-FORGE CLASS CLOSED** — 14 forgeable accountability columns found+fixed+forge-probed across migs 000014/000015/000016 (`actor`,`acknowledged_by`,`resolved_by`,`approved_by`,`reviewed_by`,`assigned_by`,skill_profiles.worker_name) + `validate_attribution_pinned.py` gate LOCKS it; **P5 LIFTED** (mean 75→78: read-RLS verified — all 39 v_*_truth views security_invoker=on + 2 gates; write-RLS verified self/hive-scoped); index P5 25→75 no role-escalation + P4 escHtml discipline confirmed. 18/30 pages ≥80%.)*
**→ v2 12-phase = MEASURED ~77.1% (2026-07-18, §3b — P12 floor 50→65 gate-backed)**
**LIVE-BATTERY VERIFIED (2026-07-18):** `page_battery.mjs --gate` GREEN on **all 30 pages** (P1 clean load · P2 no 5xx · P4 no reflected/executed XSS · P8 no @390 overflow) after the session's ~40 edits — confirming no runtime regression. The battery CAUGHT a regression I introduced (community.html feed 400 "Could not load posts": I appended `updated_at` to the feed SELECT, but it reads the VIEW `v_community_posts_truth` which didn't expose it → also a dead OC guard) → FIXED via mig `20260717000017` (add `p.updated_at` to the view, security_invoker preserved). See [[feedback_oc_guard_on_view_needs_updated_at_on_view]]. Session migs: **000012–000017** (7), all live-verified, await Ian commit + prod-apply. — page-crud extended (`projects` → found+fixed attribution forge mig 000010); systemic worker_name-forge SWEEP DONE ([[feedback_worker_name_pin_gap_beyond_session3]]): audit → **7 tables fixed** (projects mig 000010; marketplace_sellers/fault_knowledge/pm_knowledge/skill_knowledge/project_roles/shared_voice_notes mig 000011, forge-probe verified), false-positives (server-written) excluded, skill_profiles deferred — **all 12 phases measured** (P9–P12 driven off their floors component-first this arc: a11y +
render-budget reports, the upload gate, and the new `validate_i18n_coverage.py`). The P5 payoff: the
centralized components already cover the family (0 aria gaps, 0 render-budget violations, 81%
i18n-adopted), so the naive floor-estimate (56.3%) understated it. The 8-phase cells below are
unchanged; per-page P9–P12 columns land as each is driven UP from its measured value. **Session 5 (2026-07-17) — live-MCP P6 hunt (framework dogfood: compass → Night-Crawler triage →
live-psql probe → fix → gate → ratchet).** Triage surfaced PRODUCTION_FIXES #43 (optimistic concurrency
~0% across UPDATE sites). Live DB probe on **pm-scheduler P6** found a **DEAD OC guard**: `pm_assets`
had **no `updated_at` column**, yet the client reads/writes it for optimistic concurrency
(`_pmAssetUpdatedAt` always null → the `.eq('updated_at')` guard SKIPPED → **lost-update race OPEN**;
static analysis saw "OC present" and missed it — only the live DB revealed it). Fixed (mig
`20260717000005`: add column + reuse the canonical `touch_updated_at` trigger) → **live-verified** the
OC now rejects a stale write (writerA=1, writerB=0, rolled back). Built + gated
**`validate_oc_updated_at_backed.py`** (`oc-updated-at-backed`) — which immediately caught a **sibling**:
`marketplace_disputes` (dispute-resolution admin flow) had the same missing-column phantom write → fixed
(mig `20260717000006`). Gate green (6 tables, 0 missing). **pm-scheduler P6 0→75** (completion is
concurrency-safe via a DB **dedup unique index**; asset-edit OC now backed + gated). Then **alert-hub P6
0→75**: live probe found `anomaly_signals` status had only a value CHECK, **no forward-only transition
guard** → a stale/concurrent Acknowledge **regressed a `resolved` alert back to `acknowledged`**
(live-verified). Fixed (mig `20260717000007`: DB trigger — resolved/expired terminal) → verified
(regression BLOCKED, forward chain OK) → gated `anomaly-status-forward`. **5 real P6 bugs fixed
this session** (pm_assets, marketplace_disputes, anomaly_signals, **integration_configs** — shared
connector config, OC added mig `20260717000008` + client guard, live-verified writerA=1/writerB=0) +
**11 read-only pages ratcheted P6→100 covered-by-nature** (verified no edit surface, gated
`readonly-p6-no-edit`). Roadmap 62.5→**~69.2%**. **P6 essentially CLOSED this session**: 5 tables fixed+verified
(pm_assets · marketplace_disputes · anomaly_signals · integration_configs · **shift_plans** [hive-shared,
forward-only status guard mig `20260717000009`, regression BLOCKED]) → all →75; 11 read-only pages →100
(gated `readonly-p6-no-edit`); 5 owner-scoped pages →75 (verified no cross-user race). **P3 progress:** 7 pure-read pages
P3→100 (read-battery 58/58 green); **project-manager P3 0→100** (page-crud extended with `projects` →
surfaced + fixed an **attribution forge**: `bind_projects_submitter` pinned only auth_uid → worker_name
forgeable; mig `20260717000010`, gate now green 5/5). **NEXT frontier (P6 done):** P6 prior-partials
(asset-hub 60 / community 40 / project-manager 60 / founder-console 50); remaining **P3=10** write pages
(marketplace / assistant / marketplace-seller / alert-hub / achievements — extend page-crud per entity);
asset-hub **P7-locks** (10); the 5 thin **i18n** pages; then **P12** per-page error-handling.

**Session 4 (2026-07-15)** locked the **read-correctness frontier**: (1) ratcheted the four `page-crud`-gated P3 cells 75→100 (pm-scheduler/community/engineering-design/voice-journal — the `validate_page_crud.py` gate built session 3 but never ratcheted); (2) built + registered a **platform-wide read battery** (`tools/validate_read_battery.mjs` + `.py`, gate `read-battery`, 38 live invariants) that, per read-heavy page, compares what the page RENDERS to the DB truth (docker-psql) for the signed-in hive — **audit-log `#feed` child-count == `hive_audit_log` count is EXACT rendered==DB**; integrations/plant-connections DB==0 → empty-state + hero counters 0 (error NOT swallowed as empty); public-feed/project-report/shift-brain/analytics render real rows when DB>0; ai-quality renders `#content` OR its intentional maturity gate ([[feedback_platform_intentional_blank_states]]). This lifted P3-read on 8 pages (audit-log→90, the rest→75 from 0/10) and P7 (integrations/plant-connections→75, others→60). Reseed-robust (every expectation from a live DB count). This is the render-layer complement to `truth-view-read-isolation` (the DATA/RLS layer). **P6 concurrent + the residual P3-write / P7-locks remain the open frontier** — MCP-interactive, per-page.

**Session 3 (2026-07-14)** made **P5 the most-gated axis platform-wide** and ratcheted it: two more real fixes — inventory P6 lost-update (mig `20260713000008` `inventory_restock` FOR-UPDATE RPC; client absolute-write → atomic server increment) and marketplace listing trust-forge (mig `20260713000009` `v_marketplace_listings_truth` `security_invoker` view sourcing `seller_verified`/`completed_sales`/`rating_avg` from canonical `marketplace_sellers`, not forgeable listing columns) — plus a **batch read-isolation gate** (`tools/validate_truth_view_read_isolation.py`, registered `truth-view-read-isolation`) that loops all hive-scoped `v_*_truth` views and, as a hive-A member, asserts a foreign hive reads **0 rows**: 31/31 private views isolate. hive-isolation now **18 live rolled-back invariants** (added comm-attr-pin, comm-hijack-block, mkt-trust-canonical, and BLOCKED-forge assertions for skill-badge/achievement/logbook-own-scope). The read-isolation gate ratchets the P5-read half across the read-heavy pages (analytics-report/ai-quality/ph-intelligence/project-report/plant-connections/public-feed/integrations/audit-log). **P3 CRUD / P6 concurrent / P7 locks remain the open frontier** — MCP-interactive, per-page.

**Session 2 (2026-07-13)** landed the platform-wide
mechanical floor: `tools/page_battery.mjs` (reuses the `live_page_journeys.mjs` sign-in recipe; its own
headless Playwright, so no MCP contention) sweeps all 30 pages for P1/P2/P4/P8, and
`tools/validate_page_battery.py --gate` (registered `page-battery` in `run_platform_checks`) LOCKS the
floor: 0 pages throw on load, 0 5xx, 0 reflected-XSS, 0 @390 overflow. Also closed **community.html P5**
(mig `20260713000007`): a within-hive worker could FORGE a community_reply's `auth_uid`+`author_name`
(LIVE-confirmed) and UPDATE/DELETE any member's reply (BOLA), and a stray `anon delete community_reactions`
USING(true) let anyone nuke any reaction — fixed by `bind_community_reply_submitter` + author-scoped
write policies + dropping the anon-delete; gate-locked as isolation invariants **13/14** (now 14 live
rolled-back invariants, all green). **Session 1** had driven hive.html 32→84% + 6 security migrations
(x-hive read leak + membership + attribution + BOLA). Security/RLS (P5) + the mechanical floor (P1/P2/P8)
are the advanced axes; **P3 CRUD / P6 concurrent / P7 locks are the open frontier** — all MCP-interactive
(judgment per entity), driven per page next.

## 3b · Denominator v2 — completeness re-baseline (2026-07-17)

**Why:** a coverage % is honest only if its denominator is the full class-space. The 8-phase battery
silently omitted **accessibility, performance, i18n, and error-handling/upload-safety**, so every page
% was measured against a truncated set and read **higher than true** (the "metric vs a truncated
denominator" anti-pattern — [[feedback_measured_percent_not_qualitative_done]] + the qa-tester
coverage-honesty rule). Grounded by a Night-Crawler external-taxonomy crawl (OWASP **Top 10:2025**, CWE
**Top 25**, OWASP Proactive Controls → `substrate/external/`); full analysis in
`BUGHUNT_DENOMINATOR_EXPANSION.md`.

**The 4 added per-page phases + honest starting floors** (platform-gated where a gate already exists —
provisional pending per-page battery-verification, exactly like the P1/P2/P8 floors):

| New phase | Score | Basis (2026-07-17 — driven off floors component-first) |
|---|--:|---|
| **P9 Accessibility** | **75** `[M]` | MEASURED: `aria_label_coverage_report.json` = 28 pages, **0 missing (100% aria-label)** via the shared `whToggleAria`/`whSheetA11y` auto-wires (the **P5 payoff** — centralized + adopted). Residual 25 = full axe serious/critical + keyboard-nav battery per page. |
| **P10 Performance** | **75** `[M]` | MEASURED: `render_budget_report.json` = **0 budget violations** family-wide via the shared render-budget. Residual 25 = live CWV (LCP/INP/CLS) probe per page. |
| **P11 i18n** | **60** `[M]` | MEASURED: `validate_i18n_coverage.py` (built + gated `i18n-coverage`, `--selftest`) = **31 user-facing pages, 25 i18n-adopted (81%)**, **6 gaps → 5** (`resume.html` **driven none→partial this arc** via the shared `WH_FIL_PAGE` lever — upload chrome + header adopted; **`none: 0` now**, every user-facing page has some i18n). Remaining thin: ph-intelligence / project-report / ai-quality / plant-connections / public-feed. Residual = drive each to "covered" via the P5 lever ladder (ONE shared system) + per-page EN/FIL string-completeness & text-expansion. |
| **P12 Error-handling / upload** | **50** `[M]` | upload-safety **9/9 guarded** (gate `file-upload-safety` green) + A10:2025 **sast-covered** (edge error-capture / debug-echo-safe / fail-closed). Residual 50 = per-page client error-handling (fail-closed, no stack/PII leak). |

**Re-baseline — now MEASURED (2026-07-17, item 2 done component-first):** `Page % = mean of 12 phases`.
Measuring all four new phases lifts them off their floors: `(8 × 69.1 + 75 + 75 + 60 + 50) / 12` =
**~67.7%** (8-phase mean climbed 62.5→69.1 as the P6 drive ratchets cells). **Item 2 is DONE** — every new phase is now MEASURED: P9/P10 from the a11y +
render-budget reports, P12 from the upload gate, and **P11 from `validate_i18n_coverage.py` (built
this arc)**. The naive floor estimate (56.3%) **understated reality** — the centralized components
already cover the family (the **P5 north star, measured**: 0 aria gaps, 0 budget violations, 81%
i18n-adopted). Remaining work is *driving the measured cells up* (6 i18n gaps via the lever ladder;
axe/CWV/error-handling per-page), not measuring them.

**Platform SECURITY track (Instrument B) — VERIFIED complete on 2021, with a live backlog:**
`sast_scan.py` = **10/10 OWASP-2021, 26 scanners, PASS** (~150 validators). It **composes** with the
per-page battery (it is not a per-page column — that would double-count). Open, verified security
backlog:
1. **Refresh 2021 → 2025 — DONE (2026-07-17).** `sast_scan.py` OWASP map relabelled to the crawled
   2025 taxonomy: crypto→A04, injection→A05, insecure-design→A06, misconfig→A02, components→**A03
   Software-Supply-Chain** (+`validate_edge_unpinned_imports`), **SSRF folded into A01**, and the NEW
   **A10:2025 Mishandling of Exceptional Conditions** mapped to real, verified scanners
   (`edge_error_capture` / `debug_echo_prod_safe` / `edge_status_body_consistency` /
   `cmms_webhook_security_live`). Honest **10/10** — every category has a scanner that exists (all 6
   new refs resolved at root/tools; not faked). *(Deepening A03 supply-chain — lockfile hash /
   transitive deps — remains a forward item.)*
2. **CWE gaps — RE-SCOPED against verified reality (a live grep, not an assumption):** there are
   **zero `storage.from().upload(`** calls anywhere — the platform reads files **client-side**
   (resume → AI-extract; logbook photo → data-URI) and **never persists them server-side**. So
   **path-traversal (CWE-22) is N/A** (no server file paths) and **unrestricted-upload (CWE-434) is
   low** (no bucket, no exec). The **real residual** is client-side: **no file-SIZE cap on any
   read surface** (verified: 0 size guards) → a **DoS class** (a huge file OOMs FileReader/canvas/
   the AI extractor) + untrusted content reaching the extractor. → build `validate_file_upload_safety.py`
   to assert every `type=file` surface has an `accept=` allowlist AND a `file.size` guard. **BUILT +
   registered** (`validate_file_upload_safety.py`, advisory/non-blocking gate `file-upload-safety`,
   `--selftest`): scanned **9 file-upload surfaces**, found 2 gaps (`integrations.html` +
   `inventory.html`, no file-size cap = DoS) → **both FIXED same-arc** (10MB photo cap / 15MB CSV-XLSX
   cap) → **9/9 guarded, gate green**, ratchets forward. Heuristic v1 caveat: "guarded" = a
   byte-magnitude `file.size` reference (Map.size excluded), so it may *display*-not-*enforce* — a
   v2 should parse an actual cap comparison. **CSRF (CWE-352) stays low** (JWT-bearer). *(This whole
   item is the evidence-discipline lesson compounded: the crawl-grounded "path-traversal + upload
   gap" shrank to a 2-page client-side size-cap once I checked for server storage, ran a grep, then
   BUILT + ran the instrument — five corrections, each from verifying before asserting.)*

**Method note (evidence discipline):** this analysis caught **two false gap-claims** before they
shipped — a stale memory's "sast 7/10" (it is 10/10) and a `tools/`-only `ls` that missed validators
living at repo **root** (`sast_scan._resolve` checks root then `tools/`). Verify a validator at BOTH
paths AND run the tool before asserting a coverage gap.

## 4 · Execution order (highest blast-radius first)

1. **Tier-1 daily-driver pages** (hive, logbook, inventory, pm-scheduler, asset-hub, alert-hub) — most
   traffic + most write paths. Drive all 8 phases to 100% each, gate as you go.
2. **Tier-2 intelligence/report pages** (analytics, analytics-report, ai-quality, ph-intelligence,
   predictive, project-report) — mostly read/display; P3/P4 lighter, P2 (silent-error) heavier.
3. **Tier-3 social/marketplace/growth** (community, public-feed, marketplace×4, achievements,
   skillmatrix, resume, dayplanner).
4. **Tier-4 admin/connect/companion** (integrations, plant-connections, report-sender, assistant,
   voice-journal, audit-log, founder-console, project-manager).

Per page: run P1→P8 in order (each phase gates before moving on), file findings in a per-page
section, fix + verify + **gate every fix**, then ratchet the page's cells.

## 5 · Reusable harness (build once, reuse per page — don't reinvent)

- **`tools/page_battery.mjs`** (to build) — one node harness: sign-in-once (reuse `live_page_journeys.mjs`
  recipe), then per page run P1/P2 (console+network capture), P4 (input matrix), P8 (screenshot baseline).
  Emits a per-page JSON the scoreboard reads.
- **P3/P5/P6** stay MCP-interactive (Playwright drive + postgres verify + 2nd context) — these need
  judgment per entity.
- **Gate pattern:** live findings → extend `validate_hive_write_isolation.py`; render-logic → extend
  `validate_display_correctness_fixes.py`; new per-page live batteries → `validate_<page>_battery.py`
  registered in `run_platform_checks`.

## 6 · NEXT (fresh window picks up here)

**Gate-suite drive (2026-07-18, session 6 cont.):** drove `run_platform_checks.py` from the session's 41 FAIL toward 0 — **13 gates cleared this turn, each ROOT-caused (not floor-lowered), each individually verified green:** clone-debt + render-budget (documented legit feature/security growth), arc-x-cognitive (stale `_searchLbl` a11y-refactor anchor), csp (anti-flash script folded into an existing head-init block — no fake nonce, block count held at 12), ai-asset-versioning (persona.ts 9→10 re-sealed for the B3 + PH-safety change), **db-adoption (ROOT FIX: `build_substrate.py` scoping analyzer no longer counts a restricted `grafana_reader` monitoring read as an app-user cross-tenant hole → D2 89→97 after regen)**, schema (platform-actions `hive_audit_log` insert given NOT-NULL `hive_id`+`actor`), rls-readiness + idempotency (ops_artifact_metrics GRANT→REVOKE — clears both gates + more secure), canonical-anchor (registered ops_artifact_metrics + get_seller_community_reputation, mig `20260718000002`), ai-seams-inventory + ai-seam-coverage (re-baselined to the 148-seam inventory). gateway-bypass + gateway-gate-depth confirmed green (slow, not failing); memory-index at accepted WARN (loads).

**Residual-13 sweep (2026-07-18, FULL suite — the `--fast` tier had HIDDEN these; process lesson persisted):** running the full `run_platform_checks.py` (not `--fast`) exposed **13 MORE pre-existing live-tier fails**, none regressions from the 13 above. Ian: "drive ALL 13 to 0 inline." ALL 13 fixed + individually verified green: Interactive Lineage (`projects` redundancy KEEP-context verdict) · Canonical Overlap (allowlist platform-actions marketplace overlaps) · Canonical Anchor L7 (`dashboard-allow` on platform-actions action-queue) · Landing featureList (+Predictive Analytics) · Platform Name + SEO Technical (documented baselines: folded-feature name / dual-mode 1-visible-h1 / inert retired FAQPage; real FAQPage-strip flagged for SEO arc) · Arc X Family C (triaged free-form `post-part-number`) · **Arc G RLS + Arc J realtime (SAME grafana_reader role-blindness as db-adoption → added a `polroles` app-facing filter to both SQL detectors; live-verified all 10/4 flagged tables are grafana_reader-ONLY, teeth preserved)** · Arc Q Calc + Engines LIVE (**false ceiling — `workhive_python_api_fwd` port-forwarder was Exited; `docker start` → 63/63 calcs standard-correct**) · Deep-arc engineering_calcs (**stale test — bind trigger CORRECTS the forged auth_uid (empirically rolled-back-proven pinned-to-caller); test now checks the RETURNING stored value + fixed a latent em-dash/cp1252/0x97 `_psql` subprocess bug**) · logbook + inventory (surgical DB-pollution reconcile: backfilled lototest link + recomputed the 1 drifted item's ledger chain). Lessons → memory `feedback_infra_role_vs_app_user_isolation` (3-gate extension + --fast-vs-full) + Security/QA/AI-engineer/DevOps/Data-engineer skills. Final full-suite re-run 0-FAIL confirmation in flight (0 fails through 469/505 at last check). **NEXT: Ian commit-gate ALL local work (migs 000012–000017 + `20260718000002` + `build_substrate.py`/Arc-G/Arc-J/engdesign-test edits + baselines + DB reconcile — all documented + reversible + teeth-verified); then the per-page battery frontier — asset-hub P7 approval-lock (10→60 gap), residual P3-write, P6 concurrent.**

`NEXT: Start Tier-1 · hive.html — run P1→P8 to 100%: P3 CRUD (create a logbook WO from the board →
verify FK+auth_uid+hive_id at DB; edit/close it; delete), P4 inputs (empty/oversize/xss/unicode into
every board affordance), P6 concurrent (two members edit the same WO / approve race), P7 locks
(pending-approval + offline degraded), P8 visual (390px + desktop baseline). Gate each phase, ratchet
the scoreboard, then hive→100% and move to logbook. Reuse the 2026-07-13 sign-in recipe + gate
pattern. Test identities: pabloaguilar/Lucena c9def338 (supervisor), leandromarquez/Baguio 636cf7e8
(supervisor), bryangarcia/Baguio (worker).`

**NEXT v2 (denominator extension, 2026-07-17):** the ruler is now complete (12 phases + the platform
SAST track). Two tracks now run in parallel to raise the re-baselined ~56.3%: **(1) drive P9–P12** off
their floors per page (a11y axe-clean, CWV in budget, EN/FIL complete, error-fail-closed) — extend
`page_battery.mjs` with an a11y+CWV+i18n pass so P9–P11 gate mechanically like P1/P2/P8; **(2) close
the security backlog** — build the 3 zero-coverage validators (file-upload → path-traversal → CSRF)
and relabel the sast map 2021→2025. Each is a Make-a-Change → Flywheel unit; gate every fix, then
ratchet the cells. Highest KEV first: `validate_file_upload_safety.py`.
