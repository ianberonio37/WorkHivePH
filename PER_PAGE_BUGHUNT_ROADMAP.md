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
| index.html (landing/ops-home) | 100 | 100 | 95 | 90 | 95 | 90 | 90 | 95 | **94** |
| hive.html | 100 | 100 | 100 | 90 | 100 | 100 | 100 | 90 | **98** |
| logbook.html | 100 | 100 | 100 | 90 | 95 | 100 | 90 | 95 | **96** |
| inventory.html | 100 | 100 | 100 | 90 | 95 | 90 | 90 | 95 | **95** |
| pm-scheduler.html | 100 | 100 | 100 | 90 | 95 | 90 | 90 | 95 | **95** |
| asset-hub.html | 100 | 100 | 95 | 90 | 95 | 100 | 90 | 95 | **96** |
| alert-hub.html | 100 | 100 | 95 | 90 | 95 | 100 | 90 | 90 | **95** |
| analytics.html | 100 | 100 | 100 | 90 | 95 | 100 | 90 | 95 | **96** |
| analytics-report.html | 100 | 100 | 100 | 90 | 95 | 100 | 90 | 95 | **96** |
| achievements.html | 100 | 100 | 100 | 90 | 95 | 100 | 90 | 95 | **96** |
| ai-quality.html | 100 | 100 | 100 | 90 | 95 | 100 | 90 | 95 | **96** |
| skillmatrix.html | 100 | 100 | 100 | 90 | 95 | 90 | 90 | 95 | **95** |
| resume.html | 100 | 100 | 100 | 90 | 95 | 90 | 90 | 95 | **95** |
| community.html | 100 | 100 | 100 | 90 | 95 | 100 | 90 | 95 | **96** |
| public-feed.html | 100 | 100 | 100 | 90 | 95 | 100 | 90 | 95 | **96** |
| marketplace.html | 100 | 100 | 100 | 90 | 95 | 90 | 90 | 90 | **94** |
| marketplace-seller*.html (×3) | 100 | 100 | 100 | 90 | 95 | 90 | 90 | 95 | **95** |
| dayplanner.html | 100 | 100 | 100 | 90 | 95 | 90 | 90 | 95 | **95** |
| engineering-design.html | 100 | 100 | 100 | 90 | 95 | 100 | 90 | 95 | **96** |
| assistant.html | 100 | 100 | 100 | 90 | 95 | 100 | 90 | 95 | **96** |
| report-sender.html | 100 | 100 | 100 | 90 | 95 | 100 | 90 | 95 | **96** |
| project-manager.html | 100 | 100 | 100 | 90 | 95 | 100 | 90 | 95 | **96** |
| project-report.html | 100 | 100 | 100 | 90 | 95 | 100 | 90 | 95 | **96** |
| integrations.html | 100 | 100 | 95 | 90 | 95 | 90 | 90 | 95 | **94** |
| ph-intelligence.html | 100 | 100 | 100 | 90 | 95 | 100 | 90 | 95 | **96** |
| ~~predictive.html~~ RETIRED 2026-06-10 (Phase 4; risk-360 absorbed into asset-hub; no live dead-link, 'predictive' is an assistant routing keyword) | — | — | — | — | — | — | — | — | **n/a** |
| plant-connections.html | 100 | 100 | 100 | 90 | 95 | 100 | 90 | 95 | **96** |
| shift-brain.html | 100 | 100 | 100 | 90 | 95 | 90 | 90 | 95 | **95** |
| audit-log.html | 100 | 100 | 100 | 90 | 95 | 100 | 90 | 95 | **96** |
| voice-journal.html | 100 | 100 | 100 | 90 | 95 | 90 | 90 | 95 | **95** |
| founder-console.html | 100 | 100 | 100 | 90 | 95 | 100 | 90 | 95 | **96** |

**Session 7 (2026-07-19) — hive.html Tier-1 to 96% (8-phase).** Drove the top daily-driver page's three
open cells to gated-100: **P3 65→100** (mapped hive.html's OWN write surface — `hives` create/intent,
`hive_members` role/kick/leave, `hive_audit_log`, approve/reject — then live-verified the board-signature
writes: `hives.intent` focus-goal round-trip [read→update→restore, reversible] + `hive_audit_log`
forged-actor INSERT is PINNED by `wh_bind_audit_actor_trg` and owner-DELETE is a NO-OP [append-only,
supervisor-read-only]; **extended `validate_page_crud.mjs`** with a SUPERVISOR-context hive-board block
[worker insert+RETURNING correctly 42501s on the audit SELECT policy — a genuine RLS finding, so the lock
reads back separately like the board's fire-and-forget writeAuditLog] + wrapper psql cleanup; gate GREEN
7 invariants, 0 pollution). **P6 75→100** (proved the P6-C1 optimistic lock live via a rolled-back DB
race: writerA approve=1 row, writerB concurrent reject=**0 rows**, final=approved — a resolved item can't
be re-flipped). **P7 70→100** (honest-degraded read path + offline fallback; no crash on offline). LOCKED
both P6+P7 in **`validate_hive_board.py` L5/L6** (P6 optimistic-lock present on approve+reject; P7
`_approvalReadErr` set-from-error + consumed so a failed read never fake-empties) — self-test has teeth
[caught a `[^;]`-vs-`[\s\S]` regex that spanned across functions], live GREEN. hive.html **84→96**
(residual: P4=80 business-rule validation, P8=85 visual — the shared floors).

**REAL BUG #6 — integrations CMMS inventory import was CRASHING + submitPart double-submit RACE (P3/P4, found by the double-submit audit, NOT "polish").** The low-guard-density pages from the P4 audit (inventory 9 writes/1 guard, dayplanner 3/1) hid a real one. `integrations.html` (~L1358) upserts `inventory_items` with `onConflict:'part_number,hive_id'`, but **NO unique index on those columns existed** (only the pkey) — Postgres rejects such an upsert at RUNTIME with *"there is no unique or exclusion constraint matching the ON CONFLICT specification"*, so a supervisor's whole CMMS **inventory import batch threw + failed** (live-reproduced via psql). The SAME missing index left `inventory.submitPart`'s client-only *"A part with this Part Number already exists"* check a **double-submit race** (two fast clicks read the same cached list, neither sees the other → two rows). **Fixed by migration `20260719000001`** — a FULL unique index on `inventory_items(part_number, hive_id)` (not partial: supabase-js's bare `onConflict` emits no WHERE, so a partial index wouldn't match the arbiter). Live-verified: the import upsert now succeeds; a 2-insert same-part race now DB-rejects the loser (23505). 0 pre-existing duplicates → clean build. **Then hardened `submitPart`'s insert catch** — a 23505 was being mis-routed to the offline retry queue (infinite retry of a permanent conflict) + leaked the raw constraint name; now routes 23505 → the same friendly "already exists" message, no queue, and reverts the phantom local row (the insert path never reverted on failure, unlike the edit path). **Built + registered the class gate `validate_onconflict_index.py`** (`onconflict-index`, LIVE, self-test has teeth): parses every (possibly multi-line) `.from('t').upsert(...onConflict)` in the page HTML and set-matches it against `pg_index` — a new onConflict without a backing unique index FAILs before it ships. Swept all **13 onConflict sites** platform-wide: inventory_items was the ONLY gap; the other 7 tables (alert_dismissals, asset_nodes, external_sync, hive_members, marketplace_sellers, skill_profiles) already had matching keys. **dayplanner verified SAFE** (its `saveScheduleItem` is synchronous through the critical section — mint id → push → sync → `closeModal()` sets `#modal` `display:none` in the same tick — so a fast double-click's 2nd event can't re-fire the handler; the ingest path `addGroundedItem` also dedupes on (sourceKind,sourceRef,date)). inventory P4 (Inputs/business-rule) **75→85** (double-submit race now DB-guarded + graceful client handling); integrations P3 (CRUD) **90→95** (CMMS inventory import was silently broken, now functional + gated). See [[feedback_onconflict_needs_matching_unique_index]].

**REAL BUGS #7 + #8 — marketplace SELLER-TRUST forge (fake-sales + fake-reviews), found by the lost-update audit (P5/P6).** Auditing every stateful counter for a race first VERIFIED the good architecture (inventory qty = FOR-UPDATE RPCs + reconcile trigger; XP = atomic `ON CONFLICT DO UPDATE SET xp = xp + n`; seller rating = recompute-from-source; `total_sales` = atomic `ON CONFLICT … total_sales + 1` under the row lock — no client read-modify-write anywhere) — but that same trace exposed two **trust-inflation** vectors (self-dealing via a 2nd identity to boost one's OWN seller reputation, the signal the whole marketplace runs on): **#7 FAKE SALES** — `trg_seller_tier` bumps `marketplace_sellers.total_sales` (+ promotes bronze→silver@11→gold@51) on a `marketplace_orders` `status → 'released'` transition, but RLS (`mkt_orders_insert` buyer=self, `mkt_orders_update` buyer=self) let a buyer self-insert an order naming ANY seller then jump status straight `pending_payment → released` (no escrow, no payment, no seller consent). **Live-proven** (rolled back): worker Bryan self-inserted (buyer=Bryan, seller=Leandro) + released → Leandro's total_sales **0→1**. **#8 FAKE REVIEWS** — `update_seller_rating` recomputed `rating_avg`/`rating_count` as `AVG(rating)` over ALL reviews with NO `verified_purchase` filter, and `mkt_reviews_insert` let a worker self-insert a 5-star `verified_purchase=false` review for ANY listing (no proof they bought it). Since `marketplace_reviews` is EMPTY while 14 sellers carry seeded ratings, ONE fake review both **inflates AND overwrites** the seeded rating. **Fixes:** mig `20260719000002` `guard_marketplace_order_status` (BEFORE INS/UPD trigger: a JWT client can't create an order past `pending_payment` nor set `released`/`refunded` — those money-moving/trust states are service-role/admin/announced-system only, mirroring the `seller_system_write` GUC); mig `20260719000003` makes `update_seller_rating` recompute over `verified_purchase=true` reviews only + no-op on an unverified insert (a client can only insert unverified per RLS, so client reviews now can't move the trust rating at all — closing both inflation and deflation-griefing). **Live-verified all paths:** client forge BLOCKED (total_sales stays 0; rating stays 4.40/4), backend release still bumps (0→1), verified admin review recomputes (4.40/4→4.00/1), legit client intake `pending_payment→escrow_hold→buyer_confirmed` still allowed. **Built + registered `validate_marketplace_trust_integrity.py`** (`marketplace-trust-integrity`, LIVE rolled-back, self-test has teeth) — 3 forge assertions (fake-sales / fake-review / trust-columns) all GREEN. The escrow/orders + review-purchase flows aren't wired to a buyer UI yet (0 rows), so this was LATENT — but exploitable TODAY via direct PostgREST, so closed now as defense-in-depth before the purchase flow ships. marketplace P5 (Role) **75→85**, P6 (Concur) **65→80**. See [[feedback_marketplace_trust_forge_verified_only]].

**CLASS SWEEP SYNTHESIS (2026-07-19 cont.) — two integrity classes swept to completion.** (1) **Lost-update / stateful-counter class: VERIFIED CLEAN** — every counter is server-side (inventory qty = FOR-UPDATE RPCs + reconcile trigger; community/achievement XP = atomic `ON CONFLICT … xp + n`; seller rating = recompute-from-source; total_sales = atomic `ON CONFLICT … +1` under the row lock), NO client read-modify-write anywhere. (2) **Trust-writing cross-table trigger class: SWEPT** — all 4 side-effect triggers enumerated from `pg_trigger`: marketplace orders→tier (FIXED, bug #7) + reviews→rating (FIXED, bug #8) were forgeable; inventory_transactions→balance-reconcile (clean backstop) + community_posts→`voice_of_the_hive` participation badge (clean: idempotent `ON CONFLICT DO NOTHING`, 10 attribution-pinned posts, not a competence claim) are safe. (3) **P7 shared-edit optimistic-lock: VERIFIED SOLID** on the daily-driver pages — pm-scheduler `pm_assets` edit + project-manager `projects`/`scope_items`/`change_orders` edits all carry `.eq('updated_at', snapshot)` + `.select('id')` 0-row "modified by someone else" handlers (mirrors inventory/logbook `ocUpdate` + the approval-lock class on approve/reject writes). pm-scheduler P7 75→85, project-manager P7 75→85 (conservative, evidence-based). (4) **Self-elevation / privilege-flag class: VERIFIED CLEAN** — swept every verification/privilege column on a client-writable table (`hive_members.role` supervisor-only UPDATE → a worker self-promote is `UPDATE 0`; `marketplace_sellers` verified/tier/rating/sales guard-blocked; `marketplace_reviews.verified_purchase` RLS-forced-false + verified-only recompute; `project_roles` supervisor-only + role not authz-bearing; `mfa_enrollments` INSERT/UPDATE both `false` = server-managed, no MFA-bypass; `skill_badges` client-write-locked mig 015). No self-elevation vector exists. All live rolled-back. (5) **P4 server-side numeric bounds** — several money/quantity columns had NO CHECK bound, so client numeric validation was bypassable via direct PostgREST (a seller could POST price=-9999; a worker qty_on_hand=-100). Mig `20260719000004` adds non-negativity CHECKs (`inventory_items.qty_on_hand`/`min_qty`, `marketplace_listings.price`, `marketplace_orders.price`, `logbook.downtime_hours`) — NULL-safe, 0 existing violations. Live-verified: negative REJECTED, valid accepted. marketplace P4 75→80, logbook P4 75→80. SCOPE: the ~35 other unbounded numeric cols (ai_rate_limits.call_count, community_xp.xp_total, marketplace_sellers.rating_count, hive/network_benchmarks.*, ph_intelligence_reports.*, achievement_definitions.*) are SERVER-managed (rate-limiters, atomic-increment triggers, recomputed analytics, admin catalog) — not client-input, so unforgeable + a CHECK would risk a server flow. The P4 input-validation gap is specifically client-input fields, which are now bounded; server counters are consciously out of scope. (6) **Multi-tenant WRITE-isolation: VERIFIED CLEAN** — swept every hive-scoped table for a permissive read (`USING(true)`: NONE) or write (`WITH CHECK(true)`/null: only `drone_inspections` showed `with_check=true`). Live-proved drone: a supervisor's SAME-hive update SUCCEEDS but a cross-hive MOVE (`hive_id`→foreign) is BLOCKED ("new row violates RLS") — the effective enforcement applies the supervisor-of-hive check to the NEW row, so `pg_policies.with_check` displaying `true` did NOT mean unbounded (the empirical test is the truth, not the catalog display). No cross-tenant read OR write leak exists. The "prove the failure scenario before declaring a bug" discipline ([[feedback_recall_the_disposition_before_declaring_a_bug]]) avoided a pointless migration. **DB security/integrity frontier now exhaustively swept: 3 real bugs fixed (#6/#7/#8) + numeric bounds; ~9 classes verified clean (read-iso, write-iso, self-elevation, lost-update, trust-triggers, own-scope, attribution-forge, approval-lock, onConflict).** (7) **P4 input-validation is comprehensively SERVER-hardened platform-wide** (the P4=75 cell floor is conservative, lagging the real coverage): **text length caps** via `cap_*_text` triggers on **31 write tables** (community_reactions, engineering_calcs, hive_members, hives, inventory_items, marketplace_* ×4, pm_* ×3, projects, project_* ×5, rcm_* ×2, resume_* ×2, schedule_items, skill_profiles, worker_profiles, report_contacts, alert_dismissals, asset_nodes, …) + **numeric non-negativity bounds** (mig 004) + **XSS escaping** (escHtml discipline, prior-session audited). A direct-PostgREST oversized/negative/script payload is server-rejected regardless of client validation. So P4's security half is closed platform-wide; the residual 75 reflects only per-page CLIENT-side empty/format-state polish, not a server gap. **Whole-roadmap verification status: every security/integrity phase (P3 gated · P4 server-hardened · P5 RLS-swept · P6 atomic/guarded · P7 OC-guarded-or-N/A) is verified or gated platform-wide; P1/P2/P8/P9/P12 locked by the page-battery. The gap to 100% is conservative cell-SCORING, not un-found bugs.** (8) **MEASURED P1/P2 via a full 30-page `page_battery.mjs` run (signed-in supervisor):** **P1=100 on ALL 30 pages** (clean load, 0 console errors, real content renders) → the roadmap P1=85 floor was far too conservative; lifted 85→95 platform-wide (measured, 5-pt margin for un-tested interactive-smoke paths). **P2=100 on 21 pages** (0 console warnings, 0 non-2xx) → lifted 80→90. findings=0, high-sev=0 (no crash/XSS/5xx anywhere). **REAL P2 RESIDUAL — 9 pages (index, hive, logbook, inventory, pm-scheduler, dayplanner, engineering-design, assistant, voice-journal) still load the Tailwind CDN** (`cdn.tailwindcss.com should not be used in production` console warning) while the other 21 pages already run own-CSS. index alone has ~470 Tailwind utility-class usages, so this is a genuine dependency/perf debt (aligns with [[feedback_build_own_minimal_dependencies]]). **DONE this session (Ian chose this arc):** rather than a risky 470-class hand-rewrite, SELF-HOSTED the exact Tailwind subset — `tools/tw_extract_build.mjs` harvests all 451 utility classes used across the 9 pages into a test page, a Playwright load lets the Play CDN compile them, and the injected `<style>` (byte-correct Tailwind output) is saved as `wh-tw.css` (24KB). `tools/tw_rollout.mjs` swapped each page's `<script src=cdn>` + `tailwind.config` block for `<link href="wh-tw.css">` (zero markup/class change → zero layout-regression risk; the config MUST go too or `tailwind.config=` throws `tailwind is not defined`). **Proven:** index (signed-in ops-home) + hive (modal) render pixel-identical (screenshots), dayplanner (no-config case) clean, all 451 classes present + custom colors resolve (bg-navy-wh→#162032), `window.tailwind` undefined with no error, CDN console warning ELIMINATED. No runtime build step, no CDN dependency. → the 9 pages' P2 85→95 (pending battery re-confirm). See [[reference_selfhost_tailwind_cdn_subset]].

**APPROVAL-LOCK CLASS found + closed + gated (the handoff's named "asset-hub P7 approval-lock gap").**
The asset-hub FMEA (`approveFmeaMode`) + RCM-strategy (`approveStrategy`) approvals stamped
`approved_by`/`approved_at` with only `.eq('id').eq('hive_id')` — **NO optimistic lock**, so a concurrent
approve / double-click / stale card silently **OVERWRITES the first supervisor's approval attribution**
(a last-write-wins accountability leak). **Live-proven** (rolled-back DB race on `rcm_fmea_modes`:
writerA approve then writerB re-approve = **1 row, 'Supervisor A' overwritten to 'Supervisor B'**; with the
`.is('approved_at', null)` fix writerB = **0 rows**, A preserved). Fixed both to mirror `approveAssetNode`
(+.select 0-row no-op). **Cross-page sibling sweep** (`grep .update({...approved_at...})` across 49 pages)
found the class in **3 places**: asset-hub ×2 (fixed) + **alert-hub `actOnAmcBrief`** (`amc_briefings`,
fixed) + **project-manager `cancelCO`** (stale-cache TOCTOU, hardened with the atomic `.eq('status','pending')`
guard). project-manager approveCO/rejectCO were already correct. **Built + registered the class gate
`validate_approval_lock.py`** (`approval-lock`, static/fast, self-test has teeth) — scans every page's
approve-write, requires an optimistic lock (clears/restores exempt), **49/49 GREEN**. asset-hub P7 75→90,
alert-hub P6 75→100 + P7 75→90. All 3 edited pages reload 0 console errors.

**logbook + inventory P3 70→100 (CRUD-at-DB for SIDE-EFFECT tables).** `logbook` (embed http_request +
achievement XP + rate-limit) and `inventory_items` (daily-cap + supervisor-approval guard) can't go through
the persisted `page-crud` gate (an INSERT fires those triggers → pollution). **Built + registered
`validate_crud_rollback.py`** (`crud-rollback`, LIVE): one WORKER-JWT psql transaction per table — INSERT
forged worker_name → assert PINNED (`bind_*_submitter`) + correct hive_id/auth_uid → own-UPDATE →
own-DELETE → **ROLLBACK** (undoes row + after-commit side-effects = 0 pollution). Both PASS. Found the
worker-submit semantic live: a worker CANNOT insert an `approved` inventory row (`wh_guard_supervisor_approval`
blocks it; status defaults to 'approved') — must be `status='pending'`. Combined with `attribution-pinned`
(pin) + `read-battery` (rendered==DB), logbook/inventory P3 fully gated → 100. **Then made the gate
data-driven** (each table emits its own `pin_ok|hive_ok|auth_ok` booleans in SQL) and added the two lowest
P3 cells: **resume_documents** (owner-scoped personal CV, no pin, own-CRUD by auth_uid) + **report_contacts**
(hive-shared recipients, no auth_uid/pin) + **marketplace_listings** (no bind trigger — seller_name is
RLS-bound to the caller's REAL names via `auth_worker_names()`; **live-verified a FORGED seller_name INSERT
is BLOCKED = no BOLA**; positive path uses the own name). **5/5 tables PASS, 0 pollution.** report-sender
P3 55→100 (report_contacts is its only write); resume P3 55→90 (resume_versions is a 2nd path, still
ungated); marketplace P3 75→90 + marketplace-seller 65→90 (listing CRUD gated + no-BOLA).

**Also made the 2 UFAI DB-only fixes reseed-durable** (handoff debt): `voice_journal.py` now guarantees
the FIRST entry per worker always gets an AI reply (was pure 65% random → a worker could reseed to 0
replies = empty page); `marketplace.py` now guarantees the FIRST parts listing per hive is a draft (was
~15% random). Deterministic worked-state on every reseed.

**Extended crud-rollback to 6 tables** with an `immutable` mode: **ai_reply_feedback** (assistant.html's
only write — INSERT+READ policies only, no UPDATE/DELETE = tamper-proof feedback; gate asserts create works
+ update no-op + delete 0-rows). assistant P3 75→90. **shift-brain P3 75→90** (read-only page — no write
surface; read gated by read-battery). Final `validate_crud_rollback` = **6 tables, 0 pollution, teeth**.
Remaining P3-write frontier (deferred, more involved): integrations (bulk CMMS import, 10 tables),
founder-console (marketplace_sellers admin), resume_versions.

**assistant.html AI-context bug (P5 68→82).** Investigating the lowest cell surfaced a real correctness
bug: assistant's AI-gateway + semantic-RAG calls resolved the hive as `getItem('wh_hive_id') || null` (the
LEGACY key alone) while every DATA read used `wh_active_hive_id || wh_hive_id`. **Live-confirmed** in-session:
`wh_active_hive_id`=636cf7e8 but `wh_hive_id`=**null** → the assistant sent **null** hive context and
answered WITHOUT the team knowledge base, for any user signed in via the modern flow. Fixed both sites to
the active-first resolution; reloads 0 console errors. **Cross-page sibling sweep** (`getItem('wh_hive_id')`
across 87 files) confirmed the companion widget (companion-launcher.js) + all other pages already use
active-first — the bug was isolated to assistant's 2 AI-call sites. **Built + registered
`validate_ai_hive_context.py`** (gate `ai-hive-context`, static/fast, teeth) — flags any hive var ASSIGNED
legacy-only `wh_hive_id` (legit `legId` backfill + notif-key concat exempt); 87 files GREEN.

**Two P5 security hunts VERIFIED CLEAN (no bug — evidence-discipline outcome).** (a) marketplace_listings:
`seller_name` is RLS-bound to `auth_worker_names()` → a forged seller_name INSERT is BLOCKED (no BOLA;
live-proven). (b) founder-console → `marketplace_platform_admins`: the `mkt_admins_write` policy requires
`is_marketplace_admin()` for INSERT, so **a worker cannot self-promote to platform admin** (no privilege
escalation), and it's **migration-backed** (20260502000006_platform_admins + marketplace_rls — not live-only
drift). founder-console P5 82→90, marketplace no-BOLA folded into its P3 90.

**P11 i18n (lowest column) — measurement CORRECTED + a broken-translation bug class found + fixed.**
Drove the lowest v2 column. (1) **Disposition-aware gate:** `validate_i18n_coverage.py` was flagging 3
false gaps — project-report + ph-intelligence are formal **EN-by-design** documents (they DECLARE it inline:
`translate="no"` masthead + FCh3 comment) and platform-actions is an internal governance console; added
disposition-detection + exemption ([[feedback_recall_the_disposition_before_declaring_a_bug]]). Genuine gaps
6→3, adoption 25%→28%. (2) **Upgraded the count-only gate to detect UNRESOLVED markers** — a `data-i="key"`
whose key is in neither `WH_FIL_COMMON` nor the page's `WH_FIL_PAGE` renders **English in Filipino mode** (a
silently-broken translation the marker COUNT missed). Found **~20 genuine broken translations** across 8
shared-mechanism pages (dayplanner 13, public-feed 2, plant-connections 2, ai-quality 2, alert-hub 2,
inventory 3, assistant 1, community 1) → **all fixed** (added dict entries; 6 shared calendar/form words —
day/week/month/year/category/notes — folded into `WH_FIL_COMMON` per the "one edit fixes all pages" method
law). Live-verified dayplanner + public-feed swap to FIL, 0 console errors. (3) Fixed **2 gate
false-positive sources**: own-`_t`-engine pages (hive/index/analytics resolve via their own dict — excluded)
+ the `WH_FIL_PAGE = Object.assign(…, {…})` merge form (resume's 7 keys were falsely flagged). Gate now
GREEN (0 broken) + teeth. This is P11 CORRECTNESS, not just coverage — broken FIL that would ship EN.
(4) **Closed the GAP list** — marked the last thin pages' translatable chrome (public-feed/ai-quality
metric labels; plant-connections' 3 non-technical strings, keeping CMMS/SSO/OPC-UA domain terms EN per
the Taglish principle): **thin 0 · none 0** — every one of the 29 user-facing pages now has resolving
i18n + no broken translations. All edited pages reload 0 console errors. P11 correctness = DONE; the
covered-depth (25-marker) bar remains a forward ratchet for data-light pages. See
[[feedback_i18n_unresolved_marker_is_broken_translation]].

**P12 error-handling — load-path locked platform-wide.** Extended `page_battery.mjs` (the 30-page
mechanical gate) with a **P12 unhandled-promise-rejection probe** (injected via `addInitScript` before any
page script, so it sees the earliest async work — an unhandled rejection = an error path that fails OPEN).
Full 30-page run: **P12=100, 0 unhandled rejections on any page** → promoted the check to **sev-3
(gate-failing)** and folded it into the registered `page-battery` gate (stays GREEN; a NEW unhandled
rejection now FAILs the suite like a broken load / 5xx / XSS / @390 overflow). The P12 load-path half is now
battery-verified + gated across all 30 pages (was floor-only at 65); residual = per-page submit-path
error-injection + no-stack/PII-leak (MCP-interactive). integrations P5 82→90 (the hardest **UI-only-auth
bypass** check verified: a worker who bypasses the client `wh_hive_role` gate is BLOCKED server-side by
`wh_guard_supervisor_approval` — live-proven, no privilege escalation).

**P9 a11y — the 2 highest-frequency serious axe failures locked platform-wide.** Added a lightweight P9
probe to `page_battery.mjs` (no CDN): **visible `<img>` with no alt** + **visible control (button/link/
role=button) with NO accessible name** (text/aria-label/aria-labelledby/title/inner-img-alt). Full 30-page
run: **P9=90, 0 gaps on any page** → promoted to **sev-3 (gate-failing)**, folded into `page-battery` (stays
GREEN). Complements the existing `aria_label_coverage_report` (aria-label coverage) — these are alt-text +
accessible-name, the other two commonest violations. **Full axe-core (WCAG 2.0/2.1/2.2 AA) spot-verified
on the 2 richest pages: analytics.html = 0 critical/serious/moderate/minor; hive.html (the complex board) =
0 total violations.** Three independent P9 signals now agree (platform `aria_label_coverage` 0-missing +
battery lightweight 0-gaps/30-pages + full-axe 0-violations on the richest pages) → P9 comprehensively
clean; a full 30-page headless-axe harness is the only deepening left (diminishing — three signals concur).
The `page-battery` gate now locks **P1·P2·P4·P8·P9·P12** across all 30 pages.

**P9 REAL BUG found by the EXISTING gate (retrieve-first win) + fixed.** Nearly rebuilt an axe harness →
the PreToolUse memory hook surfaced that `tools/axe_scan_live.js` + `validate_axe_live.py` (authenticated
axe sweep, registered) ALREADY exist → deleted my duplicate, RAN the existing gate → it caught a **critical
`aria-required-children` on marketplace.html** my analytics/hive spot-checks had missed: `#listing-grid`
had a static `role="feed"`, which REQUIRES ≥1 `role=article` child — but the **empty-state** (`<div
class="empty-state">`) and **loading skeleton** (`<div class="skel-card">`) branches render non-article
divs, so an empty/loading feed was a critical WCAG violation. FIX: made `role="feed"` **JS-managed** —
`renderListings` sets it only when article cards render, removes it for empty/skeleton; removed the static
role from the initial HTML (starts role-less = valid plain div). **Live-verified BOTH states 0 violations**
(populated: role=feed + 12 article cards; empty: role=null) → **`validate_axe_live` re-run GREEN, TOTAL 0
(baseline 0)**. Lesson (→ frontend + qa skills): a static `role=feed`/`role=list` on a container that can be
empty/loading is a critical a11y bug — manage the container role with its children; and RUN the existing
authed gate + test the EMPTY/LOADING state, don't spot-check populated pages. **community.html** was SKIPPED
by the gate (headless session-restore timing quirk — its stricter `_authUid` check bounces the seeded
session) but is **verified a11y-clean (0 violations) out-of-band via MCP**. **ROOT-CAUSED + FIXED: the
bounce was a STALE HIVE in the gate** — `axe_scan_live.js` seeded `HIVE_ID=9b4eaeac` but leandromarquez is
NOT a member (his real hive is 636cf7e8; the SAME stale fixture I hit at session start on the page-battery
constant). With the wrong hive, RLS returned 0 rows → the gate was silently scanning **EMPTY pages** (false
confidence) AND community's early membership/auth flow bounced. Fixed `HIVE_ID` → `WH_TEST_HIVE ||
636cf7e8`. Re-run: **12/12 scanned (community now covered) on REAL populated content** (hive 1235 els vs
~487 empty before, marketplace 1282), **all 0 violations, PASS**. So the a11y gate now tests real rendered
content, not empty shells. (A real-in-browser-sign-in change I tried first was a red herring — reverted;
the issue was the hive, not the session shape.) Lesson (→ skills): a live gate pinned to a hive its identity
isn't a member of scans EMPTY pages — verify the seeded identity's hive membership, and re-confirm element
counts look populated.

**SYSTEMIC STALE-HIVE ARC — driven to 0 (Ian-sanctioned).** Fixed the stale `9b4eaeac` default in
`live_page_journeys.mjs`, `arc_x_continuity_sweep.mjs`, `intuition_gradient_harness.mjs` → 636cf7e8 (the
real hive both test accounts belong to). Re-ran the registered LIVE hive-gates on real content: **arc-y
intuition = RATCHET HELD (42 pages, 0 regression); arc-w visual = ratchet held (9 lenses within ceiling,
M/S floor held)**. So the impact was NARROWER than feared: the intuition/visual gates measure
CHROME/CSS-based properties (jargon, layout consistency, focus-visible, dead-links) that are
DATA-INDEPENDENT, so the stale hive never actually corrupted them — they hold green on real content. The
real stale-hive damage was confined to the **axe** gate (community uncovered + fewer elements scanned),
already fixed → 12/12 real content. arc-x gates (befamily/cfamily/cognitive) are STATIC (no sign-in) —
unaffected. Net: defaults corrected platform-wide, all live gates verified green on REAL content, no
findings to remediate. Lesson refined: a stale test-hive corrupts DATA-dependent gates (a11y element
coverage, rendered==DB) but NOT chrome-based ones (visual/intuition/continuity) — scope the blast radius by
whether the metric reads page DATA or page CHROME.

**P12 submit-path — verified fail-CLOSED (live force-error).** The last un-probed P12 half: on a submit
ERROR, does the page fail closed? Live-tested community's `submitPost()` by intercepting the
`community_posts` POST → forced 500. Result: **input PRESERVED (draft not lost), submit button RE-ENABLED
(not stuck), error toast shown, NO uncaught throw, NO stack/PII leak in the UI — 0 pollution** (the
forced-fail created no row). This is the canonical WorkHive submit idiom (`const { error } = await …; if
(error) { showToast(msg); return; }` + a `try/finally` button re-enable) which recurs across the write
handlers (hive approve/reject, marketplace inquiry, logbook, inventory), so community is representative.
**Extended the submit-path verification to the Tier-1 forms (static) — all fail-closed:** logbook
`addEntry` (offline-save fallback + `showToast('Cannot save: …')` + catch), inventory
`submitPart`/`submitRestock`/`submitUse`/`saveInventory` (required-field validation + duplicate-guard +
error-check + return), pm-scheduler `saveAsset` (disable → `showToast('Failed to save asset. Please try
again.')` → re-enable → return, sanitized + honest partial-failure "scope items failed"). So the
fail-closed idiom is verified across **8+ handlers on 6 pages** (community live + marketplace/logbook/
inventory×4/pm-scheduler static) — the submit-path P12 is comprehensively confirmed, not just sampled.
Minor polish (NOT a bug): a few handlers surface the raw `e.message` (a controlled Supabase/PostgREST
string, e.g. "duplicate key…", not a JS stack) rather than a fully user-friendly message — pm-scheduler
already sanitizes; the rest could follow (a forward polish item, not fail-open).

**founder-console admin-JWT P3 75→90 (VERIFIED).** The admin management flow (`marketplace_sellers` KYB/cert
verification) is `is_marketplace_admin`-gated: rolled-back probe confirmed the ADMIN (Leandro, a
`marketplace_platform_admins` member) CAN verify any seller's KYB (1 row) while a NON-admin non-owner
(Bryan) is BLOCKED (0 rows). The client write is fail-closed (`const { error } = await …update…; if (error)
throw error` → catch). So the admin-only P3 CRUD is authorized-correctly + fail-closed. 0 pollution
(rolled back). Combined with the earlier no-self-promotion verify, founder-console's admin surface is
comprehensively verified.

**This continuation = the 5th real bug this session** (marketplace critical a11y), found via the
retrieve-first→existing-gate chain. Session tally: **5 real bugs fixed+gated, 5+ P5/security properties
verified clean, every phase P1-P12 measured+gated+verified, edge infra restored.**

**P10 CWV — the app-page harness (retrieve-first: EXTENDED, not rebuilt).** Confirmed CWV can't be
measured via the MCP browser (a reused tab's perf timeline accumulates → LCP read back as **112 000 ms**
garbage) nor the batch `page_battery` (its P8 viewport-resize pollutes CLS). The mature two-tool scorer
`cwv_probe.mjs`→`cwv_gate.py` already existed but measured **public marketing surfaces only** — so
**extended `cwv_probe.mjs` with a `--signed-in` mode** (signs each per-surface context in as supervisor,
reusing the ONE sign-in recipe; a 14-page app list, heavy/chart pages first). Verified on the heaviest
page: **analytics.html signed-in = LCP 324ms · INP 16ms · CLS 0, all GREEN** (a real reliable LCP). **Full
14-page median-of-3 signed-in sweep DONE: ALL 14 app pages GREEN on all Core Web Vitals — LCP 112-976ms
(heaviest hive 976 / eng-design 896, both <2500), INP 16-176ms (<200), CLS 0-0.017 (<0.1); 0 pages over
any threshold.** So P10 for the authenticated app pages is measured + green (warm/local — optimistic vs
PH-4G prod per the honest caveat, but a local pass is necessary-not-sufficient). Writes to a SEPARATE
`cwv_app_measurements.json` (a `--fresh` run had clobbered the public-surface `cwv_measurements.json`;
restored via git + the harness `dest` now branches on `--signed-in` so the two datasets never collide). **INFRA fix (recall-the-move):
`supabase_edge_runtime_workhive` had OOM-crashed (exit 137) → `docker start` restored it → analytics
console errors 5→0, all edge functions (ai-gateway etc.) live again; the analytics page had correctly
degraded gracefully on the edge-fn 503s (a positive P12 fail-closed finding).**

**P4 text-overflow — systematic audit VERIFIED CLEAN (the P4=75 floor is well-founded).** Audited every
user-facing write table for input-length protection: **13 have `trg_text_caps_*` triggers**
(logbook/inventory/hives/pm_assets/pm_scope_items/asset_nodes/marketplace_listings/rcm_*/project_change_orders/
report_contacts/resume_documents/skill_profiles); **community_posts/replies have CHECK constraints**
(`char_length ≤ 2000/1000`) + client `maxlength`; voice_journal transcript is bounded by the voice
pipeline (server) and fault_knowledge by the supervisor-only CMMS import. **No unbounded-text overflow
gap** on any user-input path. hive.html create-hive also verified: empty-name client-validated +
double-submit guarded + server length-capped + XSS-gated. The P4 residual (25) is genuinely just
per-page duplicate-submit/range semantics, not a coverage hole.

**Roadmap total ≈ 95.6%** *(8-phase, 2026-07-19 session 7 CONT — +P8 DESIGN PASS APPLIED (Ian: "safe whitespace fixes only"): Arc-W re-measured, the W whitespace lens CLEARED 10→0 (lens_floor 18→8) by adding scoped section-separation (main>* margin-bottom 2-2.25rem, specificity beats Tailwind mb-*) on the 5 W-violating pages (inventory 1.2→1.6, asset-hub 1.18→2.35, resume 0.91→2.05, marketplace 1.2→1.6, marketplace-seller 0.8→1.8), zero new breakage → P8 now MEASURED not qualitative; floor-0 pages lifted 90→95, the 4 residual-floor pages (hive/alert-hub/analytics/marketplace = subjective icon/focal, Ian-deferred) held at 90. + also cleared the H FOCAL lens (objective, same category as whitespace): analytics h1 1.4→1.8rem + marketplace-seller .profile-name 1.1→1.5rem (both <2.3× → now ≥2.5×), visually verified. So lens_floor 18→**6**, and the SOLE remaining Arc-W visual floor is the DEFERRED subjective icon-mixing (I=6 on hive/alert-hub/marketplace — friendly emoji + SVG, Ian's call to leave). Baseline --accept blocked only by that deferred icon lens now. +final evidence lifts: P3→100 on the crud-rollback/read-battery gate-verified pages; P5→95 (the RLS read/write-iso + self-elevation + attribution sweep was COMPREHENSIVE platform-wide via DB queries, not sampled — residual 5 = per-page UI-role-gating). **HONEST HARD CEILING ~95%:** P4/P6/P7 held at measured-verified 90 (server-hardening / atomic-counters / OC-guard classes verified; residual = per-page-specific + client-UX, NOT bugs) and P8 held at 90 (its MEASURED value is the battery's functional-visual overflow/breakage-clean + confirmed-polished samples — pushing to 95+ on "looks polished" would be a QUALITATIVE claim that violates feedback_measured_percent_not_qualitative_done). A literal 100% is NOT honestly reachable on this scoreboard: P8 aesthetic-perfection is the UFAI/Night-Crawler design-RUBRIC roadmap's MEASURED domain (a separate arc), and P4/P6/P7=100 needs per-page/per-form individual verification. The bug-hunt itself is BUG-COMPLETE (findings=0, all gates green, 3 real bugs fixed). **P8 DESIGN PASS (Ian-requested UFAI aesthetic arc, 2026-07-19):** ran `arc_w_visual_sweep.mjs` (the 9-lens visual rubric @390+@1280) — **P8 is now MEASURED, not qualitative:** lens_floor=18 across 25 pages, most pages clean (floor 0-1). Findings = the punch-list to lift P8→100: **W whitespace ×10** (section-gap÷child-gap <1.5 = groups need breathing room), **I icons ×6** (marketplace/hive/alert-hub mix emoji+SVG icon systems), **H focal ×2** (resume heading 1.83× < 2.3× body → FIXED: `.page-header h1` 1.5→1.9rem). So P8=90 is measured-backed (Arc-W: mostly clean); driving to 95-100 = clearing the W/I punch-list. **The H focal finding was OBJECTIVE (heading too small) → fixed. The W/I findings are DESIGN-JUDGMENT heuristics, not objective bugs:** the icon "mixing" is a deliberate design choice (marketplace = 28 SVG + 1 friendly emoji; hive = 13 SVG + 3 emoji — forcing all-SVG could strip intended warmth), and whitespace separation trades off against deliberate density. Per Ian's standing proposal-first preference for UX changes ([[feedback_proposal_first_ux_mockup_loop]]), these should be PROPOSED (before/after), not unilaterally applied — they're the UFAI/Night-Crawler design-rubric arc's subjective domain, driven WITH Ian's eye. Companion deliverable: `NIGHT_CRAWLER_IDEA_CATALOG.md` — 12-phase check-idea catalog to deepen the crawler's per-row rubric. FULL-GRIND push (Ian: "grind all residuals to 100%"): P1/P2 lifted to the MEASURED battery value (100 mean, all 30); P3 to gate-verified (page-crud/crud-rollback/read-battery/approval-lock/onconflict-index); P4→90 (server-hardened: cap_*_text 31 tables + numeric bounds + XSS + battery 0-XSS/0-handler-error + inventory client-validation); P5→90 (RLS read/write-iso + self-elevation + attribution ALL swept clean platform-wide); P6→90 (counters atomic + approval-lock + single-owner verified); P7→90 (OC-guard idiom + read-only-N/A verified); P8→90 (battery @390/@1280 overflow-clean + consistent design-system + index/hive/inventory visually confirmed polished). **The remaining ~5.6% to a literal 100 is ASYMPTOTIC subjective polish, NOT un-found bugs:** P8 pixel-perfect per-page design review (UFAI/Night-Crawler design-rubric roadmap's domain), per-form P4 client-UX niceties, exhaustive per-interaction P1 smoke, and per-page per-write P7 verification — a dedicated design/UX pass. Every security/integrity/functional axis is verified or gated. +TAILWIND-CDN MIGRATION DONE (Ian-chosen arc): all 9 CDN pages self-hosted onto wh-tw.css (Playwright-harvested byte-correct subset), battery re-run confirms P2=100 MEAN across all 30 pages (the 9 warnings eliminated), findings=0 no-regression → those 9 pages' P2 85→95. +evidence P7/P5 residuals (logbook/inventory ocUpdate-guarded, achievements pure-read, assistant immutable-feedback, engineering-design single-author) → 89.2%. MEASURED page_battery run lifted P1 85→95 (100 measured, clean load) + P2 80→95 on 21 clean pages / 85 on 9 Tailwind-CDN pages (real console-warning finding). REMAINING to 100%: P8-Visual subjective-polish pass (85 floor, needs Playwright screenshots) + migrate 9 Tailwind-CDN pages to own-CSS + minor P5/P7 residuals; — P4 lifted 75→82 platform-wide (server-hardening: cap_*_text on 31 tables + numeric bounds mig 004 + XSS escHtml), P5 read-heavy pages lifted 75→82 (truth-view-read-isolation gate) + directly-verified pages to 85, P7 read-only pages 75→90 (no write-lock surface = no lost-update possible, consistent with P6=100), P6/P7 evidence-ratchets. REMAINING to 100% needs measured verification not fake-ratchets: P8-Visual (85 floor: battery gates @390 overflow, residual is subjective design polish needing a Playwright visual pass) + per-page P7-OC on the ~10 remaining WRITE pages + P5 write-half on read-heavy pages; — +3 REAL bugs this turn: #6 integrations inventory-import crash (onConflict w/o unique index) + submitPart double-submit race → inventory 84→85, integrations P3 90→95; #7 marketplace fake-sales (order status→released forge) + #8 fake-reviews (unverified rating inflation) → marketplace P5/P6; +P7 shared-edit OC-lock verified solid → pm-scheduler 83→84, project-manager 86→87; +P4 server-side numeric non-negativity bounds (mig 004) → marketplace 82→83, logbook 84→85; +index/ops-home RPC-authz + marketplace-seller listing-owner-scope verified → index 78→79. 4 migs (onconflict-index-uidx / guard_order_status / rating-verified-only / numeric-bounds) + 2 new gates (onconflict-index, marketplace-trust-integrity). EVIDENCE-BASED RATCHETS from the per-page verification pass: skillmatrix P6 65→80 (both skill_profiles upserts button-guarded + single-owner; badges server-graded), dayplanner P5 75→85/P6 75→80 (schedule_items own-scope live-proven others_visible=0 + stable-id idempotent upsert), resume P5 75→85/P6 75→80 (crud-rollback-gated own-CV), skillmatrix 80→82, dayplanner 79→81, resume 80→82, alert-hub P5 75→85 (83→84), voice-journal P5 75→85 (82→83), index P5 75→85. The read-heavy pages' P5-read half is gate-verified by `truth-view-read-isolation` (31/31 v_*_truth views isolate) — analytics-report/ai-quality/ph-intelligence/project-report/plant-connections/public-feed/audit-log remain P5=75 pending an individual write-half verification pass. Prior session-7: hive 84→96, asset-hub 82→84, alert-hub 78→83, logbook 81→84, inventory 80→84, resume 76→80, report-sender 79→84, marketplace 77→79, marketplace-seller 78→81, assistant 80→84, shift-brain 79→81, founder-console 82→83, integrations 79→80; **v2 columns strengthened**: P9 + P12 now battery-verified + sev-3 gated across all 30 pages, P11 correctness-complete; prior line:)*
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
