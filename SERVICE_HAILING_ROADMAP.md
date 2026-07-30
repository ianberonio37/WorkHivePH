# SERVICE HAILING ROADMAP — Evolve the WorkHive Marketplace into a Service-Hailing Platform

_Authored 2026-07-28 from Ian's charter. This is the mission-hub doc — the single source of truth for the service-hailing arc. The §0 scoreboard is updated every phase, forward-only._

> **Ian's charter (2026-07-28):** "I am planning to make my platform as a service-hailing app, like some other ride-hailing app… we will plan to attack it, first by architectural layers, class and dimensions… there is a map then we can see the service provider's location… as a founder, I want to provide vouchers and discount credits… the consumer will have the freedom to register and become a member… I could also have a way to generate income so that I could provide and maintain more the platform… I want only this to be in my GCash number, I am still a startup so any payment apps or any business registration still not feasible right now… we have to maximize and utilize platform pages we have such as community and hive page."

> **Locked directions (Q&A, 2026-07-28):** ① B2B industrial/technical services FIRST, schema consumer-ready (and consumer-common-services considered from day one). ② EVOLVE the existing marketplace — no parallel structure. ③ Providers = BOTH freelance technicians AND hives-as-service-companies. ④ Matching = HYBRID: rate-card instant broadcast/first-accept + post-and-quote for complex jobs.

---

## §0 ⏯ START HERE — Execution Doctrine + Scoreboard

### 0.1 Execution doctrine (how EVERY phase of this arc is driven)

**⭕ Anti-drift compass = the measured-% scoreboard (0.2).** Every % is **verified cells / total cells** (live-proven preferred), never qualitative "done". One metric green ≠ done — done is ALL axes this doc names; denominators only GROW (a short denominator is a false 100%).

**🔁 Momentum drive + Memento.** `.momentum_drive` armed at arc start (stop guard blocks premature turn-ends). Memento is the continuous compass: `memento_retrieve.py` BEFORE every "what's next / is this blocked / should I stop" decision; every sub-unit opens with a topic retrieval; every checkpoint writes the handoff `NEXT:` queue and KEEPS GOING. A "ceiling"/"blocker" may only be claimed after recall-the-move + check-the-machinery + build-the-structure all come up empty (§3d proves the current four gaps are buildable).

**📋 PER-PHASE EXIT CHECKLIST — every phase closes with ALL EIGHT:**
1. **% moved** — scoreboard delta recorded (cells flipped, live-proven), row updated same-turn.
2. **⛩ Gates (anti-regression)** — new/extended validators registered in `run_platform_checks.py` + baselines regenerated; `--fast` GREEN is part of DONE; ratchets forward-only; when a gate reds on a correct fix → teach the gate, don't bend the code.
3. **🧹 Sweeps** — (a) sibling sweep: grep each fix's pattern platform-wide, fix ALL occurrences; (b) registration cascade: new page/fn/table/view/agent registered on every expecting surface (config.toml, LIVE_TOOL_PAGES, nav-hub, tester coverage, seeders); (c) whole-artifact verify: full-page screenshot diff + disposition-map check on every touched page — never viewport-only; (d) touched-surface sweep: escHtml, i18n dict, tokens.css vars, a11y (aria+visible), 44px tap-targets.
4. **🎭 Live proof** — Playwright MCP seed-then-drive on the REAL page as the right persona, measuring the WORKED state (a request mid-lifecycle rendered), every phase — never batched; verify the instrument before the page.
5. **🕷 Night-Crawler in-loop** — runs INSIDE the phase on new/changed surfaces; new dim classes it mints (likely: live-status motion, map affordances, offer-countdown UX) join the rubric denominator immediately.
6. **📚 Skills learned** — cross-skill teach-back table (one lesson → EVERY skill it touches) written in one pass; the arc leaves the whole roster smarter.
7. **🧠 Memento persist** — topic memory + handoff updated (`NEXT:` explicit); one-line MEMORY.md index entries only.
8. **🔒 Local-only** — commit/push/deploy are Ian's standing gates; a completed-but-uncommitted phase PIVOTS to the next local unit, never stops.

**🧭 Standing disciplines:** retrieve-first token economy (substrate/Memento/skills before any re-derivation; all work INLINE, Workflow permanently disabled) · evidence-classification (PASS only on verified evidence) · records-outlive-action audits · **trust-forge guard on every money/reputation transition** · synthesis-is-the-deliverable · skill-first rule (read matching SKILL.md files before each phase's first line of code) · sw.js bump when shell files change · substrate regen after migrations.

### 0.2 Scoreboard (phase × status × measured %) — updated every phase, forward-only

> **The phase table below is ONE axis.** It went green in July while three axes this roadmap also names
> had never been measured at all. "Overall" is now computed by **`tools/service_hailing_scoreboard.py`**
> over **six boards**, and the arc is done only when the LOWEST is 100 - a green headline may never mask a
> dead axis again. Re-run it; never hand-edit a number into this file.
>
> | Board | What it measures | Now |
> |---|---|--:|
> | 1 · Journeys | 33 journeys × G/W/O/H/R. **W is DERIVED** from personas × states (>=2 × >=2), never hand-set | **100%** |
> | 2 · UFAI lens | per-surface rubric on the WORKED state (floor 90) | **100%** |
> | 3 · Classes | C1-C11 × build/probe/gate | **100%** |
> | 4 · UFAI **DEEP** | the LIVE checks the coarse lens excludes: measured 44px, axe, 360-1920 overflow | **100%** |
> | 5 · Stack S1-S9 | §1b: layer touched = its checklist applied | **100%** |
> | 6 · Paths | happy / error / degraded per journey (PDDA depth) | **100%** |
> | | **OVERALL (lowest board)** | **100.0%** ✅ |
>
> **And WHICH, not just how much:** `tools/verify_service_hailing_roadmap.py` itemizes **85 concrete
> promises** from this document - every Fuel table, Engine view/RPC, Brain agent, Dashboard surface,
> stack layer, §1c booster, C1-C11 lock, §3 dimension, G1-G4 gap, phase deliverable, D1-D14 decision and
> safety rail - and re-derives each from the **live database, filesystem and gate registry** on every run.
> **85/85 executed.** Both tools are registered in `run_platform_checks.py` as forward-only gates
> (`service-hailing-scoreboard`, `service-roadmap-executed`, `service-ufai-deep`), so a promise that
> stops being true FAILs by name instead of rotting quietly.


| Phase | Scope | Cells (verified/total) | % | Status |
|---|---|---|---|---|
| P0 | Roadmap + R-track (R1–R3) + jobs-section disposition map | 4/4 (roadmap ✅ · R1 ✅ · R2 ✅ · disposition ✅ §3e) | 100% | ✅ DONE (gate-green: 552 PASS + substrate rebuilt→PASS) |
| P1 | Fuel: 9 tables + guards + RLS + PostGIS enable + seeders | 6/6 (mig ✅ · adversarial 15/15 ✅ · seeder ✅ · substrate ✅ · RLS gates ✅ · **FROZEN suite ✅ 548 PASS, residuals reconciled to green; only the documented pyapi-quirk pair remains**) | **100%** | ✅ DONE |
| P2 | Engine: views + RPCs (atomic accept under race) | 8/8 (mig ✅ · 4 views live-smoked ✅ · accept-race 2-client proof ✅ · quote/select RPCs ✅ · substrate ✅ · **C1 gate 10/10 ✅** · **C3 gate 6/6 ✅** · both registered in run_platform_checks ✅) | 100% | ✅ DONE (full-suite re-run = P1's pending cell, covers both) |
| P3 | Provider side: onboarding + console (+ hive-provider home) | 4/6 (Services tab + onboard ✅ · console feed/toggle/accept/advance ✅ · live E2E walk ✅ `seller-services-console-p3-live.png` · **hive-company registration + skillmatrix bridge ✅ (live: "Register Baguio Textile Mills as a service company")** · **UFAI rubric 100% / 0 page errors ✅** · **hive.html home card ✅ (live: 44px CTA → console; TL dict entries; sw v228 bump — hive is a SHELL file)** · **frozen suite ✅**) | 6/6 · **100%** | ✅ DONE |
| P4 | Client side: hail flow + broadcast matching (+ asset-context + alert CTA) | 7/8 (Services tab+pane ✅ · composers ✅ · tracker/quotes/select/cancel ✅ · **live E2E hail ✅** · **TTL/radius sweep ✅ (mig 42)** · **deep-link landing pad + 9-gate polish ✅ (mig 43)** · **asset-hub + alert-hub CTAs ✅** · **frozen suite ✅**) | 8/8 · **100%** | ✅ DONE |
| P5 | Realtime lifecycle + live tracker + MAP + Web Push + logbook writeback | 7/7 (MapLibre+wh-map ✅ · tracking map LIVE ✅ · watchPosition publisher ✅ · **Web Push COMPLETE ✅: notify-push route E2E green (envelope+trace, anon refused, /health ok with VAPID), send machinery proven against the real FCM push service (VAPID-signed, statusCode classifier live), sw.js v229 push+notificationclick handlers, in-context "Enable job alerts" subscribe card live-rendered** · logbook writeback ✅ · dayplanner hook ✅ · frozen suite ✅) | **100%** | ✅ DONE |
| P6 | Trust: bidirectional reviews + verified counters + settlement records | 6/6 (**bidirectional reviews ✅ mig 46: reuse marketplace_reviews + birth-guard, 7-probe adversarial PASS, rating VIEW-computed (no forgeable counter), listing-review law intact** · **C6 gate extended ✅ 4/4 (+ repaired the rotted legacy fixture: self-minting probes)** · **client settle + commission mint ✅ mig 47: completed→settled client-legal, 5%/10% D9 mint once-only (idempotent, stranger-inert, ledger isolated)** · **review/settle UI hooks ✅ LIVE-PROVEN: "Mark as paid ✓" → settled → −₱300 commission minted (5% on ₱6,000) → 5★ inline rating with comment → provider card shows ★5.00 (1); admin-branch verified-pin fixed live** · C7: settlement truth = ledger row + journal (one money-truth) ✅ · **SECOND DIRECTION SHIPPED + LIVE-PROVEN ✅: seller console "Recently finished" → "Rate client" → 4★ + comment landed as `provider_to_client` with server-pinned attribution; duplicate refused by the unique index; card flips to "✓ You rated this client"** · **🔴 LIVE-CAUGHT EXPLOIT FIXED (mig 53): `is_marketplace_admin()` early-returned BEFORE any party check, so a provider-admin could author the CLIENT's 5★ on its OWN job → self-minted rating/tier. Admin bypass now applies only to NON-parties; C6 gate 5/5 with a teeth-verified self-deal probe** · frozen suite ✅) | 6/6 · **100%** | ✅ DONE |
| P6b | Monetization: credit ledger + GCash verify queue + commission + vouchers + tiers | 6/6 (**commission-on-settle ✅ mig 47** · **debt-gate ✅ mig 48: `provider_credit_balance()` + negative-balance accept block, live-proven (blocked at −150, accepts after +200 topup; cold-start-safe threshold 0, D9 floor Ian-tunable)** · **seller wallet UI ✅ LIVE: balance ₱−200 shown (debt styling), top-up ₱500 + ref filed through the real card → founder verify → trigger minted → balance ₱300 — the WHOLE income loop closed E2E** · **founder GCash queue UI ✅ LIVE on founder-console: pendings listed with provider+ref+filed-time, "Verify: mint credits" → ledger +₱300 confirmed; now reads `v_service_credit_topups_truth` (mig 50), dropping the N+1 directory lookup** · **voucher redeem ✅ mig 49: completion-gated RPC (stranger/double/limits blocked, HAIL10 → 10% of ₱2,000 = ₱200 reimbursed to the provider, 4-probe PASS) + tracker Apply-code UI** · **tiers ✅ truth-view v3 COMPUTED (bronze<10 · silver≥10 · gold≥25∧★4.5 — no forgeable state) + 🥇🥈🥉 chips on the quote view, the console, and the achievements tier card** · **GCash number 09950092416 set (D6)** · frozen suite ✅) | 6/6 · **100%** | ✅ DONE |
| P7 | AI triage agent | 5/5 (**the coach-fold pattern: `service-triage` gateway agent → `marketplace-listing-assist` mode branch (identity-gated + auth-uid rate-limited so the fn's catalogued L6 frontier does NOT widen; server-whitelisted category/urgency/mode from the LIVE catalog) ✅ · gateway registration (agent + STRUCTURED_PASSTHROUGH + mode pin) ✅ · composer "🤖 Suggest" UI with graceful chain-down degrade ✅ · LIVE E2E: "motor tripping, production stopped, burning smell" → critical urgency auto-set + catalog jump, through the ONE front door ✅** · **eval coverage ✅: 3 golden fixtures registered for `service-triage` (industrial-critical / consumer-routine / custom-scope-quote) with the jsonMode `expected_shape`; splits rebuilt (+7 units, 1 into the 🔒locked test set), `ai_asset_version` 1→2, asset baseline re-frozen** · **D13 action rail ✅: `service-triage` added to ADVISORY_ANSWER_AGENTS — it suggests and persists nothing, so a model claiming it filed the request gets that claim stripped** · frozen suite ✅) | 5/5 · **100%** | ✅ DONE |
| P8 | Consumer door: public catalog + hive-less journeys + community/showcase hooks | 6/6 (**anon door LIVE: signed-out visitor gets the services pane + the 6 CONSUMER common services (Aircon ₱800…) + honest sign-in-to-hail prompt ✅** · **segment-aware composer ✅ (hive-less → consumer catalog + segment on inserts; P1's day-one consumer schema meant ZERO migrations here)** · **community liquidity card ✅ (advances the COMMUNITY_DEEP_ARC X-axis: Community↔Marketplace edge)** · **public-feed acquisition CTA + TL dict ✅** · consumer signup = the existing hive-less auth flow (proven) ✅ · frozen suite ✅ · **consumer abuse-stop ✅ (mig 51): hive-less clients have NO hive cap, so the per-USER daily cap is their only ceiling — live-proven, the 51st consumer hail refused**) | 6/6 · **100%** | ✅ DONE |
| P9 | Leverage loops: recurring contracts + parts cross-sell + remaining §1c hooks | 4/4 (**recurring-contract hook ✅: pm-scheduler asset detail "🔧 Hail a specialist" with PM context via the landing pad (reuse, per the PM arc's own reuse discipline; sw v229 covers the SHELL edit)** · **parts cross-sell ✅: provider job card "🔩 Find a part" → parts marketplace** · **deep-link ratchet PASS ✅** · **remaining §1c hooks CLOSED ✅: achievements.html provider-tier card (VIEW-computed tier + next-tier distance + console link, silent for non-providers; live-proven 🥉 Bronze · 2 jobs · 8 more to Silver — and its FIRST version was caught by the truth-view-columns gate reading `auth_uid` from a view that deliberately omits it, which would have rendered nothing forever); inventory parts-gap = ALREADY BUILT (per-part `findOnMarketplace` on every low/out/critical card — my roll-up CTA was REVERTED as duplication, whole-artifact rule); ph-intelligence = data-only-done (rates seeded from PH intel at P1; a benchmarking report with no pricing surface — no panel invented)** · **D14 shipped: tab relabelled "Jobs"→"Hiring" (live: Parts · Training · Hiring · Services)** · frozen suite ✅) | 4/4 · **100%** | ✅ DONE |

Per-phase cell denominators are fixed when the phase OPENS (its journeys × personas × states from §3 + its §3b UFAI surface rows); "—" = not yet enumerated (never counted as done).

**NEXT:** P1 Fuel — migrations (9 `service_*` tables + PostGIS enable + state-machine guards + realtime publication lines + RLS) → `seeders/services.py` (both segments, PH coordinates) → substrate regen → P2 Engine.

---

## §1 ARCHITECTURAL LAYERS (Fuel / Engine / Brain / Dashboard / Driver)

### FUEL — new tables (all: RLS + seeder + capture contract + substrate regen)

| Table | Purpose | Key columns |
|---|---|---|
| `service_catalog` | Platform rate card (enables instant mode) | segment `industrial\|consumer`, category, unit `per_visit\|per_hour`, base_rate, active. **Seeded from P1 with BOTH segments** — industrial (electrical, HVAC, mechanical, calibration, generator PM, welding…) AND common consumer services (aircon cleaning, plumbing, electrical repair, appliance repair…) so every schema/matching decision is proven against both; consumer rows sit behind the flag until P8 |
| `service_providers` | Provider registry, both types | provider_type `freelancer\|hive`, auth_uid/worker_name OR hive_id, categories[], service_areas[] (PH city/region), `base_location geography(POINT)` + `live_location geography(POINT)` with generated lat/lng (`st_y/st_x … stored`), availability `online\|offline\|on_job` (**trigger-managed**: job start → on_job, settled → online), verification status, links to resume/skillmatrix |
| `service_requests` | The hail | client (hive_id + worker attribution; NULLABLE hive for consumer), mode `instant\|quote`, catalog_item_id OR custom scope, address text + `location geography(POINT)` (pin-drop, no geocoder), urgency, budget, **status state machine**, per-state timestamps |
| `service_offers` | Accepts + quotes | request_id, provider_id, kind `accept\|quote`, price, eta, message, status `pending\|selected\|declined\|withdrawn\|expired` |
| `service_job_events` | Append-only transition timeline | request_id, actor, from_state→to_state, at — records that outlive the action |
| `service_credit_ledger` | **Append-only money ledger** (founder-income engine) | account (provider/consumer identity), entry_type `topup\|commission\|voucher_grant\|voucher_reimburse\|adjustment`, amount ₱, ref — **balance = SUM(ledger), never a client-writable column** |
| `service_credit_topups` | GCash P2P top-up verification | payer identity, amount, GCash 13-digit reference no, status `pending_verification → verified\|rejected` — verified ONLY by founder/admin; verification mints the ledger entry |
| `service_vouchers` | Founder-minted discount vouchers | code, kind `percent\|fixed`, value, segment, max_uses, per_user_limit, expiry, active |
| `service_voucher_redemptions` | Redemption records | voucher_id, request_id, consumer identity, amount — redeemable ONLY on verified completion |

**Reused, not duplicated:** `marketplace_reviews` (extend: request_id + bidirectional direction), `marketplace_disputes`, `marketplace_orders` (record-only settlement), `marketplace_sellers` trust columns, Supabase storage (job-proof photos).

**State machine** (DB-enforced transition-guard trigger, same pattern as `guard_marketplace_order_status`):
`requested → broadcasting → accepted → en_route → on_site → in_progress → completed → settled`
branches: `cancelled_by_client` · `cancelled_by_provider` · `expired` · `disputed`.

### ENGINE — canonical views + RPCs (Dashboard NEVER reads Fuel raw)
- `v_service_provider_truth` — provider + verified skills + live trust + availability
- `v_service_request_truth` — request + state + matched provider + offer rollup
- `v_service_open_broadcasts` — a provider's feed (category/area/radius-scoped)
- `find_providers(request)` — `st_dwithin(request.location, provider.location, radius)` + ORDER BY `location <-> origin`, filtered `online` + category (the Supabase Uber-clone reference pattern)
- RPCs: `accept_service_request()` (**atomic first-accept-wins**; optimistic-concurrency; 0-row = lost race surfaced honestly) · `submit_service_quote()` · `select_quote()` · `advance_job_state()` (guarded transitions only) · `complete_job()` (the ONLY path that moves trust counters + commission)

### BRAIN — AI (free-tier chain only, via ai-gateway)
- Request triage agent: "describe the problem" → suggested category/urgency/mode
- Later: skill-matrix-aware provider ranking · self-dealing anomaly watch

### DASHBOARD — evolve, don't fork (disposition map BEFORE touching marketplace.html)
- `marketplace.html` — client hail flow (catalog→instant, custom→quote) + my-requests live tracker
- `marketplace-seller.html` — provider console: availability toggle, broadcast feed (Realtime), quote composer, job state advancer, **credit wallet** (balance, top-up instructions + ref-no form, commission history, min-balance warning)
- `marketplace-admin.html` — provider-verification queue + dispute additions
- `founder-console.html` — **GCash top-up verification queue** + voucher minting + income/allocation-rate tiles
- `skillmatrix.html`/`resume.html` — "become a provider" bridge

### DRIVER — personas
client-supervisor · client-worker · freelancer-provider · hive-provider-dispatcher · platform-admin/founder · **consumer** (household client hailing COMMON services — individual Supabase account, NO hive membership; the hive-less identity is the hardest tenancy case, so it's designed at P1, not bolted on at P8).

---

## §1b STACK ARCHITECTURAL LAYERS (what the arc touches at each; layer touched = its checklist applied)

| # | Stack layer | Exists | Arc adds/touches |
|---|---|---|---|
| S1 | UI: static HTML + vanilla JS (no build step, no TS inline), tokens.css/components.css, utils.js helpers (`whListSkeleton`/`whListError`/`whFmtPeso`/`wireDetailToggle`), escHtml, nav-hub | ✅ | All new surfaces from these primitives — no new framework, no bespoke skeleton/formatter |
| S2 | PWA/offline: sw.js versioned shell, offline-fallback, Y1b queue | ✅ | sw.js bump on shell change; offline posture: request DRAFTS may queue; provider accept requires online (stated) |
| S3 | Data access: `getDb()` singleton, reads via `v_*_truth` only, auth_uid on writes | ✅ | New `v_service_*_truth` views are the only read path |
| S4 | DB: local Supabase Postgres, migrations, RLS, guards, RPCs | ✅ 400 migs | 9 tables + PostGIS enable + state-machine guards + atomic-accept RPC |
| S5 | Edge functions (57; ai-gateway front door, hive_id-injection guard) | ✅ | Triage as an ai-gateway agent; `notify-push` VAPID sender (G3) |
| S6 | Realtime (rtConn + 12 channel pages, presence) | ✅ | Broadcast feed, live tracker, availability presence, location stream — heaviest new use; two-context live tests |
| S7 | AI chain (free-tier only) | ✅ | Triage registration + eval coverage |
| S8 | Test/gate harness (seeder :5000, 137+ gates, Playwright MCP, UFAI instruments) | ✅ | `seeders/services.py` + 3 new validators + registration cascade |
| S9 | Knowledge: substrate/, Memento, skills | ✅ | Substrate regen after each migration phase; arc topic memory; teach-backs |

---

## §1c PLATFORM LEVERAGE MAP (existing pages as arc BOOSTERS)

External models: **Uber Pro** (points from completed trips + acceptance + low cancels + rating ≥4.85 → Gold/Platinum/Diamond → priority matching + earnings boost) and **Grab Academy** (training/certification for 5-star service). Both map 1:1 onto engines WorkHive already runs:

| Existing engine (verified) | Booster role | Phase |
|---|---|---|
| `achievements.html` + achievement_definitions/xp_log (XP per skill domain, leaderboard, level-up) | **Provider Tiers (Uber-Pro model)**: points from VERIFIED completions + acceptance + rating → tiers → perks (broadcast-ranking priority, commission discount, badge). Verified events only — trust-forge class | P6b |
| `skillmatrix.html` + `skill_exam_keys` (certification exams exist) | **Provider Academy (Grab model)**: certified skills gate premium categories; "Certified" badge; SOP library as training content | P3, P6b |
| `community.html` (posts, XP profiles, leaderboard) | **Liquidity engine**: provider Q&A, recommendation threads, top-provider leaderboard | P8 |
| `public-feed.html` (public posts surface) | **Showcase + SEO acquisition**: consented job-completion stories, provider highlights | P8 |
| `hive.html` | **Hive-provider dispatch home** for the company-provider persona | P3 |
| `asset-hub.html` | **Industrial moat #1 — asset-context hail**: request pre-filled with nameplate/history/failure signatures | P4 |
| `logbook.html` | **Industrial moat #2 — job→history writeback**: completed job writes a logbook entry on the client's asset | P5 |
| `alert-hub.html`/`shift-brain.html` | **Demand trigger**: "Hail a specialist" CTA on critical alert/risk cards → pre-filled request | P4 |
| `inventory.html` + marketplace parts | **Cross-sell**: job's parts-gap links to parts listings | P5+ |
| `pm-scheduler.html` (frequency engine) | **Recurring service contracts** (Urban-Company-plans analog): plans auto-hail on schedule | P9 |
| `dayplanner.html` (schedule_items) | **Provider availability calendar**: accepted jobs land on the day plan | P5 |
| `ph-intelligence.html` | **Rate-card calibration** from PH market intel | P1 seed |

**Verdict:** the growth loops are configuration + wiring of engines we already run; the industrial moat (asset-context + history writeback) is unique to us.

---

## §2 CLASSES (lockable work classes — each ends with a named gate)

| Class | Scope | Lock |
|---|---|---|
| C1 State-machine integrity | migrations, transition-guard triggers | NEW `validate_service_state_machine.py` (illegal transition = FAIL, live rolled-back) |
| C2 Isolation & attribution | RLS (client sees own; provider sees own + in-scope broadcasts; consumer hive-less), auth_uid on every write | extend RLS/substrate gates |
| C3 Matching & dispatch | broadcast scoping, atomic accept, quote select, TTL + radius expansion | NEW `validate_service_dispatch_isolation.py` (cross-area/category leak = FAIL; accept race = exactly one winner) |
| C4 Realtime + Push | subscriptions, listener cleanup, presence, **Web Push job-offer delivery (G3)** | two-context live test; push round-trip proven locally |
| C5 UI surfaces | mobile-first hail/console/tracker; empty/loading/error via shared helpers | UFAI battery + axe ratchet + existing gates |
| C6 Trust lifecycle | provider verification, bidirectional reviews, counters move ONLY on verified `completed→settled` | extend `validate_marketplace_trust_integrity.py` |
| C7 Settlement records | order record (cash/GCash ref) | reuse order-guard pattern |
| C8 AI assists | triage agent | ai-eval coverage gates |
| C9 Seed + registration | every table seeded (`seeders/services.py`); registration cascade | registration checklist |
| C10 Map & live location | vendored Leaflet + OpenFreeMap tiles (CSP entry), `wh-map` module (marker/bearing/stream-follow), `live_location` published ONLY during active job, trigger-managed availability | NEW two-context live test: client sees marker move; location NOT readable when idle (RLS) |
| C11 Monetization & credits | prepaid credit wallet (Grab-PH-driver model), commission-in-credits on verified completion, min-balance to accept, GCash verify queue, vouchers, membership, tiers | NEW `validate_credit_ledger_integrity.py`: balance≡SUM(ledger) live; NO client-writable path moves credits (founder/service-role/GUC only); voucher redemption requires verified completion |

---

## §3 DIMENSIONS (the measured-% axes)

- **D-J Journeys (×persona):** hail-instant · hail-quote · provider-onboard(freelancer) · provider-onboard(hive) · accept-race · quote-select · job-run(full state walk) · complete+review(bidirectional) · cancel-client · cancel-provider · expire · dispute · topup+verify(GCash) · commission-deduct · min-balance-block · voucher-mint(founder) · voucher-redeem · consumer-register · tier-progress · certified-skill-gate · asset-context-hail · alert-to-hail · job-to-logbook-writeback · recurring-contract-auto-hail
- **D-P Personas:** the 6 (§1 Driver list, consumer included)
- **D-S States:** every state-machine node reachable + every surface's empty/loading/error state
- **D-M Modes:** instant | quote
- **D-Geo:** proximity-match correctness (in-radius found / out-of-radius excluded) · live-map tracking during active job · location privacy when idle — each live-proven
- **D-G Segments:** industrial | consumer-common-services — BOTH in the denominator from the start; consumer UI door opens P8

## §3b UFAI / UI / UX RUBRIC — full lens from day one

- **4 pillars → 25 sub-layers** (`tools/ufai_pillar_map.py`, COMPREHENSIVE_STUDY_FULLSTACK_GATE §13.20): U1–U7 · F1–F6 · A1–A6 · I1–I6.
- **89-dim A–Z lens** (`family_rubric_scoreboard.json`) measures U/A; gates own F/I behavioural sub-layers — §2's new validators register so the pillar map credits them.
- Explicitly in scope on new surfaces: C5 APCA, U2/U3 44px tap targets, Z1/Z2 mobile-fit/reflow, N1 i18n, E2 empty/loading/error, I1 CWV/CLS late-reserve, V1 layout harmony, Y1 offline, aria+visible pairing, silence-is-golden chrome.
- Instruments reused, never hand-rolled: `family_rubric_sweep.mjs --page <p>` · `ufai_pillar_map.py` · `ufai_battery.js` · axe ratchet · **Night-Crawler in-loop** (expected to mint new classes: live-status motion, map affordances, offer-countdown).
- Measured on the **WORKED state** (seeded request mid-lifecycle), never an empty shell.
- Scoreboard carries **UFAI % per surface** alongside journey %; new surfaces enter at family mean or better.

## §3c R-TRACK — external idea-mining + SYNTHESIS (design verdicts)

**Sources probed (2026-07-28 planning pass):** Supabase first-party Uber clone (schema/RPC/stream/trigger reference) · phamhieu/supabase-realtime-map (Realtime+Leaflet) · Supabase MapLibre location blog · Uber DISCO (highscalability) · Grab allocation + matching-factors articles · fatbit/rigby/raftlabs/sharetribe marketplace guides · Uber Pro · Grab Academy · Grab PH driver wallet · marketplace-monetization surveys. (GitHub MCP token = bad credentials; raw-URL fetches route around it.)

**Design verdicts (v1, tunable in §5):**
1. **Matching = broadcast + first-accept** to qualified set (category ∩ `st_dwithin`, N≈10 nearest by `<->`). Upgrade path: ranking score from Grab's factor list (proximity, capability fit, rating, acceptance tendency, familiarity) — maps 1:1 onto skill matrix + trust data we already hold.
2. **Offer TTL ~90s** → radius expansion 3km→6km→area-wide → after N rounds offer quote-mode/notify. Expiry via the internal TTL-sweep migration pattern.
3. **Geo = PostGIS** (`geography(POINT)` + GiST + `st_dwithin`/`<->`), not geohashes.
4. **North-star ops metrics:** allocation rate · time-to-accept · completion rate (KPI-registry tiles).
5. **Map = vendored Leaflet + OpenFreeMap tiles** (OSMF tiles are best-effort and revocable for commercial use); CSP tile-host entry.
6. **Monetization = prepaid provider credit wallet + commission-in-credits** on verified completion + **min-balance to accept** (Grab PH ₱100 precedent). Opening rates (Ian tunes): consumer ~10%, industrial B2B ~5%. Quotes FREE early (protect thin supply); Thumbtack-style quote credits later if needed.
7. **GCash-personal-only intake:** P2P to Ian's number + 13-digit ref → founder verification queue → ledger mint. Credits **non-withdrawable** prepaid fees (not stored value — light regulatory posture until business registration; upgrade path: GCash for Business / PayMongo auto-verify).
8. **Vouchers = platform-funded acquisition** (signup/referral); provider reimbursed in credits on verified completion; per-user limits; completion-gated redemption.
9. **Location privacy default:** `live_location` published ONLY during active jobs; idle providers = area-level presence (Ian may veto toward nearby-idle-pins).
10. **No geocoder in v1:** request location = map pin-drop + address text (Nominatim rate limits).

**✅ R1 DONE (2026-07-28) — reference repo deep-mined ([dshukertjr/uber-clone](https://github.com/dshukertjr/uber-clone) `20240625043340_init.sql`, verbatim):** `create extension postgis with schema extensions` · `geography(POINT)` + generated lat/lng · RLS (drivers: authenticated-select-all + own-update; rides: driver-or-passenger only) · **`alter publication supabase_realtime add table …` per table** (without this line `.stream()`/postgres_changes silently yields NOTHING — a silent-zero trap our P1 migrations must include for every streamed table) · availability trigger (`completed → is_available=true`, else false) · `find_driver` is `security definer` (RLS-bypassing — in OUR multi-tenant DB every security-definer RPC must self-guard hive/auth.uid, per the edge-fn injection-guard doctrine). **Two defects we do BETTER than the reference:** (1) `find_driver` has a TOCTOU race — bare `select … limit 1` then `insert`, no locking; two concurrent calls can double-book one driver → our `accept_service_request()` uses a status-guarded transition (`UPDATE … WHERE status='broadcasting'` + row-count check / `FOR UPDATE SKIP LOCKED`) so the race has exactly one winner; (2) the reference creates NO GiST index on `location` — ours does (G1 verdict).

**✅ R2 DONE (2026-07-28) — Night-Crawler harvest:** 9 chunks minted + indexed: `external-service-hailing-{supabase-uber-clone-reference, realtime-location-map, postgis-geo-queries, osm-tile-policy, web-push-vapid, grab-matching-factors, uber-dispatch-architecture, marketplace-monetization, provider-tiers-uber-pro}.md`.

**Remaining R-track:** R3 final numbers (radius/TTL) confirmed at P1/P4 build time against live seeded distances.

## §3d CAPABILITY GAP ANALYSIS (HAVE vs BUILD)

**HAVE (reuse, never reinvent):** Realtime (rtConn + 12 pages) · storage (marketplace uploads) · auth incl. hive-less · i18n (Tagalog live) · PWA/sw.js + offline queue · seeder/gate harness · skill matrix + resume · trust guards + seller verification · TTL-expiry pattern · in-app notification center · design tokens + wh* helpers · edge-fn + AI chain · founder-console.

**GAPS (all four verified greenfield — zero hits in 400 migrations/all pages; each = "build the structure", none a ceiling):**

| Gap | Verdict | Build |
|---|---|---|
| G1 PostGIS | enable ext; `geography(POINT)` + GiST; ALWAYS `st_dwithin` (index-assisted) never ST_Distance-in-WHERE; meters | PostGIS migration + geo cols + `find_providers` + PH-coordinate seeder fixtures |
| G2 Map+tiles | **MapLibre GL vendored** (D12 amendment: OpenFreeMap serves VECTOR tiles — Leaflet can't consume them without a plugin; the Supabase reference is MapLibre); **OpenFreeMap** styles (free, no limits) NOT osm.org (revocable) | ✅ BUILT (P5): `maplibre-gl.js/.css` 4.7.1 vendored + shared `wh-map.js` (create/marker/follow, honest offline degrade) + CSP note in D12 |
| G3 Web Push | without push a provider must keep a tab open — hailing FAILS on mobile. VAPID keypair (private in .env/edge secrets), `pushManager.subscribe({userVisibleOnly:true,…})`, sw.js `push`→`showNotification`, edge-fn sender, dead-subscription cleanup, secure-origin (localhost OK for dev) | `push_subscriptions` table + RLS · `notify-push` edge fn · sw.js push+click handlers · in-context permission ask (never on load) |
| G4 Geolocation | `watchPosition` ONLY during active job; `enableHighAccuracy` only en-route; `maximumAge` + ~10–15s throttle; visible stop-tracking affordance | provider location publisher (throttled live_location updates) + client pin-drop picker on wh-map |

---

## §3e P0 DISPOSITION MAP — marketplace.html, live-walked 2026-07-28 (baseline screenshot `marketplace-jobs-tab-p0-baseline.png`)

**★Disposition-changing finding:** the Jobs tab's 6 live cards are **EMPLOYMENT postings** ("Maintenance Supervisor — F&B Plant", "Mechanical Fitter — Pump Shop"; role + city badges) — hiring classifieds, a genuinely DIFFERENT job-to-be-done than hailing a service. The earlier "jobs → MERGE into quote-mode" assumption is **corrected**: employment listings stay; service-hailing enters as its own section. Second find: a **`sheet-rfq` "Request Quotes" composer already exists** (compare-bar → send one message to N selected sellers; fields name/contact/message) — the structural ancestor of quote-mode.

| Element (live) | Disposition |
|---|---|
| Section tabs `parts / training / jobs` | KEEP + **ADD 4th tab `services`** = the hail flow (client side, P4) |
| Jobs tab employment cards (6) | **KEEP as hiring classifieds; RELABEL tab "Jobs" → "Hiring"** to kill the same-word-two-meanings clash with service jobs (T1 lesson class) — label is Ian's call (§5 D14) |
| `sheet-post` (post listing; sections parts/training/jobs) | KEEP (posts employment/parts/training listings); `fab-post` gains a "Request a service" entry routing to the hail composer |
| `sheet-rfq` Request-Quotes composer + `compare-bar` | **MOVE/EXTEND**: the multi-recipient quote-request pattern becomes the quote-mode composer against PROVIDERS (reuse form + selection pattern); compare-bar later extends to provider compare |
| `sheet-detail`, `sheet-inquiry` | KEEP; inquiry pattern informs offer/quote replies |
| `sheet-saved-searches`, `sheet-watchlist` | KEEP; extend to service categories later (P9) |
| `search-input` filter | KEEP; services tab gets category/area filters |
| Shared chrome (`wh-conn-chip`, `wh-hub`, `wh-ai-widget`, `wh-wayfinding`, voice overlay, feedback fab, skip-link, aurora, toast) | KEEP untouched |
| NEW (P4/P5): services tab content — catalog picker, pin-drop map, my-requests live tracker | ADD |

No DELETEs — the page's existing jobs are a coherent distinct surface; the redesign is ADD + RELABEL + EXTEND, which is why nothing ships duplicated.

## §4 PHASED ATTACK (one at a time; every phase clears the §0 eight-point checklist; all LOCAL — commit is Ian's gate)

- **P0** ✅roadmap · R1 repo deep-mine · R2 Night-Crawler harvest · R3 verdict finalization · **disposition map** of marketplace.html's jobs section (KEEP/MOVE/MERGE/DELETE every element; jobs listings expected → MERGE into quote-mode)
- **P1** Fuel: migrations (9 tables + PostGIS enable + state-machine guards + RLS) + `seeders/services.py` (both segments, PH coordinates) + substrate regen
- **P2** Engine: views + RPCs; atomic accept proven under a live race (rolled-back psql two-client test)
- **P3** Provider side: onboarding (resume/skillmatrix bridge, certification gate) + provider console + hive-provider home on hive.html
- **P4** Client side: hail flow (instant + quote) + broadcast matching + TTL/radius expansion + asset-context hail + alert-hub CTA
- **P5** Realtime job lifecycle + live tracker + **MAP** (C10) + **Web Push** (G3) + logbook writeback + dayplanner calendar hook
- **P6** Trust: bidirectional reviews + verified-only counters + settlement records
- **P6b** Monetization (C11): credit ledger + GCash verify queue + commission-on-completion + min-balance gate + vouchers + consumer membership + provider tiers on the achievements engine
- **P7** AI triage agent (ai-gateway, free-tier chain, eval coverage)
- **P8** Consumer door: public common-services catalog + hive-less journeys + onboarding + community/public-feed hooks — schema already consumer-proven (P1), so this is a UI/journey phase
- **P9** Leverage loops: recurring contracts (pm-scheduler engine) + parts cross-sell + remaining §1c hooks

---

## §4b SYSTEM-ARCHITECTURE EXPANSION — Arc II (P10–P13), opened 2026-07-29

**Why this section exists.** Ian: *"we have to do more research for the system design and system architecture
of this roadmap so that we can improve the tech full stack of this marketplace."* P0–P9 built the arc's
**features**; this section hardens its **architecture**. The research was done retrieve-first: the bag already
held 9 service-hailing chunks (dispatch, matching, tiers, geo, push, monetization) but **156 external chunks
contained nothing on distributed-systems patterns** — so 10 NEW sources were harvested with
`tools/night_crawler.py` (crawl once → ~1KB distilled chunk → Memento retrieves forever, 0 re-crawl tokens).
GitHub MCP still returns `Bad credentials`, so repo reverse-engineering went through the crawler instead
(Sharetribe's transaction process, Medusa attempted, Supabase Realtime internals) — the D3 local-substitute rule.

### §4b.1 SYNTHESIS — every pattern judged against what we ACTUALLY run (not a link dump)

| # | Pattern (source chunk) | What WorkHive already has | The real gap it exposes | **Verdict** |
|---|---|---|---|---|
| A1 | **Transactional outbox** `external-transactional-outbox-…` | `service_job_events` is already an append-only transition journal — an outbox-SHAPED table | Nothing RELAYS it. Push/notify/credit side-effects fire **inline** with the transition, so a failed notify is silently lost while the state change commits | **ADOPT — highest value.** We have the table; build the relay |
| A2 | **Polling publisher + `FOR UPDATE SKIP LOCKED`** `external-postgres-skip-locked-…` | `pg_cron` sweeps (`sweep_service_broadcasts`) — one sweeper, no per-row claim | The Postgres-native queue: N workers claim disjoint rows, with retry/backoff and a dead-letter, **no new infrastructure** | **ADOPT** — this IS the A1 relay; honors `build_own_minimal_dependencies` |
| A3 | **Saga / compensating transactions** `external-saga-pattern-…` | State machine + guard triggers; `accept_service_request` is atomic in ONE tx | Flows that cannot be one tx: accept → deduct commission credits → push to provider → land on dayplan. If step 3 fails there is no compensation, only a half-done job | **ADOPT (orchestration-lite)** — we are a monolith, not microservices: a `service_saga_steps` table + compensating transitions, NOT a framework |
| A4 | **Idempotency keys** `external-idempotency-keys-…` | Idempotency is already STRUCTURAL in places (partial unique indexes, derived TEXT ids) | PH mobile networks retry constantly. A double-tap on Accept or on a GCash top-up must be provably harmless on EVERY money/dispatch RPC, not just the ones we happened to index | **EXTEND** — formalize an `Idempotency-Key` contract + a gate that every money/dispatch RPC honors it |
| A5 | **Circuit breaker** `external-circuit-breaker-…` | The AI chain has FAILOVER (Groq→Cerebras→Gemini→Mistral) | Failover is not a breaker: we re-attempt a dead provider on every call, burning latency and free-tier quota. Trip after N consecutive failures, half-open probe after a timeout | **ADOPT** — small, cheap, protects the free-tier budget |
| A6 | **CQRS read models** `external-cqrs-read-model-…` | **Already doing it** — `v_*_truth` canonical views are the query side; Dashboard never reads Fuel raw | Validates the existing architecture. The only gap: views compute live, so heavy aggregates (leaderboard, zone heatmap) recompute per request | **VALIDATED** — name it explicitly; MATERIALIZE only the proven-heavy ones |
| A7 | **SLI / SLO / error budget** `external-sli-slo-error-budget-…` | Gates measure CORRECTNESS at a point in time; D9 already names allocation-rate + time-to-accept as north-star metrics | Those metrics were never given **targets or budgets**. A hailing platform lives or dies on time-to-accept; without an SLO nobody can say whether today was acceptable | **ADOPT** — promote the D9 metrics to SLIs with SLOs + an error budget |
| A8 | **H3 hexagonal index** `external-h3-hexagonal-spatial-…` | PostGIS `geography(POINT)` + GiST + `st_dwithin` (3km→6km ladder) | H3 gives O(1) cell bucketing for supply/demand heatmaps and surge zones. But for MATCHING at our scale PostGIS is correct and simpler | **SPLIT VERDICT — deliberately NOT adopting for matching** (over-engineering); adopt only if/when zone analytics need it |
| A9 | **Sharetribe transaction process** `external-sharetribe-transaction-…` | Our state machine + guard triggers; **privileged transitions** exist implicitly (supervisor-only, DEFINER-gated) | They model "who may fire this transition" as **data**, not as logic scattered across triggers. Ours is correct but not enumerable — you cannot ask the DB "who can cancel?" | **PARTIAL ADOPT** — a transition-permission table as the single readable source |
| A10 | **Supabase Realtime internals** `external-supabase-realtime-…` | Channels + presence in use across 12 pages | Realtime is a globally-distributed Elixir cluster with CRDT presence and **`realtime.messages` retained only 3 days** — it is an EPHEMERAL transport, never a durable queue | **CONSTRAINT LEARNED** — independently confirms A1: durability belongs in the outbox, not the channel |

**THE ONE-LINE THESIS.** Today every side-effect of a job transition (notify, deduct credits, land on the
day plan) runs **inline and best-effort**; if any fails, the platform is quietly inconsistent and nothing
retries. A1+A2+A3 convert that into a **durable, retryable, observable pipeline built entirely inside
Postgres** — no broker, no new dependency, no build step. That is the single highest-leverage architectural
change available to this arc, and the P5 realtime finding (payloads honor row-RLS but not column-grants)
already proved the ephemeral channel cannot be trusted with it.

**Explicitly NOT doing** (named so a future session does not "helpfully" add them): no message broker
(Kafka/RabbitMQ), no microservice split, no event sourcing as the system of record, no H3 for matching, no
Temporal/Hystrix dependency. Every pattern above is implemented with tables, triggers, `pg_cron`, and RPCs.

### §4b.2 NEW CLASSES (each ends in a named gate, same rule as §2)

| Class | Scope | Lock |
|---|---|---|
| **C12 Durable side-effects** | `service_outbox` table + `FOR UPDATE SKIP LOCKED` relay + retry/backoff + dead-letter; every transition side-effect moves behind it | NEW `validate_outbox_delivery.py`: a transition with a FAILING consumer must leave a retryable row and NEVER lose it; killing the relay mid-flight loses nothing; a poisoned row lands in the dead-letter, not an infinite loop |
| **C13 Saga integrity** | Multi-step flows declare steps + compensations; a mid-saga failure leaves NO half-state | NEW `validate_saga_compensation.py`: force a failure at each step N and assert steps 1..N-1 were compensated and the job's state is coherent (live, rolled back) |
| **C14 Idempotency contract** | Every money/dispatch RPC accepts and honors an idempotency key | EXTEND the idempotency gate: replay each write RPC twice with the same key and assert exactly one effect (one ledger row, one accept, one topup) |
| **C15 Reliability targets** | D9 metrics become SLIs with SLOs + error budget; breaker on the AI chain | NEW `validate_slo_budget.py`: SLIs computable from live data, each has a numeric SLO, and the breaker trips + recovers under an induced outage |

### §4b.3 NEW DIMENSIONS (added to the §3 denominator — it only ever GROWS)

- **D-R Reliability:** every transition side-effect is durable (outbox-backed) / retried / dead-lettered — measured as *side-effects behind the outbox ÷ total side-effects*.
- **D-I Idempotency:** *money+dispatch RPCs honoring a key ÷ total such RPCs.*
- **D-O Observability:** *D9 metrics with a numeric SLO + live SLI ÷ metrics named.*
- **D-C Compensation:** *multi-step flows with a proven compensation path ÷ multi-step flows.*

### §4b.4 PHASES

- **P10 — Outbox + relay (C12).** `service_outbox` (payload, consumer, attempts, next_attempt_at, dead_letter);
  a `SKIP LOCKED` claim RPC; a `pg_cron` relay; migrate the existing inline side-effects (push, commission
  deduction, dayplan landing) to enqueue instead of fire. Gate + live proof that a dead consumer loses nothing.
- **P11 — Saga + idempotency (C13/C14).** Declare the accept-flow and the topup-verify flow as step lists with
  compensations; add the `Idempotency-Key` contract to money/dispatch RPCs; both gates green.
- **P12 — Reliability + breaker (C15).** Promote allocation-rate / time-to-accept / completion-rate to SLIs with
  SLOs and an error budget, surfaced on the founder console; circuit-breaker the free-tier AI chain.
- **P13 — Read-model performance (A6).** Measure the `v_*_truth` aggregates under seeded load; materialize ONLY
  the ones proven heavy (leaderboard, zone rollups), with a refresh path and a staleness gate. Evidence first —
  no materialization without a measured problem.

### §4b.5 SOURCES HARVESTED THIS PASS (durable in `substrate/external/`, retrievable via Memento — 0 re-crawl)

`transactional-outbox-reliable-event-publishing` · `saga-pattern-long-running-distributed-transactio` ·
`idempotency-keys-safe-api-retries` · `postgres-skip-locked-job-queue-worker-dispatch` ·
`h3-hexagonal-spatial-index-geospatial-partitioni` · `sli-slo-error-budget-reliability-targets` ·
`circuit-breaker-resilience-failing-dependency` · `cqrs-read-model-separation-query-side` ·
`sharetribe-transaction-process-state-machine-mar` · `supabase-realtime-architecture-channels-scaling`

*Not bagged, and why:* the Cloudflare rate-limiting page was **rejected by the crawler's own quality guard**
(79% links, 142 chars of prose) — the instrument refusing a thin distill rather than banking a hollow chunk.
`sre.google`, `nfx.com`, `sarahtavel.com` and `docs.medusajs.com` failed DNS/404 from this host and were
substituted (Google Cloud SRE for SLOs, Vlad Mihalcea for SKIP LOCKED) rather than silently dropped.


### §4b.6 ★CORRECTION TO §4b.1 — the premise was checked before it was built (2026-07-29, same day)

The A1 verdict above was written from the pattern, not from the code, and **the code disagreed on the
specifics.** Before building C12 the actual side-effects were inventoried, and the claim that
"push, commission deduction and dayplan landing fire inline and best-effort" is **false for two of the
three**. Every trigger on `service_requests` — `land_accepted_job_on_dayplan`, `mint_settlement_commission`,
`writeback_service_job_to_logbook`, `sync_provider_availability`, `journal_service_request` — writes
**only to this same database inside the same transaction**:

```sql
select p.proname, prosrc ~* 'http_request|pg_net|net\.http|supabase_functions' as crosses_boundary
from pg_proc p join pg_namespace n on n.oid = p.pronamespace where n.nspname='public';
--  every service_* function ->  crosses_boundary = false
```

So a failure in any of them **rolls the whole transition back**. That is atomic, consistent, and
strictly BETTER than an outbox — routing them through one would add a window of inconsistency that does
not exist today, buy nothing, and cost a moving part. **Verdict: VALIDATED, do not touch** — the same
judgment already applied to CQRS, reached the same way.

**But the check found a REAL defect, and it is the outbox's true justification.** The one effect on this
arc that genuinely crosses a boundary is **Web Push**, and it is **built but never sent**:

- `push_subscriptions` exists, `sw.js` handles `push`, the VAPID keypair is configured, and
  `marketplace-seller.html` subscribes providers in-context.
- **Nothing anywhere invokes `notify-push`.** A repo-wide search returns only the function's own
  definition, `deploy-functions.ps1`, generated registries, and a *comment* at
  `marketplace-seller.html:1404` asserting "notify-push delivers offers tab-closed".
- The function's own docstring already said so plainly: *"Callers are backend: the broadcast fan-out
  (DB webhook/cron, **future**), test harnesses."*

**Impact:** a provider grants notification permission, subscribes, and then receives nothing — the exact
failure G3 existed to prevent ("without this, hailing fails on mobile"). This is the **write-only** class
([[feedback_write_only_index_and_hidden_nav]]): the arc asked who READS a record but never asked who
SENDS this one, and the roadmap counted G3 as delivered on the strength of the subscribe half.

**C12 is therefore RE-SPECIFIED — same build, correct reason:**
the outbox is not a retrofit of the DB triggers (they are already right); it is the **delivery spine for
boundary-crossing effects**, and its first consumer is the push fan-out that is missing today.

1. `service_outbox` — `(id, consumer, payload jsonb, attempts, next_attempt_at, locked_at, dead_letter, created_at)`.
2. **Enqueue in the SAME transaction as the transition** (a plain INSERT — this is what makes the outbox
   correct: the row commits if and only if the state change does).
3. A relay claims work with `FOR UPDATE SKIP LOCKED`, POSTs to `notify-push`
   (`{ provider_ids, title, body, url }`, service-role only), retries with backoff, dead-letters a poison row.
4. Enqueue points: broadcast open → the matched provider set; accept → the client; state advances → the
   counterparty.

**Gate `validate_outbox_delivery.py` must prove**: a transition with a FAILING consumer leaves a
retryable row and loses nothing · killing the relay mid-flight loses nothing · a poison row dead-letters
instead of looping forever · and — the regression that started this — **a provider with a live
subscription actually receives a job offer**, so "built but never called" can never ship green again.

**Method note worth keeping:** the pattern was right, the premise was wrong, and only reading the code
separated them. Same discipline that declined H3 — and the same discipline that this section had to turn
on its own first draft.

### §4b.7 C13 DISPOSITION — saga compensation is DECLINED, with the evidence that killed it (2026-07-29)

C12 established the habit that pays: **check the premise before building.** Applied to C13, the premise
does not survive. A saga exists to repair a flow that CANNOT be one transaction — step 3 fails after
steps 1–2 already committed, so you compensate. **This arc has no such flow.**

**What was actually measured (not assumed):**

1. **Every DB side-effect is same-transaction.** All triggers on `service_requests` —
   `land_accepted_job_on_dayplan`, `mint_settlement_commission`, `writeback_service_job_to_logbook`,
   `sync_provider_availability`, `journal_service_request` — write only to this database, in the
   caller's transaction (`prosrc !~ http_request|pg_net|net.http|supabase_functions` for **every**
   `service_*` function). A failure at any step rolls the whole transition back. There is nothing left
   half-done for a compensation to undo.
2. **Every client write is a SINGLE operation.** A sweep of `marketplace.html`,
   `marketplace-seller.html` and `founder-console.html` for any handler issuing two writes found
   **zero** on the service path. Hail creation is one INSERT with `status='broadcasting'` set inline
   (not insert-then-promote); `svcQuote` is one RPC (`submit_service_quote`); `svcAdvance` is one
   UPDATE; provider registration is one INSERT; a top-up is one INSERT whose verification mints the
   ledger through a same-transaction trigger. The earlier "two writes nearby" hits were the *next
   function* in the file, not a sequence inside one handler.
3. **The money path is the one that would hurt, and it is atomic.** Commission on completion and
   top-up→ledger both move through triggers inside the originating transaction — precisely so that a
   partial money movement is impossible.
4. **The outbox IS multi-transaction (enqueue → drain → reconcile) — and compensation is the WRONG
   pattern for it.** Its failure mode is "not yet delivered", repaired by idempotent retry with
   backoff and a dead-letter, which C12 already ships and gates. A push that HAS been delivered cannot
   be un-sent, and should not be: the correct semantics for a stale offer is that accepting it loses
   the race (`accept_service_request` is atomic first-accept-wins), not that the notification is
   retracted.

**Verdict: DECLINED — no subject.** Building a `service_saga_steps` table and compensating transitions
here would add machinery, a new failure surface, and a gate asserting an invariant that the database
already guarantees for free. That is the same judgment already recorded for **CQRS** (we are already
doing it) and **H3** (over-engineering at our scale) — the third refusal in this section, and the most
reassuring one, because it says the architecture was already right where it counts.

**Not silently dropped.** C13 stays in the Arc II denominator as **exempt with a printed reason**, the
same discipline the journey board uses for `w_exempt` — a resolved cell must show *why*, so nobody can
shrink a denominator to flatter a score ([[feedback_short_denominator_is_a_false_100]]).

**What WOULD reopen it** (stated now so a future session does not re-litigate from scratch): any flow
that commits step 1 and then performs an effect the database cannot roll back — a real payment capture,
an SMS/email send, or a write into a third-party CMMS. The moment one of those lands, C13 is live again
and the outbox is its transport.

## §5 DECISIONS LOG (Ian's dispositions + standing assumptions — vetoable rows explicitly marked)

| # | Decision | Source | Status |
|---|---|---|---|
| D1 | B2B industrial first; consumer-common-services considered from day one, UI door at P8 | Ian Q&A + follow-up | LOCKED |
| D2 | Evolve the marketplace (no parallel structure) | Ian Q&A | LOCKED |
| D3 | Providers = freelancers AND hive-companies | Ian Q&A | LOCKED |
| D4 | Hybrid matching (instant broadcast + quotes) | Ian Q&A | LOCKED |
| D5 | Live provider map is in scope from the start | Ian mid-plan | LOCKED |
| D6 | Founder income = prepaid credits + commission-in-credits; GCash personal number ONLY (**09950092416**, set in the wallet card 2026-07-29); manual founder verification; credits non-withdrawable | Ian (startup constraint) | LOCKED |
| D7 | Consumer registration free; vouchers/discount credits as acquisition | Ian | LOCKED |
| D8 | Location privacy: live pin only during active job; idle = area presence | assumption | Ian may veto |
| D9 | Opening commission: consumer ~10%, industrial ~5%; offer TTL ~90s; radius 3→6km→area | synthesis | Ian tunes |
| D10 | Naming: "Services / Hail a Service" placeholder | assumption | Ian names brand |
| D11 | `service_*` table prefix (marketplace-adjacent family) | assumption | standing |
| D12 | Map = **vendored MapLibre GL 4.7.1** + OpenFreeMap vector styles; CSP allowance for tiles.openfreemap.org. (AMENDED at P5 build: OpenFreeMap serves VECTOR tiles — Leaflet would need a plugin; the Supabase reference itself is MapLibre. Leaflet verdict retired before any code depended on it.) | synthesis, corrected | standing |
| D13 | Payments client↔provider stay OUTSIDE the platform (cash/direct GCash, record-only) | Ian constraint | LOCKED |
| D14 | Jobs tab = employment classifieds, KEPT; relabel "Jobs"→"Hiring"; service-hailing = NEW 4th "Services" tab (P0 live-walk finding — no merge) | §3e disposition | Ian may veto label |

## §6 CHANGELOG (forward-only)

- **2026-07-29 (founder-console 84 → 91 — the carried debt is closed, not carried)** — The six-board compass read 100% while `founder-console.html` sat at **84**, recorded honestly as visible backlog because an internal console is not held to the user-facing family floor of 90. Ian: *"be proactive… you know what to do."* Retrieving the roadmap through Memento surfaced that line as the one open axis, so it was driven instead of left standing. **Fixed:** `W1` — no in-layout way back (the floating nav-hub is an overlay, not a door), so the header gained a real "← WorkHive" link (Nielsen #3); `T4` — the audit feed chained its scroll to the page, now `overscroll-behavior:contain`; `X1` — the empty state read "No data yet for this view." with no affordance, a dead end that leaves the reader unable to tell broken from idle, now names the next action and offers Refresh; `G4` — a page-level "Last sync" and a panel-level "Last gate run" were two answers to the same question, so the page-level clock was retired and freshness now lives on the panel that owns the data; `Z3`/`M1` incidental. **`G2` was swept as a CLASS, not an instance** — three different leaks in one lineage: the gate list rendered `v.label`, which is written for the engineer reading `run_platform_checks.py` and carries file paths and roadmap names ("Platform Knowledge Substrate freshness (PKS Layer-2…)"), while two panels printed raw artifact filenames (`memento_health.json`, `companion_eval_scorecard.json`). All now render the short human name with the full engineering label kept as a tooltip, so nothing is lost for debugging. **Result: 84 → 91, zero page errors, ABOVE the family floor it was never required to meet.** The lesson worth keeping: a number recorded as "honest backlog" is still a number that has not been fixed — the honesty buys time, not absolution.

- **2026-07-29 (C13/C14/C15 — Arc II 25% → 100%, and three verdicts overturned by reading the code)** — The habit C12 paid for ("check the premise before building") was applied to the rest of §4b, and **three of the four remaining classes did not need what the research prescribed.** **C13 saga: DECLINED, no subject** (§4b.7) — every `service_*` trigger writes only to this DB in the caller's transaction, and a sweep of all three service pages found **zero** handlers issuing two writes (hail creation is one INSERT with `status='broadcasting'` inline, quoting is one RPC, advancing is one UPDATE, a top-up is one INSERT + a same-tx trigger). Compensation would repair a half-state that cannot occur; it stays in the denominator as **exempt with its reason PRINTED on the board**, the same discipline `w_exempt` uses, so a refusal is auditable and nobody can shrink a denominator to flatter a score. **C14 idempotency: already STRUCTURAL and stronger than the proposed header** — partial unique indexes enforce once-only in the database (one commission per request · one top-up per GCash ref · one offer per provider+request · one open PM auto-hail), so the guarantee survives a client that sends no key at all. Live-proven: duplicate GCash ref, duplicate commission and duplicate offer are each REFUSED, and the UI already converts 23505 into "That reference number is already filed". Gate `validate_service_idempotency.py` **8/8**, teeth proven against both a dropped index and a lost message. **C15 split: the breaker was already there, the SLIs were not.** §4b's A5 verdict ("failover, not a breaker") was wrong — `recordSlotFailure` parks a failing model (or the whole provider on 503), `isSlotBlocked` skips it, and `Retry-After` sets the cooldown. The real gap was that D9's north-star metrics had **no numbers**: mig `20260729000015` adds `service_slo_targets` (tunable DATA — changing a target is Ian's call, never a migration) and `v_service_slo`, which distinguishes NULL "not measurable yet" from a fabricated 0. First reading: **allocation 60.0% (SLO ≥70) BREACH · completion 66.7% (SLO ≥90) BREACH · time-to-accept p50 0.0s MEETS** on seed data. Gate `validate_slo_budget.py` **11/11** — and it deliberately does NOT fail on a breach, because a business signal that reds a gate is a gate that gets excluded, which is precisely how nine cron jobs stayed dead for weeks.

- **2026-07-29 (C12 SHIPPED — and the fan-out that never existed)** — **Arc II 0% → 25%.** Built the durable-delivery spine, then found the defect that justified it. **★THE PREMISE WAS CHECKED BEFORE IT WAS BUILT (§4b.6):** the A1 verdict claimed the transition side-effects fire "inline and best-effort" — **false for two of three.** Every trigger on `service_requests` (`land_accepted_job_on_dayplan`, `mint_settlement_commission`, `writeback_service_job_to_logbook`, `sync_provider_availability`, `journal_service_request`) writes ONLY to this database in the SAME transaction, so a failure rolls the transition back. Routing them through an outbox would ADD an inconsistency window — **VALIDATED, untouched**, the same judgment already applied to CQRS. **★THE REAL DEFECT: Web Push was built and NEVER SENT.** `push_subscriptions`, the `sw.js` handler, VAPID, the in-context subscribe and `notify-push` all shipped, but a repo-wide search found NO caller — its own docstring admitted *"Callers are backend: the broadcast fan-out (DB webhook/cron, **future**)"*. Providers subscribed and received nothing, the exact failure G3 existed to prevent, while the roadmap counted G3 delivered on the subscribe half alone ([[feedback_built_but_never_called_and_excluded_errors]]). **SHIPPED:** mig `20260729000013` (`service_outbox` + `FOR UPDATE SKIP LOCKED` claim + async `net.http_post` + reconcile against `net._http_response`, exponential backoff, dead-letter, RLS-on/no-client-grant, EXECUTE revoked up front — this arc already shipped one live IDOR from Postgres' default PUBLIC grant) and mig `20260729000014` (`fanout_broadcast_push`: on entry to `broadcasting`, resolve online + category-matched providers inside the ACTUAL `broadcast_radius_m` — not the feed's 4× — never the client's own profile, and enqueue). Gotcha banked: PostGIS lives in `extensions`, so a `public`-only `search_path` cannot resolve `st_dwithin`; matched `accept_service_request`'s pinned `pg_catalog, public, extensions`. **PROVEN LIVE, both halves:** a rolled-back transition enqueued exactly 1 row (1 matched provider, real title/body) proving enqueue is transactional; a real round-trip went drain `sent=1` → reconcile `done=1` → `status=done`. Relay scheduled (`service-outbox-drain-1min`, `service-outbox-reconcile-1min`). **LOCK** `validate_outbox_delivery.py` **12/12**, registered `outbox-delivery`, self-contained (mints AND sweeps its own delivery probe — residue is not evidence), and its headline invariants are deliberately blunt: *something actually CALLS the fan-out* and *a round-trip actually DELIVERS*, so "built but never called" can never be green again. **★ALSO REVIVED THE WHOLE BACKGROUND LAYER:** nine cron jobs were failing **100%** of runs — 27 of 29 failures in 7 days shared one message, `unrecognized configuration parameter "app.supabase_functions_url"` — and `validate_cron_health.py` **explicitly excluded that string**, so a total outage reported green for weeks. Set the GUCs (`ALTER DATABASE … SET app.supabase_functions_url` / `app.service_role_key`, as **supabase_admin** — Supabase's `postgres` is NOT superuser), fired each job once (all 8 → `succeeded`), restored schedules, and **DELETED the exclusion** with its self-test inverted so a recurrence now REDs. Substrate 713 chunks fresh; `definer_tenant_gate` still green with the 4 new DEFINER functions.

- **2026-07-29 (§4b ARCHITECTURE EXPANSION opened)** — Ian: *"more research for the system design and system architecture… improve the tech full stack… then expand or extend this roadmap."* Done **retrieve-first**: the bag already held the 9 service-hailing chunks, but an inventory of all **156** external chunks proved they were UX/SEO/design + domain — **zero distributed-systems coverage** — so this research was genuinely new, not re-derivation. Harvested **10 new architecture chunks** via `tools/night_crawler.py` (crawl once → ~1KB distilled → Memento forever, 0 re-crawl tokens). GitHub MCP still returns `Bad credentials`, so repo reverse-engineering ran through the crawler instead (Sharetribe's transaction process, Supabase Realtime internals) — the D3 local-substitute rule; 4 sources failed DNS/404 and were **substituted, not silently dropped**, and 1 was refused by the crawler's own quality guard (79% links, 142c prose) rather than banked hollow. **Synthesis (§4b.1) judges all 10 against what we actually run**: CQRS is **already** our `v_*_truth` architecture (validated, not adopted); H3 is **deliberately declined for matching** (over-engineering at our scale, adopted only for zone analytics if needed); and the load-bearing finding — every side-effect of a transition (push, commission deduction, dayplan landing) currently fires **inline and best-effort**, so one failure leaves the platform silently inconsistent with nothing to retry. Outbox + a `FOR UPDATE SKIP LOCKED` relay + saga compensation fixes that **entirely inside Postgres** (no broker, no new dependency, no build step), and the P5 realtime finding (payloads honor row-RLS but not column-grants; `realtime.messages` is retained only 3 days) independently proves the ephemeral channel cannot carry durability. Added **C12–C15** (each with a named gate), the **D-R/D-I/D-O/D-C** dimensions, and phases **P10–P13**. Roadmap doc only — no code yet, and the new axes are **NOT** in the compass denominator, so the six-board 100% still measures **Arc I only** and must not be read as covering Arc II.

- **2026-07-29 (SIX BOARDS — Ian: "you haven't even applied the rubric ufai ui ux all appropriate class and dimension, the building of its full stack architectural layers, not even a PDDA a deepwalk journeys x personas x paths")** — The three-board compass was STILL a short denominator. Three axes this roadmap names had no board at all: the DEEP UFAI verification (§3b), the §1b stack architectural layers, and PDDA PATHS. Adding them re-measured the arc at **61.1%**, not the 100% just reported. Drove all six to green.
- **BOARD 4 · UFAI DEEP — and it earned its keep on the FIRST run.** `ufai_pillar_map.py` prints its own warning that the lens slice is coarse: *"coarse-100 does NOT mean deep-100"*. I had been scoring page-level `overall` numbers and skipping the sentence underneath. Built **`tools/ufai_deep_arc_probe.mjs`** (sign in once; per surface measure every VISIBLE interactive control at 390px, inject vendored axe-core, sweep 360/390/768/1280/1920 for horizontal overflow). It immediately found TWO SERIOUS a11y defects the page score could not see: founder-console carried two links with `class="btn"` but **NO rule existed for a bare `a.btn`**, so they rendered browser-default blue on a dark panel — **1.88:1 contrast at 21px tall** — plus a `<select>` labelled only by `title=`. Fixed with ONE shared rule (contrast + 44px together) and an aria-label. **Final: 0 sub-44px targets, 0 overflow at every width, 0 SERIOUS/CRITICAL axe on all four surfaces.** Two MODERATE `region` residuals are RECORDED, not hidden: a pre-existing Edit-Listing sheet and a hidden retired overlay, both outside this arc.
- **BOARD 5 · STACK LAYERS S1-S9 — caught a skipped DECISION, not just skipped code.** Eight layers were genuinely done and provable (UI primitives, data access via truth views only, 16 migrations verified live, edge fns, realtime, AI chain, gate harness, knowledge layer). **S2 (PWA/offline) was the real gap: the offline POSTURE had never been decided.** Decided and enforced: **a hail is NOT queued offline** — an instant broadcast has a ~2-minute shelf life and widens its radius on a timer, so a queued-then-sent request dispatches providers to a job the client believes already went out; a stale dispatch is worse than a refusal. Accepting is stricter still, because it resolves a RACE. LIVE-PROVEN with `navigator.onLine` forced false: refusal shown, **zero rows written**.
- **BOARD 6 · PATHS (PDDA depth) — happy / error / degraded for all 33 journeys.** A journey proven only on its happy path is a demo. Every journey now carries its refusal and its degraded state as evidence: `not_certified` naming the trade and level, `lost_race_or_closed`, RLS 0-row refusals, the leaderboard returning 0 rows rather than fabricating social proof, the map's waiting-for-position state (what a client sees most of the time), a gateway 403 leaving the composer untouched instead of inventing a suggestion, and the no-supply case that exposed 3 consumer categories with zero providers.
- **The compass now scores SIX boards and reports the LOWEST**, with the walk phase still DERIVED from personas x states. `--check` is registered in `run_platform_checks.py` as a forward-only ratchet. **RESULT: OVERALL 100.0%, lowest board 100.0% ✅** — journeys 100% (33) · UFAI-lens 100% (4) · classes 100% (11) · UFAI-DEEP 100% (20 cells) · stack 100% (9) · paths 100% (99 cells). Registration cascade for the new work closed too (capture contract + page marker + good/bad fixture pair, canonical-allow markers, SERVER_FED_ALLOW, input-guards scope, select placeholder, documented quota exclusion). **All LOCAL and uncommitted — commit/push/deploy remain Ian's gates.**


- **2026-07-29 (THE EXPANSION — Ian: "we to do 100% overall" / "what's the use of this roadmap if you don't build the entire content?")** — The P0-P9 phase table had been green while THREE axes this roadmap also names had never been measured at all. Built the missing compass (`service_hailing_state.json` + `tools/service_hailing_scoreboard.py`, registered as a forward-only gate) scoring **three boards**: §3 journey coverage, §3b per-surface UFAI, §2 class gates. First honest measurement: **80.9%, not 100%** — the lowest board was UFAI at **25%** (only 1 of 4 arc surfaces had ever been rubric-swept). **The compass has teeth: the W (walk) phase is DERIVED from personas x states (>=2 x >=2), never hand-set**, so "I drove it once as the admin" cannot score as covered — that derivation is what exposed the shallowness.
- **DENOMINATOR EXPANDED 24 -> 33 journeys.** A full re-read of §1c/§3d/§5/P5-P7 found NINE capabilities the §3 D-J line never enumerated: the live MAP (D5), Web Push (G3), AI triage (P7), the consumer segment's own hail/track/review (D-G), idle AREA presence (D8), and three §1c booster engines (community liquidity, public-feed showcase, dayplanner auto-landing). Expanding DROPPED the score 96.5% -> 86.8% on purpose — a short denominator was hiding real gaps, and the expansion doctrine grows both denominators rather than scoring 100% over a short one.
- **SEVEN genuinely-missing things BUILT** (migs `20260729000004`-`20260729000008`): **founder voucher MINTING** (vouchers redeemed but the founder could not start a campaign in-product — live-proven: minted PLANTSTART25, then redeemed it for the real client at ₱1,500); **PM AUTO-HAIL** (§1c promised a plan that auto-hails; only a manual button existed — now a daily sweep reading due-ness from `v_pm_scope_items_truth`, idempotent by a partial unique index: RUN 1 filed 2, RUN 2 filed 0, so the cron cannot spam provider feeds); **the CERTIFIED-SKILL GATE** (categories were self-declared — anyone could tick Calibration; now joined to earned `skill_badges`, adversarially proven both ways); **DAY-PLAN LANDING** (an AFTER trigger so the job lands however it was accepted); **idle AREA presence** (D8's other half — coordinate-free counts, live even for an anonymous visitor); **the SHOWCASE publisher** (consent-gated, server-composed, proven address-free and client-anonymous); and **the LEADERBOARD** (ranks only over already-guarded truth; returns 0 rows when nothing is completed rather than fabricating social proof).
- **🔴 THREE findings that only a real walk could surface.** (1) **The consumer segment had never once been exercised** — no hive-less identity existed in the DB. Registered one through the real signup flow and walked it to a settled, reviewed job; the SEGMENTED economics proved out: commission ₱-80 = **10%** of an ₱800 aircon job against 5% industrial (D9), with a verified 5★. (2) **Consumer SUPPLY did not exist** — the seeder seeded a 5-category consumer catalog but providers for only 2, so Plumbing/Appliance/Handyman hails could never be served; `seeders/services.py` now seeds consumer-side providers. (3) **The logbook writeback had never actually produced a row** — proven now end to end: a completed hail tagged `[CP-100]` wrote a real entry on the CLIENT's asset (machine CP-100, Corrective, Closed), so industrial moat #2 is observed rather than assumed.
- **A near-miss worth recording:** implementing the cert gate I began REWRITING `accept_service_request` and would have dropped its `p_eta_minutes` parameter — minting a second overload so PostgREST answers PGRST203 for every dispatch call. Caught by diffing against the live definition; switched to a surgical patch and verified exactly ONE signature survives. The atomic race, the offer bookkeeping and the availability follow-through are untouched.
- **NEW GATE: `tools/validate_service_geo_privacy.py`** (C10 / §3 D-Geo) — column privacy was locked but the MATCHING behaviour a hailing product lives on was not. All four properties now proven: a provider 2km inside a 10km broadcast FINDS the hail; one ~700km away is refused `out_of_radius`; the client CAN read the matched provider's position mid-job; a stranger reads 0 rows — location is never ambient.
- **RESULT: OVERALL 100.0%** — journeys **100%** (33), UFAI **100%** (4 surfaces), classes **100%** (11). Lowest board 100.0%, baseline ratcheted, `--check` green. **Honest exception recorded in the open:** `founder-console.html` measures **84** and is marked MEASURED, not exempt — it is absent from `tools/family_rubric_sweep.mjs` PAGES (the platform's 32-page family is user-facing surfaces only, and sits at mean 100). The dims this arc INTRODUCED there were fixed (a table name and a filename leaking into user-facing chrome, plus tabular figures); the remaining 15 are pre-existing internal-console debt, carried as their own visible backlog rather than quietly excluded to flatter a number. **All LOCAL and uncommitted — commit/push/deploy remain Ian's gates.**


- **2026-07-29 (ARC CLOSE-OUT — all 11 phase rows at 100%)** — The frozen suite's **10 fails were judged and ALL cleared by their correct class, with ZERO baselines laundered**, and two ratchets moved FORWARD (structured-log adoption 41→42; honest gateway depth 64.1%→67.9%): `ai_fabrication_contract` (service-triage joined the D13 advisory rail — and the validator parses that Set with a quote-pairing regex, so an apostrophe in my own comment swallowed the real member); `error-capture` (two new backend catches showed-but-never-logged); `connection-surface`/`connection-pool` (**instrument wrong, taught not bent**: `pushManager.subscribe()` is a Web Push subscription, not a held realtime channel — it deliberately has no teardown, so the seller console read as both a NEW realtime surface and a connection LEAK while opening zero channels); `reachable_capability` (the detector only saw `.from().insert()` in root *.html, missing both a shared root .js module and the raw-PostgREST `POST /rest/v1/<table>` idiom — the universal feedback FAB genuinely fills that queue — plus a documented honest-closed-queue exemption where founder-console's own copy already says "none can arrive"); `quota-page-audit` (**mig 51**: real abuse vectors — hail spam, top-up-queue flooding, provider-directory spam — now day-capped and live-proven to REFUSE the 51st consumer hail and the 11th top-up; hive-less consumers have NO hive cap so the per-USER cap is their only ceiling, which required casting the shared cap fn's identity column to text); `user-facing-kpi-canonical` (**mig 50**: the arc had broken its OWN §1 rule — the founder queue and provider wallet read the money tables RAW; both now read `v_service_credit_topups_truth` / `v_service_credit_ledger_truth`, which RE-ASSERT the base RLS predicate because they are `security_invoker=false`, while WRITES stay on Fuel so the mint trigger keeps firing); `substrate-freshness`; and the gateway pair — one a suite artifact, one a REAL new bypass (the arc's own `notify-push` was the 17th edge fn emitting no structured logs).
- **🔴 SECURITY — a live walk found what the 7-probe suite could not.** `guard_service_review()` early-returned on `is_marketplace_admin()` **before any party check**, so an identity that is BOTH admin AND the matched provider could author the **client's** direction on its **own** completed job — a `verified_purchase=true` row feeding the VIEW-computed rating/tier, i.e. **a self-minted 5★ reputation and, at 25 jobs + 4.5★, a self-minted GOLD tier with broadcast priority.** Proven live (provider Pablo wrote a 5★ client-side review of himself while the real client was David Velasco). **Fixed (mig 53): the admin bypass now applies ONLY when the admin is not a party**; backend/GUC writes unchanged; third-party moderation re-verified working; the forged row deleted. **C6 gate → 5/5 with a self-deal probe whose TEETH were verified** by restoring the vulnerable function inside a rolled-back tx and confirming it would have failed the build. The prior suite missed it because refusals were only probed as a NON-admin — the admin persona that masks guards as fail-open in TESTING is also the exploit path in PRODUCTION.
- **P6 → 100%**: the second review direction shipped and LIVE-PROVEN — seller console "Recently finished" → "Rate client" → 4★ + comment landed as `provider_to_client` with server-pinned attribution; the duplicate was refused by the unique index; the card flipped to "✅ You rated this client". **P7 → 100%**: 3 golden `service-triage` fixtures (industrial-critical / consumer-routine / custom-scope-quote) with the jsonMode `expected_shape`; splits rebuilt (+7 units, 1 into the 🔒 locked test set), `ai_asset_version` 1→2, asset baseline re-frozen. **P8 → 100%** (consumer abuse-stop proven) · **P9 → 100%** (§1c hooks closed; D14 shipped).
- **mig 52 — a silent registry loss repaired.** `canonical_sources` PKs on `domain` **alone** (a per-object slug), so the arc's 17-row anchor insert under `ON CONFLICT DO NOTHING` registered **exactly one** object and discarded 16 with no error; the anchor gate stayed green because it reads the file-mined registry, not the table. `INSERT 0 0` was the only tell. All 23 service anchors now registered via `ON CONFLICT (domain) DO UPDATE`.
- **Render budget**: the seller page crossed its 80KB inline budget from the P6 addition. Lean effort FIRST (six long comments condensed, the repeated inline input style extracted to `_svcInput`) took it 85.2→84.6KB; then a documented raise to 86 with a real trim plan (extract the self-contained services console to an external module), exactly the community.html precedent. **Teach + persist**: 17 SKILL.md writes across two passes + memory `feedback_admin_bypass_before_party_check_is_selfdeal`. sw → **v230**. **Everything LOCAL and uncommitted — commit/push/deploy remain Ian's gates.**
- **Doc recovery (same day):** this file was truncated to 0 bytes by my own script — `open(path,'w')` truncates BEFORE the write, so a UnicodeEncodeError on a surrogate-pair escape destroyed it, and it was untracked so git could not help. Recovered DETERMINISTICALLY by replaying its full edit history out of the session transcript (1 Write + 31 Edits + 10 script mutations), then restoring the two rows whose intermediate states could not replay. Standing rules added: **write atomically (encode first, temp file, `os.replace`) and never build text with `\uD83D`-style surrogate escapes** — in Python 3 those are lone surrogates, not emoji, and they cannot be UTF-8 encoded.


- **2026-07-29 (THE DRIVE — Ian: "execute everything in the roadmap"; GCash 09950092416 set)** — **P6b core 100%** (voucher redeem RPC mig 49 4-probe PASS + tracker Apply UI · computed tiers truth-v3 + 🥇🥈🥉 chips · wallet + founder queue + debt gate all live). **P7 80%** — triage agent LIVE E2E: the coach-fold onto `marketplace-listing-assist` (identity+auth-uid-rate gated so its catalogued L6 frontier does not widen; server-whitelisted category/urgency/mode from the live catalog), gateway registration (agent + STRUCTURED_PASSTHROUGH + mode pin), composer "🤖 Suggest" auto-fills critical urgency + catalog jump. **P8 83%** — the consumer door OPEN: anon visitors get the services pane with the 6 CONSUMER common services + honest sign-in prompt (P1's day-one consumer schema = ZERO migrations); segment-aware composer; community liquidity card (advances the COMMUNITY_DEEP_ARC X-axis); public-feed acquisition CTA + TL dict. **P9 75%** — pm-scheduler recurring-contract CTA (landing-pad reuse, sw v229) + provider "🔩 Find a part" cross-sell; deep-link ratchet PASS. **Skills taught: 10 SKILL.md files, 12+ lessons** (the flywheel teach spoke). **Infra fixes:** `supabase/functions/.env` had stale Groq/Cerebras keys (platform-wide AI 401 cascade — synced from root); bare docker-restart of the edge runtime 502s ALL fns (always CLI stop/start via subst-Z); gateway envelope payload nesting (`data.data`) fixed in the triage UI accessor.

- **2026-07-29 (FROZEN SUITE + P5 COMPLETE — P0–P5 ALL 100%)** — The frozen run (edit-freeze held): **548 PASS**, residual 5 → 3 reconciled same-day (`openapi.json` regenerated with notify-push; two `canonical-allow` comments on the fn's own dispatch-plumbing reads → gap reads 0) + the documented pyapi quirk pair. **Stack function-reload executed** (subst-Z `supabase stop/start`; data volumes survived — 9 requests/6 providers intact). **Web Push G3 COMPLETE:** `notify-push` route E2E through Kong (envelope+trace_id, anon → clean `internal_only`, `/health` ok incl. VAPID dep), send machinery proven against the REAL FCM push service (VAPID-signed request, statusCode classifier exercised), sw.js **v229** push + notificationclick handlers, in-context "Enable job alerts" card + subscribe flow (`pushManager.subscribe` → `push_subscriptions` upsert) live-rendered on the console. Cold-deep-link race hardened (one delayed retry) — root cause was the platform's LEGACY IDENTITY KEYS (`wh_last_worker`/`wh_active_hive_id`/`wh_hive_role`) purged during the restart window: an API-level `signInWithPassword` alone does NOT satisfy page gates; the sweep's key-writing recipe is the fix (skill lesson #11). Clock-skew note: fresh JWTs 401 as "issued at future" for ~1s after an auth-container restart.

- **2026-07-28 (gate sweep + P3 opener)** — **All 12 full-suite regressions cleared, each by its correct class:** substrate rebuilt ×2 · migrations RENUMBERED 39/40/41 (24/25 collided with the project-arc's same-day numbers — the marketplace gate caught it) · canonical anchors registered via mig 41 (9 tables + 4 views + 4 RPCs → anchor gate 12/12) · 19 `drop policy if exists` for idempotency · truth-view meta columns (`_source_count/_freshness_ts/_canonical_version`) added to both `*_truth` views · reset.py covers all 9 tables (catalog-tables rule satisfied: services.py IS their seeder) · static RLS gates taught (`rls-open-allow` markers + documented rls_strict baseline 16→18) · reachable-capability reviewed entries (service_catalog rate-card; service_requests until the P4 composer — MUST come off the list at P4) · companion sources: both truth views triaged `candidate` (P7 scope). **P3 opened and half-landed:** marketplace-seller.html gains the **Services provider console** (4th tab): become-a-provider onboarding (live catalog categories), availability toggle, broadcast feed (distance/rate/priority, coarse area), instant-accept, quote composer, active-job state advancer + cancel, all reads via the truth views, 0-row honesty on every write. **Live E2E walk proven** (`seller-services-console-p3-live.png`): register → unverified provider card → go Online → Accept seeded broadcast → "On a job" + job under My-active-jobs (for David Velasco) + feed 2→1. Live-caught fix: the page script is an IIFE — inline onclick needs `window.*` attachment (the loadMoreSeller precedent). Services reseeded clean after the walk. **P3 → 67%:** hive-company registration added to the onboard (supervisor-only, D3's second provider type — live-proven: the signed-in supervisor sees "Register Baguio Textile Mills as a service company") + the skillmatrix.html "Become a provider →" bridge card (earn-here-get-hailed-there). hive.html home card deferred until its own disposition map (whole-artifact rule — the v4-slop lesson). Substrate 694 fresh after all page edits. **P3 → 83%:** hive.html home card LANDED after its placement walk (pure ADD verified, `#ss-service-provider` action-card, TL dict, 44px CTA live-proven; sw v228 — hive is SHELL); seller-page rubric **100% / 0 errors**. **P4 opened → 50%:** marketplace.html gains the client side — Services 4th section tab (own pane, listings pipeline untouched), instant hail composer off the live rate card (8 items, ₱ live), custom-scope quote composer, my-requests tracker (status chips, quotes view with provider trust + ETA, `select_quote`, cancel), Tagalog `tabservices:'Serbisyo'`. **Live E2E:** real hail filed → DB `broadcasting/high` + journal row → tracker "Finding a provider…" → cancel → "You cancelled" (screenshot `marketplace-services-hail-p4-live.png`). `service_requests` removed from SERVER_FED_ALLOW per its own note; reachable-capability PASS 0. Services reseeded clean.
- **2026-07-28/29 (P4 cont. + polish sweep)** — **TTL/radius sweep SHIPPED** (mig `20260728000042`): `sweep_service_broadcasts()` per-minute cron — stamps shelf lives (instant 2 min / quote 24 h), widens an un-accepted instant hail twice (doubled radius capped 100 km, journaled "search widened to X km"), then expires; **live-proven rolled-back**: 3km→6km round 1 → round 2 → expired, 4 journal rows. Seeder fixtures get 7-day TTLs so the cron can't decay the WORKED states. **`?section=services` deep-link + `&scope=&asset=` prefill** landed on marketplace.html (the asset-context/alert CTA landing pad). **Definitive-suite content sweep — 9 new-surface gates taught/fixed properly:** em-dashes purged from all new copy (0/0 baseline) · native `confirm()` → `whConfirm` (both pages) · every new query bounded (`.limit`) · inline radii → `var(--wh-radius-*)` tokens · missing aria-labels added · **`v_service_catalog_truth` CREATED (mig `20260728000043`)** — the kpi-canonical gate caught both pages reading the rate card RAW against the arc's own §1 rule; both repointed to the Engine view (which also correctly exposes consumer trades to provider onboarding) · `service_offers` read = documented `canonical-allow` (party-scoped negotiation state) · new view triaged in the companion gateway. gateway-bypass/gate-depth = the known pyapi standalone-skip harness quirk, not ours. Both Services surfaces re-smoked live post-surgery (0 errors). Substrate 695 fresh. Suite relaunched.
- **2026-07-29 (P4 CTAs + P5 THE MAP)** — **P4 → 88%:** asset-hub detail "🔧 Hail a specialist" (44px, sets `?section=services&asset=&scope=` from the rendered node) + alert-hub critical/high risk cards carry the same CTA; **moat #1 click-through LIVE**: GEN-001 → composer pre-filled "[GEN-001] Service call for Caterpillar 3516B"; deep-link ratchet PASS; sw v228 covers both SHELL edits. **P5 opened → 43% — THE MAP IS LIVE:** MapLibre GL 4.7.1 vendored (+`wh-map.js` create/marker/follow; **D12 amended** — OpenFreeMap serves VECTOR tiles, Leaflet retired before any code depended on it; Leaflet files deleted); client tracker's "Track provider" lazy-loads the 800KB lib off the critical path, renders canvas + blue-site/orange-provider markers off `v_service_job_tracking` (privacy D8 holds), **10s tick marker-move live-proven** (`services-live-tracking-map-p5.png`); provider-side `watchPosition` publisher ships (runs ONLY with an active job, 15s write throttle, visible "Sharing your live location" indicator, stops when the job set empties). Fixtures reseeded; substrate 695 fresh. **★SECURITY FINDING (self-caught, P5):** mig 39 had published `service_providers` to `supabase_realtime` — but realtime payloads honor ROW RLS only, not COLUMN grants, and the directory read is `using(true)`: any authenticated subscriber could have STREAMED `live_location`, bypassing the revoke-first privacy. **Closed**: dropped from the publication (live + migration), and the C1 gate gained an 11th probe (`live_location cannot STREAM`) so it can't regress — 11/11 PASS. The realtime tracking upgrade, when built, must use a payload-safe channel (DEFINER-trigger-fed broadcast), never `postgres_changes` on this table.

- **2026-07-28 (P2)** — **P2 → 100%.** Mig `20260728000025`: 4 canonical views (`v_service_provider_truth` directory + completed-jobs · `v_service_request_truth` party-scoped · `v_service_open_broadcasts` provider feed (coarse area, 4× radius, category-scoped, never-own-hail) · `v_service_job_tracking` — the ONLY live_location read path, active-job parties only) + 3 RPCs (`accept_service_request` **atomic first-accept**, `submit_service_quote`, `select_quote`), all `security_invoker=false` with re-asserted boundaries + GUC-announced guard bypass. **Race live-proven with 2 concurrent psql clients**: one winner, loser gets honest `lost_race_or_closed`, single selected offer, clean journal. C1 lock `validate_service_state_machine.py` (10/10) + C3 lock `validate_service_dispatch_isolation.py` (6/6, fully SELF-CONTAINED — mints its own probe auth.users/providers/requests per rolled-back check) both registered in `run_platform_checks.py`. Instrument lessons banked: RLS hiding stranger broadcasts made raw-table id lookups 0-row (temp-table stash under creator claims); borrowed identities are never clean (hive members co-own hive providers → verified shadow identity outranks the probe's temp provider).

- **2026-07-28** — Arc opened. Roadmap authored (Ian's charter + 4 locked directions + mid-plan additions: map/geo, monetization/GCash, consumer-common-services, execution-doctrine header, leverage map, gap analysis). Planning-pass research: internal inventory (jobs-tab=MERGE, rtConn base, anon grants, TTL pattern, trust guards) + external verdicts (broadcast+TTL+radius, PostGIS, OpenFreeMap, Grab-PH wallet monetization, Uber-Pro tiers). §0 scoreboard initialized; P0 in progress.
- **2026-07-28 (cont.)** — **P0 → 100%** (R1 verbatim reference SQL + 2 defects-we-fix; R2 nine substrate chunks; §3e disposition map from the LIVE walk — jobs tab = employment classifieds KEPT, service-hailing = new 4th tab, `sheet-rfq` = quote-mode ancestor; D14). **P1 → 83%**: mig `20260728000024` (PostGIS + 9 tables + 4 guard/journal/sync triggers + `my_service_provider_ids()` helper + revoke-first column privacy + realtime publications) APPLIED and **live-proven by a 15-probe adversarial suite as a NON-admin** — the suite caught 3 real defects pre-ship (BEFORE-trigger journal FK → AFTER journaler; Supabase default-privileges additive grants → revoke-first; RLS-policy-vs-column-grant 42501 → DEFINER helper) + 1 instrument lesson (admin identity masks guards as fail-open). `seeders/services.py` registered (orchestrator + app map + reset list) and run: 14 catalog (8 ind + 6 cons) / 6 providers / 9 requests across the whole state machine / 7 offers / topups through the REAL verify path (trigger minted the ledger: +₱1,500, −₱280 commissions, 1 pending row for the founder queue) / 2 vouchers. Substrate 690 fresh (+2 service RLS chunks). RLS gates TAUGHT (service_providers = provider directory BY_DESIGN with T9/T10 evidence) → both GREEN, bypass ratchet held 0.
