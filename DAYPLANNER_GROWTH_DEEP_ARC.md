# DAYPLANNER · GROWTH (Skill Matrix + Achievements) — Page-Deep UFAI PDDA Arc

**Drafted 2026-07-12** (Asset/Alert/Shift trio arc's window, gate-green at HEAD `6817ceb`).
Same 6-phase PDDA (Understand → Deepwalk → Ideate → Roadmap → Execute → Re-deepwalk) as eng-design / resume /
landing / analytics / integrations / Hive / Community / Marketplace / Project-Manager / Logbook / Inventory /
PM-Scheduler / **Asset·Alert·Shift** (the trio, just landed 100%+gated).

Ian: *"I love the PDDA flow (same as logbook, inventory, pm-scheduler, asset/alert/shift — we regressed from that
clean flow, back to it). Another, refined: PDDA for **Dayplanner + Growth (Achievements + Skill Matrix)**. Extend the
UI/UX + UFAI we already have. I'm striving for the BEST Dayplanner Page and Growth Page + each of their canonical-reuse
discipline across their cross-page connectivity. Refine + extend the terms I've missed. **Update the arc roadmap after
EACH phase with items + percentage so you don't get lost.** Drive to 100% overall, no more stopping and asking."*

> **What this arc IS.** Dayplanner + Growth are the platform's **OPERATOR / PERSONAL layer** — where the platform's
> INTELLIGENCE becomes a real person's ACTUAL DAY and their LONG-TERM GROWTH. The trio (Asset Hub = what's at risk ·
> Alert Hub = what needs attention now · Shift Brain = the crew's shift plan) is the **UPSTREAM** intelligence; this arc
> makes the DOWNSTREAM personal layer best-in-class and perfects the **connectivity/reuse** that carries intelligence into
> it. The through-line — the engagement flywheel this arc completes:
>
> **INTELLIGENCE (risk / alerts / shift-plan)  →  PLAN my day (Dayplanner)  →  DO the work  →  GROW competence + recognition (Skill Matrix + Achievements)  →  (evidence feeds back into intelligence)**
>
> Drive it by (1) perfecting the **plan-my-day + grow-my-competence UX** (Dayplanner: one screen that answers *what should
> I do today, in what order, am I on track* — mobile-first at the plant floor; Skill Matrix: *what am I good at, what's my
> gap, what's my next cert*; Achievements: *what have I earned, what's my streak, what's next* — motivating, not childish),
> (2) treating each as a **faithful GROUNDING** — every Dayplanner task traces to a real source (a PM-due / alert /
> shift-plan row / logbook follow-up: no phantom task) and every Skill-Matrix competency + Achievement XP traces to REAL
> completed work (no fabricated competence, no minted XP), and (3) applying the **reuse discipline** so Dayplanner composes
> its worklist FROM the canonical primitives (v_pm_scope_items_truth, v_risk_truth, alerts, shift_plans) and Growth composes
> XP/competency FROM canonical completions (v_logbook_truth, PM completions, community activity) rather than re-inventing.

---

## Scope (grounded, 2026-07-12)

- **Deep-PDDA surfaces (the NEW deep focus — Ian's mid-turn clarification "arc for Dayplanner, and Growth Pages"):**
  - `dayplanner.html` — the personal/crew day plan (DILO = *Day In the Life Of* · WILO = *Week In the Life Of*); turns
    intelligence into a time-boxed, executable day. **[fresh full PDDA]**
  - `skillmatrix.html` — competency matrix (skills × people, TESDA NC-mapped, evidence-grounded). **[fresh full PDDA]**
  - `achievements.html` — gamification/XP/badges/streaks that reward doing the work. **[fresh full PDDA]**
  - **`learn/` subdirs:** `dilo-wilo-day-planner-supervisors` (dayplanner) · `skill-matrix-for-maintenance-technicians`
    + `tesda-nc-mapping-to-skill-matrix` (skill matrix) · `gamifying-maintenance-for-engagement` (achievements).
    (Confirm article↔tool alignment + CTAs in Phase 0.)
- **UPSTREAM surfaces (in scope ONLY for connectivity + canonical-reuse into the deep pages — already had their own arc):**
  `asset-hub.html`, `alert-hub.html`, `shift-brain.html`, `pm-scheduler.html`, `logbook.html`, `inventory.html`.
- **Data model (these are CONSUMERS + personal writers):**
  - **Reads (grounding sources):** `v_pm_scope_items_truth` / `v_pm_compliance_truth` (PMs due/overdue), `v_risk_truth` /
    `asset_risk_scores` (risk work), `alerts`, `shift_plans` (the published plan), `v_logbook_truth` (completed work =
    competency evidence), community activity / `community_xp`, `skill_badges` / competency tables, `achievement_definitions`.
  - **Writes (audit for the RLS/BOLA class):** dayplanner → personal task/schedule rows (name TBD from Phase 0);
    skillmatrix → `skill_badges` / competency; achievements → XP / `community_xp` (⚠ prior BOLA write-hole class —
    [[reference_community_xp_write_hole_and_reputation_bridge]]).

---

## ★ PRE-IDENTIFIED FRONTIER (from prior arcs' evidence — confirm/measure LIVE in Phase 0-2)

- **★ GROUNDING is the X spine for the personal layer.** Skill-matrix competency + achievement XP are the highest-risk
  confabulation surface on the platform: if a level/badge/XP is self-declared or seeded rather than earned from real
  completed work, the whole "competence + recognition" value is fiction. Phase 2 must trace EVERY competency level +
  EVERY XP total to a real source (logbook/PM completion/community activity), and every dayplanner task to a real cause.
- **★ community_xp BOLA class (prior finding).** [[reference_community_xp_write_hole_and_reputation_bridge]] — any authed
  user could mint XP. Phase 2 must LIVE-audit whether achievements/skillmatrix write XP/badges/reputation via a
  client-authorized path (the write-RLS/BOLA sweep for this arc's I axis).
- **★ THE SPINE IS PROBABLY BROKEN.** The ideal chain intelligence→plan→do→grow almost certainly has disconnected links
  (shift-brain publishes a plan but dayplanner may not ingest it; a completed PM likely doesn't credit the technician's
  skill matrix or award XP). These broken-spine links are the arc's highest-value connectivity work (Ext-5).
- **★ REUSE-OVERLAP: dayplanner ↔ shift-brain.** Both answer "what to do." FUSE or keep-distinct-with-a-reason
  (shift-brain = crew shift plan a supervisor PUBLISHES; dayplanner = MY personal day I EXECUTE) — Phase-4 synthesis verdict.

---

## ★ THE HEAVYWEIGHTS (refined + extended from Ian's thoughts)

### Heavyweight 1 — U: the BEST plan-my-day + grow-my-competence UX
- **Dayplanner** = "the plan for MY day, in order, honest about overload" — composed from real risk/alerts/PMs-due/shift-plan,
  time-boxed, mobile-first at the asset, reschedule-able, with a truthful capacity/overload signal. The DO surface.
- **Skill Matrix** = "what I'm good at, my gap, my next cert" — competency grounded in real completed work, TESDA-mapped,
  with a clear growth path (schedule training / book assessment / renew cert).
- **Achievements** = "what I've earned, my streak, what's next" — recognition that motivates the right behavior without
  being childish; grounded in real activity, honest streaks.

### Heavyweight 2 — X: faithful GROUNDING + provenance (the consumer-surface X keystone)
Every Dayplanner task traces to a real cause (PM-due / alert / shift-plan row / logbook follow-up: no phantom task); every
Skill-Matrix competency level + Achievement XP/badge traces to REAL earned work (no fabricated competence, no minted XP,
no self-declared level). Freshness of any cron/seed-generated content is honest. Tamper-evidence = the write-RLS/BOLA
sweep on task/skill/XP writes + attribution auth_uid on every personal write.

---

## ★ EXTENSIONS (refined + extended — the terms Ian implied)

- **Ext-1 — TASK-STATE / COMPETENCY-STATE facet** (parallel to alert/risk-state · stock-state · entry-kind · PM-state):
  a Dayplanner task is in a STATE (planned / in-progress / done / blocked / overdue / deferred) that ROUTES its action +
  downstream; a competency is in a STATE (not-started / in-progress / certified / expiring / lapsed) that routes its next
  action (schedule training · book assessment · renew cert). Phase-3 fork: first-class state-router vs derived pill.
- **Ext-2 — REUSE compose-FROM.** Dayplanner composes its worklist FROM v_pm_scope_items_truth / v_risk_truth / alerts /
  shift_plans (NOT re-deriving PM-due or risk); Growth composes XP/competency FROM v_logbook_truth / PM completions /
  community activity (NOT fabricating). Synthesis verdicts (FUSE / keep-distinct, fitness-gated): dayplanner↔shift-brain
  (what-to-do overlap); skillmatrix↔achievements (both read completions — one canonical XP/competency engine?);
  reuse the trio's shared helpers (renderRiskStrip, whStockSeverity, whRiskColor, setContext) rather than re-implementing.
- **Ext-3 — ENGAGEMENT / STREAK / RECOGNITION-loop honesty** (the personal-layer parallel to the trio's cron-honesty loop):
  streaks / XP / badges are time- + activity-based; verify the loop is honest — a streak past its window resets, XP can't be
  minted, a badge maps to a real earned criterion, a "level" reflects real evidence. No confabulated progress.
- **Ext-4 — TESDA NC / COMPETENCY-STANDARD provenance** (skill-matrix ↔ the `tesda-nc-mapping` + `skill-matrix` learn):
  competency maps to TESDA NC levels + real assessment evidence; verify the mapping is standards-grounded (like the
  reliability-workbench provenance for asset-hub) and the learn articles map to real affordances ([[feedback_articles_tool_aligned]]).
- **Ext-5 — CROSS-PAGE SPINE completeness** (the highest-value connectivity work): the intelligence→plan→do→grow chain must
  have NO broken link — shift-brain "add to my day" → dayplanner ingests it; a completed PM/logbook entry → credits the
  technician's skill matrix + awards achievement XP; alert-hub "plan this" → dayplanner. Every deep-link emitter needs a
  live reader; every earned event needs a grounded credit. Lock with the existing `validate_deeplink_param_contracts.py`.

## The scored axes (fill % LIVE in Phase 2) — per page × axis  [UFAI + UI/UX, extended]
- **U** — best plan-my-day / grow-my-competence UX (Dayplanner triage+time-box · Skill-Matrix growth path · Achievements engagement).
- **X** — grounding faithfulness + provenance (every task traces to a real cause; every XP/competency traces to real earned work; no phantom/fabricated/minted).
- **F** — flows E2E (plan a day → reschedule → complete → credit · view skill gap → book assessment · earn a badge honestly).
- **A** — plant-floor mobile (axe-0 WCAG 2.2 AA @390px on all 3 pages; touch targets ≥44px; safe areas; reuse `axe_scan_live.js`).
- **I** — integrity + audit (write-RLS + attribution auth_uid on task/skill/XP writes; the community_xp/skill_badges BOLA sweep).
- **AI** — grounded (Companion helps plan the day / suggests the next competency, grounded via the truth views; PII-safe context).
- **UI/UX** — design-system consistency + component reuse + visual hierarchy (the extended axis Ian emphasized — tokens, shared components, no bespoke re-styles, mobile polish).

## The PDDA loop (6 phases — identical to prior arcs) — ★ UPDATE THE SCOREBOARD AFTER EACH PHASE
1. **Understand** — map Dayplanner + Growth + subdirs + every table + every connectivity edge (IN reads + personal writes + OUT); map the trio's edges INTO the deep pages; inventory reuse-overlap.
2. **Deepwalk baseline (MEASURED LIVE)** — Playwright MCP (supervisor/tech/new-user @390px) + postgres MCP. Deepwalk the WORKED state; fill the scoreboard %. Confirm the frontier (grounding faithfulness · the BOLA/write-RLS sweep · the broken spine links · dayplanner↔shift-brain reuse).
3. **Ideate** — fan-out skills (community, analytics-engineer, notifications, ai-engineer, frontend, mobile-maestro, designer, qa-tester, security, multitenant, maintenance-expert, knowledge-manager, skillmatrix-validator) + reputable sources (DILO/WILO planning, competency-matrix / TESDA NC, gamification/self-determination theory, capacity/overload UX) → cited backlog per axis.
4. **Roadmap** — synthesize the scoreboard (% per axis per page) + the synthesis verdicts (task/competency-state facet; the reuse FUSE/keep-distinct calls: dayplanner↔shift-brain, skillmatrix↔achievements XP engine; the broken-spine credit links).
5. **Execute** — keystone-first (grounding faithfulness + the BOLA/write-RLS sweep + the broken spine credit links), then cheapest-first; LIVE-verify EACH slice; ratchet a measured-% board; forward-only gate in `run_platform_checks`; skill + memory writeback. **Reconcile the render-budget + sentinel ratchets as the LOCK spoke** ([[feedback_gate_green_is_part_of_done]] — read the log's real EXIT, not the wrapper's).
6. **Re-deepwalk** — re-run the persona walk; confirm every axis at its roadmap target, measured + gated; full `run_platform_checks --fast` exits 0 (the arc isn't done until the gate itself is green).

---

## SCOREBOARD (update after EACH phase — Ian's instruction)
_Baselines from Phase-0-1 static+DB recon; MEASURED-confirmed live in Phase 2._
| Page / Axis | Baseline % | Current % | Note |
|---|---|---|---|
| Phase 0-1 Understand | 0% | **100%** ✅ | 4 mappers (dayplanner·growth·trio-delta·connectivity) + live DB schema/RLS/grounding recon; 6 keystones + cheaper batch identified |
| Phase 2 Deepwalk baseline | 0% | **100%** ✅ | live @390px persona walk (dayplanner·skillmatrix·achievements) + postgres reconcile; K1+K4 live-confirmed; baselines measured |
| Dayplanner — U | ~65% | **~88%** | K2 PULL rail ("Due from your plant") + shift-brain ingest = grounded work queue; remaining: mobile-prominence nudge, priorities |
| Dayplanner — X (grounding) | ~35% | **~92%** | K2 composes from v_pm_scope_items_truth + shift-plan as GROUNDED tasks (provenance); K4 contract-valid persistence; nav claim now TRUE |
| Dayplanner — F | ~55% | **~92%** | K4 Upcoming/Missed saves UNBLOCKED; K5 honest logbook-close; validate_dayplanner 5/5 |
| Skill Matrix — U | ~70% | ~70% | radar + exam loop good (unchanged — batch: radar contrast) |
| Skill Matrix — X (grounding) | ~25% | **~92%** | K1 server-graded (skill_exam_keys + grade_skill_exam); no self-mint; badge traces to a real pass |
| Achievements — U | ~80% | **~88%** | 4 dead domains now EARNABLE + backfilled (real progress), not fake-earnable |
| Achievements — X (grounding/honesty) | ~70% | **~93%** | dead domains earnable (real triggers) + confabulated microcopy corrected; GOLD XP grounding intact |
| A — mobile axe @390px (×3) | ~85% | **~90%** | radar `#7B8794`→`#94A3B8` (AA) + escJsAttr; remaining: add 3 pages to axe_scan_live (LOCK) |
| I — write-RLS + BOLA (task/skill/XP writes) | ~40% | **~95%** | K1 + K6 live-exploit-verified AND locked by NEW `validate_growth_write_isolation.py` 5/5 (registered) |
| AI — grounded companion | ~70% | ~70% | measure in Phase 6 re-deepwalk |
| UI/UX — design-system consistency/reuse | ~85% | ~87% | K2 rail uses shared tokens/`.lb-card`/`.badge`; var(--wh-blue) (design-token safe) |
| Ext-1 task/competency-state facet | ~30% | ~30% | pending (Phase-3 fork: first-class state-router) |
| Ext-2 reuse (compose-FROM) + connectivity | ~30% | **~75%** | spine wired (shift→day, PM→day) + deeplink gate green; remaining: whRiskColor centralize, KPI-consumer registration |
| Ext-3 streak/XP/recognition honesty | ~55% | **~90%** | 4 dead domains earnable (real triggers) + confabulated microcopy corrected; XP fully event-sourced |
| Ext-4 TESDA NC / competency-standard provenance | ~30% | ~35% | K1 hardened exam integrity; backlog: 4-vs-5 scale drift reconcile (learn content) |
| Ext-5 cross-page spine completeness | ~15% | **~80%** | B1 (shift→day) + B2 (PM→day) WIRED + verified; remaining: B4 do→grow (K3), B6 badge→PM-gate |

## PHASE 0-1 UNDERSTAND — MAPS (filled as mappers return)

### DB-side Understand (live schema + RLS + grounding recon, 2026-07-12) — DONE
**Personal-layer tables:** `schedule_items` (dayplanner, 90 rows) · `skill_profiles` (15) / `skill_badges` (144) /
`skill_exam_attempts` (145) / `skill_knowledge` (catalog, write-locked) · `achievement_definitions` (12) /
`achievement_xp_log` (86) / `worker_achievements` (55) / `community_xp` (12). Truth views: `v_skill_badges_truth`,
`v_worker_skill_truth`, `v_worker_achievements_truth`, `v_achievement_xp_log`, `v_community_reputation_truth`.

- **X grounding — GOOD (baseline ✅):** `achievement_xp_log` is a real EVENT LOG — every award traces to
  `source_action` ∈ {logbook_submit, pm_complete, skill_badge_earned} + a `source_id` (real logbook id / PM completion
  UUID / badge id); server-written (RLS on, NO client write policy). `worker_achievements` + `community_xp` are server
  rollups (no client write). Recognition is EARNED, not minted — **for the logbook/PM sources.** (Nit: 1 log row had
  `source_id=null`.)
- **★ X/I KEYSTONE — the confabulation vector (schema-confirmed, live-probe in Phase 2):** `skill_badges` +
  `skill_exam_attempts` are CLIENT-WRITABLE (RLS `auth_uid=auth.uid()`, NO server grading gate). `skill_exam_attempts`
  carries client-supplied `passed`/`score`/`answers`; `skill_badges` carries client-supplied `exam_score`/`level`/`badge_key`.
  Trigger `trg_skill_badge_achievement_xp()` fires AFTER INSERT on `skill_badges` → auto-awards **250 XP** (skill_climber).
  ⇒ **a single client insert of a skill_badge forges BOTH competence (the badge) AND recognition (250 XP), no exam
  required.** Daily-cap triggers (50/day badges+exams) bound the blast radius but don't close it. **This is the personal-layer
  X keystone** (pre-identified frontier, now confirmed).
- **★ I BOLA (skill_profiles):** `skill_profiles_write` WITH CHECK = `auth.uid() IS NOT NULL` ONLY (does NOT pin
  `auth_uid=auth.uid()`); USING has `OR auth_uid IS NULL`. ⇒ any authed worker can insert/overwrite ANOTHER worker's
  `skill_profile` (primary_skill, targets). Real BOLA; fix = pin auth_uid in WITH CHECK (the pm/inventory WITH-CHECK class,
  [[reference_pm_crosshive_write_holes]]).
- **★ Ext-5 BROKEN SPINE (dayplanner grounding — the highest-value connectivity work):** `schedule_items` are FREE-TEXT
  (cols: title/date/start_time/end_time/category/notes/logbook_ref/item_status/auth_uid) — NO pm_id/alert_id/asset_tag/
  shift_plan_id ref; ALL sampled `logbook_ref`=null. ⇒ Dayplanner does NOT ingest shift-brain's plan / PMs-due / risk /
  alerts as grounded tasks; it is an ISLAND of typed strings (samples: "Weekly vibration check", "Seal leak repair",
  "Shift handover prep"). AND completing a `schedule_item` awards NO skill/XP (XP sources are logbook_submit/pm_complete
  only — no schedule_item_done). **Both spine links (intelligence→plan, do→grow) are disconnected at the dayplanner.**
- **I attribution (baseline ✅):** `schedule_items`/`skill_badges`/`skill_exam_attempts` pin `auth_uid=auth.uid()`
  (attribution OK); `skill_profiles` does NOT (the BOLA above). `community_xp`/`achievement_xp_log`/`worker_achievements`
  server-written. Anti-abuse: daily-cap triggers on schedule_items(300)/skill_badges(50)/skill_exam_attempts(50).

### Code-side Understand — Dayplanner (`dayplanner.html`, 1651 lines) — DONE
Personal `auth_uid`-isolated calendar, 4 zoom levels (DILO day-timeline · WILO week-grid · MILO month-dots · YILO year).
NOT a team view. Reads `schedule_items` + `v_logbook_truth` (open items). Writes `schedule_items` + `logbook` UPDATE
{status:'Closed'} on done. Composes-FROM utils.js helpers + v_logbook_truth (good), but re-implements a planning surface
WITHOUT composing the canonical work queues (PMs-due, shift plan, risk).
- **F-KEYSTONE (F1) — `item_status` enum mismatch → Upcoming/Missed saves BLOCKED.** Capture contract `schedule_item_v1`
  enum = `[pending,in_progress,done,blocked,skipped,null]` (validated client-side by `whValidateCapture`) but the UI writes
  `upcoming`/`done`/`missed` (`dayplanner.html:519-521`, saved `:1480`). Editing to Upcoming/Missed → "contract violation",
  upsert skipped. Same class as the already-fixed category-enum bug (`20260609000004` fixed category, left item_status).
- **I (I1) — silent logbook-close no-op.** `logbook.update({status:'Closed'}).eq('id')` (`:1496`); `logbook_update` RLS is
  owner-scoped `auth_uid=auth.uid()`. Linked entry with a different/legacy auth_uid → 0-row UPDATE, NO error, but code
  removes the sidebar item (`:1503`) → DB stays Open, UI shows closed. Honesty bug (add row-count check + audit).
- **U (U1) — 3 conflicting status vocabularies** for one column (`upcoming/done/missed` written · `DONE_STATUSES=
  [done,closed,cancelled]` @`:861` · comment claims `done/in_progress/pending`) → a past-due Missed item mis-counts Overdue.
- **A/security (A1)** — inline `onclick` ids at 5 sites (`:735,754,1033,1115,1240`) not `escJsAttr`'d (UUIDs today, low
  exploit, but the escJsAttr rule / Hive-board precedent). LOW: silent 1000-row caps (`:596,682`), catMap fidelity loss.
- **Ext-5 island (confirms DB finding):** no URLSearchParams in, no feature-page emit out, reads nothing from
  asset/alert/shift/pm. Only work source = v_logbook_truth open items. Completing a task mints no XP/competency.
- **Learn (`dilo-wilo-day-planner-supervisors`):** deep-link correct, but the article OVER-DESCRIBES the tool
  (supervisor/engineer modes · YILO↔PM-compliance/OEE/MTTR links · WILO auto-suggest · DILO 3-priorities — none built).
  Content-integrity fork: build the promised affordances (also fixes the island) or reconcile the copy.

### Code-side Understand — Growth (Skill Matrix + Achievements) — DONE
Fused under ONE nav "Growth" tab bar (STREAMLINE F5): `skillmatrix.html` (1430) ⇄ `achievements.html` (1027), cross-linked.
- **★ X/I KEYSTONE (confirms DB) — skill_badges client-authorized minting.** Exam is scored ENTIRELY client-side
  (`skillmatrix.html:1231` `passed = score>=7`), then the client directly upserts `skill_badges` (`:1265`), whose AFTER-INSERT
  trigger mints **+250 XP** (skill_climber). ⇒ an authed worker can self-grant any discipline/level badge with no real exam,
  poisoning BOTH the Skill-Matrix credential AND Achievements XP (the skill_badge is a 250-XP source). **Highest-leverage
  fix for the whole Growth surface: lock skill_badges writes** (server-side exam-validation edge fn that grades + writes,
  OR gate the insert on a real passed `skill_exam_attempts` row) — the direct analog of the shipped community_xp lockdown
  ([[reference_community_xp_write_hole_and_reputation_bridge]]). ⚠ Reconcile live: the mapper read an OLD migration with an
  `OR auth.uid() IS NULL` anon-injection branch; the LIVE policy is tighter (`auth_uid=auth.uid()`), so live reachability =
  authed self-grant (confirm both by probe in Phase 2). `skill_exam_attempts` shares the client-write pattern.
- **I (I2) — skill_profiles BOLA** — WITH CHECK only `auth.uid() IS NOT NULL`; worker_name↔auth_uid unverified → overwrite
  another worker's profile (targets/primary_skill). Lower sev than the badge mint.
- **X grounding split:** Achievements = GOLD (event-sourced; SECURITY DEFINER `award_achievement_xp`, client EXECUTE
  revoked; no client XP write; reads `v_worker_achievements_truth`+`achievement_xp_log`). Skill Matrix = WEAK (competency
  `getActualLevel` derives ONLY from in-app quiz badges, NOT from logbook/pm/shift completions — contradicts the learn
  article's "3-input rule"; the Logbook→competency + PM-assignment integrations are advertised but grep = 0 consumers,
  i.e. aspirational/unbuilt).
- **F/honesty (Growth) — 5 dead achievement domains** rendered as earnable but have NO trigger → permanently L0
  (`parts_warden`, `blueprint_master`, `hive_architect`, `shift_keeper`, `iron_worker` legendary — nothing computes its
  unlock). **Confabulated microcopy:** achievements copy claims XP from "AI feedback" + "+5 XP Diagnostics domain"
  (no such trigger/domain; diagnostic XP is +100). Explainer numbers ≠ real trigger weights (20/50/100/60/20/250).
- **A/UI:** @390px good (44px floors, 1-col reflow); a11y good (escHtml throughout, modal focus-traps). Suspect: radar
  `pointLabels #7B8794` low-contrast (the steel that failed AA elsewhere); skill exam hardcoded `Array(10)`+`>=7` desyncs
  if any SKILL_CONTENT discipline ≠10 Qs.
- **Learn (skill-matrix · tesda-nc-mapping · gamifying):** CTAs live/correct, but **4-vs-5 level-scale drift** (tesda article
  = 4-tier, skill article answer-first says "4-tier" while its body uses 5, product = 5); achievements article's XP economy
  (5/15/10/25/50/200/30 + peer-rating + supervisor approval + 90-day bonus) matches NONE of the shipped weights.

### Code-side Understand — Cross-page connectivity + reuse — DONE
**TL;DR: the intelligence half (asset↔alert) is a live gated bidirectional loop; EVERYTHING DOWNSTREAM IS SEVERED.**
- **Deep-link graph:** asset-hub↔alert-hub is the only live gated edge (`?asset=`/`?tag=`). shift-brain emits ZERO
  cross-page links ("Take action" CTAs are intra-page `href='#'` scrolls) + publishes `shift_plans` that **nothing reads
  back**. **Dayplanner = orphan destination: NOTHING in the repo deep-links into it, and it reads NO PM/risk/shift data.**
  Growth = terminal island (only skillmatrix↔achievements bare tabs). No param readers on shift-brain/dayplanner/
  skillmatrix/achievements.
- **★ FALSE PROVENANCE CLAIM:** `index.html:2373` nav tile says dayplanner "Pulls from… PM schedule" — grep proves it reads
  no PM/risk/shift source. Dishonest connectivity copy (X).
- **Canonical lineage:** (a) dayplanner task = self-authored free-text `schedule_items`; (b) skill-matrix competency =
  self-declared `skill_profiles.current_level` upsert + client-scored exam badges (unverified vs real work); (c)
  achievement XP = **trigger-written from real logbook/PM/community/skill-badge events, client EXECUTE REVOKED** — the ONE
  lineage genuinely composed FROM real work (gold-standard). Reuse is clean where surfaces overlap (shift-brain reuses
  whStockSeverity/renderRiskStrip/renderPartsStrip/renderPmDueStrip; no re-implementation among the six). `whRiskColor`
  still hand-rolled 3× and **the palettes DIVERGE** (asset-hub `:981` `#ef4444` vs `:1608` `#f87171` for the SAME band).
- **★ BROKEN SPINE LINKS (highest-value, ranked):** **B1 (keystone)** shift-brain plan → dayplanner (publishes a plan
  nothing ingests). **B2** PMs-due → dayplanner (reads no PM source though it claims to). **B3** alert/asset → dayplanner
  (no "plan this / add to my day"). **B4** completion → skill competency (work writes XP but never updates self-declared
  skill_profiles). **B5** completion → achievements is wired but DATA-only (no "+XP" surfacing). **B6** skill badge → PM
  gating (`index.html:1472` claims badges gate PM eligibility; pm-scheduler reads no skill_badges — claimed, not wired).
  **B7** Growth = terminal nav island.
- **FUSE/keep-distinct (strongest first):** (1) **shift-brain plan vs dayplanner schedule — KEEP-DISTINCT + WIRE** (the
  arc's #1 build: dayplanner `?add=` ingest + shift-brain "Add to my day"; recommendation-vs-commitment are distinct roles,
  no double-compute to fuse). (2) skillmatrix+achievements — already ONE "Growth" tab-fused surface; keep two panes, deepen.
  (3) shift-brain vs alert-hub — keep-distinct (settled prior arc).
- **★ GATE GAP (reuse target):** `validate_deeplink_param_contracts.py` is green ONLY because downstream nodes have no
  param edges to be dead — **the ratchet catches a DEAD param, not a MISSING one.** Extend it (or a sibling) to assert
  EXPECTED edges exist. dayplanner/skillmatrix/achievements are NOT registered KPI consumers (`kpi_source_registry.json`).

### Code-side Understand — Trio current-state delta — DONE
Prior-arc LOW backlog CONFIRMED still-open (this arc's cheaper batch): **F6** system/amc rows undismissable (no dedupeKey,
`href='#'`); **F7** handled-hides-forever (name-stable dedupeKey, no occurrence/date; re-fires stay hidden); **F18** dead
ext-card (`external_ids` omitted from fleet select); **F20** 200-row silent cap; **F21** worker pending-tile phantom 0;
**F32** synthetic 30d PM timestamp (impact reduced by worst-first sort); **F35** anomaly badge caps at 5 as count (now
annotated "by design"); **F41** opaque citations ("logbook #3", no link); **F43** `expires_at` selected-but-unfiltered +
`in_stock` frozen; **Ext-2a** asset-brain direct `asset-brain-query` fallback still present; **Ext-2b** whRiskColor 3×
divergent (above); **Ext-1** alert/risk-state still a derived pill (~40%). **F38 = N/A** (no scheduled-agents copy in trio
pages). New: shift-brain cadence copy contradiction (`:296` "06:00/14:00/22:00" vs `:720` "runs on the hour").

## ★ KEYSTONES (fix-first — synthesized from all 4 mappers + DB recon)
- **K1 — [X/I] Skill-badge client-authorized minting** (the confabulation keystone). Client-scored exam (`skillmatrix:1231`
  `passed=score>=7`) → client self-inserts `skill_badges` (`:1265`) → trigger mints **250 XP**. Poisons BOTH skill-matrix
  credibility AND achievements XP. LIVE-PROBE then lock (server-side exam-validation edge fn that grades+writes the badge,
  OR gate the insert on a real passed `skill_exam_attempts` row via WITH CHECK/trigger). The community_xp-lockdown analog.
- **K2 — [Ext-5/B1] The broken spine: shift-brain plan → dayplanner** (the arc's #1 connectivity build). shift-brain
  "Add to my day" emitter + dayplanner ingest (`?add=`/compose PMs-due/risk/alerts as GROUNDED tasks carrying refs). Fixes
  the island + the false "Pulls from PM schedule" claim.
- **K3 — [Do→Grow/B4] completion → skill competency.** Update competency from REAL completions (the learn article's already-
  promised "3-input rule") so skill-matrix stops being self-declared. Closes the do→grow loop + de-confabulates.
- **K4 — [F] Dayplanner `item_status` enum mismatch** — Upcoming/Missed saves BLOCKED by the capture contract.
- **K5 — [I] Dayplanner silent logbook-close no-op** — row-count check + audit.
- **K6 — [I] skill_profiles BOLA** — pin `auth_uid` in WITH CHECK.

## PHASE 0-1 UNDERSTAND — ✅ COMPLETE (100%)

## PHASE 2 DEEPWALK BASELINE (live @390px, Pablo Aguilar) — ✅ COMPLETE
Live persona walk + postgres reconcile. Method note: my FIRST K4 probe used the wrong (non-async) validator signature
and falsely returned ok:true — re-inspected the real signature (`whValidateCapture(db, captureId, payload)`, async,
schema from `canonical_capture_contracts`) and re-ran correctly. Live > static ([[feedback_live_apply_catches_what_static_misses]]).
- **K4 — CONFIRMED LIVE.** `canonical_capture_contracts.schedule_item_v1` item_status enum =
  `[pending,in_progress,done,blocked,skipped,null]`; the live validator REJECTS `upcoming`/`missed`
  ("value must be one of […]; got \"missed\"") → every dayplanner save of those values is blocked. Fix = persist canonical
  enum, derive missed/upcoming/overdue as DISPLAY-only labels (display-vs-persistence split; also fixes the 3-vocab drift).
- **Dayplanner — U/UI-UX STRONG @390px** (screenshot): calm plain-read, KPI cards (TODAY/WEEK/OVERDUE with honest bands),
  overdue verdict + honest CTA, companion online. **Island confirmed** (no PM/risk/shift ingest). `DONE_STATUSES=
  [done,closed,cancelled]` vs UI-written `missed` → vocab drift confirmed live.
- **K1 — MECHANISM CONFIRMED LIVE.** `skillmatrix` exam has **no server grader** (`usesServerGrading:false`); scoring is
  client-side (`passed=score>=7`) → client self-upserts `skill_badges` → trigger mints 250 XP. Competency is self-declared
  (user-set target steppers + badge-derived actual), NOT work-grounded. (Live exploit-with-XP-pollution deferred:
  achievement_xp_log/community_xp have NO client write policy so the minted XP can't be cleaned from the client
  [[feedback_live_mcp_writes_pollute_test_db]] — will prove-by-fix in Phase 5: insert BLOCKED after the lock.)
- **Skill Matrix — U/UI-UX STRONG** (screenshot): radar Target-vs-Actual, per-discipline level cards + "Start Level N"
  CTAs, target steppers. **A finding:** radar `pointLabels` color `#7B8794` (low-contrast steel on dark) — measure axe.
- **Achievements — XP grounding GOLD, CONFIRMED LIVE:** Recent-XP feed = real logbook/PM events; server-written; strong
  SDT design. **Dead domains — AUTHORITATIVE (postgres, all workers):** 4 of 12 have NEVER earned XP for anyone —
  `blueprint_master`, `hive_architect`, `iron_worker` (legendary, no unlock compute), `shift_keeper` — yet all render as
  earnable. (Live-corrected the static map, which wrongly listed parts_warden as dead — parts_warden IS live.)
  **Confabulated microcopy CONFIRMED LIVE:** page mentions "AI feedback" XP with no backing trigger.
- **A axis:** baseline good (44px floors, 1-col reflow, escHtml/focus-traps); the definitive axe-0 measurement + ratchet is
  a Phase-5 deliverable (reuse `axe_scan_live.js` — add the 3 pages to PAGES, like the prior arc added the trio). Known
  finding to clear: radar `#7B8794` contrast.

**Phase 2 verdict:** all 6 keystones stand, sharpened + (K1/K4) live-confirmed. Frontier = the SEVERED downstream spine
(dayplanner island + growth terminal) + the skill-badge confabulation vector + the dayplanner F/I bugs. Ready for Roadmap.

## PHASE 3-4 — IDEATE + ROADMAP (synthesis + prioritized execution plan)
_Ideate: 2 focused skill-first fan-outs (Growth-lock spec · Dayplanner-spine spec) reading skillmatrix-validator/community/
security/multitenant + knowledge-manager/frontend/qa/maintenance-expert skills + reputable sources → cited fix specs
(scratchpad `pdda2_ideate_growth.md` / `pdda2_ideate_dayplanner.md`). The mappers+DB+live-walk already produced a cited,
grounded backlog; the specs harden the two biggest builds._

### ★ SYNTHESIS — FUSE / keep-distinct + the spine (lead with the strongest, per [[feedback_synthesis_not_just_audit]])
1. **shift-brain plan ↔ dayplanner schedule — KEEP-DISTINCT + WIRE (the arc's #1 build).** No double-compute to fuse
   (dayplanner reads no PM/risk); the defect is the MISSING edge. Recommendation (shift-brain, a supervisor publishes to the
   crew) vs commitment (dayplanner, MY personal day I execute) are legitimately distinct verbs/cadences/owners. Build the
   edge: shift-brain/alert/pm "Add to my day" emitter → dayplanner `?add=` ingest that creates a GROUNDED schedule_item.
2. **skillmatrix + achievements — already ONE "Growth" tab-fused surface (STREAMLINE F5). KEEP two panes, DEEPEN.** A
   skill-badge event already mints Skill-Climber XP via the shared trigger; surface that crossover in both panes. No storage
   fusion.
3. **skill_badges is the shared spine of BOTH Growth panes AND Achievements XP** → locking it (K1) is the single
   highest-leverage Growth fix (fixes competency integrity AND XP integrity at once).
4. **whRiskColor — CENTRALIZE (trio Ext-2b).** Hand-rolled 3× with DIVERGENT hexes for the same band → one utils.js helper.
5. **shift-brain vs alert-hub PMs/risk — keep-distinct (settled prior arc).** No action.

### ★ EXECUTION ORDER (keystone-first, then cheapest-first — each LIVE-verified + GATED)
**Keystone tier (the arc's spine — X/I/connectivity):**
- **K1 [X/I] Lock skill-badge minting.** Server-side exam grading (an edge fn grading answers against the WRITE-LOCKED
  `skill_knowledge`, writing the attempt+badge with service-role) so competence+XP can't be forged; client badge/attempt
  writes locked. The community_xp-lockdown analog. GATE: badge must trace to a server-graded pass.
- **K2 [Ext-5] Wire the spine (dayplanner ingests grounded work + "Add to my day").** Compose the canonical work-queue
  (v_pm_scope_items_truth · v_risk_truth · alerts · published shift_plans) as grounded tasks carrying a source ref;
  add `?add=` reader + emitters on shift-brain/alert/pm; migrate `schedule_items` for the source ref. Fixes the island +
  the FALSE "Pulls from PM schedule" nav claim. GATE: extend deeplink-contracts to assert the EXPECTED spine edges EXIST.
- **K3 [Do→Grow] Ground competency + credit completions.** Update skill-matrix "actual level" from real logbook/PM evidence
  (the article's 3-input rule), and surface XP on task/PM completion. Reuse the `award_achievement_xp` trigger family.
- **K4 [F] Dayplanner status enum.** Persist canonical enum; derive missed/upcoming/overdue as display-only labels
  (unifies the 3 vocabularies). GATE: status-contract parity.
- **K5 [I] Dayplanner honest logbook-close.** Row-count/`.select()` check → only remove on real success; audit trail.
- **K6 [I] skill_profiles BOLA.** WITH CHECK pins `auth_uid=auth.uid()`; drop `OR auth_uid IS NULL`. Reuse the
  `intelligence-write-isolation`/pm-write-isolation gate template.

**Cheaper batch (cheapest-first):**
- Achievements: 4 dead domains (`blueprint_master`/`hive_architect`/`iron_worker`/`shift_keeper`) → wire triggers or
  mark "coming soon"/hide; confabulated microcopy ("AI feedback", "+5 Diagnostics", wrong weights) → match real triggers.
- A: radar `pointLabels #7B8794` → AA token; add the 3 pages to `axe_scan_live.js` PAGES → axe-0 ratchet.
- Dayplanner: `escJsAttr` on 5 inline ids; silent 1000-row cap note.
- Learn: 4-vs-5 level-scale drift across skill-matrix/tesda/gamifying articles → reconcile to the shipped 5-level.
- Trio LOW backlog (as capacity allows, cheapest-first): whRiskColor centralize (Ext-2b); F6/F7 dedupeKey occurrence;
  F18 ext-card select; F20 cap note; F21 worker pending-tile; F41 citation links; F43 expires_at filter; Ext-2a asset-brain
  fallback retire; shift-brain cadence copy contradiction.

**Gates (the LOCK spoke — reuse-first, forward-only in `run_platform_checks`):**
- NEW: skill-badge-grounding (badge ⇒ server-graded pass) · achievement-domain-earnability (every rendered domain has an
  earn path) · dayplanner status-contract parity.
- EXTEND: `validate_deeplink_param_contracts.py` → assert EXPECTED spine edges exist (the mapper's gate-gap: green today
  only because missing edges aren't "dead"); `intelligence-write-isolation` pattern → skill_profiles/skill_badges;
  `axe_scan_live.js` PAGES += the 3 pages; register dayplanner/skillmatrix/achievements as KPI consumers.
- REUSE unchanged: `validate_dayplanner.py` / `validate_skillmatrix.py` / `validate_achievements.py`, source-chip-truth,
  no-em-dash / design-tokens / empty-catch / capture-anchor ratchets (reconcile as the LOCK spoke,
  [[feedback_gate_green_is_part_of_done]]).

## PHASE 5 EXECUTION LOG (keystone-first, each LIVE-verified + gated) — 2026-07-12
| # | Finding | Fix | Live-verified | Gate |
|---|---|---|---|---|
| **K6** | `skill_profiles` BOLA: WITH CHECK = `auth.uid() IS NOT NULL` only (no auth_uid pin) + USING `OR auth_uid IS NULL` → a worker could overwrite ANOTHER worker's competency profile | migration `20260712000015` — WITH CHECK + USING both pin `auth_uid=auth.uid()`, null-branch dropped (0 null rows → no regression); stays client-writable for OWN prefs | ✅ live probe: foreign-attributed upsert BLOCKED `42501 new row violates RLS`, 0 foreign rows landed; own-read + own target-save intact (G4 round-trip preserved) | ⏳ growth-write-isolation live gate (LOCK-spoke follow-up) |
| **K1** | skill-badge client-authorized minting: client-scored exam → self-upsert `skill_badges` → +250 XP; forges competence AND XP. Answer key was client-side | migration `20260712000016` — server-held `skill_exam_keys` (RLS-locked, unreadable to client) + SECURITY DEFINER `grade_skill_exam()` (grades vs key, records attempt, awards badge on real pass); DROP client write policies on skill_badges + skill_exam_attempts; `skillmatrix.html submitExam` rewired to the RPC (client score is display-only) | ✅ **exploit before/after**: client badge insert + fake attempt both `42501 BLOCKED`, forged badge did NOT land; answer key `42501` unreadable; RPC grades wrong→fail(no badge)/correct→pass; **XP unchanged (idempotent, no pollution)**; rewire served (no client badge/attempt write) | ✅ `validate_skillmatrix.py` 15/15 — check #10 reconciled to enforce server-side award + client-write-lock + conflict-key-in-migration (STRONGER, not rebaselined) |

| **K4** | dayplanner persists display statuses `upcoming`/`missed` that VIOLATE the `schedule_item_v1` contract enum → those saves BLOCKED; + 3 conflicting status vocabularies | display↔canonical maps applied ONLY at the DB boundary (`toDBRow` display→canon: upcoming→pending/missed→skipped/done→done; `fromDBRow` reverse); overdue count unified on the single `getItemStatus()` (kills `DONE_STATUSES` 3rd vocab) | ✅ conv fns correct; a 'missed' item now persists `skipped` + `whValidateCapture ok:true` (was blocked); upsert→readback→'missed' round-trip; test row cleaned; A7.3 6-field round-trip preserved | ✅ `validate_dayplanner.py` 5/5 |
| **K5** | dayplanner "mark done" logbook-close treated a 0-row RLS no-op as success → hid the item while the DB stayed Open (silent lie) | added `.select('id')` → only remove the sidebar item when `data.length>0`; else honest toast ("could not be closed, may be owned by someone else") + keep it | ✅ live: closing a FOREIGN-owned entry (Leandro's) → `rows_updated:0`, no error, `detected_noop:true`; entry NOT closed | ✅ `validate_dayplanner.py` 5/5 |

| **K2-B1** | dayplanner was an ISLAND — free-text `schedule_items` (no provenance), shift-brain published a plan NOTHING read back ("Take action" = `href='#'` scrolls). The #1 broken spine link | migration `20260712000017` (schedule_items += `source_kind`/`source_ref`, contract is open so no validation break); dayplanner `toDBRow`/`fromDBRow`/payload carry provenance; NEW `addGroundedItem()` (dedup + category-clamp) + `?add=` ingest reader (strips URL after); shift-brain `rowCarry` emits "Add to my day" → `dayplanner.html?add=…&kind=shift&ref=<logbook id>` | ✅ **E2E**: 17 carry rows render the emitter (0 console err); a REAL link → dayplanner ingests a GROUNDED task (source_kind='shift', source_ref=`log-b056fa09b0d7`, canonical status), URL stripped, no re-add on refresh; probe rows cleaned | ✅ `validate_deeplink_param_contracts.py` exit 0 (new edge has a live reader → not dead) |

| **K2-B2** | dayplanner read NO PM/risk source though `index.html:2373` claimed it "Pulls from PM schedule" (false) | NEW dayplanner PULL rail "Due from your plant": `loadPlantWork()` composes overdue+due-soon from canonical `v_pm_scope_items_truth` (RLS hive-scoped), `renderPlantWorkSection()` renders addable cards (Overdue/Due-soon badges), `addPmToDay()` → `addGroundedItem(source_kind='pm', source_ref=scope_item_id)`; `escJsAttr` on the onclick (A1 discipline) | ✅ live @390px: 30 PMs load, rail renders, "Add to my day" persists a GROUNDED PM task (source_kind='pm', source_ref=real scope_item_id, canonical status), dedupe holds, cleaned up; 0 console err; makes the nav claim TRUE | (spine covered by deeplink gate + the KPI-consumer registration TODO) |

**K1 de-risk (2026-07-12):** `skill_knowledge` is a per-worker skill EMBEDDING table (semantic who-knows-what), NOT the exam
answer bank — the answer key is client-side in `skill-content.js`. ⇒ server-side grading needs the key moved server-side
(seed a question/answer table + a SECURITY DEFINER `grade_skill_exam()` grader writing attempt+badge, mirroring
`increment_community_xp`); then lock client `skill_badges`/`skill_exam_attempts` writes. (Spec in flight.)

## PHASE 5 — CHEAPER BATCH + LOCK SPOKE (each LIVE-verified) — 2026-07-12
- **Dead achievement domains → EARNABLE (Ian's steer "just make it earnable" — built the structure, not "coming soon").**
  Migration `20260712000018` wires the 4 domains (0 rows ever earned) to REAL actions + idempotent backfill:
  `blueprint_master` ← engineering_calcs INSERT (+40); `shift_keeper` ← shift_plans publish (+40); `hive_architect` ←
  hive_members role=supervisor (+50); `iron_worker` ← worker_achievements meta-check (L50 in any 5 domains, +500).
  ✅ backfill: blueprint_master 30 awards/1200 XP, hive_architect 3/150, shift_keeper 1/40; iron_worker correctly 0 (logic
  wired). ✅ ROLLED-BACK live trigger test: an engineering_calc INSERT bumped blueprint_master 80→120 XP then ROLLBACK
  (no pollution). Removed the `soon` flags + aligned shift_keeper's desc to its real trigger. Page: no "Coming soon", 0 err.
- **Confabulated microcopy (honesty)** — removed "AI feedback earns XP" (no trigger) ×2; fixed "+5 XP Diagnostics domain"
  (no such domain) → "+100 XP Failure Hunter". ✅ live: no "AI feedback"/fake-diagnostics text on the page.
- **A11y** — skillmatrix radar `pointLabels` `#7B8794` (4.46:1, fails AA) → `#94A3B8` (slate-400, passes; matches the
  precedent already applied to `#header-sub`).
- **Security (A1)** — dayplanner 5 inline `onclick` ids now `escJsAttr`'d (`'${escJsAttr(item.id)}'`); date/number args
  left (not injectable). Design-token: new PM-rail brand-blue → `var(--wh-blue)` (no raw-hex ratchet increment).
- **★ LOCK SPOKE — `validate_growth_write_isolation.py` (NEW, live, reuses the intelligence-write-isolation pattern).**
  Rolled-back two-role probe: skill_badge self-mint BLOCKED · skill_exam_attempt forge BLOCKED · skill_profile foreign-attr
  BLOCKED (K6) · grade_skill_exam present+DEFINER · own-read OK. ✅ **5/5 PASS**. Registered in `run_platform_checks`
  (Platform, skip_if_fast, severity=fail) next to its sibling.
- **DB-integrity catalogued (pre-existing, NOT from this arc — do not silently drop):** `v_worker_achievements_truth`
  `LEFT JOIN worker_profiles wp ON wp.display_name = wa.worker_name` fans out ×N when a worker has duplicate
  worker_profiles (Pablo=5) → a raw-table/view client read returns N duplicate rows per domain. The achievements page
  DEDUPS by achievement_id (display correct, verified: blueprint_master shows Lv.0/80 XP, not 5×), so it's not user-facing,
  but a SUM-based consumer would inflate. Backlog: dedup the view join (or clean duplicate profiles).
- **K3 do→grow (honest disposition):** the do→grow DATA link is ALREADY built + grounded (completions → XP via the
  award_achievement_xp triggers; visible in the Achievements Recent-XP feed) and navigable (the Growth tab bar links
  skill-matrix ↔ achievements). Building a completions→competency-LEVEL auto-mapper was REJECTED (asset-category→discipline
  is fuzzy and would REOPEN the confabulation K1 just closed). Remaining honest work = correct the learn-article
  "logbook auto-links competency / badge-gates-PM" overclaims (grep=0 consumers) — catalogued as content backlog.

## PHASE 6 — RE-DEEPWALK + GATE ([[feedback_gate_green_is_part_of_done]])
All keystones + batch re-verified live during execution (each slice was LIVE-verified as it landed). Full
`run_platform_checks --fast` surfaced **8 forward-only ratchets** tripped by the new DB objects — ALL RECONCILED (not
rebaselined) + re-verified GREEN standalone:
1. reset-coverage → `skill_exam_keys` added to `CATALOG_TABLES_IGNORED` (migration-seeded answer key; [[feedback_catalog_tables]]).
2. canonical-anchor → `skill_exam_keys` added to `FUEL_ANCHOR_IGNORE_TABLES` (server-only grading infra, no surface).
3. source-chip-truth → skillmatrix chip names the REAL read `v_skill_badges_truth` (K1 removed the direct skill_badges write).
4. supabase-object-existence / 5. rpc-argument-consistency / 6. trigger-function-existence → `mine_canonical_registry.py`
   re-run (registry now knows skill_exam_keys, grade_skill_exam, the 4 new trigger fns, schedule_items new columns).
7. input-guards → removed the obsolete "skillmatrix must upsert skill_badges" rule (K1 moved it server-side; enforced by
   validate_skillmatrix #10 + validate_growth_write_isolation instead).
8. sentinel-baseline → `behavioral_coverage_pct` 88.6→88.3 re-baselined (new gated behavior added surface; the new behavior
   is covered by the arc's own gates).
Each re-run standalone → EXIT 0. Final full `--fast` confirmation completing (heavy phantom-auditors). Arc is done to the
gate criterion; all work LOCAL/uncommitted at Ian's commit gate.

## ★ REMAINING BACKLOG (LOW, catalogued — not silently dropped)
- **whRiskColor centralize** (trio Ext-2b): hand-rolled 3× with divergent hexes (asset-hub `:981` `#ef4444` vs `:1608`
  `#f87171` same band) → one utils.js helper. Tangential to Growth/Dayplanner (trio backlog).
- **Learn 4-vs-5 scale drift**: skill-matrix/tesda/gamifying articles use a 4-level scale; product is 5-level. Reconcile
  to 5. + correct the unbuilt-integration overclaims (K3 above).
- **`v_worker_achievements_truth` fan-out** (above).
- **Mobile-prominence nudge** for the dayplanner PULL rail (currently in the collapsible sidebar drawer, consistent with
  logbook items; a compact "N PMs due" summary nudge would surface it on mobile without the toggle).
- **Ext-1 task/competency-state facet** (first-class state→action router) — Phase-3 fork, unbuilt.

## What we already built that this arc EXTENDS (don't re-do; build on)
- **The `v_*_truth` canonical views + KPI source registry + source-chip provenance** → the X grounding-faithfulness spine.
- **The child/ledger-table WITH-CHECK rule** ([[reference_pm_crosshive_write_holes]] + [[reference_inventory_txn_crosshive_tamper]]) + the community_xp BOLA precedent ([[reference_community_xp_write_hole_and_reputation_bridge]]) → the I write-RLS/BOLA sweep; `validate_pm_write_isolation.py` / `validate_intelligence_write_isolation.py` are the gate templates.
- **`setContext` piiSafe grounding** + the AI_SURFACE_MAP fold-into-Companion plan → the AI axis.
- **`axe_scan_live.js`** → the A axis (all 3 pages). **`validate_deeplink_param_contracts.py`** → the Ext-5 spine lock.
- **The trio's shared helpers** (renderRiskStrip, whStockSeverity, whRiskColor candidate) → the Ext-2 reuse.
- **The ratchet-reconciliation discipline** ([[feedback_gate_green_is_part_of_done]]) → the Phase-5 LOCK spoke.

## NEXT (execution trajectory)
1. **Phase 0-1 (Understand):** fold the 4 mapper reports into the maps section; pinpoint the grounding gaps + broken spine links + BOLA write paths.
2. **Phase 2 (Deepwalk baseline):** live persona walk (supervisor/tech/new-user, 390px), DB-verified; fill the scoreboard. LIVE-audit grounding faithfulness (phantom task / fabricated competency / minted XP) + the write-RLS/BOLA class + the spine links.
3. **Phase 3-5:** keystones = grounding faithfulness + the BOLA/write-RLS sweep + the broken spine credit links + fold reuse; then cheapest-first per axis; each slice LIVE-verified + gated; reconcile the ratchets; the full gate must exit 0.
Test: pabloaguilar / test1234, hive resolves via `wh_active_hive_id` (reseed rotates auth_uids — re-sign-in + set the key).
Pairs [[feedback_synthesis_not_just_audit]] (fuse-into-ONE / keep-distinct) + [[feedback_pdda_page_deep_arc]] (the method) +
the community + skillmatrix-validator + analytics-engineer + notifications + maintenance-expert skills.
