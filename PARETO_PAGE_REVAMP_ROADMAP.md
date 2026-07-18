# Arc P — The Pareto Page Revamp (concise, scannable, confident, well-arranged)

**Created:** 2026-07-02 · **Owner:** Ian + Claude · **Status: R0 COMPLETE + GATE BUILT + WAVE 0 + WAVE 1 SHIPPED (local, at Ian's commit gate).** All 24 nav pages live-walked (platform R0 avg ≈ 70%). `validate_pareto_content.py` built + registered (`pareto-content`, ratchet); **gate still PASS at 0 defensive phrases after Wave 1.** **Wave 0 (defensive-copy kill): gate 10 → 0** (P4 floor met). **Wave 1 (2026-07-02) DONE + live-verified (0 console errors, desktop+mobile):** (a) **hive.html density revamp — the 33% outlier → ~5/6 lenses**: verdict HOISTED above presence/focus (P1), `#ss-action` now ends in a data-driven primary CTA button ("Assign 30 overdue PMs →") (P3), 6 co-equal ghost buttons → one "⋯ More" overflow menu (P3), Network-Benchmark/Pattern-Alerts/Activity-Feed collapsed into `<details class="wh-disclose">` + Supervisor-Action-Log default-collapsed (P2) — **8.5 → 3.2 screens (−62%)**; (b) **FUSION 3a — "What to do next" → primary button** on pm-scheduler/analytics/shift-brain/inventory/alert-hub/asset-hub (each CTA applies the filter / scrolls to the list / navigates, per branch) + **index home P3** (first role-action = solid primary, "Secure account" nudge demoted from solid-orange). NEW shared components in `components.css`: `.ac-cta` (primary next-action button) + `.wh-disclose` (progressive-disclosure) — inlined on the 4 pages that don't `<link>` components.css. **Wave 2 (2026-07-02) DONE + live-verified:** FUSION 2 list-discipline (shift-brain carry 19→6+"Show all"; voice-journal + inventory initial slice 30→8 with Load More, 7→~2.5-2.9 screens; analytics OEE table → top-8 "Show all" worst-first) + skillmatrix §C bugs fixed (radar chart `layout.padding` → 0 pointLabel overflow; "1 discipline **has** a quiz" grammar; "5/5" sub disambiguated). Gates all PASS. NEXT = Wave 3 (resume/community/assistant declutter + index landing 20→~8 screens + remaining §C bugs [community empty-void, marketplace watchlist auto-open, assistant↔analytics grounding mismatch] + §E Stair-2/3 re-walks). Findings/synthesis: `PARETO_R0_FINDINGS.md`.
**WAVE 3 REMAINDER + §E RE-WALK COMPLETE (2026-07-02, second turn; local, gate-clean, live-verified, at Ian's commit gate).** Driven from a 5-agent read-only mapping fan-out, applied, live-walked as Pablo Aguilar / Lucena. Shipped: (1) **FUSION 5 meta-caption wall** killed platform-wide via one `renderSourceChip` `method[]` arg -> `<details class="wh-method">` disclosure + JS-injected CSS (reaches Tailwind pages); `notes:`->`method:` on 8 pages. (2) **audit-log humanize** (snake_case badge -> Title Case, raw UUIDs behind Show-details; a TDZ ReferenceError caught+fixed live). (3) **asset-hub critical-first** (stable sort, verified 6/6/15/3). (4) **assistant RAG scope-label** (local fallback; server align = Ian-gated deploy). (5) **index landing 20->~8 screens** (Problem section MERGED into the 4 Gaps as "The gap:" lines, personas de-sparsed, hedges killed in visible+JSON-LD, docHeight 10,321->8,686px; mobile hero CTA now in-fold). (6) **§E ph-intelligence + ai-quality POPULATED re-walk** via a temp Stair-3 readiness bump (reverted): both ~5/6 (up from empty-state ~67%), P4 clean after fixing 11 discovered prose em dashes. All gates green (pareto P4=0, seo 6/6, source-chip/jargon/structural). **NEXT: platform-wide em-dash P4 sweep+validator; full 4-persona walks (P6); project-report populated; dayplanner/pm re-verify.** Details: `PARETO_R0_FINDINGS.md` top status block.

**Spine of record.** Sources indexed in memory `reference_pareto_content_design_sources` (retrieve before grading any page). **R0 findings + synthesis of record: `PARETO_R0_FINDINGS.md`** (per-page P1–P6 verdicts + evidence screenshots `arcP-*` + §B fusion verdicts + §D gate spec + §F wave plan).

> **R0 headline (2026-07-02):** Ian's "we won't fake this" complaint = **ONE shared component** (`maturity-gate.js` "We won't fake this" empty-state on 5 pages) + index's FAQ — fixable in ~8 edits → P4 floor 0 platform-wide (Wave 0, do first). The defensive-copy §2 priors were 3× over-counted (code comments / JSON-LD / AI system prompts — displayed count is far lower). The REAL recurring defect is **DENSITY / progressive-disclosure** (hive.html 33% is the outlier — 110 tiles/8.5 screens) and **P3 "one primary action"** (the "WHAT TO DO NEXT" block is prose, not a button, on ~7 dashboards). Exemplars to propagate: **analytics-report** (content), **integrations + logbook** (tool/empty-state).

---

## §0 — THE ASK (Ian, 2026-07-02) + refined/extended intent

**Ian's words:** revamp every feature page on the **Pareto principle** — displayed words should be **concise, key points, understandable at a glance** (you should NOT have to read every sentence). The **visual UI/UX and arrangement of things** must truly improve. Prove it with a **live MCP persona deep end-to-end journey on every feature page**. And kill the **defensive/apologetic copy** ("we won't fake this…", in ph-intelligence / hive board) — it reads as if we were faking before; it's beneath the product.

**Refined into 6 measurable lenses (the "Pareto pass" rubric — how each page's % is computed):**

| # | Lens | A page PASSES the lens when… | Source |
|---|---|---|---|
| **P1** | **Glance-first (verdict/key-points)** | the page's ONE job is answered by a verdict or key-points block graspable in ~5s without reading prose; conclusion is front-loaded (inverted pyramid) | NN/g scan (~20-28% of words read); Calm Dashboard verdict-first |
| **P2** | **Vital-20% prominent, rest progressive-disclosed** | the high-impact 20% is visually dominant; secondary detail is in `<details>`/tabs/"show more", not a wall; hide-zero tiles | NN/g Pareto; Calm/List-view contracts |
| **P3** | **One obvious primary action** | exactly one primary CTA per view; secondary actions demoted; no competing equally-weighted buttons | Hick's law; Arc V effortless |
| **P4** | **Confident, concise, jargon-glossed copy — ZERO defensive hedging** | verb+object microcopy; no "we won't fake / honestly / really works / trust us / for real"; jargon has a gloss; no em dashes | NN/g 3 C's; GOV.UK plain English; Arc Y L1 |
| **P5** | **Visual hierarchy & arrangement** | clear size/weight/color hierarchy; related things grouped; generous whitespace; scannable structure (headings, bullets, bold key terms), not prose walls | Arc W visual; NN/g layer-cake |
| **P6** | **Live persona-proven** | field-tech / supervisor / new-worker / admin can each complete the page's core job in a deep E2E walk and the glance-comprehension holds live | [[feedback_deep_mcp_walk_every_page]] |

**Page % = lenses passed (P1–P6) / 6, MEASURED in the R0 walk** ([[feedback_measured_percent_not_qualitative_done]] — the priors below are readiness BANDS, not scores). Arc target: every feature page P1–P6 = 100%, gated.

**Extended — dimensions Ian didn't name but the sources demand (add to scope):**
- **Consistency / one-term-per-concept** across pages (design-system tokens; same label for the same thing).
- **Mobile conciseness** — even tighter on small screens; the glance-block must survive 375px (mobile-maestro).
- **Information scent** — nav/button/link labels predict what you'll get (pairs Arc Y).
- **Cognitive-load ceiling** — Miller 7±2: cap simultaneous choices/tiles per view; chunk.
- **Empty/loading/error states** are also copy surfaces — apply P4 there too (designer skill: specify every state).
- **Measure, don't vibe** — a `validate_pareto_content.py` gate makes the %s ratcheted, not opinion.

---

## §1 — METHOD (reuse the harness, don't rebuild)

Live MCP persona deep E2E journey per page, driven by the **existing** browser-CI persona harness (`browser_ci_persona_walk.mjs`) + Playwright MCP for the human-eye pass — NOT a new tool ([[reference_playwright_mcp_reuse_mega_gate]], [[feedback_playwright_live_every_phase]], [[feedback_soft_judge_do_it_yourself]]). Per page: walk it live as field-tech / supervisor / new-worker / admin; capture the P1–P6 verdict WITH evidence (screenshot + measured word/element counts), fix, re-walk. Synthesis is the deliverable, not the findings list ([[feedback_synthesis_not_just_audit]]).

**Instruments to reuse/extend:** `score_ia_streamlining.py` (KEEP/CONSOLIDATE/MOVE/REMOVE), the Calm Dashboard spec, Arc W/Y ratchets, axe-core. **New gate to build:** `validate_pareto_content.py` — per page: defensive-phrase count = 0 (P4), words-per-primary-view ≤ ceiling (P1/P2), ≥1 verdict/keypoint block (P1), exactly 1 primary CTA (P3), reading-grade ≤ target (P4). Forward-only ratchet, registered in `run_platform_checks`.

---

## §2 — THE DEFENSIVE-COPY CLEANUP (P4, measured today — a real, sized sub-arc)

Scan already ran (broad regex; verify each in context): defensive/apologetic/hedging phrases per page —
`founder-console 36 · index 9 · ai-quality 8 · hive 5 · assistant 5 · resume 3 · ph-intelligence 3 · asset-hub 2 · analytics 2 · alert-hub 2 · shift-brain 1 · logbook 1 · dayplanner 1`.
The anti-pattern classes to kill: **"we won't fake / not faking"** (implies prior fakery), **"honestly / really / actually / for real / trust us / we promise"** (hedging that signals distrust of the user), over-explaining that restates the obvious. Replace with confident verb+object statements of what the thing IS/DOES. **P4 gate floor = 0 defensive phrases platform-wide.**

---

## §3 — PER-PAGE SCOREBOARD (24 nav feature pages; % = R0-measured, priors = readiness band)

Readiness prior heuristic: **Hi** = already Calm-Dashboard opt-in + low defensive copy; **Med** = opt-in but copy debt OR simple tool; **Lo** = content-heavy + defensive copy, no calm contract. All targets = P1–P6 100%.

**R0-MEASURED (2026-07-02 live walk) — the `% (R0)` column now holds measured scores; "Measured gap" replaces the speculative priors. Full evidence per page in `PARETO_R0_FINDINGS.md`.**

| # | Page | Job-to-be-done (its "one thing") | Measured gap (R0) | % (R0) |
|---|---|---|---|---|
| 1 | index.html (landing + signed-in home) | "what do I do right now?" | home P3 = 3 co-equal CTAs (brightest = "Secure account" toast); landing 20.6 screens; FAQ "honestly"; mobile hero logo eats fold | **~58%** |
| 2 | hive.html | hive health verdict + next action | ⚠️ WORST — 110 tiles / 8.5 screens, verdict buried, no primary CTA; defensive=0 (prior "5" = code comments) | **~33%** |
| 3 | alert-hub.html | which alerts need me now | strong triage-first; 4-buttons × 30 cards choice overload; defensive=0 (prior "2" false) | **~67%** |
| 4 | asset-hub.html | asset status at a glance | verdict-first + clean rows; long meta-caption; defensive=0 (prior "2" false) | **~75%** |
| 5 | analytics.html | the KPI verdict, not a chart wall | already verdict-first (NOT a chart wall); control density; defensive=0 (prior "2" false) | **~75%** |
| 6 | ph-intelligence.html | the PH-market insight, key points | *empty-state only (Stair-1)*; **P4 defensive via shared maturity-gate.js**; full report = re-walk | **~67%\*** |
| 7 | pm-scheduler.html | what's due / overdue | strong Calm pattern; next-action is prose not button; defensive=0 | **~75%** |
| 8 | inventory.html | what's low / out | all 27 parts inline (7 screens); best P3 ("+Add Part"); defensive=0 | **~67%** |
| 9 | logbook.html | log an entry fast; recent at a glance | ⭐ EXEMPLAR — action-first, AI shortcuts, 1.1 screens; defensive=0 (prior "1" false) | **~83%** |
| 10 | skillmatrix.html | who can do what, gaps | ⚠️ BROKEN radar chart; "5/5 complete" vs "not trackable" contradiction; grammar bug; defensive=0 | **~50%** |
| 11 | dayplanner.html | today's plan, one view | verdict + "+Schedule" primary; DILO/WILO/MILO/YILO jargon tabs; defensive=0 (prior "1" false) | **~75%** |
| 12 | shift-brain.html | handover key points | verdict + Publish-to-crew primary; 30-PM + 19-carry-forward inline; defensive=0 (prior "1" false) | **~75%** |
| 13 | project-manager.html | project status verdict | verdict + "+New project" primary; "end_date" raw in copy; defensive=0 | **~75%** |
| 14 | project-report.html | the report, front-loaded | *empty (no project)*; template IS inverted-pyramid (§1 Exec Summary); populated = re-walk (in-app flow) | **~67%\*** |
| 15 | analytics-report.html | the analytics narrative, key points | ⭐⭐ CONTENT EXEMPLAR — generated LIVE: HEADLINE→ExecSummary→"what this means" glosses→Appendix | **~96%** |
| 16 | engineering-design.html | pick a calc fast | validated picker (search + 6 disciplines + 1-line descs); empty right column; defensive=0 | **~80%** |
| 17 | assistant.html | ask + get a grounded answer | grounded-answer PROVEN live; empty state lacks starter chips; defensive=0 (prior "5" = system prompt) | **~67%** |
| 18 | voice-journal.html | speak → captured entry | mic "Tap to start" primary; 25/80 entries inline; defensive=0 | **~75%** |
| 19 | resume.html | build/upload → ATS resume | 15-action choice overload; "3 ways to start" duplicated; defensive=0 (prior "3" = reassurance) | **~58%** |
| 20 | marketplace.html | find/list a service (free) | scannable cards; busy 7-chip trust row; Stripe-removal clean; ⚠️ watchlist modal auto-open | **~75%** |
| 21 | community.html | see/post, onboarding | ⚠️ empty-void layout bug ("Load more" stranded); scannable posts; defensive=0 | **~58%** |
| 22 | integrations.html | connect a system | ⭐ ONBOARDING EXEMPLAR — status-first + numbered how-to + wizard; defensive=0 | **~83%** |
| 23 | audit-log.html | who did what | clean filter-first + Export-CSV; raw UUIDs/snake_case types in UI; defensive=0 | **~78%** |
| 24 | ai-quality.html | AI trust verdict | *empty-state only (Stair-1)*; **P4 defensive via shared maturity-gate.js** ("we refuse to show numbers that would mislead"); full dashboard = re-walk | **~67%\*** |
| + | founder-console.html (internal) | founder ops | not walked (internal, low user-priority); 5th maturity-gate consumer — same shared P4 fix applies | — |

*\* seen only in the maturity-gated/empty state; POPULATED Pareto score unknown until walked on a Stair-2/3 hive or via the in-app flow (re-walk items in `PARETO_R0_FINDINGS.md` §E — build the structure, not a ceiling).*

**Platform R0 average ≈ 70%.** Fusion verdicts + ranked fixes: `PARETO_R0_FINDINGS.md` §B. Gate spec: §D. Revised wave plan: §F.

(Non-nav/utility pages — status, symbol-gallery, validator-catalog, promo-poster, offline-fallback, *-test, *.backup — are OUT of the user-facing Pareto scope; test/backup files are removal candidates, not revamp targets.)

---

## §4 — SEQUENCE

1. **P0 study (measure the denominator):** build `validate_pareto_content.py` skeleton + run the P1–P6 rubric live across all 24 → fill the `% (R0)` column with MEASURED scores (replaces priors). Lead with the synthesis: which pages share a job → could fuse.
2. **Wave 1 — the dashboards** (index, hive, alert-hub, asset-hub, analytics): highest traffic + already calm-contract → biggest Pareto lift; verdict-first + hide-zero + defensive-copy = 0.
3. **Wave 2 — the content-heavy** (ph-intelligence, ai-quality, assistant, reports): prose→key-points, internal-voice→user-voice, defensive→confident.
4. **Wave 3 — the tools** (logbook, inventory, pm-scheduler, skillmatrix, eng-design, resume, voice-journal, dayplanner, shift-brain, project-*, marketplace, community, integrations, audit-log): one-primary-action + scan-first.
5. **Lock:** `validate_pareto_content.py` registered + per-page ratchet; Calm/Arc-W/Arc-Y ratchets stay green; skill writeback (designer, seo-content, frontend, mobile-maestro, qa-tester); memory + handoff.

**Floor / exit:** every nav feature page P1–P6 = 100%, **each proven by a live 4-persona deep walk**, defensive-phrase count = 0 platform-wide, gate registered + forward-only. Stay LOCAL; commit/deploy = Ian's gate.
