# Arc P — R0 Live-Walk Findings (measured, one page at a time)

> **STATUS 2026-07-02 (post-R0): GATE BUILT + WAVE 0 SHIPPED (local, at Ian's commit gate).**
> - **`validate_pareto_content.py` built + registered** in `run_platform_checks` (id `pareto-content`, group Platform, `--gate` ratchet, blocker-on-rise). Scans HTML visible text + maturity-gate-consumer inline JS + shared DOM-renderer `.js`, **stripping code-comments / JSON-LD / AI-system-prompts first** (the R0 3× over-count lesson). Reproduced R0 exactly: **10 displayed defensive phrases, 0 false positives** (maturity-gate.js 5 · ai-quality caller 3 · ph-intelligence caller 1 · index FAQ 1). Baseline auto-tightens (Rule B).
> - **Wave 0 (FUSION 1) done + live-verified:** rewrote the shared `maturity-gate.js` empty-state (badge `Honest Empty State`→`Locked`; `<h1>We won't fake this.</h1>`→`${pageName} unlocks at Stair ${n}: ${stairName}`; default `why`→confident) + ai-quality & ph-intelligence caller `why` strings + index FAQ (visible + JSON-LD). **Gate 10 → 0 (P4 FLOOR MET, ratchet locked at 0).** Live re-walk confirms ph-intelligence now reads "PH Intelligence unlocks at Stair 3: Predictive-Ready" and ai-quality "AI Quality + ROI unlocks at Stair 2: Disciplined" — zero "won't fake/refuse/mislead/honest-empty". Same shared fix covers hive/alert-hub/founder-console.
> - **WAVE 1 DONE + live-verified (2026-07-02, 0 console errors, desktop+mobile).** (a) **hive.html density revamp (the 33% outlier):** verdict `#supervisor-summary` HOISTED above presence/focus (P1 verdict-first: top=188px, presence demoted to 870px); `#ss-action` ends in a data-driven primary CTA button (live: "Assign 30 overdue PMs →" → pm-scheduler.html, matching the real "30 PMs overdue" verdict) (P3); the 6 co-equal ghost buttons → ONE "⋯ More" overflow menu, all ids + supervisor-reveal JS preserved (P3); Network-Benchmark + Pattern-Alerts + Hive-Activity collapsed into `<details class="wh-disclose">` + Supervisor-Action-Log default-collapsed (P2) → **8.5 → 3.2 screens (−62%)**. hive → ~5/6. (b) **FUSION 3a — "What to do next" → primary button** live-verified on pm-scheduler (auto-applies Overdue filter), analytics (MILL-001 → Predictive tab), shift-brain ("Inspect 6 risk assets →"), inventory ("Order 3 low parts →"), alert-hub ("Clear 59 critical/high →"), asset-hub ("Browse the asset list →"). (c) **index home P3:** first role-action = solid-fill PRIMARY, 2nd tinted secondary; "Secure account" guest nudge demoted from solid-orange. NEW shared `components.css` `.ac-cta` + `.wh-disclose` (inlined on the 3 pages missing the `<link>`). Gates: pareto-content PASS@0 + css-class/id/orphan/inline-onclick/aria all PASS. **NEXT = Wave 2** (FUSION 2 list-discipline + skillmatrix radar chart).



> **STATUS 2026-07-02 (SECOND TURN) — WAVE 3 REMAINDER + §E RE-WALK COMPLETE (local, gate-clean, live-verified, at Ian's commit gate).**
> All units below driven from a read-only mapping fan-out (5 agents), applied, then live-walked as Pablo Aguilar / Lucena. Final gates ALL green: pareto-content P4=0, css-class/onclick/aria/orphan-setter, seo 6/6, source-chip-truth 0, user-facing-jargon 0.
> - **FUSION 5 (meta-caption wall) killed platform-wide** — `renderSourceChip` (utils.js) gained an optional `method[]` arg that renders a `<details class="wh-method">` "How this is computed" disclosure (44px tap summary, ⓘ marker); CSS injected via a guarded JS `<style>` in utils.js so it reaches the Tailwind pages too. `notes:`->`method:` on pm-scheduler/inventory/skillmatrix/shift-brain/dayplanner/hive/analytics(window->method)/asset-hub(risk chip). Visible chip is now ONE glance-first line. Live-verified pm-scheduler (3 clauses in the disclosure) + analytics (template-literal clause resolved to "90d").
> - **audit-log humanize** — snake_case target-type badge humanized (rcm_strategies->"RCM Strategy" map + snake->Title fallback; CSS uppercase->capitalize); raw UUID target_name gated OUT of the scannable row, surfaced in Show-details; CSV stays raw. CAUGHT+FIXED a TDZ ReferenceError (the `const` helpers must live in the module-state block at the top, not beside renderFeed which runs during init). Live-verified: 7 rows, badges "Worker Profile"/"Alert", 0 snake_case, 0 raw UUID in rows, 0 console errors.
> - **asset-hub critical-first** — stable criticality-desc sort on `filtered` before the Load-More slice. Live-verified strict order: 6 critical / 6 high / 15 medium / 3 low.
> - **assistant RAG scope-label (§C#5)** — buildSystemPrompt LOGBOOK header + conversation-rule now scope the answer to "your recent logbook entries only" and defer fleet-wide MTBF to the Analytics Engine. This is the LOCAL client-fallback fix; the primary ai-gateway/ai-orchestrator grounding align is an Ian-gated edge-fn deploy (flagged, not done).
> - **index landing 20->~8 screens** — Problem section MERGED into "Four gaps. One hive." (each gap card leads with a red "The gap:" problem line; one fewer full-height section); personas de-sparsed; day-after essay + learn padding trimmed; beehive metaphor cut from the hero (survives once in the Join CTA, value prop now first); FAQ hedges "selling a dashboard, not a system" + "This is intentional" killed in the visible answer AND its JSON-LD twin. docHeight 10,321px->8,686px. Mobile 375 hero fold FIXED (logo 150->118 + hero vertical-rhythm trim): the primary "Join the Hive" CTA is now fully in-fold (bottom 662 < 812). SEO gates still 6/6.
> - **§E ph-intelligence + ai-quality POPULATED re-walk DONE** — built the structure per doctrine (inserted a temp Stair-3 `hive_readiness` snapshot for Lucena, walked both, then DELETED it and verified the DB reverted to Stair 1/62; no pollution). **ph-intelligence populated ~5/6** (headline verdict "Top failure cause: Wear" + 3 stat cards + exec summary + reliability-ranking bars + ranked failure causes + "Your Plant vs Network" color-coded deltas; P3 next-action is prose). **ai-quality populated ~5/6** (verdict "AI is helping your hive, 474 calls" + 3 stat cards incl honest no-data sub-states; P3 prose). Both P4 clean AFTER fixing **11 prose em dashes** discovered in their now-visible copy (the empty-state walk never saw them). FUSION 5 "ⓘ" disclosure confirmed rendering on both.
> - **em-dash P4 sweep DONE** — built `validate_no_em_dash.py` (flags PROSE em dashes in displayed copy: HTML text per-text-run + title/aria/placeholder attrs + inline JS display strings + content .js; excludes comments/harness JS) + registered `no-em-dash` in run_platform_checks (Rule-B forward-only ratchet, blocker-on-rise, so NO NEW em dash can enter). Cleared **855 -> 137** displayed em dashes: I hand-fixed 7 high-value pages, then a **43-agent parallel workflow fixed 685 more** across the platform (engineering-design.js 180, skill-content.js 165, analytics 49, etc.; each agent context-chose colon/comma/parens and ran node --check). The **137 residual are all internal/identity/placeholder** the agents correctly left: calc-type ID keys used in `===` ("Chiller System — Air Cooled", per Memento), AI system-prompt strings (wh-persona voice), and `|| '—'` no-value glyphs — NOT displayed prose. Every structural + SEO + provenance gate stayed green through all 685 edits; every edited JS file node --check-clean; heavily-edited pages (engineering-design 180 edits) render correctly.
> - **Recurring 404 FIXED** — `wh-persona.js` mapped the hezekiah/zaniah avatars to legacy `james-256.jpg`/`rosa-256.jpg` that never existed (404 on EVERY page + failed the SW install `addAll`); repointed to the real `hezekiah.png`/`zaniah.png`, fixed the sw.js precache list, bumped sw.js v158 -> v159. `validate_image_asset_existence` now PASSES; live console 0 errors.
> - **FUSION 5 gap closed** — project-manager.html had its own inline meta-caption wall (Status buckets / Past end date / Completion %); converted `notes:`->`method:` so it collapses behind the disclosure like the other 9 pages. Live-verified: one glance-first line + 3 clauses in the disclosure.
> - **NEXT queue** — (1) em-dash: OPTIONAL decouple the calc-type display label from its id in engineering-design.js so "Chiller System — Air Cooled" can display "Chiller System: Air Cooled" without breaking the `===` identity keys (the last ~34 of the 137); (2) full 4-persona walks (field/new-worker/admin; R0+this turn were supervisor-only) for P6; (3) project-report POPULATED via the in-app Project Manager -> Detail -> Print Report flow; (4) dayplanner + project-manager quick live re-verify; (5) OPTIONAL: FUSION 3a primary-CTA button on ph-intelligence "cross-check in your logbook" (ai-quality's next-action is a behavioral nudge, no single click, leave as prose).

> **§G PERSONA-WALK PROGRESS (P6 axis, 2026-07-02 turn 2, in progress).** R0 + Waves were supervisor-only (Pablo Aguilar). Started the FIELD-TECH walk as David Velasco (worker, 300 entries; sign-in recipe + set `wh_hive_role='worker'` + `wh_last_worker='David Velasco'` — the front-door login sets these, the programmatic sign-in does not). Findings so far: (a) **field-tech signed-in home** = "Log a Job" is the primary role-action (correct for a worker); (b) **logbook P6 PASS** — log form present, "What happened? →" single primary, voice-fill-first (fastest path), copy clean (0 em dashes, "Step 1: Machine & Type"); (c) **hive board** — role isolation correct (worker does NOT see the supervisor action log), FUSION 5 "How this is computed" disclosure renders for the worker too, 0 em dashes; the `#supervisor-summary` verdict is empty for a worker (expected, supervisor-scoped) but the worker gets their OWN glance verdict on the home ("TODAY · PM OVERDUE, 30 PM tasks are due, Open the scheduler to claim the next one" + a primary Open-PM-Scheduler action) = worker glance-first PASS, RESOLVED; (d) **assistant P6 PASS** — grounding-aware greeting personalized to David ("I can see your job records"), 3 starter chips, input present. **NEW-WORKER walk (Emma Velasquez, worker, 100 entries):** (e) **home P6 PASS** — personalized greeting, "Log a Job" primary role-action (correct first step for a new worker). **REAL RECURRING BUG FOUND (fix queued, out-of-Arc-P but worth doing):** `brand_assets/rosa-256.jpg` 404s on EVERY page — root cause `wh-persona.js:202` maps the `zaniah` avatar to a non-existent legacy filename `rosa-256.jpg`; the only persona image present is `brand_assets/zaniah.png`. FIX = point zaniah (+ check hesekiah/`james-256.jpg`) to the real file; DEFERRED until the em-dash sweep releases wh-persona.js (it's in the sweep set). NEXT: finish field-tech + new-worker on pm-scheduler/inventory/dayplanner/analytics + confirm worker glance-verdict.

Companion to `PARETO_PAGE_REVAMP_ROADMAP.md`. Each page is walked LIVE via Playwright MCP (desktop 1440 + mobile 375, signed-out + signed-in where dual-surface), measured against the P1–P6 rubric. `%` = firm lenses passed / 6 (partial = 0.5). Evidence = measured word/element counts + screenshots in repo root `arcP-*`.

Rubric: **P1** glance-first verdict/key-points · **P2** vital-20% prominent + progressive disclosure · **P3** exactly one primary action · **P4** confident copy, ZERO defensive hedging · **P5** visual hierarchy/scannable · **P6** live-persona-proven.

---

## Page 1 — index.html (landing + signed-in home) · walked 2026-07-02

**Dual-surface** ([[feedback_landing_page_always_in_scope]]). Measured both.

### Surface B — signed-in home (as Leandro Marquez)
Measured: **195 total visible words**, ~65 in the fold, 1×h1, verdict card present, console clean (401 only when signed-in RPC probes dashboard).

| Lens | Verdict | Evidence / issue |
|---|---|---|
| P1 glance-first | ✅ PASS | Green "ALL CLEAR — Nothing urgent right now. Review the alert feed or the AMC daily brief." verdict card answers "what do I do now?" in ~2s. Calm verdict-first contract working. |
| P2 vital-20% | ✅ PASS | Verdict dominant; secondary collapsed under "▸ More". |
| P3 one primary action | ❌ FAIL | **3 co-equal CTAs in hero**: verdict card (→ alert-hub), "Hive Board" (→ hive, 319px cyan-tint), "Ask Zaniah" (→ assistant, 319px green-tint). Worse: the single **brightest** button on the page (solid-orange `rgb(247,162,27)` "Secure account →") is a **housekeeping toast**, not the job. CTA hierarchy points at the wrong thing. |
| P4 copy | ✅ PASS | Home copy is confident + concise; no defensive phrases on this surface. |
| P5 hierarchy | ⚠️ PARTIAL | Clean hierarchy + whitespace, but mid-page is sparse/empty below the two buttons — feels under-filled rather than calm. |
| P6 persona | ⏸ defer to re-walk | Renders for all roles; nav hub exposes every tool. |

**Home score: ~4/6.** Primary fix = **P3**: choose ONE primary action (open Hive Board OR resolve top alert), demote the other two to secondary, and stop letting the "Secure account" toast be the brightest control.

### Surface A — signed-out landing (marketing)
Measured: **2,236 total words**, **20.6 screens** (docHeight 10,321px), 1×h1 / 12×h2 / 14×h3, **16 FAQ `<details>`** (good progressive disclosure). Hero fold = 37 words.
Section flow: Hero "Access Your Memory / Free Industrial Tools for Every Filipino Worker" + maturity-stage card → What is WorkHive? → tool logos → "Filipino workers are skilled. The system is failing them." → "Four gaps. One hive." (2×2 card grid) → "The day after WorkHive." → "Every worker has a role in the hive." (3 persona cards) → FAQ (16) → "Practical writing for the Philippine plant floor" (3 articles) → "Join the hive. Build the future." (email CTA).

| Lens | Verdict | Evidence / issue |
|---|---|---|
| P1 glance-first | ⚠️ PARTIAL | Hero headline + tool list gives a decent 5s "what is this," but there's **no verdict/key-points TL;DR**; the value prop is diluted by the "beehive… 80 million years" metaphor sentence before the point. 20-screen body has no summary-first. |
| P2 vital-20% | ⚠️ PARTIAL | Tools + "free" + stats prominent; FAQ correctly collapsed. But **10 full-height sections at ~equal weight**; mid-page essays aren't progressively disclosed. |
| P3 one primary action | ✅ PASS | Hero "Join the Hive" solid-orange is the clear single primary; "See how it works" is a demoted secondary. |
| P4 copy | ❌ FAIL (low count) | Measured defensive copy — **not the "9" prior**: (1) FAQ "**Honest answer:** 2 weeks… No tool delivers results faster **honestly**" (dup'd in visible FAQ line 1950 + JSON-LD schema line 282); (2) mild "**This is intentional.**" (Solo-Mode FAQ, line 1945/274). "not just a consumer" (line 2445) is an aspirational testimonial, not defensive. So real defensive instances ≈ **2–3**, concentrated in the FAQ — floor is 0, so still fails, but the prior over-counted. |
| P5 hierarchy | ⚠️ PARTIAL | Strong scannable bits (2×2 "Four gaps" grid, collapsible FAQ, big statements). But **excessive empty whitespace** — the "Every worker has a role" persona section renders nearly empty; 20.6 screens for 2,236 words is bloated. Scannable-but-long. |
| P6 persona | ⏸ defer to re-walk | Renders. |

**Landing score: ~3/6** (P1 0.5, P2 0.5, P3 1, P4 0, P5 0.5, P6 defer).

**Mobile (375px) — landing:** decorative WorkHive hex logo consumes the **entire first ~470px** of the fold; the value-prop headline "Access Your Memory / Free Industrial Tools…" starts ~530px down and the "Join the Hive" **primary CTA is well below the fold** (P1/P3 mobile regression). Floating chat bubble overlaps the hero paragraph text (P5 mobile overlap). Fix: shrink/relocate the hero graphic on mobile so headline + primary CTA are in the first viewport.

### Page 1 combined R0 = **~3.5/6 ≈ 58%**
**Top revamp actions (ranked):**
1. **P3 signed-in home** — collapse 3 co-equal CTAs → 1 primary; the brightest button must be the job, not "Secure account".
2. **P4** — kill "Honest answer / honestly" in the results FAQ (in BOTH visible + JSON-LD); soften "This is intentional." → confident statement of what Solo Mode *is*.
3. **P1/P5 landing** — add a hero key-points/verdict block; tighten 20.6 screens (fix the empty persona section; progressively disclose mid-page essays); front-load the point before the beehive metaphor.
4. **P5 home** — fill the sparse mid-page or tighten vertical rhythm so "calm" doesn't read as "empty."

Evidence files: `arcP-01-index-landing-desktop-full.png` (signed-in home), `arcP-01-index-landing-SIGNEDOUT-desktop-full.png`, `arcP-01-index-landing-REVEALED-full.jpeg`.

---

## Page 2 — hive.html (Hive Live Board) · walked 2026-07-02 · signed in as pabloaguilar (supervisor), hive "Lucena Pharmaceutical Mfg."

Measured: **1,526 total words**, **142 fold words** (dense), **8.5 screens** (docHeight 7,671px), 1×h1 / 7×h2 / 3×h3, **110 card/tile/stat elements**. Console clean.
Top-to-bottom: header + 6 ghost buttons → ON SHIFT NOW presence → YOUR HIVE'S FOCUS → **"Hive needs your attention"** banner (+ "30 PMs overdue, Open PM Scheduler and bulk-assign") → 3 stat cards (Maturity Stair 1 · Adoption Health At Risk 36/100 · Open Issues 52) → 19 WOs / 5 members → stair progress bars → adoption 5-dim bars → adoption checklist → 3 alert cards → "Ask the Reliability Coach" → **Network Benchmark table** → **Pattern Alerts** (repeat-failure cards) → **full Hive Activity feed** (~20 items) → Team Pacing → **Supervisor Action Log** (another long list).

| Lens | Verdict | Evidence / issue |
|---|---|---|
| P1 glance-first | ⚠️ PARTIAL | The health verdict DOES exist ("Hive needs your attention" + "At Risk 36/100" + "52 open issues" + a next-action hint), but it's crowded by presence + focus + maturity-stair in a 142-word first screen — verdict-present-but-buried, not clean glance-first. |
| P2 vital-20% | ❌ FAIL | **The dominant problem.** 110 tiles / 8.5 screens with everything expanded INLINE — network-benchmark table, pattern alerts, full activity feed, AND a supervisor action log all fully rendered. Almost no progressive disclosure. This is the board-density the roadmap flagged. |
| P3 one primary action | ❌ FAIL | The actual next action ("Open PM Scheduler") is a small inline link inside the warning banner; the fold is otherwise 6 ghost buttons (Leave Hive, Audit Log, AI Quality, Plant Connections, Show Invite Code, Switch Hive). No single dominant primary CTA. |
| P4 copy | ✅ PASS (prior corrected) | **Grep for `fake|we won't|trust us|for real` = 0 matches.** The prior "5 defensive (won't fake)" was 100% false-positives on JS **code comments** ("honest blocker", "not just stale localStorage", "actually discoverable" — lines 620/1301/1721…). Displayed copy is confident + operational. |
| P5 hierarchy | ⚠️ PARTIAL | Good card styling + section labels, but the stacked 8.5-screen length with inline-expanded feeds collapses the layer-cake after screen ~2; hard to scan to a decision. |
| P6 persona | ⏸ defer | Rich for supervisor; field/new-worker would see a thinner board. Deep persona pass at re-walk. |

**Page 2 R0 = ~2/6 ≈ 33%.** Top revamp actions:
1. **P2 density** — collapse Network Benchmark / Pattern Alerts / Activity Feed / Supervisor Action Log into `<details>`/tabs/"show more"; default view = verdict + top-3 issues only.
2. **P3** — promote ONE primary "next action" button (e.g. "Assign 30 overdue PMs →") at the top; demote the 6 ghost buttons into an overflow menu.
3. **P1** — hoist a single clean health-verdict block above presence/focus so the "should I worry?" answer is the first thing seen.
4. **Cross-page correction** — the defensive-copy priors (§2 of the roadmap) were measured with a regex that counted **code comments + non-defensive "not just/honest/actually"**; every page's P4 must be re-measured against **displayed text only**. index's real count ≈2–3 (FAQ), hive's = 0.

Evidence: `arcP-02-hive-desktop-full.jpeg`.

---

## Page 3 — alert-hub.html (Alert Hub) · walked 2026-07-02 · signed in supervisor

Measured: **1,062 total words**, **285 fold words** (densest fold of the 3 dashboards), **5.8 screens** (5,243px), 1×h1 / 2×h2, filter chips = All 65 / AMC 4 / Risk 6 / PM 30 / Stock 3 / Staging 2 / Pattern 20 / System 0. Console clean.
Structure: title + "Everything that needs your attention, in one place." → red "Needs your attention now" banner → 3 summary cards (HIGH-SEVERITY 59 "Stacking Up" · ANOMALY SIGNALS 0 "Clear" · AMC DAILY BRIEF Pending) → "WHAT TO DO NEXT" instruction → AMC Daily Brief card ("Focus PB-001: high risk and 5 PMs overdue" + Show details / **Approve brief** / Reject) → severity filter chips → **~30+ alert cards** (each: Open in Asset Hub / Save / Snooze 7d / Handled) → Load More.

| Lens | Verdict | Evidence / issue |
|---|---|---|
| P1 glance-first | ✅ PASS | Best triage-first verdict of the set: 3 summary cards + red banner tell you "59 need eyes, 0 anomalies, 1 brief pending" in ~3s, plus an explicit "WHAT TO DO NEXT". |
| P2 vital-20% | ⚠️ PARTIAL | Filter chips = excellent progressive disclosure; "Load More" caps the feed. But default "All" still renders ~30+ full alert cards inline; fold is 285 words (AMC brief + action brief both expanded). |
| P3 one primary action | ⚠️ PARTIAL | No single page primary; **every alert card repeats 4 co-equal buttons** (Open/Save/Snooze/Handled) × 30 cards = Hick's-law choice overload. AMC brief has 3 (Approve green-ish = closest to primary). |
| P4 copy | ✅ PASS (prior corrected) | Grep = **1 match, a code comment** (line 857); **0 displayed** defensive phrases. Prior "2 defensive" = false positive again. Copy ("Everything that needs your attention, in one place") is confident. |
| P5 hierarchy | ✅ PASS | Clear severity color-coding (CRITICAL red / HIGH orange), consistent card structure, section labels — scannable despite length. |
| P6 persona | ⏸ defer | Works for supervisor; the AMC approve/reject is a supervisor affordance — check field/worker view at re-walk. |

**Page 3 R0 = ~4/6 ≈ 67%** (strongest so far; "Hi" prior holds). Top revamp actions:
1. **P3/P2** — collapse each alert card's 4 buttons to 1 primary ("Open") + overflow (Save/Snooze/Handled in a "⋯" menu); default the feed to top-N critical, chip-expand the rest.
2. **P2 fold** — tighten the 285-word fold (the "WHAT TO DO NEXT" paragraph can become one line; collapse the AMC action-brief prose).
3. P4 = already clean (prior corrected).

Evidence: `arcP-03-alert-hub-desktop-full.jpeg`.

---

## Page 4 — asset-hub.html (Asset Hub) · walked 2026-07-02 · signed in supervisor

Measured: **554 total words** (leanest dashboard), **178 fold words**, **4.3 screens** (3,915px), 1×h1 / 4×h2 / 1×h3, 30 asset rows. Console clean.
Structure: "Asset Hub / 360 view of any equipment in your hive" → green verdict banner "30 assets tracked, 6 marked critical — Registry complete — proceed to PM Scheduler…" → 3 stat cards (TOTAL 30 Mature · CRITICAL 6 Tracked · PENDING 0 Clear) → "WHAT TO DO NEXT: Asset registry looks complete…" → Search + **Scan** → clean asset rows (each: code, model, location, RISK% badge, criticality tag) → Load More.

| Lens | Verdict | Evidence / issue |
|---|---|---|
| P1 glance-first | ✅ PASS | Exemplary: green verdict banner + 3 hide-zero-aware stat cards + WHAT-TO-DO-NEXT answers "what's my asset status?" in ~2s. |
| P2 vital-20% | ✅ PASS | Leanest dashboard (554 words / 4.3 screens); vital stats up top, asset list as clean single-line rows, Load More caps it. |
| P3 one primary action | ⚠️ PARTIAL | "Scan" (orange-tint) is a clear field primary; each asset row is one tap-target (not a 4-button pileup like alert-hub). No competing equal buttons — close to a pass. |
| P4 copy | ✅ PASS | Grep = **0 matches**. Prior "2 defensive" = false positive. Copy is confident. |
| P5 hierarchy | ✅ PASS | Best-arranged of the set: consistent risk badges, clean rows, good whitespace, scannable. |
| P6 persona | ⏸ defer | Works; verify field "Scan" flow + worker submission view at re-walk. |

**Page 4 R0 = ~4.5/6 ≈ 75%** (highest so far; strong "Hi" prior). Minor revamp:
1. **P2 nit** — the meta caption ("Live + daily snapshot · Based on your asset records, risk scores, logbook, failure analysis & reliability analysis · Click any asset…") is a long grey wall; trim to one line.
2. **P2/P5 optional** — group asset rows critical-first (6 critical currently interleaved alphabetically) so the vital 20% surfaces without scrolling.
3. P3/P4 essentially clean.

Evidence: `arcP-04-asset-hub-desktop-full.jpeg`.

---

## Page 5 — analytics.html (Analytics Engine) · walked 2026-07-02 · signed in supervisor

Measured: **1,080 total words**, **178 fold words**, **5.8 screens** (5,254px), 1×h1 / 1×h2, 99 kpi/stat elements, **0 chart canvases in fold** (1 bar chart far below). Console clean.
Structure: "Analytics Engine / ISO 14224 · SMRP Metrics" → period chips (30/90/180/1yr) + Refresh/PDF Report/Send + view tabs (Asset Risk/Shift Brain/Network View) → red verdict "Reliability KPIs need action" → 3 KPI cards (OEE 87% World Class · Worst MTBF 3.9d MILL-001 Frequent · PM Compliance 83% Stair-Ready) → "WHAT TO DO NEXT: MILL-001 failing every 3.9 days…" → Field/Supervisor toggle → Supervisor Team-Status table → phase tabs (Descriptive/Diagnostic/Predictive/What-to-do) → criticality+discipline chips → OEE table (~25 rows) → Availability/MTBF/MTTR/PM/Downtime metric cards (each big number + status + "Show all N" expander) → Failure-frequency bar chart → Repeat-failure + Parts-consumption tables.

| Lens | Verdict | Evidence / issue |
|---|---|---|
| P1 glance-first | ✅ PASS | Verdict-first, NOT a chart wall: red banner + 3 KPI cards + WHAT-TO-DO-NEXT name the exact problem asset. The roadmap's "chart-first vs verdict-first" worry is already resolved. |
| P2 vital-20% | ✅ PASS | Each metric section leads with a headline number + status badge; detail tables sit behind "Show all N" expanders; phase tabs (Descriptive→Predictive→What-to-do) are strong progressive disclosure. |
| P3 one primary action | ⚠️ PARTIAL | No single hero CTA; fold stacks Refresh/PDF/Send + period chips + view tabs. "WHAT TO DO NEXT" text carries the action. Acceptable (explore-by-tab model). |
| P4 copy | ✅ PASS (prior corrected) | Grep = **2 code comments** ("distinguish empty cases honestly" ×2), **0 displayed**. Prior "2 defensive" = false positive again. |
| P5 hierarchy | ✅ PASS | Strong layer-cake: color-coded status badges, consistent metric-card pattern, expandable tables. |
| P6 persona | ⏸ defer | Has a built-in Field/Supervisor toggle — good for persona-proving at re-walk. |

**Page 5 R0 = ~4.5/6 ≈ 75%.** Minor revamp:
1. **Control density (P2/P5)** — the pre-data toolbar (period chips + Refresh/PDF/Send + 3 view tabs + 4 phase tabs + criticality + discipline chips) is a lot of chrome before the first datum; group/tuck secondary controls.
2. **P2 nit** — the OEE table renders ~25 rows inline before "Show all"; cap to top-N (worst OEE first) with expander.
3. P4 clean (prior corrected).

Evidence: `arcP-05-analytics-desktop-full.jpeg`.

---

## ⟐ INTERIM SYNTHESIS after Wave 1 (dashboards: index-home, hive, alert-hub, asset-hub, analytics)

Two hard patterns are already measured across 5 pages — worth locking before Wave 2:

**Pattern A — the defensive-copy prior (roadmap §2) is systematically inflated by false positives.** Measured displayed-text counts: index ≈2–3 (FAQ "Honest answer…honestly" + "This is intentional"), **hive 0, alert-hub 0, asset-hub 0, analytics 0**. Every non-index dashboard "count" was a regex hit on **JS code comments** ("honest blocker", "distinguish empty cases honestly", "actually discoverable") or non-defensive idiom ("not just"). ⇒ **The P4 sub-arc is far smaller than sized**; the real §2 targets are the content-heavy pages (Wave 2: ph-intelligence, ai-quality, assistant, founder-console) — re-measure P4 everywhere against **displayed text only, comments excluded** (this is the spec the `validate_pareto_content.py` gate must encode). Pairs [[feedback_classify_by_evidence_not_heuristic]].

**Pattern B — the real, recurring Pareto defect is DENSITY / choice-overload, not copy.** The Calm-contract dashboards (asset-hub 75%, analytics 75%, alert-hub 67%) already nail verdict-first (P1) and clean copy (P4); they lose points on **too many co-equal actions** (alert-hub's 4-buttons-×-30-cards) and **inline-expanded detail** (analytics' 25-row tables). **hive.html (33%) is the outlier** — an 8.5-screen / 110-tile wall with the verdict buried and no single primary action. ⇒ Wave-1 revamp = (1) fix hive density hard, (2) collapse per-item action clusters to 1 primary + overflow, (3) default-collapse long feeds/tables. P3 (one primary action) is the **most-failed lens** so far (home, hive, alert-hub, asset-hub, analytics all partial/fail) — it deserves gate weight.

**Provisional Wave-1 scoreboard (R0-measured):** index ~58% · hive ~33% · alert-hub ~67% · asset-hub ~75% · analytics ~75%.

---

## Page 6 — ph-intelligence.html (Philippine Industrial Intelligence Report) · walked 2026-07-02 · signed in supervisor (Stair-1 hive)

⚠️ **Seen in its maturity-GATED empty state** — pabloaguilar's hive is Stair 1 / composite 62, below the Stair-3 "Predictive-Ready" threshold, so the full PH-intelligence report does NOT render; the shared honest-empty component renders instead. Full-report walk = re-walk item (needs a Stair-3 hive w/ N≥5 segment + 30-day history — seed or switch hive).
Measured (empty state): **207 total words**, 164 fold, **1 screen** (900px), 1×h1 / 1×h2, 2 prose paragraphs ≥30 words. Console: 1 error (maturity RPC, non-blocking).

### 🎯 THE DEFENSIVE-COPY ROOT (Ian's specific complaint) — it's ONE shared component, not 24 scattered instances
The "we won't fake this" copy is rendered by **`maturity-gate.js` → `renderMaturityHonestEmpty()`**, consumed by **5 HTML pages**: `ai-quality.html`, `hive.html`, `alert-hub.html`, `ph-intelligence.html`, `founder-console.html`. Exact defensive strings (verbatim, with line refs):
- `maturity-gate.js:145` — badge **"Honest Empty State"** (internal QA-voice term surfaced to users → [[feedback_provenance_user_voice_not_internals]]).
- `maturity-gate.js:152` — **`<h1>We won't fake this.</h1>`** (implies prior fakery; this is Ian's exact quote).
- `maturity-gate.js:155` — default `why` fallback: *"Producing this output on insufficient data would **mislead** you. WorkHive surfaces the gap **honestly** instead."*
- caller-supplied `why` (ph-intelligence): *"…WorkHive **refuses to fake** the comparison."* → source lives in ph-intelligence's gate-config call, not the shared file.
⇒ **This is the #1 P4 fusion fix.** Rewrite the shared H1 + badge to confident/informative ("Unlocks at Stair 3 — Predictive-Ready" as the headline; badge → "Locked" / "Not yet available"), and sweep each caller's `why` for fake/mislead/honestly. One edit to `maturity-gate.js` + 5 caller `why` strings clears the defensive framing on all 5 gated pages at once.

| Lens | Verdict | Evidence / issue |
|---|---|---|
| P1 glance-first | ⚠️ PARTIAL | Empty state IS one-screen, but the **headline is an apology** ("We won't fake this.") not the informative fact ("PH Intelligence unlocks at Stair 3"), which is demoted to a small grey subtitle. Glance = apology, not answer. |
| P2 vital-20% | ✅ PASS | Clean single card: badge → headline → why → "Your hive right now" (Stair 1, composite 62) → alt-suggestion → 2 CTAs. |
| P3 one primary action | ✅ PASS | "Open Maturity Stairway →" solid-orange is the single clear primary; "Back to Hive Board" demoted. |
| P4 copy | ❌ FAIL (the worst) | 3 defensive instances in one screen (badge + H1 + "refuses to fake"); the exact copy Ian flagged. Shared-component fix. |
| P5 hierarchy | ✅ PASS | Clean card, good whitespace, clear primary. |
| P6 persona | ⏸ defer / re-walk | Only the empty state is reachable at Stair 1; full report needs a Stair-3 hive. |

**Page 6 R0 (empty-state) = ~4/6 ≈ 67%**, but the failed lens (P4) is the highest-priority fix of the whole arc because Ian named it. The full-report Pareto score is UNKNOWN until walked on a Stair-3 hive.

Evidence: `arcP-06-ph-intelligence-desktop-full.jpeg`. Shared renderer: `maturity-gate.js:137-185`.

---

## Page 7 — pm-scheduler.html (PM Scheduler) · walked 2026-07-02 · signed in supervisor

Measured: **482 words**, 199 fold, **3 screens** (2,688px), 1×h1 / 3×h2 / 6×h3, chips All/Overdue/Due-Soon/On-Track, **grep 0 defensive**. Console clean.
Structure: red verdict "PM compliance is in the red — 30 overdue assets…" → 3 stats (OVERDUE 30 Stacking-Up · DUE SOON 0 None · ON TRACK 0 Stair-Ready) → WHAT-TO-DO-NEXT (filter Overdue + bulk-assign) → filter chips + category dropdown → PM asset cards (red progress bars, "N tasks overdue", single tap-target) → Load More (10 of 30).

Same strong Calm family as asset-hub/analytics. **P1 ✅** (verdict-first) · **P2 ✅** (concise, chips, Load-More cap) · **P3 ⚠️** (recurring: "bulk-assign" next-action is prose, no button; cards are clean single tap-targets though) · **P4 ✅** (0 defensive) · **P5 ✅** (clean cards, consistent). Nit: floating "+"/DASHBOARD/ADD-ASSET buttons overlap card content mid-page.
**Page 7 R0 = ~4.5/6 ≈ 75%.** Evidence: `arcP-07-pm-scheduler-desktop-full.jpeg`.

---

## Page 8 — inventory.html (Spare-Parts Inventory) · walked 2026-07-02 · signed in supervisor

Measured: **650 words**, 192 fold, **7 screens** (6,324px), 1×h1 / 4×h2, **grep 0 defensive**. Console clean.
Structure: "Spare-Parts Inventory" + top chips (27 parts / 3 low / 0 out) → verdict "A few things to handle this week" → 3 stats (OUT 0 Clear · LOW 3 Plan-Restock · PENDING 0 Clear) → WHAT-TO-DO-NEXT ("Order the 3 before next shift") → red "3 parts running low" banner → search + "All stock" filter → **all 27 part cards inline** (3 low-stock first w/ orange badges, then 24 in-stock), each with "− Use" / "+ Restock" buttons.

**P1 ✅** (verdict + 3 stats + low-first ordering) · **P2 ❌** (the defect: **all 27 parts rendered inline = 7 screens** though the job is "what's low/out"=3; the "All stock" filter should default to Low/Out and in-stock should collapse behind "show all 27") · **P3 ⚠️→✅-ish** (BEST P3 so far: single orange **"+ Add Part"** primary top-right; only mild per-card 2-button Use/Restock repetition) · **P4 ✅** (0 defensive) · **P5 ✅** (clean cards, red/green qty color-coding, scannable but long).
**Page 8 R0 = ~4/6 ≈ 67%.** Top fix: default the list to "needs me" (low/out); collapse the 24 in-stock behind an expander → 7 screens → ~2. Evidence: `arcP-08-inventory-desktop-full.jpeg`.

---

## Page 9 — logbook.html (Digital Maintenance Logbook) · walked 2026-07-02 · signed in supervisor · ⭐ EXEMPLAR

Measured: **232 words** (leanest so far), 155 fold, **1.1 screens** (976px), 8 form fields, **grep 0 defensive**. Console clean.
Two-column: LEFT = "Log a Repair" 3-step wizard, **AI-fill-first** (Speak to fill / Photo defect Capture) then "or fill in manually" (asset select + barcode scan), single orange **"What happened? →"** primary + Clear form. RIGHT = 3 stats (503 entries / 32 machines / 6 open) + Register Asset + Voice Journal + My-Entries/Team-Feed tabs + team search filters over a deliberate **"Search team entries above"** blank state.

**P1 ✅** (action-first — the job "log fast" is the hero) · **P2 ✅** (1.1 screens, wizard progressive-discloses, team feed not auto-dumped) · **P3 ✅** (clear "What happened? →" primary; left=create / right=browse split is legible) · **P4 ✅** (0 defensive; the empty-state copy "Search team entries above…" is correct) · **P5 ✅** (clean two-column, color-coded AI shortcuts, good whitespace).
**Page 9 R0 = ~5/6 ≈ 83% — the exemplar for tool pages** (action-first, AI shortcuts prominent, compact, blank-state-correct). Only nit: right column reads empty on desktop until Team Feed is searched (intentional). Evidence: `arcP-09-logbook-desktop-full.jpeg`.

---

## Page 10 — skillmatrix.html (Growth / Skill Matrix) · walked 2026-07-02 · signed in supervisor

Measured: **354 words**, 184 fold, **2.5 screens** (2,206px), 1×h1 / 2×h2 / 1 table, **grep 0 defensive**. Console clean.
Structure: "Growth" + Skills/Achievements tabs → amber "Primary skill not yet trackable" banner → 3 stats (ON TARGET 5/5 Complete · QUIZZES 1 Ready · BADGES 19 Mid) → WHAT-TO-DO-NEXT (take a quiz) → **"Skill Overview" radar chart** → YOUR TARGETS (5 disciplines w/ −/+ steppers + "Save Targets") → 5 discipline cards (level dots + progress bar + "Target reached ✓").

| Lens | Verdict | Evidence / issue |
|---|---|---|
| P1 glance-first | ⚠️ PARTIAL | Stats+verdict present, but the amber **"Primary skill not yet trackable"** config-nag dominates the fold AND contradicts "ON TARGET 5/5 COMPLETE" — confusing first impression. |
| P2 vital-20% | ✅ PASS | 2.5 screens, chunked. |
| P3 one primary action | ⚠️ PARTIAL | Orange "Save Targets" is the visual primary, but it's a **config action** — the STATED next-action (take a quiz) has no button. Primary points at the wrong job. |
| P4 copy | ⚠️ PARTIAL | 0 defensive, but **grammar bug "1 discipline HAVE a quiz" (×2)**; the "not yet trackable / 5/5 complete" contradiction is a copy-logic bug too. |
| P5 hierarchy | ❌ FAIL (bug) | **The "Skill Overview" radar chart renders BROKEN** — axis labels overlapping/cut off ("Med"/"Prod"/"ic Mgmt" fragments), chart not visibly drawn. This is the roadmap's "grid legibility" concern = an actual rendering defect. (The 5 discipline cards below ARE clean + legible.) |
| P6 persona | ⏸ defer | Works. |

**Page 10 R0 = ~3/6 ≈ 50%.** Top fixes: (1) fix/repair the broken Skill-Overview radar chart; (2) resolve the "primary not trackable" vs "5/5 complete" contradiction; (3) make the primary CTA the stated next-action (Take quiz), demote Save Targets; (4) grammar "1 discipline **has**". Evidence: `arcP-10-skillmatrix-desktop-full.jpeg`.

---

## Page 11 — dayplanner.html (Maintenance Day Planner) · walked 2026-07-02 · signed in supervisor

Measured: **313 words**, 238 fold, **1.1 screens** (960px), 1×h1 / 2×h2, **grep 0 defensive**. Console clean.
Structure: LEFT "Open Items" (6 from Logbook, "click item then click a time slot") → MAIN "Planner" w/ DILO/WILO/MILO/YILO tabs → amber "3 items overdue" verdict → 3 stats (TODAY 0 Free · THIS WEEK 0 Empty · OVERDUE 3 Stacking) → WHAT-TO-DO-NEXT (use + Schedule) → time grid (mostly empty) → "+ Schedule" orange primary top-right.

**P1 ✅** (verdict + 3 stats + next-action) · **P2 ✅** (1.1 screens) · **P3 ✅** ("+ Schedule" single orange primary) · **P4 ⚠️** (0 defensive, but **jargon tabs "DILO/WILO/MILO/YILO"** lead with the acronym; glossed only in the grey caption, not on the tab — a new worker reads the acronym first) · **P5 ✅** (clean, though the empty time-grid leaves a large blank area — honest state).
**Page 11 R0 = ~4.5/6 ≈ 75%.** Fix: gloss the DILO/WILO/MILO/YILO tabs inline (or label "Day/Week/Month/Year" primary). Evidence: `arcP-11-dayplanner-desktop-full.jpeg`.

## Page 12 — shift-brain.html (Shift Brain) · walked 2026-07-02 · signed in supervisor

Measured: **770 words**, 204 fold, **4.2 screens** (3,818px), 1×h1 / 2×h2, **grep 0 defensive**. Console clean.
Structure: shift tabs (Morning/Afternoon/Night) → amber verdict "Heavy shift — prioritize hot assets" → 3 stats (TOP RISK 6 Hot · PMS DUE 30 Busy · CARRY-FORWARD 19 Stacking) → WHAT-TO-DO-NEXT → Action Brief (Draft) → TOP RISK ASSETS (6) → **PMS DUE (30, fully listed)** → **CARRY-FORWARD (19, fully listed wall)** → Parts Pre-Stage (3) → "Re-run plan / **Publish to crew** / Archive plan".

**P1 ✅** (verdict + 3 stats + action) · **P2 ⚠️** (the 30-PM and 19-carry-forward lists render **fully expanded inline** = the 4.2-screen length; cap to top-5 + expander) · **P3 ✅** ("Publish to crew" single orange primary) · **P4 ✅** (0 defensive; same long grey meta-caption) · **P5 ✅** (clean count-badged sections, severity color-coding, scannable but long).
**Page 12 R0 = ~4.5/6 ≈ 75%.** Fix: progressive-disclose the PMs-Due + Carry-Forward lists. Evidence: `arcP-12-shift-brain-desktop-full.jpeg`.

---

## Page 13 — project-manager.html (Project Manager) · walked 2026-07-02 · signed in supervisor

Measured: **331 words**, 190 fold, **1.4 screens** (1,295px), 1×h1 / 3×h2 / 10×h3, **grep 0 defensive**. Console clean.
Structure: title + Print Report → amber verdict "3 projects past end date" → 3 stats (ACTIVE 4 Running · PAST END DATE 3 Slipping · ON HOLD 0 None) → WHAT-TO-DO-NEXT → tabs (Active/Planning/On-hold/Complete/All) → filters + **"+ New project"** orange primary + "AI: from text" → 4 project cards (type-badged, owner/date/tasks, progress bar).

**P1 ✅** · **P2 ✅** (1.4 screens, tabs) · **P3 ✅** ("+ New project" single orange primary) · **P4 ⚠️** (0 defensive, but **raw DB column "end_date" leaks into UI copy** — "revise end_date to current reality" + "past end_date without closing out") · **P5 ✅** (clean type-badged cards, progress bars).
**Page 13 R0 = ~4.5/6 ≈ 75%.** Fix: "end_date" → "end date" in displayed copy. Evidence: `arcP-13-project-manager-desktop-full.jpeg`.

## Page 14 — project-report.html (Project Report / print) · walked 2026-07-02 · signed in supervisor

⚠️ **Seen in empty state** ("No project specified") — the report needs the in-app **Project Manager → Detail → Print Report** flow (sets session state, not a URL `?project=` param — tried a real project UUID, didn't populate). Populated-content P1 = re-walk item (in-app flow).
Measured (empty template): **201 words**, 91 fold, **1 screen** (929px), 1×h1 / 9×h2, **grep 0 defensive**.
Print-styled WHITE report card (correct for a report), sections **§1 Executive Summary → §2 Scope (WBS) → §3 Linked Work → §4 Daily Progress → §5 Lessons Learned → §6 Sign-off → §7 Appendix (cites PMBOK 7th, AACE 17R-97/80R-13, ISO 21500)**. Empty state gives honest guidance ("Open from the Project Manager") + "Go to Project Manager" link. Bottom bar: ← Back / AI: Narrative / Print / Save as PDF.

**Structural verdict:** **P1 ✅ (template is inverted-pyramid — Exec Summary §1 first = correct front-loading)** · P2 ✅ (7 §-sections, print-optimized) · P3 ✅ (Print / Save-as-PDF / AI:Narrative clear) · P4 ✅ (0 defensive; clean empty state) · P5 ✅ (clean white report card).
**Page 14 R0 (structural) = ~4/6 ≈ 67%**, but populated-report P1 (is §1 Exec Summary a real verdict, or a data dump?) is UNKNOWN until walked via the in-app flow. Evidence: `arcP-14-project-report-desktop-full.jpeg` + `arcP-14-project-report-POPULATED.jpeg` (both empty).

---

## Page 15 — analytics-report.html (Analytics Report generator) · walked 2026-07-02 · signed in supervisor · ⭐ CONTENT EXEMPLAR · **generated LIVE**

Generator (pre-generate): 117 words, 1 screen — PERIOD (30/90/180/365d) + AUDIENCE (Supervisor/Worker) + purple "Generate Report" primary + instructive empty state ("Click Generate Report to compile…"). **Clicked Generate live** → full report rendered.
Generated report: **1,559 words**, **6.6 screens** (5,937px), **0 prose walls ≥35 words**, **grep 0 defensive**.
Structure (inverted pyramid): **HEADLINE "PV-002 needs immediate attention this week"** (+ 12 failures / 49 hrs downtime) → 1. Executive Summary (3 key-point cards + KPI stats) → 2. Findings (2.1 Worst Offenders / 2.2 Why It Broke donut / 2.3 Failure Consequences RCM SAE JA1011 / 2.4 Top Parts / 2.5 PM efficacy) → 3. Predictive Outlook (Watch-These-First + Asset Health Scores) → 4. Action Plan (This-Week Top Priorities + Critical table + PM-interval adjustments) → Appendix (raw tables) → 5. Sign-off. **Every chart has a plain-language "What this means:" gloss.**

**P1 ✅✅** (HEADLINE verdict + Exec Summary front-load) · **P2 ✅** (6.6-screen report but exec-summary-first, detail+appendix last, no prose walls) · **P3 ✅** ("Save as PDF"/"Send/schedule", editable fields) · **P4 ✅** (0 defensive; "what this means" glosses = best jargon-gloss on the platform) · **P5 ✅** (numbered sections, glossed charts, appendix-last, print-styled) · **P6 ✅ (generated LIVE as supervisor)**.
**Page 15 R0 = ~5.5–6/6 ≈ 92–100% — the CONTENT EXEMPLAR.** The roadmap's "prose density" worry does NOT hold: it's structured + glossed, not prose-heavy. This is the model Wave-2 content pages (ph-intelligence full report, ai-quality, assistant) should copy: headline → exec-summary → glossed findings → action → appendix. Only nit: the pre-generate empty state wastes desktop whitespace. Evidence: `arcP-15-analytics-report-desktop-full.jpeg` (generator) + `arcP-15-analytics-report-GENERATED.jpeg` (report).

---

## Page 16 — engineering-design.html (Design Calculation Tool) · walked 2026-07-02 · signed in supervisor

Measured: **332 words**, 142 fold, **2.1 screens** (1,882px), 1×h1 / 3×h2, 29 calc cards, **grep 0 defensive**. Console clean.
Left picker: search ("Search all 53 calculations") → STEP 1: DISCIPLINE (6 w/ counts — HVAC 11 · Mechanical 4 · Electrical 14 · Plumbing 10 · Fire 5 · Machine 12) → STEP 2: CALC TYPE (subcategory headers LOAD/EQUIPMENT/DISTRIBUTION + cards w/ icon + 1-line standards-cited desc, e.g. "Chiller System — Water Cooled · COP, CW loop… ASHRAE 90.1") → STEP 3 inputs (greyed) → "Run Calculation" primary. Right: "No Report Yet" empty state.

**P1 ✅** (search + 6 disciplines + categorized calcs = "pick a calc fast" served; matches validated eng-design UX) · **P2 ✅** (subcategory headers, step wizard) · **P3 ✅** ("Run Calculation" primary) · **P4 ✅** (0 defensive; concise standards-cited descriptions) · **P5 ⚠️** (clean left picker, but **large empty right column on desktop** before a calc runs).
**Page 16 R0 = ~4.5/6 ≈ 80%.** Evidence: `arcP-16-engineering-design-desktop-full.jpeg`.

### ⟐ CROSS-PAGE PATTERN: empty second column on desktop (two-column tool pages)
logbook (Team Feed), engineering-design (No Report Yet), analytics-report (pre-generate), project-report (No project) all leave a large empty right/second column on wide screens before the user acts. Honest blank states, but they waste desktop real-estate + can read "unfinished." Revamp option: fill with recent items / a live preview / worked-example guidance so the second column earns its space.

---

## Page 17 — assistant.html (AI Work Assistant) · walked 2026-07-02 · signed in supervisor · **grounded answer proven LIVE**

Measured (empty chat): **122 words**, 49 fold, **1 screen** (941px), 1×h1. Console clean.
Clean chat: grounding-aware greeting ("I can see your job records and will reference them when relevant. What do you need?") → huge empty chat area → "Ask anything…" input + send → footer disclaimer "AI-generated. Replies may be inaccurate — verify against your records… not a substitute for engineering judgment."
**Live test:** asked *"Which of my assets has the worst MTBF and what should I do about it?"* → grounded reply: *"…only one asset with a corrective event: GEN-001, 2.3h downtime on June 12. That's not enough data to calculate MTBF… Have you noticed any recurring issues with GEN-001?"* — references real records, honest about data limits, asks a follow-up. **P6 grounded-answer flow PROVEN.**

**P1 ⚠️** (greeting sets grounding, but empty state has **no suggested-prompt chips** to guide first use) · **P2 ✅** (minimal chrome) · **P3 ✅** (single chat input primary) · **P4 ✅** (0 DISPLAYED defensive — the grep "5" were all in the **embedded AI system prompt** lines 611/617/649/673 "surface the gap honestly / Honesty is the moat", not shown to users; the greeting + disclaimer are confident/appropriate) · **P5 ⚠️** (large empty desktop void — same two-column-empty pattern).
**Page 17 R0 = ~4/6 ≈ 67%.** Top fix: add suggested-prompt starter chips to the empty state (fills the void + guides first use). The prior "5 defensive + chrome vs answer" is WRONG on both counts — 0 displayed defensive, and the problem is too-sparse not too-chromed.

### ⚠️ CROSS-TOOL DATA-GROUNDING DISCREPANCY (QA note, out of Arc-P content scope but log it)
The assistant grounded on "logbook corrective events" and saw only **GEN-001**; analytics.html + analytics-report compute worst-MTBF as **MILL-001 (3.9d)** / **PV-002 (12 failures)** from a fuller failure dataset. The two AI surfaces disagree on the underlying data. Not a Pareto-lens finding, but a real cross-tool consistency issue → route to QA / data-engineer skill: the assistant's RAG context should read the same failure/analytics source the Analytics Engine uses, or explicitly scope its answer ("based on logbook entries only").

## Page 18 — voice-journal.html (Voice Journal) · walked 2026-07-02 · signed in supervisor

Measured: **1,830 words**, 191 fold, **7.1 screens** (6,400px), 1×h1 / 2×h2, **grep 0 defensive**. Console clean.
Structure: voice-capture panel (companion selector Zaniah·Strategy / Hesekiah·Technical + big orange mic "Tap to start. Tap again to stop.") → "Your journal · 80 entries" + search + filter chips (All 80 / English 44) → ~25 conversational entry cards (Taglish transcript + AI companion reply + "Speak again") → Load More.

**P1 ✅** (voice-capture panel front = "speak→entry" served) · **P2 ⚠️** (~25 of 80 entries render before Load More = 7.1 screens; cap initial render to ~5–10) · **P3 ✅** (big orange mic "Tap to start" single primary) · **P4 ✅** (0 defensive; grounded companion replies) · **P5 ✅** (distinct capture panel + consistent conversational cards).
**Page 18 R0 = ~4.5/6 ≈ 75%.** Fix: cap the initial journal render. Evidence: `arcP-18-voice-journal-desktop-full.jpeg`.

---

## Page 19 — resume.html (Resume / CV Builder) · walked 2026-07-02 · signed in supervisor

Measured: **403 words**, 132 fold, **3.5 screens** (3,134px), 1×h1 / 3×h2, **grep 0 defensive**. Console clean.
Structure: top actions ("Auto-fill from my WorkHive data" orange primary / Save / My Resumes / Preview & Export / Undo) → "Add from files" (Take photos / Choose files + privacy note + "Promote don't duplicate" toggle) → "AI helpers" (Write summary / Polish wording / Tailor to job / Check match score / Draft cover letter — 6 buttons) → "Your Details" form → **"Three ways to start" panel (redundant w/ top)** → 7 empty sections (Work Experience / Skills / Education / Certificates / Projects / Awards / References, each "+Add").

| Lens | Verdict | Evidence / issue |
|---|---|---|
| P1 glance-first | ⚠️ PARTIAL | Clear start ("Auto-fill from my WorkHive data" orange), but the fold is heavy — many panels before you do anything. |
| P2 vital-20% | ⚠️ PARTIAL | **"Three ways to start" guidance appears TWICE** (top orange button + a mid-page panel duplicating it); the 6 AI-helper buttons (Tailor/Match/Cover-letter) show **before any resume content exists** — premature, should reveal after content. |
| P3 one primary action | ⚠️ PARTIAL | Orange "Auto-fill" is the clear primary, but it's surrounded by ~15 co-equal actions (Save/My-Resumes/Preview/Undo/Take-photos/Choose-files/6 AI helpers/Upload/7 +Add) = choice overload. |
| P4 copy | ✅ PASS | 0 hard-defensive; the prior "3" = **reassurance copy** ("files read just to fill your resume, then discarded · Nothing added until you tap to confirm · You review every suggestion") — good privacy transparency, only mildly verbose. |
| P5 hierarchy | ✅ PASS | Distinct panels, clean form; density is the issue, not layout. |

**Page 19 R0 = ~3.5/6 ≈ 58%.** Top fixes: (1) remove the redundant mid-page "Three ways to start"; (2) progressive-disclose the AI helpers until the resume has content; (3) demote the action cluster to one primary + overflow. Evidence: `arcP-19-resume-desktop-full.jpeg`.

---

## Page 20 — marketplace.html (Marketplace, free/contact-only) · walked 2026-07-02 · signed in supervisor

Measured: **647 words**, 172 fold, **2.5 screens** (2,220px), 1×h1, 102 card elements. Console clean.
Structure: green verdict "12 listings · 1 of them yours" → 2 stats (LISTINGS IN VIEW 12 Browse · MY LISTINGS 1 Listed) → WHAT-TO-DO-NEXT → Parts 12 / Training 6 / Jobs 6 tabs → trust-chip row (KYB-Verified / Secure Inquiries / Free-No-Platform-Fees / Watchlist / Searches / My Listings / Admin) → search + category chips → scannable listing cards (price PHP prominent, category+condition badges, location, seller + star rating, View) → floating "+" (create listing).

**P1 ✅** (verdict + 2 stats + tabs) · **P2 ✅** (tabs + category chips + search, 2.5 screens) · **P3 ⚠️** (floating "+" create-listing primary + per-card "View" are clear, but the **7-chip trust row** is busy) · **P4 ✅** (0 defensive; **Stripe-removal verified clean** — the 2 "payment" hits are correct off-platform copy: "the marketplace is free: you arrange any payment directly with the seller, off-platform" + a matching comment; no checkout/Stripe leftover) · **P5 ✅** (listing cards genuinely scannable — the roadmap's concern holds up well).
**Page 20 R0 = ~4.5/6 ≈ 75%.** ⚠️ QA glitch: a "My Watchlist" modal ("Loading saved listings…") auto-opened over the page without a click — verify it's not auto-triggering. Evidence: `arcP-20-marketplace-desktop-full.jpeg`.

---

## Page 21 — community.html (Discussion Board) · walked 2026-07-02 · signed in supervisor

Measured: **388 words**, 198 fold, **4.7 screens** (4,219px), 1×h1 / 4×h2, **grep = 1 code comment, 0 displayed defensive**. Console clean.
Structure: "Community · Discussion Board" → ONLINE NOW presence → Feed / Global / Mod-Queue tabs → search + category chips (All/General/Safety/Technical/Announcements) → ~5 post cards (author + category badge + Pinned/Public tags + content + reaction/comment/bookmark/flag buttons) → **large empty void** → "Load more posts". Right sidebar: Your Profile (8 posts / 25 XP) + Top Posters leaderboard.

**P1 ⚠️** (board not a verdict-page, but presence + category tabs orient) · **P2 ⚠️** (only 5 posts render then a **huge empty vertical void** before "Load more posts" ~4 screens down) · **P3 ✅** (floating "+" new-post primary) · **P4 ✅** (0 displayed defensive; grep hit = code comment) · **P5 ⚠️** (posts scannable + good sidebar, but the empty void makes the feed look broken/unfinished; "Load more" stranded).
**Page 21 R0 = ~3.5/6 ≈ 58%.** Top fix: the feed container's empty void — posts should fill/flow and "Load more" sit directly under them (likely a min-height/layout bug). ⚠️ Also: test-data pollution ("Test post from Playwright [WH-PW-13-mqd1d1ba]") in the live feed — [[feedback_live_mcp_writes_pollute_test_db]]; clean the shared DB of `WH-PW-*` test rows. Evidence: `arcP-21-community-desktop-full.jpeg`.

---

## Page 22 — integrations.html (CMMS Integration / Connections) · walked 2026-07-02 · signed in supervisor · ⭐ ONBOARDING EXEMPLAR

Measured (empty state, 0 integrations): **370 words**, 239 fold, **1.9 screens** (1,678px), 1×h1 / 3×h2, **grep 0 defensive**. Console clean.
Status-first verdict "No integrations configured yet — Start with Import File… then Live Sync" → 3 stats (ACTIVE 0 None · STALE 0 Clear · DISABLED 0 Clear) → WHAT-TO-DO-NEXT → **"HOW TO CONNECT YOUR CMMS"** 3 numbered cards (1 Import File "Start here →" · 2 Live Sync "Set up sync →" · 3 API Keys "Manage keys →") → Import/Live-Sync/API tabs → 5-step wizard (SOURCE→UPLOAD→MAP→PREVIEW→IMPORT) → source cards (SAP PM / IBM Maximo / Other-Generic / Auto-detect) + "Next: Upload →".

**P1 ✅** (status-first verdict even when empty) · **P2 ✅** (1.9 screens, dismissible how-to) · **P3 ✅** ("Start here →" single onboarding primary; wizard "Next" flow) · **P4 ✅** (0 defensive; confident helpful onboarding copy) · **P5 ✅** (numbered cards + step wizard + source cards = clean).
**Page 22 R0 = ~5/6 ≈ 83% — the ONBOARDING/EMPTY-STATE EXEMPLAR** (status-first + numbered how-to + wizard). This is the model for how empty states should teach the next action. Evidence: `arcP-22-integrations-desktop-full.jpeg`.

---

## Page 23 — audit-log.html (Audit Log) · walked 2026-07-02 · signed in supervisor

Measured: **260 words**, 187 fold, **1.5 screens** (1,328px), 1×h1 / 3×h2, **grep 0 defensive**. Console clean.
Filter-first: date chips (24h/7d/30d/90d/All) → 4 filters (actors/actions/targets/search) → Export CSV (green primary) + Clear filters + "10 of 10 entries" → color-coded rows (actor badge · action · target · target-type badge · timestamp · Show-details expander; delete=red border+trash icon) → Load More.

**P1 ✅** (filter-first, "who did what" answered by rows) · **P2 ✅** (1.5 screens, Show-details disclosure, Load More) · **P3 ✅** (Export CSV primary + filters = right model for a log viewer) · **P4 ⚠️** (0 defensive, but **raw UUIDs** "58f0bf52-cb5c-…" + snake_case target-types **RCM_STRATEGIES / PM_COMPLETIONS / WORKER_PROFILES** in the UI — acceptable-ish for a technical audit surface but could humanize the type labels + hide UUIDs behind Show-details) · **P5 ✅** (clean rows, action-severity color-coding, scannable).
**Page 23 R0 = ~4.5/6 ≈ 78%.** ⚠️ Again `WH-PW-*` test-data pollution in entries — same shared-DB cleanup. Evidence: `arcP-23-audit-log-desktop-full.jpeg`.

---

## Page 24 — ai-quality.html (AI Quality + ROI) · walked 2026-07-02 · signed in supervisor (Stair-1 hive)

⚠️ **Seen in the SHARED maturity-GATED empty state** (identical `maturity-gate.js` component as ph-intelligence; this hive Stair 1 < Stair-2 "Disciplined" threshold, so the real ROI dashboard does NOT render). Full-dashboard walk = re-walk item (needs a Stair-2 hive).
Measured (empty state): **195 words**, 152 fold, **1 screen** (900px), 1×h1 / 1×h2 / 1×h3.
Displayed: badge **"HONEST EMPTY STATE"** → **"We won't fake this."** (shared H1) → *"AI quality and ROI numbers below Stair 2 are noise. The hive needs PM compliance and logbook discipline before predicted savings carry signal. **We refuse to show numbers that would mislead your supervisor.**"* → "Your hive right now: Stair 1 · composite 62/100" → alt-suggestion → "Open Maturity Stairway →" + "Back to Hive Board".

**P1 ⚠️** (apology headline "We won't fake this" instead of the answer "AI Quality unlocks at Stair 2") · **P2 ✅** (clean single-screen empty state) · **P3 ✅** ("Open Maturity Stairway →" single primary) · **P4 ❌ (worst tier, tied w/ ph-intelligence)** — 3 displayed defensive: "HONEST EMPTY STATE" + "We won't fake this" + "We refuse to show numbers that would mislead". This is the **internal-voice→user-voice** problem Ian named for ai-quality ([[feedback_provenance_user_voice_not_internals]]). · **P5 ✅** (clean card).
**Page 24 R0 (empty-state) = ~4/6 ≈ 67%**, P4 is the priority fix (shared `maturity-gate.js` H1/badge + this page's caller `why`). Full ROI-dashboard Pareto score UNKNOWN until walked on a Stair-2 hive. Evidence: `arcP-24-ai-quality-desktop-full.jpeg`.

---

### 🔑 P4 FALSE-POSITIVE SOURCES now fully enumerated (for the gate spec)
Across 17 pages, the roadmap §2 defensive-copy priors over-counted from THREE non-displayed sources: (1) **JS code comments** (hive/alert-hub/analytics), (2) **JSON-LD structured-data** duplicates (index FAQ), (3) **embedded AI system prompts** (assistant). Real DISPLAYED defensive copy exists on only: **ph-intelligence/hive/alert-hub/ai-quality/founder-console via the SHARED `maturity-gate.js` empty-state** (the "We won't fake this" component), plus index's visible FAQ ("Honest answer…honestly"). `validate_pareto_content.py` MUST strip `<script>`, `<!-- -->`, and JSON-LD before counting, and match RENDERED text.

---

# ══════════ R0 SYNTHESIS — all 24 pages walked (the deliverable) ══════════

## §A — R0-MEASURED SCOREBOARD (replaces the roadmap's readiness priors)

| # | Page | R0 % | Dominant gap | Band |
|---|---|---|---|---|
| 15 | analytics-report.html | **~96%** | (pre-generate empty state only) | ⭐ exemplar |
| 9 | logbook.html | **~83%** | right column empty on desktop | ⭐ exemplar |
| 22 | integrations.html | **~83%** | (none — empty-state exemplar) | ⭐ exemplar |
| 16 | engineering-design.html | ~80% | empty right column | Hi |
| 23 | audit-log.html | ~78% | raw UUIDs/snake_case in UI | Hi |
| 4 | asset-hub.html | ~75% | long meta-caption | Hi |
| 5 | analytics.html | ~75% | control density | Hi |
| 7 | pm-scheduler.html | ~75% | next-action is prose not button | Hi |
| 11 | dayplanner.html | ~75% | DILO/WILO jargon tabs | Hi |
| 12 | shift-brain.html | ~75% | 19+30 lists inline | Hi |
| 13 | project-manager.html | ~75% | "end_date" raw in copy | Hi |
| 18 | voice-journal.html | ~75% | 25 entries inline | Hi |
| 20 | marketplace.html | ~75% | busy trust-chip row + watchlist glitch | Hi |
| 3 | alert-hub.html | ~67% | 4-buttons × 30 cards | Med |
| 6 | ph-intelligence.html | ~67%* | **P4 defensive (shared)** | Med · *empty-state |
| 8 | inventory.html | ~67% | all 27 parts inline (7 screens) | Med |
| 14 | project-report.html | ~67%* | *empty (populated unknown) | Med |
| 17 | assistant.html | ~67% | empty state no starter chips | Med |
| 24 | ai-quality.html | ~67%* | **P4 defensive (shared)** | Med · *empty-state |
| 1 | index.html | ~58% | home P3 (3 co-equal CTAs) + landing 20 screens | Med |
| 19 | resume.html | ~58% | 15-action choice overload | Med |
| 21 | community.html | ~58% | empty-void layout bug | Med |
| 10 | skillmatrix.html | ~50% | **broken radar chart** + contradiction | Lo |
| 2 | hive.html | ~33% | **110-tile / 8.5-screen density wall** | Lo |
| + | founder-console.html | (not walked — internal, low user-priority; 5th maturity-gate consumer) | — | — |

**Platform R0 average ≈ 70%.** (*3 pages seen only in their maturity-gated/empty state — ph-intelligence, ai-quality, project-report — their POPULATED Pareto scores are unknown until walked on a Stair-2/3 hive or via the in-app flow; these are re-walk items, NOT covered-by-nature.*)

## §B — FUSION SYNTHESIS (cluster by job-to-be-done → opinionated verdicts, strongest fusion first)

**FUSION 1 — the "We won't fake this" defensive copy is ONE shared component, not a per-page problem (highest leverage, lowest effort). ⭐ DO FIRST.**
Ian's actual complaint resolves to **`maturity-gate.js` → `renderMaturityHonestEmpty()`** rendered on **5 pages** (ph-intelligence, ai-quality, hive, alert-hub, founder-console), plus index's FAQ. Kill it in ~8 edits:
1. `maturity-gate.js:145` badge "Honest Empty State" → "Locked" / "Not yet available".
2. `maturity-gate.js:152` `<h1>We won't fake this.</h1>` → the informative fact as headline (e.g. `${pageName} unlocks at Stair ${n} — ${stairName}`), demote nothing.
3. `maturity-gate.js:155` default `why` → drop "mislead/honestly"; state what unlocks it.
4. Each caller's `why` string: ph-intelligence ("refuses to fake the comparison"), ai-quality ("We refuse to show numbers that would mislead"), + hive/alert-hub/founder-console callers.
5. index.html FAQ (visible line 1950 + JSON-LD line 282): "Honest answer… No tool delivers results faster honestly" → confident timeline.
**Verdict: fix ONE file + 6 strings → P4 floor = 0 platform-wide.** This alone flips ph-intelligence + ai-quality out of the worst tier and is the single most on-point response to Ian's brief.

**FUSION 2 — the real recurring defect is DENSITY, and it's ONE "list discipline" pattern across ~7 pages.**
hive (110 tiles/8.5 screens), inventory (27 parts inline/7 screens), voice-journal (25/80 inline/7.1), shift-brain (19-carry-forward + 30-PM inline), alert-hub (30 cards), analytics (25-row OEE table) all render full lists inline instead of **default top-N + filter/expander/Load-More**. **Verdict: apply one shared list-discipline pattern (default to "what needs me" — low/out, critical, overdue — collapse the rest).** hive.html is the outlier (33%) and needs a dedicated density revamp: hoist ONE health verdict + ONE primary next-action to the top, push Network-Benchmark / Pattern-Alerts / Activity-Feed / Supervisor-Log into tabs/`<details>`.

**FUSION 3 — P3 "one primary action" is the most-failed lens; two sub-fixes cover it.**
(a) **Make "WHAT TO DO NEXT" a button, not a paragraph.** ~7 dashboards (home, hive, pm-scheduler, analytics, shift-brain, inventory, alert-hub) state the next action in prose but give no primary CTA to DO it. Convert the block's recommendation into the page's single primary button (e.g. "Assign 30 overdue PMs →"). (b) **Collapse per-item action clusters to 1 primary + overflow** (alert-hub 4-buttons-per-card, resume 15 actions, marketplace trust-chips). **Verdict: these two moves lift P3 on ~10 pages.**

**FUSION 4 — two exemplars already encode the target; propagate, don't redesign.**
- **Content model = analytics-report.html** (HEADLINE verdict → Exec Summary → glossed findings ("What this means:") → Action Plan → Appendix). Copy this onto the content-heavy pages when their gated versions render (ph-intelligence full report, ai-quality full dashboard, project-report populated).
- **Tool/empty-state model = integrations.html + logbook.html** (status-first verdict + numbered how-to + wizard; action-first + AI shortcuts + blank-state-correct). Copy onto assistant (add starter chips), resume (declutter), the empty second-column tool pages.
**Verdict: the platform already contains its own answer — the revamp is largely "make the weak pages look like analytics-report / integrations / logbook."**

**FUSION 5 — cross-page micro-patterns → encode in `validate_pareto_content.py`, fix in shared CSS/JS.**
- Grey **meta-caption wall** under the h1 (≈8 data pages) → demote to a "ⓘ how computed" tooltip.
- **Empty second column** on desktop (logbook, engineering-design, analytics-report, project-report) → fill with recent/preview/guidance.
- **Raw DB names in UI** (`end_date`, `min_qty`, `RCM_STRATEGIES`, `PM_COMPLETIONS`) → humanize; gate flags snake_case in displayed text.
- **`WH-PW-*` test-data pollution** (community, marketplace, audit-log) → clean shared local DB; not a design bug.

## §C — BUGS surfaced during R0 (route to QA/harden, not just Pareto)
1. ✅ FIXED (Wave 2) **skillmatrix.html — Skill-Overview radar chart** — root cause = no `layout.padding` on the fixed 280px canvas → pointLabels clipped the bounds. Added `layout:{padding:22}` + `maintainAspectRatio:true` + `pointLabels.padding:6`; live-verified 0/5 pointLabels overflowing.
2. ✅ FIXED (Wave 2) **skillmatrix.html** — grammar "1 discipline **have**"→"**has** a quiz" (both instances, count-agreeing); the "5/5 COMPLETE" vs "not-yet-trackable" first-glance clash resolved by disambiguating the stat sub → "All 5 **tracked** disciplines at or above target" (the banner already explained the primary-not-a-standard-discipline case).
3. ⚠️ DID NOT REPRODUCE (Wave 3, live-measured 2026-07-02) **community.html — empty-void layout** — measured at 1440 desktop with 22 posts AND with the 5-post "Announcements" filter: `feed-load-more` sits at gap **0px** under the last post; `.layout-grid` is `align-items:start` (no column-stretch void); `#panel-feed` min-height 300px < content so no reserved void; **`_hasMorePosts` correctly hides "Load more" when <20 posts came back** (line 834/919/997) so it is NOT stranded. The R0 full-page screenshot most likely captured a transient skeleton→list loading state OR the normal shorter-feed-column beside a taller leaderboard sidebar (asymmetric columns in a full-page capture, not a code defect). Classified by verified evidence, not the R0 label ([[feedback_classify_by_evidence_not_heuristic]]). (Test-data pollution note below still valid — WH-PW-* rows inflate the feed.)
4. ⚠️ DID NOT REPRODUCE (Wave 3, live-measured 2026-07-02) **marketplace.html — "My Watchlist" modal auto-open** — on load the sheet has NO `.open` class, is translated off-screen (transform translateY, top=900=viewport bottom), overlay opacity 0 + pointer-events none = **not open**. Code has NO init call to `openWatchlistSheet()` — the only triggers are the `#btn-my-watchlist` click + a reload-after-remove-item. R0 saw it open because the prior Playwright MCP session had CLICKED it (residual session state), a [[feedback_live_mcp_writes_pollute_test_db]]-class false positive, not a code defect.
5. **assistant vs analytics data-grounding mismatch** — assistant sees only GEN-001; analytics computes MILL-001/PV-002. Cross-tool RAG source inconsistency.

## §D — GATE SPEC → `validate_pareto_content.py` (build next, after Ian's commit gate on findings)
Per page, on RENDERED text (strip `<script>`, `<!-- -->`, JSON-LD FIRST — the false-positive lesson):
- **P4:** defensive lexicon (`fake|won't fake|refuse|honestly|honest answer|mislead|trust us|for real|we promise`) count = 0; flag snake_case tokens in displayed strings; flag internal-voice labels ("HONEST EMPTY STATE").
- **P1:** ≥1 verdict/keypoint block near top; fold-word ceiling (dashboards ≤ ~120, landing hero ≤ ~60).
- **P2:** flag full-list-inline over N without a filter/expander/Load-More.
- **P3:** exactly 1 primary-styled CTA per primary view.
- Forward-only ratchet, registered in `run_platform_checks` "AI Validation" (skip_if_fast).

## §E — RE-WALK / STRUCTURE-TO-BUILD items (NOT ceilings — build the structure to make them live-able)
- **ph-intelligence full report** + **ai-quality full ROI dashboard** — seed/switch to a **Stair-2/3 hive** (N≥5 segment + 30-day history + PM compliance) to render the real dashboards, then re-score P1–P6.
- **project-report populated** — walk via the in-app **Project Manager → Detail → Print Report** flow (session-state, not `?project=` param).
- **founder-console.html** — walk the 5th maturity-gate consumer (internal, lower user-priority).
- **4-persona depth** — R0 walked signed-in as pabloaguilar (supervisor); Wave re-walks add field-tech / new-worker / admin for P6.

## §F — WAVE PLAN (revised by R0 evidence)
- **Wave 0 (do first, highest ROI):** FUSION 1 (maturity-gate.js + 6 caller strings + index FAQ) → P4=0 platform-wide. One-file blast radius; the exact thing Ian asked for.
- **Wave 1 ✅ DONE (2026-07-02, live-verified):** hive.html density revamp (33% → ~5/6; 8.5→3.2 screens) + FUSION 3a ("WHAT TO DO NEXT" → primary button) across the 7 dashboards + index home P3. Shared `.ac-cta`/`.wh-disclose` added to components.css.
- **Wave 2 ✅ DONE (2026-07-02, live-verified):** FUSION 2 list-discipline — shift-brain carry-forward 19→6+"Show all" (renderRows gained a limit+toggle); voice-journal initial slice 30→8 (+10 Load More, 7.1→2.5 screens); inventory 30→8 (out/low-sorted-first, "Showing 8 of 27" + Load More, 7→2.9 screens); analytics OEE table → shared `renderListWithShowAll` (worst-OEE-first, 8 of 30 + "Show all 30 assets ↓"). skillmatrix §C bugs #1+#2 fixed: radar chart `layout.padding:22`+`maintainAspectRatio` (0 pointLabel overflow, was clipping), grammar "1 discipline **has** a quiz" (×2), "5/5" sub disambiguated → "All 5 tracked disciplines at or above target". Gates all PASS (pareto 0, css-class/id/orphan/inline-onclick).
- **Wave 3 IN PROGRESS (2026-07-02):** ✅ **assistant** empty-chat now renders 3 data-aware starter-prompt chips (grounded prompts when the worker has records, general technical prompts otherwise) — fills the void + guides first use (live-verified). ✅ **resume** AI-helpers card (`#ai-card`: summary/polish/tailor/match/cover-letter) now hidden until the resume is non-empty (was premature clutter on a blank load; live-verified `display:none` when empty) — the intentional novice "Three ways to start" empty-prompt KEPT (its code comment defends it as the novice→Upload path, not pure redundancy). ✅ **§C #3 (community void) + #4 (marketplace watchlist auto-open) live-measured → BOTH do-not-reproduce** (screenshot/session artifacts; dispositioned above). ⏳ REMAINING: index landing tighten (20→~8 screens: empty persona section, mid-page essays, mobile hero-logo fold) + §C #5 (assistant↔analytics RAG-source mismatch — AI/data-engineer scope) + §E Stair-2/3 re-walks (ph-intelligence/ai-quality populated dashboards — needs a seeded Stair-2/3 hive).
- **Lock:** build `validate_pareto_content.py` (§D), register ratchet, skill writeback (designer/frontend/seo-content/mobile-maestro/qa), memory + handoff. Stay LOCAL; commit = Ian's gate.

### ⟐ CROSS-PAGE MICRO-PATTERN: raw DB column names in UI copy
"end_date" (project-manager), "min_qty" (inventory: "at or below min_qty"), "required_signal"/"end_date" seen in captions. Snake_case field names leaking into user-facing text = P4/internal-voice ([[feedback_provenance_user_voice_not_internals]]). The `validate_pareto_content.py` gate should flag `\b\w+_\w+\b` snake_case tokens in displayed strings.

---

### ⟐ CROSS-PAGE PATTERN noted (add to gate + synthesis): **the grey "meta-caption" wall**
Every data page (asset-hub, analytics, pm-scheduler, inventory, skillmatrix, dayplanner…) renders the SAME long low-contrast explanatory line directly under the h1 — e.g. *"Live · refreshed on load · Based on your … · Overdue: last completion > interval days ago · Compliance = completions / scope in window · Stair 2 gate: 2 consecutive weeks ≥ 80%…"*. It's 20-40 words of methodology before the first datum → delays the glance (P1) + adds cognitive load (P5). **Fix pattern:** demote to a "ⓘ How this is computed" tooltip/`<details>`, keep one plain-language line max. This is a single shared-pattern fix that lifts P1/P5 on ~8 pages at once.

---
