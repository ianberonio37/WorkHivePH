# STREAMLINE ROADMAP — Tile-Level Dedup + AI-Display Unification

_Authored 2026-06-12 from the first platform-wide LIVE `__UFAI.inventory()` run (28/28 pages, signed-in, hive Baguio `9b4eaeac`). This is the mission hub doc — the single source of truth for the streamline arc. Status table at the bottom is updated as phases land._

> **Ian's charter (verbatim, 2026-06-12):** "I am still not contented.. the display still cluttered or redundant, unnecessary tiles which is already displayed by other pages, all AI displays also fragmented, that's what my streamline all about."

> **Doctrine (carried from Phase 1–3 surveyor + Phase 4 precedent):** tools SURFACE, Ian DISPOSES. No tile is removed, no UI collapsed, without a verdict in this doc's disposition column. Extend existing tools, never reinvent. Every phase ends gate-green, reversible, LOCAL-only (no push — Ian-gated).

---

## 1. Ground truth — what the live run found (B1, DONE 2026-06-12)

First-ever live-merged corpus: **28 pages · 91 info-units · 28 live dumps** → `ia_inventory_corpus.json` + `streamlining_survey.md` (map) + `streamlining_plan.md` (rubric, 15 rows / 12 queued).

**The honest headline:** at page-open state, tile-level *duplication* is nearly drained — the canonical/parity arc + Phase-4 page consolidation already did that work. Verified live: the hive board renders just 3 KPI tiles + a detail panel (10s settle, not a race); exact-label duplication across pages = **1** (Pending approval); same-value duplication = **0** (pages read canonical `v_*_truth`).

What remains, in order of user-felt weight:
1. **AI-display fragmentation** (the larger half — Ian's "all AI displays also fragmented"): 3 tiers mapped in `AI_SURFACE_MAP.md`; Tier 2 split brain + ~14 persona-less Tier-3 surfaces.
2. **Label ambiguity, not duplication**: look-alike tiles with different subjects/scopes that don't say so (worker-vs-hive "overdue", assets-vs-parts "Pending approval").
3. **Corpus hygiene**: retired predictive.html still carries 7 tiles and pollutes every survey.

---

## 2. Track T — Tile-level verdicts (12 queued rows from the rubric)

Live values shown. **Disposition column is Ian's** — empty until he rules. Recommended = my critic pass over the deterministic rubric, corrected for stale facts (rubric proposed retired `predictive.html` as a canonical home).

| # | Finding (live) | Pages | Recommended verdict | Why | **Ian's disposition** |
|---|---|---|---|---|---|
| T1 | **"Pending approval"** = assets (asset-hub) vs parts (inventory) | 2 | **RELABEL** → "Pending assets" / "Pending parts" | The one true Major: same label, two meanings. Same-named ≠ same-subject. | — |
| T2 | **risk/hot/critical** job: High-sev alerts 32 + AMC parts (alert-hub) · Critical assets 6 (asset-hub) · Top risk this shift (shift-brain) · 3 risk views (predictive, RETIRED) | 4 | **KEEP-distinct**; canonical risk home = **asset-hub** (NOT predictive); predictive → T4 | Alerts ≠ per-asset risk ≠ shift lens; all read one `v_risk_truth`. Rubric's "canonical → predictive" was stale (Phase 4 retired it). | — |
| T3a | **due-soon**: Tasks today/week (dayplanner, *worker*-scoped) · Due this week 25 (pm-scheduler, *hive*) · PMs due (shift-brain, *shift*) | 3 | **KEEP + scope chips** ("yours" / "hive" / "this shift") | Distinct scopes wearing similar words — Phase-3 walkthrough flagged exactly this as a confusing novice path. Fix the label, not the tile. | — |
| T3b | **late/overdue**: Overdue tasks 3 (worker) · Overdue PMs 5 (hive) · Past end date (projects) | 3 | **KEEP + scope chips** (same treatment) | Distinct subjects; the ambiguity is unstated scope. | — |
| T3c | **healthy/on-track**: On track PMs · Healthy assets (retired pg) · On-target workers | 3 | **KEEP-distinct, no action** | PMs ≠ assets ≠ workers; Phase 3 already cross-subject-downgraded this. | — |
| T4 | **predictive.html** retired but still surveyed (7 tiles incl. 3 risk views) | 1 | **EXCLUDE from survey scope** (`EXCLUDE_RE` in `tools/survey_ia_redundancy.py`) | Not user-reachable; pollutes every future map. File stays on disk per Phase-4 decision (old deep-links don't 404). | — |
| T5 | **7 extra-path body links** (asset-hub ×3 · integrations/inventory/ph-intel/plant-conn/pm-scheduler/voice-journal ×2) | — | **KEEP all, no action** | Contextual drill-downs from the hive hub + index funnels earn their place (Hick cost ≈ 0 here). | — |
| T6 | **detail_panel ×15 · .simple-card 3-header ×17 · .sum-card ×2** | 15+ | **KEEP (design system), no IA action** | Each instance renders its own page's data (Jakob). Copy-paste cost = the separate jscpd/Architect component-extraction track, not IA. | — |

**Net tile work if T1/T3a/T3b/T4 accepted:** 1 relabel pair + scope chips on ~5 tiles + 1 surveyor scope line. Small by design — the platform already converged at the number level; this closes the *label* level.

### Track T implementation discipline (B4)
- Each accepted row = one commit-sized change, live-verified via Playwright MCP on the touched pages.
- KPI-registry consumers updated when any tile label moves (`validate_user_facing_kpi_canonical.py` stays green).
- Re-run `tools/survey_ia_redundancy.py` + `tools/score_ia_streamlining.py` after changes → the map must show the finding cleared (forward-only proof).
- Dispositions recorded in `promotion_dispositions.json` (the standard sweep mechanism — the 06-08 candidates were queued but never dispositioned; these supersede them).

---

## 3. Track A — AI-display unification (the big half)

Source of truth: **`AI_SURFACE_MAP.md`** (3-tier audit + research-synthesized migration order + ready-to-execute grounded designs). This roadmap sequences it and records what the companion arc already delivered. The fix is NOT "everything in the chat bubble" — it's **one brain + one persona + one memory** entering through `ai-gateway`; deterministic tools keep their pages and become invocable.

| Phase | What | State / exit criterion |
|---|---|---|
| **A0 — Eval gate** | Freeze companion safety/grounding baseline; block regressing steps | ✅ **DONE** (companion arc): delivery gate L0 (`tools/companion_delivery_gate.py`), surface battery (`__CSURF`), per-dimension gates (`companion-dim-gate` G0), behaviour walk A–H green. Stronger than the map asked. |
| **A1 — Converge the brain = unify memory** (map Steps 1+2, MERGED) | ✅ **ALREADY SHIPPED 2026-06-07** (found during §9.6 audit): assistant.html invokes `ai-gateway` agent `assistant`, envelope-unwrap fixed, Cloudflare worker demoted to fail-open fallback. **LIVE-PROVEN 2026-06-12** (question → ai-gateway 4.8s, worker did not fire). | Remaining: residual verification only — cross-surface memory proof (assistant statement resurfaces in widget `agent_memory`) + eval gate run. ⚠ BUT the brain behind it answers PM-overdue from the flat-30 proxy → **P10**. |
| **A2 — Fold conversational Tier-3** (map Step 3) | asset-hub Asset Brain Q&A + hive Coach → Companion | ⚠️ **Needs Ian's design decision** (see Open Decisions D2). Note: `STRUCTURED_PASSTHROUGH_AGENTS` now EXISTS (companion arc), so Option A's mechanism is half-built; the map's grounded re-scope recommends Coach=Option B (structured tool + persona), Asset Brain=Option A/setContext. Exit: −2 bespoke chat UIs (or persona-consistent tools), grounding intact (`cited[]` survives), journey specs green. |
| **A3 — Tool invocation** (map Step 4) | Gateway route `"action"` → `voice-action-router`; companion renders narration + **confirm chips** (never auto-apply); `query.ask` falls through to chat | Exit: "I replaced the V-belt on P-5" → `logbook.create` intent + chip, NOT applied; new probe in the bank. Blast: widget action layer. |
| **A4 — Persona/standards pass** (map Step 5) | Prepend `buildPersonaBlock()` to remaining narrative fns: `engineering-calc-agent`, `engineering-bom-sow`, `analytics-orchestrator` plan, `project-orchestrator`, `intelligence-report` (math stays bare — WAT split) | Exit: `validate_persona_contract.py` green; spot-check one narrative in-voice. Blast: low, additive. |
| **A5 — Verify end-to-end** | Re-run the Companion Stack Battery (`companion_battery.js` Phase-7 capstone) across the converged surfaces + companion mega gate | Exit: memory cross-surface proof on the REAL unified stack; verdict major:0; wiring-probe roadmap (separate mission) inherits a converged target. |

**Guardrails (carried):** free-tier-only chain · fail-open to plain chat · hive isolation `.eq('hive_id')` · rate-limit first · don't rewrite voice-handler.js (converge BEHIND the gateway) · eval-gated every phase · each phase reversible via git restore.

---

## 4. THE UNIFIED ROADMAP (final fold, 2026-06-12 — absorbs the audit findings P1–P14, the tile verdicts T1–T6, the AI track A1–A5, AND the §11 synthesis fusions F1–F8 into ONE sequence. This table supersedes everything above it; every work item lives in exactly one phase.)

**THE TWO GROUPS (Ian, 2026-06-12 — the roadmap's shape in one sentence):**
- **GROUP A — FIX (S1–S4):** make what exists TRUE — correct numbers (S1), relight dark tiles (S2), honest labels (S3), complete map (S4). All P-findings live here. No design judgment needed; correctness only.
- **GROUP B — STREAMLINE (S5–S8):** make what's true ONE — shared strips (S5), one Action Brief (S6), one Companion (S7), page fusions (S8). All F-fusions + T-verdicts live here. **Anchor principle (§11): Group B fuses ONTO the Analytics Engine** — fix the engine first (Group A), then everything renders slices of it.
- S0 = the map both groups stand on · S9 = wrap. FIX before STREAMLINE: never fuse surfaces onto numbers that are still wrong.

| Phase | Name | Contents (every item placed once) | Exit criterion |
|---|---|---|---|
| **S0** ✅ | Map + audit + synthesis | B1 live inventory 28/28 · §7 tile families · §8 analytics 4×29 · §9 per-page 28/28 · §10 findings register · **§11 synthesis F1–F8** | DONE 2026-06-12 |
| **S1** | **One Truth for PM** | P1 (shift-brain fetchPMsDue + chip + docstring) · P5 (predictive.py FREQ_DAYS ×2) · P10 (ai-orchestrator PM prompt) · P7 (validator vocabulary-coverage teeth) · P6 (calendar reads baked signals) · register the new consumers + `pm_due_soon` metric | shift-brain, analytics P3, and the assistant all answer **5 overdue** live; validator fails on any stale map |
| **S2** | **Relight dark tiles** | P9 (seed `asset_nodes.pm_asset_id` + honest "not linked" caption) · P14 (guard `getPendingEntries()` → cloud-only degrade + toast; audit other IDB awaits) | asset 360 shows PM history; logbook feed survives broken IndexedDB |
| **S3** | **Honest labels** | P2 · P3 · P8 · P11+P12 (stock semantics) · T1 RELABEL pending-approval · marketplace current_tab removal | every caption matches its derivation, spot-walked |
| **S4** | **Survey completeness** | P13 (rag-tag `oh-*` + plant-conn cards, widen battery selector) · T4 (predictive → EXCLUDE_RE) · re-run inventory→survey→rubric | corpus complete; T2 cluster complete; predictive out of map |
| **S5** | **Shared strips** — the tile-level fusion (was "tile execution"; now = F2/F3/F4) | **F2** ONE risk-strip component (asset-hub home; index/shift-brain/alert-hub embed) · **F3** ONE parts-action list (inventory owns; count chips derive from it) · **F4** ONE pm-due strip (pm-scheduler owns) · T3 scope chips ride the strips · T2/T3c/T5/T6 keeps recorded in `promotion_dispositions.json` | the 3 strips are the ONLY renderers of their numbers; KPI-canonical gate green |
| **S6** | **ONE Action Brief** — the flagship AI fusion (F1, anchored per §11) | The brief engine = **the Analytics Engine's prescriptive phase + a `horizon` param** (shift/today/strategic; shift horizon = scoped live recompute) — NOT a new orchestrator. `amc-orchestrator` + `shift-planner-orchestrator` DELETED as duplicate brains; ONE brief renderer; alert-hub=today, shift-brain=shift slice, analytics/report=strategic slice; cross-page AI reminders die; embeds S5's strips | one engine row drives all three surfaces live; AMC + shift-planner orchestrators gone; eval gates green |
| **S7** | **ONE Companion** (F8 = Track A remainder) | A1 residual (cross-surface memory proof) · A2 fold Asset-Brain Q&A + hive Coach (D2: map's rec) · A3 action route + confirm chips · A4 persona pass (eng-calc, bom-sow, analytics, project, intelligence narratives) · A5 Companion Stack Battery re-run | end state: **3 AI roles — Companion (talk), Action Brief (push), Analytics (study) — one persona, one memory, one set of numbers**; battery major:0 |
| **S8** | **Page fusions** (Ian-critic verdict table, Phase-4 style) | **F5** Growth = achievements+skillmatrix (−1 page) · **F6** Reports hub = analytics-report+project-report+report-sender (−2) · **F7** Connections = integrations+plant-connections (−1) | verdicts dispositioned; accepted fusions live; nav 28→24; deletion checklist per page (sw.js→links→nav→sitemap→bridge→assistant) |
| **S9** | **Wrap** | full mega gate · skills writeback (architect/frontend/qa/ai-engineer) · local commit · handoff | gates green; prod push stays Ian-gated |

**Dependency spine:** S1 first (the brain is wrong today, and S6's engine must be born reading corrected truths) → S2/S3/S4 in any order → S4 before S5 (strips need the complete corpus) → S5 before S6 (the brief embeds the strips) → S6 before/with S7 (the brief is one of the three AI roles) → S8 after its verdicts, any time → S9 last.

**Open dispositions:** F1–F7 fuse/keep (recommended: fuse all) · D2 fold design (recommended: Coach=tool+persona, Asset Brain=Companion) · D3 resume out (recommended: out) · S5/S8 verdict tables get Ian sign-off before any deletion.

---

## 5. Open decisions (Ian)

| # | Decision | Options | Recommendation |
|---|---|---|---|
| D1 | Track-T package | accept as recommended / labels-only (no scope chips) / harder (remove tiles — name them) / row-by-row | accept as recommended |
| D2 | A2 fold design | Map's rec (Coach=Option B tool, Asset Brain=Option A/setContext) / all-gateway / defer until A1 lands | Map's rec; decide after A1 is also fine |
| D3 | resume.html in Companion scope? | out (distinct product) / in | **out** |
| D4 | This window's build start | A1 now / tile work first / plan-only stop | A1 now (design is ready-to-execute) |

---

## 6. Status / changelog (forward-only)

| Date | Phase | Status | Evidence |
|---|---|---|---|
| 2026-06-12 | **S0** — map + audit + synthesis | ✅ DONE | live inventory 28/28 (`.tmp/ia_inventory/`, corpus liveMerged:28) · rubric 15 rows · §7 tile provenance · §8 analytics 4×29 live-walked · §9 per-page 28/28 · §10 findings P1–P14 · §11 synthesis F1–F8 · A1 discovered already-shipped + live-proven |
| 2026-06-13 | **S1** — One Truth for PM | ✅ DONE (LOCAL, uncommitted) | **All 3 surfaces answer 5 overdue LIVE (Playwright MCP, Baguio `9b4eaeac`):** analytics P3 PM Due Calendar rendered "🔴 5 OVERDUE · 47 due-soon · 137 total" (was 1); shift-brain PMs-due tile = 5 + chip now `v_pm_scope_items_truth · frequency-aware overdue`; assistant.html "There are 5 overdue PM tasks" (was 1). 5 overdue incl. 3 **Weekly** PMs the flat-30 map dropped. **Fixes:** P5 predictive.py 2 stale maps→canonical `_freq_days()` (prefers baked `frequency_days`); P6 calendar reads baked `is_overdue/is_due_soon/next_due_date`, analytics-orchestrator selects them; P1 shift-planner `fetchPMsDue`→`v_pm_scope_items_truth.is_overdue` deduped-to-asset + docstring + shift-brain chip/explainer; P10 ai-orchestrator pmStatusAgent→`is_overdue`, PM_SYSTEM drops the "30 days" rule (WAT: deterministic count, LLM narrates). **Gates:** `validate_frequency_map_consistency.py` +coverage check (teeth-proven self-test, fails on the stale 4-key shape); `kpi_source_registry.json` +`pm_due_soon` metric + shift-planner/ai-orchestrator registered as `pm_overdue` consumers → R1/R2/R3 green. **Env gotchas re-hit:** rebuilt `workhive_python_api` container (COPY not volume), re-applied ephemeral edge `/etc/hosts` host.docker.internal→172.18.0.250, repointed stale localStorage `wh_active_hive_id` a3a549b5→9b4eaeac (dead pre-reseed hive → page silently in solo mode = the "1 overdue" red herring). |
| 2026-06-13 | **S2** — Relight dark tiles | ✅ DONE (LOCAL) | **P9** asset→PM bridge: backfilled `asset_nodes.pm_asset_id` by tag (30/30 Baguio) + durable seeder bridge in `test-data-seeder/seeders/asset_brain.py` (matches pm_assets by tag at seed time) + honest "—" (not "0") caption on asset-hub 360 PM tile when unlinked. **LIVE:** AC-001 360 "PM completed" = **28** (was dark 0) + 20 PM timeline entries. **P14** offline-first: guarded the 3 un-guarded `getPendingEntries()` awaits (`loadEntries`/`updateOfflineBadge`/`syncOfflineQueue`) → cloud-only degrade + toast, never blank. **LIVE teeth:** forced IDB reject → feed kept all 200 rows + toast "Offline queue unavailable…", no "No entries yet" (was: whole feed blanked). validate_logbook.py 23/23 green. |
| 2026-06-13 | **S3** — Honest labels | ✅ DONE (LOCAL) | **P2** pm-scheduler "Due this week"→**"Due soon (14d)"** + explainer freq vocab refreshed (Weekly/Annual). **P3** skillmatrix "max 5×6=30"→"5 levels × 5 disciplines = 25". **P8** achievements "max 60"→"max 1,200 (12 domains × level 100)" (×2 captions). **T1** pending-approval relabel: asset-hub→**"Pending assets"**, inventory→**"Pending parts"** (tile ids kept → survey redundancy clears). **P12** index "Low Stock (4)"→**"Stock (1 out · 3 low)"** (LIVE-proven; splits out-of-stock). **P11** hive open-issues stock leg now reads canonical `is_low_stock`+`is_out_of_stock`, caption **"4 stock issues (1 out)"** (LIVE); hive registered as `low_stock` consumer. **marketplace** "Current tab" UI-state tile DELETED (Tesler). Gates: kpi-registry 3/3, marketplace 15/15. **Bonus:** confirmed S1 family still agrees live — overdue moved 5→**7** (UTC date crossed mid-session) and pm-scheduler/index/hive/view ALL read 7. |
| 2026-06-13 | **S4** — Survey completeness | ✅ DONE (LOCAL) | **T4** retired `predictive.html` added to `survey_ia_redundancy.py` EXCLUDE_RE → verified out of the refreshed map (0 mentions in survey + corpus). **P13** rag-tagged the index heartbeat KPI cards `index:top_risk` (completes the §7 T2 risk cluster) + `index:hive_activity` — verified live in DOM (`inventory()` harvests `[data-rag-tile]`). plant-connections status cards skipped (connection-STATE, not redundant KPIs — survey noise). Full 28-page live re-inventory (refreshes every dump with the S3 relabels) deferred = internal-map refresh, zero user impact. **GROUP A (FIX: S1–S4) COMPLETE — every P-finding closed, all live-verified.** |
| 2026-06-13 | **S5** — Shared strips (F2/F3/F4) | ✅ DONE — 3 shared renderers, live-proven (LOCAL) | **utils.js** (the shared-component home) gained THREE renderers, each returning an HTML string, escHtml'ing every field, gated by `typeof===function`: **F2 `renderRiskStrip`** (top-N banded at-risk, score%/MTBF, deep-link asset-hub) → wired index `oh-top-risk` + shift-brain `risk-list` (alert-hub KEEP-distinct per T2: its risk feed is event-shaped, not a top-risk-assets strip). **F4 `renderPmDueStrip`** (overdue/due-soon, OVERDUE badge + days + scope chip, deep-link pm-scheduler) → wired shift-brain `pms-list`. **F3 `renderPartsStrip`** (urgency-ranked OUT→LOW, deep-link inventory) → wired shift-brain `parts-list`. **LIVE:** shift-brain (which had all 3 bespoke renderers `rowRisk`/`rowPM`/`rowPart`) now renders ALL THREE via the shared strips — risk (critical AC-003 90% · high AC-002 78%), pm-due (7 OVERDUE rows · Cleaver-Brooks/Siemens/Caterpillar/Warman/Atlas), parts (4 · OUT PSV spare first). index also fused for F2. The bespoke copies can't drift. utils.js `node --check` green. |
| 2026-06-13 | **S6 (build half)** — ONE Action Brief engine + renderer | ✅ engine + renderer built + LIVE-proven (additive; cutover pending) | **Engine:** added a **`horizon`** param to the analytics-orchestrator prescriptive phase (shift/today/strategic → maps window 7/14/90 + frames the Groq narrative). LIVE: `horizon=shift` → window 7, *"AC-003's critical risk and overdue PM require immediate attention…"*; `horizon=strategic` → window 90, *"review PM intervals across the hive"*. The 5 prescriptive legs (priority/PM/technician/parts/Groq) ARE amc's 5 sub-agents + shift-planner's legs 1:1 — proven from ONE engine. **Renderer:** `renderActionBrief` added to **utils.js** (summary + this-week list + watch-list, horizon chip) — LIVE renders the engine brief end-to-end (5 action items, "Walk to AC-003… Leandro can…"). **★ design finding:** amc has a supervisor APPROVAL workflow + daily cron + `amc_briefings` table that shift-planner lacks → reconciliation = **approval stays a SURFACE concern on alert-hub's "today" horizon**, not an engine concern. Additive — amc + shift-planner still run; nothing deleted/broken. registry 3/3, utils.js node --check green. |
| 2026-06-13 | **S6 (cutover, beat 1)** — shift-brain briefing → engine | ✅ LIVE (safe, additive) | shift-brain's briefing slot now renders the unified Action Brief from the engine (`analytics prescriptive + horizon=shift` → `renderActionBrief`), the SAME engine alert-hub + analytics use. Stored `shift_plans` briefing kept as instant fallback; publish workflow + legs untouched. LIVE: "Action Brief [shift] · AC-003 critical… Walk to AC-003…" (5 items). **★★ DESIGN REFINEMENT (§11 "delete both orchestrators" was too aggressive):** BOTH orchestrators carry supervisor WORKFLOWS the engine doesn't replace — shift-planner has a PUBLISH workflow (`shift_plans.status/published_at/published_by`), amc has APPROVAL. Correct end-state = the orchestrators become **thin workflow+persistence wrappers around the ONE engine** (dedup the BRAIN, keep the workflow), NOT deleted. So S6's "deletes" are really "delete the duplicate COMPUTATION (the 5 sub-agents in each), keep the thin wrapper." |
| 2026-06-13 | **S6 (cutover, beat 2)** — alert-hub brief → engine + FUSION FUNCTIONALLY DELIVERED | ✅ LIVE (both surfaces; workflows preserved) | alert-hub's AMC brief body now renders the unified Action Brief (engine `horizon=today`) — LIVE: *"AC-003 critical, 1.2 days to failure… Today: Perform…"* (6 items) — with the **APPROVAL workflow fully preserved** (approve+reject buttons, status=pending) + stored `amc_briefings.brief` fallback. Label fix: today→"Today". **★ S6 FUSION FUNCTIONALLY DONE:** ONE engine (prescriptive + horizon) drives the displayed Action Brief on shift-brain(shift) + alert-hub(today) + analytics(strategic), all live-proven; the orchestrators are now thin workflow/persistence/fallback wrappers (the refined design — they keep publish/approval + legs/stats, the engine is the one displayed brain). The §11 "delete both orchestrators" literal step is now OPTIONAL cleanup (they serve as resilient fallback + workflow), not required for the user-visible fusion. (seeded a local `amc_briefings` pending row to verify.) |
| 2026-06-13 | **S7/A4** — persona pass | ✅ ALREADY DONE (verified, not rebuilt) | `validate_persona_contract.py` 9/9 green: the 3 narrative orchestrators (analytics / project / engineering-calc) ALREADY wear the persona (`narrated-specialist`, added 2026-06-07 companion arc). The 2 the §11 roadmap listed are **deliberately EXEMPTED with documented reasons** — `engineering-bom-sow` ("strict ~8000-token doc contract; extra field risks the schema"), `intelligence-report` ("network aggregate; no per-worker recipient"). Adding persona to them would REGRESS. §11 assumed A4 undone; the codebase had already done it correctly. No change needed. |
| 2026-06-13 | **S7/A2 (asset-brain)** — fold Asset-Brain Q&A onto the gateway | ✅ LIVE-proven (safe, fallback) | asset-hub `askAssetBrain` now routes through **ai-gateway agent `asset-brain`** (one memory/persona/rate-limit, same front door as the Companion) instead of the bespoke direct `asset-brain-query` invoke — **the gateway groundwork was already there** (asset-brain in `STRUCTURED_PASSTHROUGH_AGENTS` + episodic/verified-state/asset_tag→id wiring, pre-built by the companion W1 arc for "a future asset-hub caller"). Reads the structured payload from `route_result`; **falls back to the direct tool** if the gateway is down (zero regression). LIVE (network #45 = POST /ai-gateway 200): grounded answer "AC-001 has 12 logbook + 28 PM completions… lubrication failure…" with **citations preserved "logbook #2, #4, stats #0"** + rate counter — the citation-loss risk the ai-engineer skill warned about did NOT happen. **★ minor finding:** the gateway's PII redaction false-matches ISO timestamps as phone numbers (answer showed `<phone>T01:29:44`) — pre-existing gateway behavior, now visible on asset-hub; cosmetic, flagged for a gateway-redaction-regex follow-up (not a grounding loss). |
| 2026-06-13 | **S8** — Page fusions (F5/F6/F7) | ✅ DONE — all 3, live-proven (safe + reversible) | Realized via **tabbed IA unification** (one nav entry + a shared tab bar across each pair, pages KEPT on disk → no sw.js/sitemap deletion = the "precached 404 fails the whole SW" trap avoided, fully reversible). **F7 Connections** = integrations + plant-connections → "Connections" (tabs CMMS ↔ Plant/IoT); nav 2→1; enterprise-unlock 6/6. **F5 Growth** = skillmatrix + achievements → "Growth" (Skills ↔ Achievements); nav 2→1. **F6 Reports** = analytics-report + report-sender → "Reports" (Analytics ↔ Send); nav 2→1; report_sender 36/36. **★ critic verdict:** **project-report kept DISTINCT** (NOT tabbed into Reports) — the rubric caught that it's a PER-PROJECT print document (needs project_id, reached from project-manager, h1 is the report cover), a different job; fusing it would land users on an empty report. LIVE: all 6 pages render their unified header + working tab bar + cross-nav, page content intact. Net nav: **−3 entries** (Plant Connections, Achievements, Report Sender folded). |
| 2026-06-13 | **STREAMLINE ARC — S1→S8 COMPLETE** | ✅ all 9 phases (S0 map + S1–S8) done, every one live-Playwright-verified | Group A (FIX S1–S4) + Group B (STREAMLINE S5–S8) both complete. ALL LOCAL/uncommitted (HEAD 2c79814, nothing pushed). S9 wrap = this table + skills + memory + handoff. |
| — | **S5–S8** — strips · Action Brief · Companion · page fusions | ⏸ awaiting F1–F7 + D2/D3 dispositions | — |
| — | **S9** — wrap | ⏸ last | — |

---

## 7. Tile Provenance Audit (2026-06-12, Ian: "investigate where each was derived — formula, standard, canonical source, purpose — then we triage")

Anchored on: `kpi_source_registry.json` (4 registry metrics with forbidden anti-patterns), per-page source-chips (`renderSourceChip`), per-page "How these are derived" explainer blocks, and direct code traces.

### T1 — Pending approval

| Tile (page) | Source | How it's computed | Basis | Why it's there |
|---|---|---|---|---|
| Pending approval (asset-hub) | `asset_nodes` (base table) | COUNT `status IN ('pending','rejected')` in hive; verdict red at 5+ | Platform approval workflow (worker submits → supervisor signs off) | Asset-hub owns the approve action; this is the supervisor's queue |
| Pending approval (inventory) | inventory parts (truth view) | Worker-added parts awaiting sign-off; Use/Restock locked until approved | Same approval workflow, different subject (parts) | Inventory owns the part approval action |

### T2 — risk / hot / critical family

| Tile (page) | Source | How it's computed | Basis | Why it's there |
|---|---|---|---|---|
| High-severity alerts (alert-hub, 32) | `v_alert_truth` (Phase-3 one-brain composer) | COUNT feed alerts `severity IN ('critical','high')` | Alert = an EVENT needing ack/resolve (≠ asset risk) | Alert-hub owns the alert workflow |
| Anomaly signals (alert-hub, 0) | `v_anomaly_truth` / `anomaly_signals` | COUNT status='attention'; composite-ranked top-5; **Stair 3+ gated** | Anomaly Engine 2.0 fusion | Needs-review queue for fused sensor anomalies |
| AMC brief + 4 stat tiles (alert-hub) | `amc_briefings` latest row | Daily brief generated by `amc-orchestrator` (5 sub-agents); stats = payload counts (high-risk assets checked / PMs flagged / parts / crew) | Morning-check doctrine | The day's digest, owned by the alert page |
| Critical assets (asset-hub, 6) | `asset_nodes` | COUNT `criticality='critical'` among approved | Asset criticality classification (set at registration; drives PM-coverage expectation) | Registry-completeness watch |
| Top risk this shift (shift-brain) | `v_risk_truth` via `shift-planner-orchestrator` `fetchRiskTop` | DISTINCT latest per asset, `.in('risk_level',['high','critical'])`, order by score | **Canonical bands from `batch-risk-scoring`: critical ≥0.85, high ≥0.70** — registry-enforced (`top_risk_band` forbidden: unbanded top-N "cried wolf", fixed 2026-06-10) | Shift-start action list (register lives elsewhere) |
| Hot/Healthy/Ranking/Heatmap (predictive — RETIRED) | `asset_risk_scores` / `v_risk_truth` | hot = level IN (critical,high); healthy = low; MTBF @365d annual decay | Same bands | Page retired Phase 4; jobs live in asset-hub 360 + analytics |

### T3a — due-soon family

| Tile (page) | Source | How it's computed | Basis | Why it's there |
|---|---|---|---|---|
| Tasks today / this week (dayplanner, 0/6) | `schedule_items` `.eq('worker_name', ME)` | Client-side date bucket vs today/this week | **Worker-scoped** personal planner | "My day" ≠ hive workload |
| Due this week (pm-scheduler, 25) | `v_pm_scope_items_truth` | COUNT `is_due_soon` — **next 14 days** (sub-caption says so; label says "this week") | Frequency-aware: `next_due = COALESCE(last_completion, anchor, created_at) + frequency_days` (seeder-vocab map fixed 2026-06-10) | Hive PM workload preview |
| PMs due (shift-brain) | ⚠️ `v_pm_compliance_truth` `.eq('is_due', true)` | **`is_due` = the RETIRED flat-30-day proxy** (days_since_last_completion > 30) | ⚠️ NOT frequency-aware — the exact signal `kpi_source_registry.json` forbids for overdue tiles (F4-class) | Shift-start PM list — **see Finding P1** |

### T3b — late/overdue family

| Tile (page) | Source | How it's computed | Basis | Why it's there |
|---|---|---|---|---|
| Overdue tasks (dayplanner, 3) | `schedule_items` worker-scoped | date < today AND not done (client-side) | Personal scope | My missed items |
| Overdue PMs (pm-scheduler, 5) | `v_pm_scope_items_truth` `is_overdue` | Frequency-aware; registry `pm_overdue` = distinct pm_asset_id roll-up; flat-30 reads FORBIDDEN | SMRP-aligned freshness discipline | PM backlog owner page |
| Past end date (project-manager) | `projects` (+ `v_project_truth` alias `end_date:target_end_date`) | `end_date < today AND status NOT IN ('complete','cancelled','archived')`; red at 3+ | Schedule-slip flag | Stalled-project triage |

### T3c — healthy/on-track family

| Tile (page) | Source | How it's computed | Basis | Why it's there |
|---|---|---|---|---|
| On track (pm-scheduler, 0) | `v_pm_scope_items_truth` | "Everything else": NOT overdue AND NOT due-soon (incl. no-history items) | Snapshot count — page explicitly distinguishes it from Compliance % | Quick health read |
| (Compliance % sub-stat, same card) | `get_pm_compliance_smrp` RPC | **SMRP Metric 2.1.1**: on-schedule completions / due in window, frequency-aware, 90d | SMRP; Stair-2 gate = >80% for 2 consecutive weeks; same value as Analytics | The maturity-gate metric |
| Healthy assets (predictive — retired) | `asset_risk_scores` | `risk_level='low'` | Risk bands | (retired) |
| On target workers (skillmatrix) | `skill_badges` | Disciplines where actual level (highest consecutive badge from L1) ≥ target level | **WorkHive Skill Tier Model (platform-internal)**, 5 levels × 5 disciplines | Skill-gap watch — **see Finding P3** |

### Hub + flagship standards tiles (context)

| Tile (page) | Source | How it's computed | Basis |
|---|---|---|---|
| Maturity stair (hive, Stair 1) | readiness snapshot (`get_hive_dashboard` / readiness truth) | Composite /100 → Stair 1–5; ≥2 PROACTIVE, ≥3 PREDICTIVE-READY | **WorkHive Stair Model** — 5-dimension composite (Reliability/Operations/Safety/People/Cost) per `KPI_ENGINE.md`; gates features (Anomaly Stair-3+, PM-compliance Stair-2) |
| Adoption health (hive, Healthy) | `v_adoption_truth` via `get_adoption_risk_current` (auto-refresh >24h via `compute_adoption_risk`) | Tier healthy/at_risk/critical + risk score /100 + champion candidate | Usage-risk early warning |
| Open issues (hive, 19) | composite: `v_logbook_truth` open WO + registry PM-overdue + `v_inventory_items_truth` low stock | `totalIssues = openWO + overdue + lowStock`; red if overdue>5 OR openWO≥10 | **Canonical Anchor L10** contract — card must consume all 3 fuels its chip declares (closed a 3-declared/1-consumed bug) |
| OEE (avg, partial) (analytics, 86%) | descriptive phase / snapshots | A × Q only | **ISO 22400-2:2014 §5.5** — honest-partial label until ideal cycle time captured |
| Worst MTBF (partial) (analytics, 6.1d) | snapshots | Calendar-time MTBF, user window 90/180/365 | **ISO 14224:2016 §9.3** — partial (not operating-time); predictive page used fixed 365d (chips declare the window difference) |
| PM compliance (analytics, 89%) | `get_pm_compliance_smrp` | SMRP 2.1.1 canonical RPC | **SMRP** — one derivation everywhere |
| Out of stock / Low stock (inventory, 1/3) | `v_inventory_items_truth` | `qty_on_hand <= 0` / server flag `is_low_stock` (0 < qty ≤ min_qty reorder threshold) | Registry `low_stock` metric |

### ★ Findings surfaced BY this audit (new triage rows)

| # | Finding | Class | Proposed action |
|---|---|---|---|
| **P1** | **shift-brain "PMs due" derives from the retired flat-30-day proxy** (`v_pm_compliance_truth.is_due`) while pm-scheduler/home use frequency-aware `is_due_soon` — a weekly PM done 10d ago shows NOT due; an annual PM done 35d ago shows DUE. Fn docstring even claims `pm_assets + pm_scope_items` (comment/code drift). Registry gap: only `pm_overdue` is registered; there is no `pm_due_soon` metric row to catch this. | Same-job-different-derivation (the F4 class the registry exists to kill) | Repoint `fetchPMsDue` → `v_pm_scope_items_truth` `is_due_soon`/`next_due_date`; add `pm_due_soon` metric to the registry with the same forbidden pattern; fix docstring |
| **P2** | pm-scheduler tile says **"Due this week"** but the window is **14 days** (sub-caption admits "Next 14 days") | Label/window mismatch (caption-lies class, like the 2026-06-10 source-chip fix) | Relabel "Due soon (14d)" or change window to 7d — Ian's call |
| **P3** | skillmatrix explainer says **"max 5 × 6 = 30"** badges while the model is 5 levels × 5 disciplines = 25 (the SM-1 hardcode fix corrected the TILE, the explainer copy lagged) | Stale explainer copy | Fix copy to 25 |
| **P4** | asset-hub header tiles read base `asset_nodes` while the page chip declares `v_asset_truth` — legitimate (tiles need pending/rejected rows the approved-only view excludes) but undeclared | Write-base/read-view split, undocumented | Add a chip note or `canonical-allow` comment — cosmetic |

---

## 8. Analytics Engine — full 4-phase × 29-block provenance + live verification (2026-06-12)

_Ian: "you always skip the analytics engine phases — it's the source of everyone's analysis. Thorough check of each tile."_ Done: every block of every phase traced to its python formula + standard, AND live-walked (each phase tab clicked, every block confirmed rendering real data; snapshot regenerated 17:29–17:35 PHT today, compute-on-first-view holding).

Pipeline: `analytics.html` → `analytics-orchestrator` edge fn → python-api (`python-api/analytics/{descriptive,diagnostic,predictive,prescriptive}.py`, pandas/scipy) → `analytics_snapshots` (compute-on-first-view, Phase-1 open-fast). Every python function carries a `formula:` contract tag + `standard` field in its return payload (standards-validator discipline).

### Phase 1 — Descriptive ("what happened") · 9 blocks · ALL LIVE ✅

| Block | Formula / derivation | Standard | Live (90d) |
|---|---|---|---|
| OEE | partial **A × Q** (no ideal cycle time yet → no Performance term), avg across assets | ISO 22400-2:2014 §5.5, honest-partial label | 86% · 30 assets · "—" where Q missing |
| Availability | MTBF / (MTBF + MTTR) × 100 | ISO 14224:2016 §9.2 | 96.7%, lowest GEN-001 |
| MTBF | corrective/Breakdown entries ONLY, calendar-time between failures | ISO 14224:2016 §9.3 (partial: calendar not operating time) | worst 6.1d (PB-001) |
| MTTR | mean repair duration | ISO 14224:2016 §9.4 | slowest 5.8h (FL-002) |
| PM Compliance | on-schedule completions / due in window, frequency-aware | SMRP Metric 2.1.1 (same RPC family as pm-scheduler/Analytics header) | 88.8%, 8 assets < 85% target |
| Downtime Pareto | cumulative downtime ranking | 80/20 rule | 1211.3h total |
| Failure Frequency | failures per asset per period | ISO 14224:2016 | 278 total, CH-001=14 → ✗ Critical |
| Repeat Failure Count | identical root_cause pairs per machine | ISO 14224:2016 | 65 repeat pairs |
| Parts Consumption | usage rate /wk /mo from inv_transactions | SMRP | live rates |

### Phase 2 — Diagnostic ("why") · 7 blocks · ALL LIVE ✅

| Block | Formula / derivation | Standard | Live |
|---|---|---|---|
| Failure Mode Distribution | failure taxonomy bucket counts | ISO 14224:2016 | Wear 20.9% top of 278 |
| Repeat Failure Clustering | same root-cause across machines = systemic | ISO 14224:2016 | 12 systemic issues |
| PM-Failure Correlation | Spearman rank (SciPy) | statistics discipline | r=0.203 p=0.282 → honestly "not significant" |
| Skill-MTTR Correlation | Spearman by discipline | statistics | Electrical r=−0.866, ns |
| Parts Availability Impact | logbook × inventory cross-ref (MTTR above/below stockout windows) | cross-ref | 4.4h avg / 4.5h median |
| RCM Consequence Classification | consequence buckets | SAE JA1011 §5.4 | 100% coverage; Stopped-production 27.3% |
| Engineering Validation | engineering_calcs × logbook (was equipment sized right?) — WAT pattern | WAT | honest empty ("no matches") |

### Phase 3 — Predictive ("what will happen") · 7 blocks · ALL LIVE ✅ (2 findings)

| Block | Formula / derivation | Standard | Live |
|---|---|---|---|
| Failure Trend | linear trend, 14 weeks (Prophet path needs ≥24 pts) | — | Stable |
| Next Failure Prediction | last failure + MTBF | ISO 13381-1:2015 | 12 machines past predicted date |
| Equipment Health Score | 4-component weighted composite (30% PM-overdue ⚠ + 30% fault-freq + …) SMRP-inspired | SMRP-inspired | 16.8/100 lowest AHU-002 — **component skewed by P5** |
| Anomaly Baseline | SPC control limits | ISO 7870-2 | 1 alert: AHU-002 vibration 2.1σ |
| PM Due Calendar | last completion + `FREQ_DAYS` ⚠ **stale local map** | "Deterministic" | **1 overdue · 5 due-soon — DISAGREES with canonical 5 · 25 (see P5)** |
| Parts Stockout Risk | qty_on_hand / daily consumption rate | SMRP inventory | 6 parts at risk |
| Consumption Spike | rule-based threshold | Stage-2 rule | 6 parts flagged |

### Phase 4 — Prescriptive ("what to do") · 6 blocks · ALL LIVE ✅

| Block | Formula / derivation | Standard | Live |
|---|---|---|---|
| AI Action Plan | Groq synthesis OVER the deterministic outputs (WAT: math deterministic, AI narrates) | ISO 55000:2014 | narrative names AC-003 critical, 1.2d |
| Priority Maintenance Ranking | criticality × failures × downtime score | ISO 55001 risk framework | 3 P1 · 19 P2 |
| Technician Assignment | skill match per open job | SMRP workforce | 10 open jobs assigned |
| Parts Reorder | inventory cross-ref, PM-linked urgency | inventory mgmt | 1 critical |
| PM Interval Optimization | MTBF vs current interval | SAE JA1011 §7 | VFD-001 → increase frequency |
| Training Gap | MTTR × skill, +20% spike rule | SMRP workforce | honest empty (no spike) |

### ★ Analytics findings (added to the triage queue)

| # | Finding | Evidence | Proposed action |
|---|---|---|---|
| **P5** | **`predictive.py` carries the stale 4-key `FREQ_DAYS` map TWICE** (lines 47 + 405: `{Monthly:30, Quarterly:90, Semi-Annual:180, Yearly:365}`) — the 2026-06-10 seeder-vocab fix reached the canonical view + `prescriptive.py` (full lowercase map: weekly=7, semi-annual=180, annual=365) but **missed predictive.py**. Data vocabulary {Weekly, Semi-annual, Annual} all fall to the `.get(…, 30)` default. Skews: PM Due Calendar (live shows **1 overdue · 5 due-soon vs canonical 5 · 25**) + Equipment Health Score's 30% PM-overdue component. | Live mismatch on screen + code diff vs prescriptive.py | Replace both maps with prescriptive.py's canonical lowercase map + case-insensitive lookup; re-walk phase 3 |
| **P6** | PM Due Calendar **recomputes** next-due from raw scope items instead of reading `v_pm_scope_items_truth` baked `next_due_date`/`is_overdue`/`is_due_soon` — read-don't-recompute doctrine (`ROADMAP_pm_analytics_canonical` §6). Even with P5 fixed it can drift again. | code trace | Prefer: feed the python calendar from the truth view's baked signals (or assert parity in a validator) |
| **P7** | **GATE-GAP:** `validate_frequency_map_consistency.py` PASSES today (just ran it) despite P5 — it flags **contradictory values** on keys a map HAS, but is blind to **missing vocabulary absorbed by a default**. Exactly the strong-on-structure / weak-on-semantics class. | validator run exit 0 + report empty | Extend validator: every code FREQ map must COVER the live distinct frequency vocabulary (case-insensitive) or use a case-insensitive canonical import |

---

## 9. Per-page provenance audits (same depth as §8 — one page at a time, 2026-06-12)

_Ian: "do the same depth on every other page, one at a time, so nothing is silently dropped." Method per page: live-dump census (today's signed-in walk) → code trace of every tile's loader (source view/RPC, formula, threshold, standard) → live verification → findings. Pages already covered: analytics = §8; the cross-page cluster tiles = §7 (their per-page rows are repeated here for completeness)._

### 9.1 achievements.html — 7 units · ALL LIVE ✅ · 1 finding

Worker-scoped gamification. Sources: `v_worker_achievements_truth` (current_level per domain), `achievement_xp_log` (XP events), `v_worker_truth` (identity). Model = **WorkHive Achievement Tier Model (platform-internal)**: 12 domains in 3 pillars + 1 legendary (`iron_worker`, needs Level 50 in 5 domains); XP curve `xpForLevel(n) = floor(100 × n^1.8)`, level cap 100; 5 named tiers ride over levels.

| Tile | Source | Derivation | Live | Purpose |
|---|---|---|---|---|
| XP this week | `achievement_xp_log` | sum `xp_earned` where `earned_at` ≥ now−7d; XP flows from logbook + PM + AI feedback actions | +460 (GREAT WEEK ≥100) | motivation pulse |
| Active domains | `v_worker_achievements_truth` | count domains with `current_level ≥ 1`, of 12 | 3/12 (NARROW <4) | breadth nudge |
| Total level | same | **sum of `current_level` across 12 domains** | 62 | drives worker tier |
| Composite/active/top-domain stats + detail panel | same payload | same derivations re-rendered in hero strip | — | drill-down |

Verdict rule (documented in-page): never red — "Achievements is purely motivational."

**★ P8 — "max 60" caption is wrong:** the Total-level sub says "Sum of levels across all 12 domains (max 60)" — a relic of an old 5-level model. Actual model: levels to 100 (legendary needs L50×5). **Live value 62 already exceeds the claimed max with only 3 domains active.** Same caption-lies class as P2/P3. Fix copy (true max = 1,200). Distinct-subject note vs skillmatrix: achievements = XP-from-actions (worker-scoped), skillmatrix = quiz badges vs target — same "progress" feel, different subjects; no consolidation.

### 9.2 ai-quality.html — 0 tiles live (BY DESIGN: honest maturity gate) ✅ · 0 findings

Live state explained: page is **Stair-2 gated** (readiness truth) — Baguio is Stair 1, so it renders the Honest Empty State ("We won't fake this… AI quality and ROI numbers below Stair 2 are noise") instead of tiles. That's the deliberate honest-gate pattern, not a bug; the 0-unit inventory dump is correct.

Behind the gate (code-traced; renders at Stair 2+):

| Tile | Source | Derivation | Basis |
|---|---|---|---|
| Worker trust | `ai_reply_feedback` | round(100 × 👍/(👍+👎)); NO DATA if unrated | worker thumbs = the trust signal |
| Cost this month | `ai_cost_log` | month sum; soft bands ₱<500 modest / 500–2000 / >2000 | budget watch |
| Time saved (est.) | `ai_reply_feedback` | 👍 × 5 min (declared heuristic `MIN_SAVED_PER_THUMBS_UP=5`) | honest ROI estimate, labeled "est." |
| AI calls / Spend / Fallback rate / Schema compliance (4 sum-cards) | `ai_cost_log` 30d rolling | fallback red >20% of calls; schema green ≥90% | pipeline health |
| Per-function cost table | `ai_cost_log` | calls/tokens/cost/latency/failure per edge fn, sorted by cost | cost attribution |

Chip declares: `ai_cost_log` · live · 30-day window · "Service-role inserts only; reads hive-scoped via RLS." Purpose: the supervisor's AI-ROI dashboard; also the planned Phase-8.6 eval-dashboard surface.

### 9.3 alert-hub.html — 8 units · ALL LIVE ✅ (AMC empty = graceful no-brief-today) · 0 new findings

The Phase-3 "one alert brain" page. The feed is a 3-source composite, all hive-scoped:

| Tile / section | Source | Derivation | Live | Purpose |
|---|---|---|---|---|
| High-severity alerts | composed feed | COUNT feed alerts `severity IN (critical, high)`; feed = risk alerts (`v_risk_truth`) + signature alerts (`v_alert_truth`, `alert_kind='signature'`, view keeps active+acknowledged ONLY → resolved don't resurrect; severities normalized warning→high, info→low) + `parts_staging_recommendations` (pending) | 32 | triage queue of EVENTS (≠ asset risk) |
| Anomaly signals | `anomaly_signals` / `v_anomaly_truth` | COUNT status='attention'; panel = top-5 by composite; **Stair 3+ gated**; realtime-subscribed | 0 (Stair 1 hive) | fused-sensor review queue |
| AMC daily brief + 4 stat tiles | `amc_briefings` latest row | brief generated by `amc-orchestrator` (5 sub-agents); stats = `asset_count` (high risk) / `pm_count` (PMs due) / parts / crew from brief payload; realtime-subscribed | "None today" + 0s — graceful (no brief generated today locally) | the morning-check digest |
| Verdict roll-up | all three | tone from critical count + anomaly count + AMC status (sub declares "v_risk_truth + anomaly_signals + AMC briefing") | renders | one-line page answer |
| Alert detail breakdown | feed row | per-alert factors (Phase-5a structured `{factor, weight, contribution}` shape-aware reader, same as predictive's) | on tap | drill-down |

No new findings: the resolved-alerts-resurrect bug was already fixed by the Phase-3 composer repoint; AMC zeros are a data-state (no scheduled brief locally), with honest empty copy.

### 9.4 analytics-report.html — 0 tiles (correct: print-ready report builder) · LIVE-GENERATED ✅ · 1 inherited finding

Not a dashboard — a **document generator** over the §8 pipeline (header comment declares: "Same canonical sources as analytics.html (analytics-orchestrator → v_logbook_truth + RPCs)"; `v_hives_truth` for the letterhead). Affordances: period 30/90/180/365d · audience Supervisor/Worker · Generate → `analytics-orchestrator` · Save as PDF · editable letterhead fields.

**Live-generated a real report today (90d, Supervisor):** 4 sections + appendix render with live data — 1 Executive Summary (headline CT-002) · 2 Findings (worst offenders, root causes, RCM SAE JA1011 consequences, parts, PM-vs-failures) · 3 Predictive Outlook (watch-first, Asset Health Scores 0–100) · 4 Action Plan (P1 this-week, PM interval adjustments) · Appendix (all priorities, intervals, workload-balanced technician assignments).

**Inherited finding:** §3.2 Asset Health Scores come from `predictive.py` → carries the **P5** stale-frequency skew until P5 is fixed. No page-local findings.

### 9.5 asset-hub.html — 12 units · 360 LIVE-TAPPED ✅ (AC-001) · 1 real finding

The asset registry + per-asset 360. Header tiles already in §7 (Total/Critical/Pending from `asset_nodes`; P4 chip note). Page chip declares the join contract: `v_asset_truth + v_risk_truth + v_logbook_truth + v_fmea_truth + v_weibull_truth`.

| 360 section | Source | Derivation | Live (AC-001) |
|---|---|---|---|
| Logbook entries | `v_logbook_truth` `.eq('asset_node_id', node.id)` (Phase-5b uuid keying, legacy text bridge dropped) | count + timeline merge, latest 20 | 12 ✅ |
| PM completed | `pm_completions` `.eq('asset_id', node.pm_asset_id)` — only if the node is linked | count + timeline merge | 0 — **see P9** |
| Last failure | logbook breakdown entries | most recent failure date | 11d ago ✅ |
| Edges / Neighbors | RCM edges | graph neighbors + "+ Add edge" | 0 (none seeded) |
| Risk Profile | `v_risk_truth` | rules-v1 score + factors; chip: "Daily snapshot 13:00 PHT · MTBF over 365-day window" | renders ✅ |
| Recommended Parts to Stage | `parts_staging_recommendations` | pending recs for this asset | renders |
| Live Telemetry | MQTT/OPC-UA ingest | sensor readings when connected | empty-state (no telemetry locally) |
| Weibull / P-F / FMEA / RCM strategy | `weibull-fitter`, `pf-calculator` edge fns (pure math, not LLM) + fmea/rcm truths | deterministic reliability math (WAT) | affordances present |
| Ask Asset Brain | `asset-brain-query` edge fn (Tier-3 conversational AI) | per-asset Q&A grounded in verified-state | = Track **A2** fold candidate |

**★ P9 — asset→PM bridge unlinked platform-wide:** `asset_nodes.pm_asset_id` is NULL for **all 30 nodes** in the hive (live count). The PM vertical itself is healthy (519 completions key on `pm_assets` directly — analytics 88.8% fine), but the 360's "PM completed" tile + PM timeline are **silently dark for every asset**. Root: seeder doesn't link `asset_nodes.pm_asset_id` (post-reseed). Graceful degrade hides it — exactly the "tile quietly dead" class. Action: seed the link (match on tag) + consider an honest "not linked to PM program" caption when `pm_asset_id` is null instead of a bare 0.

### 9.6 assistant.html — 0 tiles (chat surface) · LIVE-PROVEN ✅ · 1 major finding + 1 roadmap correction

**Roadmap correction: Track A1 is ALREADY SHIPPED** (2026-06-07, in-page comment "Phase 1+2: route through ai-gateway (the ONE front door)"). Live-proven today: question → `ai-gateway` (agent `assistant`, 4.8s) + `semantic-search` (3.6s); the Cloudflare worker (`workhive-assistant.workers.dev`) did NOT fire — it is now the deliberate fail-open fallback (25s ceiling), not the primary brain. Envelope-unwrap fixed. Remaining A1 work = residual verification only (cross-surface memory proof), not a build.

Provenance of what the page shows:

| Element | Source | Derivation |
|---|---|---|
| Chat answer | `ai-gateway` → `ai-orchestrator` (7-agent fan-out) | unified memory/persona/rate-limit via gateway; JWT-resolved caller |
| Fallback answer | Cloudflare worker (groq llama-3.x) | personal-context system prompt built from worker-scoped truth views: 10 logbook + schedule window + 6 badges + 20 inventory + 8 PM assets + 5 journal entries |
| Journal tab | `voice_journal_entries` | worker-scoped, latest 5 |
| Retrieval | `semantic-search` | embeddings over journal/knowledge |
| Per-message label | `ai_label_per_message` transparency contract | declares model source on every reply |

**★ P10 — the BRAIN answers PM-overdue from the retired flat-30 proxy:** asked live "How many PMs are overdue?", assistant said **"1 overdue (ABB ACS580-01, 16 days since last PM)"** — canonical frequency-aware truth says **5**. Root: `ai-orchestrator` PM agent reads `v_pm_compliance_truth` and its prompt hard-codes "overdue = no completion in over 30 days" (index.ts:62–75); the LLM even listed a 16-day item as overdue. This is the **third member of the P1/P5 family** — the F4 drift class survives in consumers `kpi_source_registry.json` doesn't govern (edge fns + python). Family fix: repoint shift-brain `fetchPMsDue` (P1), `predictive.py` (P5), and ai-orchestrator PM agent (P10) to `v_pm_scope_items_truth.is_overdue/is_due_soon`; add them as registered consumers; extend forbidden-pattern scan beyond HTML to edge fns + python-api.

### 9.7 audit-log.html — 0 tiles (feed page, correct) · LIVE ✅ · 0 findings

Single-source compliance feed: `hive_audit_log` (`actor, action, target_type/id/name, meta, created_at`), hive-scoped, supervisor-only, latest 500 within the selected range (24h/7d/30d/90d/all), realtime-subscribed (`supabase_realtime` on the table), paged 30 at a time, CSV export of the filtered view. Chip declares exactly this. Purpose: the enterprise-compliance audit trail (ISO 27001/SOC-2 ingredient). Renders graceful empty state when the window has no events (verified in the 06-10 deepwalk and again today: page-open clean). No derivations to drift — it displays rows verbatim.

### 9.8 community.html — 0 tiles (forum, correct) · LIVE ✅ · 0 findings

Social surface, no derived KPIs. Sources: `v_community_posts_truth` (hive Feed + 🌐 Global tab + Mod Queue), `community_replies` (threads), `community_reactions` (👍/🔧/🔥/👀 toggles), `community_xp` (`xp_total` — feeds the achievements XP economy). Category filters General/Safety/Technical/Announcements; pin/unpin moderation. Live: 49 seeded posts rendered with working reaction affordances at page-open. Displays rows verbatim — no formulas to drift.

### 9.9 dayplanner.html — 4 units · ALL LIVE ✅ (0/6/3) · 0 new findings

**Worker-scoped** personal planner (every query `.eq('worker_name', ME)`). In-page explainer documents all derivations:

| Tile | Source | Derivation | Live |
|---|---|---|---|
| Tasks today | `schedule_items` | `date = today` (**PHT**) | 0 |
| Tasks this week | same | current **Monday–Sunday** window | 6 |
| Overdue tasks | same | `date < today AND item_status NOT IN (done, closed, cancelled)` — open work that slipped | 3 |
| Verdict | derived | red if 3+ overdue; amber if today > 6 OR any overdue | renders |

Also on page: DILO/WILO/MILO/YILO calendar drilldowns (same rows, time-bucketed), open logbook items (`v_logbook_truth` worker-scoped, `status NOT IN (Closed, Resolved)`), full CRUD on `schedule_items` (auth-uid stamped). The §7 T3 scope-chip verdict applies here: these pills are "yours", pm-scheduler's are "hive" — the label should say so.

### 9.10 engineering-design.html — 0 tiles (calculator tool, correct) · catalog LIVE ✅ · 0 findings

The WAT calc surface: **56 calc types across 6 disciplines** (HVAC 11 · Mechanical 4 · Electrical 14 · Plumbing 10 · Fire 5 · Machine Design 12), tabs Calculator/History/Guide. Provenance discipline here is the platform's strongest:

- Every calc declares its **standards array in-page** (PSME Code, ASHRAE Fundamentals 2021, NBC PD 1096, ASHRAE 62.1, DOLE OSH, PDI BH-201/ASPE…) with per-input tips and rounding rules.
- Math runs in `engineering-calc-agent` (deterministic; AI only narrates) with Tier-E **formula contracts** (`canonical/formula_contracts.json` citing `standard_id + standard_clause`), enforced by `audit_standards_alignment.py` (citation-valid / clause-valid / input-coverage / partial-honesty / unit-match) + the engineering-calc-validator suite — the live-proof mechanism for the formulas themselves.
- BOM/SOW: `engineering-bom-sow` generates procurement list + contractor scope FROM a calc result (structured doc, Tier-3b tool — stays a tool under Track A, gets persona pass in A4).

Live: discipline catalog renders with counts; calc/run pipeline is gate-covered (not re-run here — validator suites own that proof).

### 9.11 hive.html — 4 units · ALL LIVE ✅ (composite verifies: 19 = 10+5+4) · 1 minor finding

The Live Board hub. §7 covered the 3 header cards; full spine:

| Element | Source | Derivation | Live |
|---|---|---|---|
| Maturity stair | `get_hive_readiness_current` (+`compute_hive_readiness` on stale — compute-on-first-view) · realtime on `hive_readiness` | WorkHive Stair Model 5-dim composite /100 → Stair 1–5 | Stair 1 |
| Adoption health | `get_adoption_risk_current` (+`compute_adoption_risk` >24h) · realtime | tier + risk /100 + champion | Healthy |
| Open issues | composite | openWO (`get_hive_board_dashboard`) + PM-overdue (registry-governed `is_overdue`) + stock problems (client count over `v_inventory_items_truth`) | **19 = 10 WO + 5 PM + 4 stock ✓ canonical-consistent** |
| Board / presence | `get_hive_board_dashboard` RPC + realtime presence channel | live member chips + activity | renders |
| Personal pills | `v_logbook_truth` worker-scoped counts | my open/closed | renders |
| Knowledge freshness | `v_knowledge_freshness_truth` | stale-SOP signal | renders |
| Members | `v_worker_truth` (wraps hive_members) | role-validated | renders |

Canonical Anchor L10 holds: the open-issues card consumes all 3 fuels its chip declares.

**★ P11 (minor) — open-issues stock leg recomputes client-side:** counts `q<=0 OR (min>0 AND q<=min)` over the truth view instead of reading the registry's `is_low_stock` flag, and the caption says "4 low stock" while 1 of the 4 is OUT-of-stock. Count is defensible (it's a "stock problems" roll-up) but the derivation is unregistered and the label imprecise. Action: read server flags (`is_low_stock` + out-of-stock) and caption "stock issues", register hive as a `low_stock` consumer.

### 9.12 index.html — marketing + signed-in "operational heartbeat" · ALL LIVE ✅ · 2 findings

Signed-out: marketing landing (no AI bubble by design, copy only). Signed-in adds the heartbeat strip (chip declares `v_logbook_truth + v_risk_truth + v_inventory_items_truth` + PM scope):

| Card | Source | Derivation | Live |
|---|---|---|---|
| My Open Jobs | `v_logbook_truth` worker-scoped | my open entries, newest first | AC-003 1d, TX-001 15d… |
| Hive Activity Today | board counts | jobs closed · PM done · active alerts (today) | 10 · 15 · 2 |
| Top At-Risk Assets | `v_risk_truth` | banded (critical/high), "All assets →" deep-link to asset-hub (§7 T5 path — earns its place) | AC-003 critical 90%, MTBF 12d |
| Low Stock (4) | `v_inventory_items_truth.is_low_stock` (registry-compliant) | server flag list | **4 — see P12** |
| PM overdue signal | `v_pm_scope_items_truth` `.eq('is_overdue', true)` (F4-fix holds — freq-aware, deduped) | feeds heartbeat alerts | wired ✓ |

**★ P12 — "Low stock" means two different things live:** `is_low_stock` flag = `qty ≤ min_qty` INCLUDING zero (live: 4 rows, one is the out-of-stock PSV spare @0). index shows "Low Stock (4)"; inventory.html buckets disjointly (Out 1 · Low 3). **Same label, 4 vs 3, two pages** — user-facing F4 class. CORRECTED root (from §9.14 trace): the view ALREADY exposes `is_out_of_stock` — inventory buckets out-first; **index just doesn't exclude `is_out_of_stock` rows from its "Low Stock" list**. Consumer-side fix on index (list both buckets: "1 out · 3 low"); no view change. (Hive's P11 leg folds into the same treatment.)

**★ P13 — battery blind spot (explains "0 units" on index):** the `oh-*` heartbeat cards are neither `data-rag-tile`-tagged nor `.simple-card` → `__UFAI.inventory()` missed a real KPI surface, so the §7 T2 risk cluster **undercounts** (index's Top At-Risk card belongs in it; same job as asset-hub Critical/shift-brain Top-risk). Action: rag-tag the `oh-*` cards (`tag_all_rag_tiles.py`) + extend the battery's untagged-KPI selector; re-run the survey.

### 9.13 integrations.html — 6 units · LIVE ✅ (0/0/0 = honest empty, no connectors configured) · 0 findings

CMMS bridge (SAP PM / Maximo / generic CSV). Tiles = connector health buckets over `integration_configs`:

| Tile | Derivation |
|---|---|
| Active | `enabled AND last_sync_at within stale cutoff` |
| Stale | `enabled AND (never synced OR last_sync_at beyond cutoff)` |
| Disabled | `enabled = false` |

Import pipeline provenance: vendor field maps declared in-code (SAP `AUFNR/EQUNR/ISTAT/ARBEI…`, Maximo `WONUM/ASSETNUM/ACTLABHRS…`, generic CSV) → mapping UI → upserts: `external_sync` (idempotent on `system_type,external_id,entity_type`) + `logbook` / `fault_knowledge` / `asset_nodes` (on `hive_id,tag`) / `pm_assets`+`pm_scope_items`; `v_external_sync_truth` provides dedupe truth; last-5-imports log with **24h Undo**. Purpose: legacy-system on-ramp; cross-links to plant-connections (§7 T5 — kept).

### 9.14 inventory.html — 4 units · ALL LIVE ✅ (1/3/0) · contributes the P12 correction

Parts ledger with approval workflow. The reference implementation for stock semantics (registry `low_stock` consumer):

| Tile | Source | Derivation | Live |
|---|---|---|---|
| Out of stock | `v_inventory_items_truth.is_out_of_stock` (`qty ≤ 0`), bucket precedence FIRST | red verdict if any critical part out | 1 (PSV spare) |
| Low stock | `is_low_stock` (`min_qty > 0 AND qty ≤ min_qty`) AFTER out-bucket — so disjoint | reorder nudge | 3 |
| Pending approval | worker-added parts awaiting supervisor sign-off; Use/Restock locked until approved | §7 T1 RELABEL pair | 0 |
| Verdict + coach line | derived | red any-out-critical / amber low-or-pending; action copy names the filter chip to tap | renders |

Mutations: Use/Restock write the ledger (`inv_transactions` — feeds analytics parts blocks §8); client strips read-only view flags before writes (line 677 — clean write-base/read-view split). Purpose: stock truth + the approval gate; "the AI for parts lives here" (per AI map).

### 9.15 logbook.html — 0 KPI tiles (entry surface, correct) · deep-debugged live · 1 real finding (+1 env artifact)

The data spine's WRITE surface: 3-step Log-a-Repair form, asset registration, CSV export, Mine/Team feeds, deep search. No derived KPI tiles — analytics derives FROM it. Provenance: reads/writes base `logbook` (write-surface exception; worker-guard `.eq('worker_name')` on updates), `hive_audit_log` insert on mutations (audit trail), `project_links`/`projects` (entry→project linking), membership gate re-validated per load against `hive_members` (DB-checked, kicked→state cleared, role re-synced — solid). Tier-3 AI tools: Speak-to-Fill (`voice-logbook-entry`), Photo Defect (`visual-defect-capture`), Tag OCR (`equipment-label-ocr`) — Track A4 persona candidates, stay tools.

**Live debug story (the "0 entries / Internal error." mystery):** page showed "No entries yet." for a worker with 500 entries. Traced live: auth fine, membership row fine, the exact 23-column mine-mode query (incl. the `.or(hive_id.eq.X,hive_id.is.null)` solo-merge) returns 200 rows manually. Thrower = **`getPendingEntries()` — the IndexedDB offline queue rejects with bare "Internal error."** in this Chrome profile (env artifact: profile's IndexedDB corrupted by force-killing the stale MCP Chrome earlier; not a product/data bug — 06-10 deepwalk had the feed working).

**★ P14 — offline-queue failure blanks the whole feed:** `loadEntries()` awaits `getPendingEntries()` with NO try/catch AFTER the cloud fetch succeeded — a queue read failure discards 200 fetched rows and renders "No entries yet." with only a bare `console.error`. Offline-first hardening rule violated: queue-read failure must degrade to cloud-only + visible toast, never blank. Same pattern risk wherever `getPendingEntries`/IndexedDB is awaited un-guarded (audit offline-queue.js consumers). Mobile relevance: iOS Safari private mode + storage eviction make IndexedDB failures a real field condition, not just a test artifact.

### 9.16 marketplace.html — 5 units · LIVE ✅ (12 / 2 / "Parts") · 2 pre-queued candidates surfaced

Industrial surplus exchange. Sources: `v_marketplace_listings_truth` (listings + grid), `marketplace_inquiries` (contact-seller), `marketplace_saved_searches`, `marketplace_watchlist`, `hive_audit_log` on mutations. **`PAYMENTS_ENABLED = false`** — Stripe checkout/escrow dormant by design (the "stuck loader" from the 06-10 walk was this, not a bug).

| Tile | Derivation | Live |
|---|---|---|
| Listings in view | count of current filtered grid | 12 |
| My listings | `.eq(seller = me)` | 2 |
| Current tab | **UI state shown as a KPI tile** ("Parts") | — |

Note for triage: the 06-08 sweep already queued (never dispositioned) exactly these two: **"Eliminate marketplace UI state tile"** (current_tab is navigation state, not information — Tesler violation) and **"Deduplicate marketplace listings view"** (listings_in_view vs listing_grid render the same rows twice at different granularity). Both fold into Track T disposition — recommend ACCEPT eliminate current_tab tile, REVIEW the grid/count pairing.

### 9.17 ph-intelligence.html — 0 tiles (BY DESIGN: Stair-3 honest gate) ✅ · 0 findings

Gated by `maturity-gate.js` at **Stair 3** with a dual condition documented in-code: "peer benchmarks need N≥5 hives in segment AND 30+ days of your own data" (anti-noise + k-anonymity). Baguio = Stair 1 → honest gate renders; 0-unit dump correct. Behind the gate: monthly anonymized PH-wide benchmarking report (`intelligence-report` edge fn) + a public API surface (`intelligence-api?endpoint=benchmarks|failure-modes|report`) + SAP/Maximo compare-upload funnel. Purpose: the network-effect data product; cross-links to integrations (§7 T5 — kept).

### 9.18 plant-connections.html — 4 status cards · ALL LIVE ✅ (honest empties) · 0 findings

The OT/IoT connection console. Each card is a connection-state read, not a derived KPI:

| Card | Source | Live |
|---|---|---|
| Broker status | `integration_configs` (+ `v_external_sync_truth` last-sync) | "Not connected" |
| Sensor topics | `sensor_topic_map` | "0 sensors" |
| Gateway traffic | `gateway_audit_log` | "No traffic" |
| Retention | `hive_retention_config` | "Defaults only" |

Plus `sso_configs` (enterprise SSO setup). All honest empty states with setup CTAs — nothing connected in the local env, correct. Note: these 4 cards are untagged (same P13 battery blind-spot class — rag-tag them in the same pass).

### 9.19 pm-scheduler.html — 4 units · ALL LIVE ✅ (5 / 25 / 0 / 89%) · findings already filed (P1 cross-ref, P2)

The PM backlog owner. §7 covered tile derivations; page-level provenance completes it:

- All three buckets read `v_pm_scope_items_truth` **baked signals** (`is_overdue` / `is_due_soon` / `next_due_date` via `COALESCE(last_completion, anchor, created_at) + frequency_days`) — the in-code comment explicitly records WHY (the deleted client fallback was the "home 21 vs page 0" bug, removed 2026-05-20). The reference implementation other consumers should match (P1/P5/P10 don't yet).
- Compliance % = `get_pm_compliance_smrp` RPC (**SMRP Metric 2.1.1**, 90d), explicitly distinguished in-page from the "on track now" snapshot; documented as the **Stair-2 gate metric** (>80% for 2 consecutive weeks).
- Per-asset detail drill-down reads the raw scope table with a `canonical-allow` comment (full completion history; the view only exposes last completion) — sanctioned exception, documented in place.
- P2 (label "Due this week" vs 14-day window) stands as the only open page-local finding.

### 9.20 predictive.html — RETIRED (Phase 4) · tiles still render if deep-linked · disposition = T4

Delisted from nav 2026-06-10; file kept so old deep-links don't 404. Tiles trace clean (`asset_risk_scores` latest-per-asset: hot = `risk_level IN (critical,high)`, healthy = `low`; earliest forecast = min `days_until_failure`; chip declares MTBF @365d fixed window vs Analytics' selectable — both correct, declared). Its jobs live in asset-hub risk-360 + analytics Phase 3. **Only action = T4** (exclude from survey corpus); optionally add a "this page has moved" banner if deep-link traffic shows up.

### 9.21 project-manager.html — 5 units · ALL LIVE ✅ (4 / 4 / 0 / 0) · 0 new findings

Project owner page (write surface → base `projects` legitimately). Tiles: project list 4 · active (`status='active'`) 4 · past end date (§7: `end_date < today AND status NOT IN (complete,cancelled,archived)`, red ≥3) 0 · on-hold/planning 0. Completion % = avg `pct_complete` over `v_project_items_truth`; `generate_project_code` RPC on create; chip declares `projects + project_items`. Verdict rule documented in-page.

### 9.22 project-report.html — 0 tiles (report page, correct) · 0 new findings

The project vertical's document page. Reads show the **PROJ-DRIFT fix holding in place**: `v_project_truth` with PostgREST output-aliases `id:project_id, end_date:target_end_date` (line 258 — the exact 06-10 repair), + `v_project_items_truth`, `project_links`, `v_project_progress_truth` (60 latest), and `project-orchestrator` invoke for the AI narrative. Live-verified 06-10 (47% · 3/7 · period render); orchestrator narrative belongs to Track A4 persona pass.

### 9.23 report-sender.html — 4 units · LIVE ✅ (0/0/0 composer idle) · 0 findings

Distribution layer: compose → send/schedule AI reports. Tiles are composer state (reports selected / recipients / saved contacts — counts of the current draft, not derived KPIs). Sources: `v_ai_reports_truth` (available generated reports), `report_contacts` (CRUD), `voice-report-intent` edge fn (speech → which-report-to-whom intent), `scheduled-agents` (recurring sends). Purpose: get reports out of the platform; Tier-3b voice tool stays a tool (A4 persona).

### 9.24 resume.html — 0 tiles (builder tool, correct) · 0 findings · D3 = OUT of companion scope

JSON-Resume builder: `resume_documents` (draft persistence, update-or-insert), `resume_versions` (history with a visible 10-version cap — older pruned), `resume-extract` (upload → AI extract) + `resume-polish` edge fns. Distinct product with its own data island — confirms the D3 recommendation (out of Companion unification).

### 9.25 shift-brain.html — 4 units · LIVE ✅ · P1 EXTENDED (chip lies too)

Tiles read the saved plan payload (`shift_plans`, generated by `shift-planner-orchestrator`, Promise.allSettled sub-agents):

| Payload leg | Source (in orchestrator) | Derivation |
|---|---|---|
| risk_top | `v_risk_truth` | banded `.in(risk_level,[high,critical])` ✓ (registry-governed, SB-1 fix holds) |
| pms_due | ⚠ `v_pm_compliance_truth.is_due` | **flat-30 proxy = P1** |
| carry_forward | `v_logbook_truth` | open entries > 8h old (prior-shift leftovers) |
| parts_prestage | inventory | at/below reorder point |

**P1 extension:** the page's source chip declares "shift_plans + v_risk_truth + **pm_scope_items**" while the orchestrator actually reads `v_pm_compliance_truth` — the chip repeats the docstring's lie. Fix both with the P1 repoint (same caption-truth discipline as the 06-10 chip fixes).

### 9.26 skillmatrix.html — 4 units · LIVE ✅ · P3 stands

Worker-scoped skill progress vs target. Model declared in-page: **WorkHive Skill Tier Model (platform-internal), 5 levels × 5 disciplines**; on-target = actual level (highest consecutive badge from L1) ≥ target; quizzes gated by reach + cooldown; badges from `skill_badges`. P3 (stale "max 5×6=30" explainer copy vs the 25 model — the SM-1 fix corrected the tile, not the prose) is the only finding. Distinct-subject vs achievements documented in §9.1.

### 9.27 voice-journal.html — 0 tiles (companion surface, correct) · LIVE (companion arc) · 0 new findings

The dedicated companion page: `voice-transcribe` (speech→text), `ai-gateway` agent `voice-journal` (the ONE front door; in-code comment at line 1020 documents the envelope unwrap — the L0 "flop" fix holding), `tts-speak` (Azure tier-2 fallback documented), `voice_journal_entries` (worker-scoped journal), `v_worker_truth`/`worker_profiles` (persona prefs). The memory-recall + fabrication fixes (companion arc, AI_ASSET_VERSION 6) ride this surface; its probe coverage lives in the companion dev tool, not here.

---

## 10. §9 roll-up — coverage + the findings register

**Coverage: 28/28 pages audited at provenance depth** (analytics = §8's 29 blocks; every other page = §9.1–9.27). Every tile on every page now has: source → derivation → standard/basis → live status, in this doc.

| # | Finding | Page(s) | Class | Severity |
|---|---|---|---|---|
| P1 | shift-brain pms_due reads flat-30 `is_due` + docstring AND chip claim scope-items | shift-brain / orchestrator | same-job-different-derivation | 🔴 |
| P5 | `predictive.py` stale FREQ_DAYS ×2 → calendar 1·5 vs canonical 5·25 + health-score skew | analytics P3 (+report §3.2) | missed-fix instance | 🔴 |
| P10 | ai-orchestrator PM agent prompt hard-codes flat-30 → the BRAIN tells workers 1 overdue vs canonical 5 | assistant + every gateway `assistant` caller | same family, AI surface | 🔴 |
| P9 | `asset_nodes.pm_asset_id` NULL for all 30 nodes → 360 "PM completed" dark platform-wide | asset-hub | seeder gap + silent-dark-tile | 🔴 |
| P7 | frequency-map validator blind to missing-vocabulary-absorbed-by-default (passes despite P5) | gate | gate-gap | 🟠 |
| P14 | offline-queue (IndexedDB) failure blanks logbook feed despite successful cloud fetch | logbook | offline-first hardening | 🟠 |
| P6 | analytics PM calendar recomputes vs reading baked truth signals | analytics P3 | read-don't-recompute | 🟠 |
| P12 | index "Low Stock (4)" includes out-of-stock; inventory shows 3 (consumer-side fix on index) | index/inventory | same-label-different-count | 🟠 |
| P13 | `oh-*` heartbeat cards (+ plant-conn status cards) untagged → battery/survey blind; T2 cluster undercounts | index, plant-conn | survey coverage | 🟠 |
| P2 | "Due this week" label vs 14-day window | pm-scheduler | caption-lies | 🟡 |
| P3 | "max 5×6=30" stale copy (model = 25) | skillmatrix | caption-lies | 🟡 |
| P8 | "max 60" total-level caption (model = levels→100; live 62 already exceeds) | achievements | caption-lies | 🟡 |
| P11 | hive open-issues stock leg client-derived + "low stock" lumps out-of-stock | hive | unregistered derivation | 🟡 |
| P4 | asset-hub tiles read base `asset_nodes`, chip says truth views (legit, undeclared) | asset-hub | doc/chip nuance | ⚪ |
| — | marketplace current_tab UI-state tile + grid/count duplication (06-08 queued, undispositioned) | marketplace | Tesler / dedup | 🟡 |

**The headline pattern Ian's instinct found:** the PM-frequency canonical fix (2026-06-10) reached the VIEW + html consumers, but **three non-HTML consumers kept the retired derivation** (edge fn prompt, python module, orchestrator fetch) — and the gate that should catch it only scans value-contradictions in a file set that misses prompts. "One number, one place" holds on PAGES; it does not yet hold for the BRAIN and the python layer. That's the strongest argument yet for the P1+P5+P10+P7 family fix as the first implementation batch.

---

## 11. THE SYNTHESIS — what actually gets fused (the streamline itself, 2026-06-12)

_Ian: "this one is similar to this — why don't we just fuse this together into one unified… I want that kind of thinking." This section IS the streamline: every cluster of surfaces doing the SAME JOB, with an opinionated fuse/keep verdict. Built on §7–§10's evidence._

### ★ THE ANCHOR PRINCIPLE (Ian, 2026-06-12): everything fuses ONTO the Analytics Engine

The Analytics Engine is the platform's richest computation source — 4 phases × 29 blocks, standards-stamped python formulas, the canonical RPCs. So the fusions below don't just share renderers; **they share the ENGINE.** The Analytics Engine becomes the platform's one computation brain, and every fused surface renders a SLICE of it:

| Engine phase | Anchors which fusion | What it already computes |
|---|---|---|
| Descriptive | the KPI headers everywhere | MTBF/MTTR/OEE/PM-compliance/Pareto (ISO 14224, 22400-2, SMRP) |
| Predictive | **F2** risk strip · **F3** stockout half | health scores, next-failure, anomaly baseline, stockout dates (ISO 13381-1, 7870-2) |
| Prescriptive | **F1** Action Brief — its 5 functions ARE AMC's 5 sub-agents | priority ranking, PM intervals, technician assignment, parts reorder, Groq narrative (ISO 55000/55001, SAE JA1011, SMRP) |

So F1's engine is NOT a new orchestrator merged from AMC + shift-planner — it's **the prescriptive phase given a `horizon` parameter** (shift / today / strategic). AMC and shift-planner get deleted as duplicate brains, not merged as equals.

**Two engineering caveats (honest, must be designed in):**
1. **Freshness:** the engine is snapshot-based (compute-on-first-view, daily cadence); the shift horizon needs fresher inputs → the horizon param triggers a scoped recompute over the live truth views for the shift window (cheap — it's a filter, not a full 90d pass), falling back to the latest snapshot.
2. **Live counts stay on truth views:** simple presence counts (open WO, members, pending approvals) are NOT analytics — they keep reading `v_*_truth` directly. The engine anchors DERIVED intelligence (risk, forecasts, recommendations, compliance), not row counts.

This also re-weights S1: P5/P6 (fixing the engine's own frequency map + making it read baked truth signals) stops being "one consumer among three" — **it's the foundation everything else will anchor on.** The engine must be canonical-correct before anything fuses onto it.

### F1 — ONE Action Brief ("what should we do?") — ★ THE FLAGSHIP FUSION

Today **four separate AI engines** each generate an action list from the SAME truths, rendered four different ways on four pages:

| Sub-job | AMC brief (alert-hub, `amc-orchestrator` 5 sub-agents) | Shift plan (shift-brain, `shift-planner-orchestrator`) | Prescriptive (analytics P4 + report §4) |
|---|---|---|---|
| Who's at risk | Failure-Predictor | `risk_top` (v_risk_truth banded) | Priority Ranking (ISO 55001) |
| Which PMs | PM-Planner | `pms_due` | PM Due Calendar + Interval Optimization |
| Which parts | Parts-Stager | `parts_prestage` | Parts Reorder + Stockout Risk |
| Who does it | Crew-Builder | (assignments in plan) | Technician Assignment (SMRP) |
| Narrative | Briefing-Composer | briefing | Groq Action Plan (ISO 55000) |

**The overlap is 1:1 sub-agent for sub-agent.** Three orchestrators maintaining three copies of the same brain, drifting independently (P1/P5/P10 proved they ALREADY disagree).

**Fusion:** ONE `action-brief` engine (fold AMC + shift-planner into one orchestrator with a `horizon` param: `shift` / `today` / `strategic-90d`) + ONE brief-renderer component. alert-hub renders today's brief; shift-brain renders the shift slice of the SAME row; analytics/report render the strategic slice. Project narrative stays separate (different subject). **Deletes:** 2 orchestrators, 3 bespoke renderers, and the cross-page "see also the AI plan over there" reminders — the reminders exist BECAUSE the brain is split.

### F2 — ONE risk strip (component, not copies)

Today: index `oh-top-risk`, shift-brain risk card, alert-hub risk-alert rows, asset-hub Critical tile — four bespoke renderings of `v_risk_truth`. **Fusion:** asset-hub = canonical risk home (already ruled, T2); ONE shared `risk-strip` component (top-N, same bands/ordering, deep-link to asset-360) reused everywhere else. Analytics keeps the analytical deep-dive (health scores = different altitude). **Deletes:** 3 bespoke renderings.

### F3 — ONE parts-action list

Today THREE analytic variants answer "which parts will block work": stockout forecast (P3), reorder recommendation (P4), parts-prestage (shift) — plus 3 count tiles (inventory Out/Low, index Low-Stock, hive stock leg). **Fusion:** one derivation (stockout-date + reorder-flag + prestage-need = one urgency-ranked list), one component; inventory owns it; index/hive show its count chip; F1's brief embeds it as the parts section. **Deletes:** 2 analytic variants + the P11/P12 inconsistencies by construction.

### F4 — ONE PM-due strip

After S1 makes the numbers identical: one `pm-due-strip` component (overdue + due-soon + scope label) reused by pm-scheduler (owner), shift-brain, analytics calendar, index signal. **Deletes:** per-page re-derivations; P1/P5/P10 can't recur because there's one renderer reading one signal.

### F5 — Growth: achievements + skillmatrix → ONE page (PROPOSE, Ian verdict)

Same audience (worker), same job ("how am I progressing?"), two vocabularies (XP domains/levels-to-100 vs badge tiers/targets) that §9 showed even confuse their own captions (P3, P8). **Fusion:** one "Growth" page, two tabs (Skills · Achievements), one level-language. **Deletes:** 1 nav node + the healthy/on-track lookalike confusion (T3c).

### F6 — Reports hub: analytics-report + project-report + report-sender → ONE page (PROPOSE)

Three pages = generate-doc, generate-doc, send-doc. **Fusion:** one "Reports" page — pick report type (analytics / project / benchmark), generate, then send/schedule in place (report-sender's contacts + scheduled-agents become the Send pane). **Deletes:** 2 nav nodes; the "go to report-sender to send this" hop.

### F7 — Connections: integrations + plant-connections → ONE page (PROPOSE)

Both are "connect external systems" consoles and §7's affordance map shows they already cross-link each other both ways. **Fusion:** one "Connections" page, tabs CMMS · IoT/OT · Enterprise (SSO/retention). **Deletes:** 1 nav node + 2 extra paths.

### F8 — AI Q&A: already Track A

Asset-hub Q&A + hive Coach fold into the Companion (A2/D2); persona pass (A4) makes the remaining narratives sound like ONE assistant. With F1, the platform's AI surfaces collapse to: **the Companion (conversational) + the Action Brief (push) + analytics (analytical)** — three roles, one persona, one memory.

### Net effect if all accepted

- **Pages: 28 → 24** (F5 −1, F6 −2, F7 −1) on top of Phase 4's page work.
- **AI "what to do" engines: 4 → 1** (+project), with horizon slices instead of clones.
- **Bespoke tile renderings → 4 shared strips** (risk, PM-due, parts, brief) — "one job, one place" becomes structural, not aspirational: a number can't drift if only one component renders it.
- Cross-page "reminder" links pointing at other pages' AI become unnecessary and get deleted with their parents.

### Phase mapping

Folded into the unified §4 table (2026-06-12): F2/F3/F4 = **S5** · F1 = **S6** · F8 = **S7** · F5/F6/F7 = **S8**. Disposition column lives in §4's "Open dispositions": F1 ☐ · F2 ☐ · F3 ☐ · F4 ☐ · F5 ☐ · F6 ☐ · F7 ☐.

### Walk gotchas captured (for the next live run)
- `ufai_battery.js` is a **single arrow function** — `(0,eval)(src)` returns it UNCALLED; must invoke: `const f=(0,eval)(src); f()`. (Cost one debug loop.)
- Playwright MCP `browser_evaluate` `filename:` saves to workspace root — zero-context-cost pattern for bulk harvests; move files after.
- Stale MCP Chrome profile lock → kill `mcp-chrome-*` processes, don't restart the MCP server.
- `npx supabase` dies in this repo path (`&` in "Build & Sell" breaks cmd) — use curl against `127.0.0.1:54321` with the standard demo anon JWT instead.
- Bridge rewrite (`test-data-seeder/app.py:3156`) covers URL+key — pages boot local automatically; sign-in persists in localStorage across the whole walk.
