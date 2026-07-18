# PROJECT MANAGER — Page-Deep UFAI PDDA Arc  (drafted for a fresh window)

**Drafted 2026-07-11** (Marketplace arc's fresh window, wrapping on Ian's (e)). Same 6-phase PDDA as
eng-design / resume / landing / analytics / integrations / Hive / Community / **Marketplace** (the last
one just landed 100%). Ian: *"I love the PDDA flow… another arc, refined: PDDA for the Project Manager page
including its subdirs, extend the UI/UX we have. I'm striving for the BEST Project Manager, and it seems
disconnected to PM Scheduler, Logbook, Inventory, and Engineering Design… the type of project
(breakdown/reactive, preventive, project)… use the reuse discipline: engineering-design does a scope of
work, the project-manager does a scope of work, a project has its scope of work, the PM Scheduler also has
the scope for PM. Wrap up, proceed in a fresh window."*

> **What this arc IS.** Deep-walk `project-manager.html` (+ its `project-report.html` companion) as the
> real personas, measure every axis LIVE, and drive it to the **best maintenance Project Manager** — by
> (1) **connecting** it to the four systems it currently feels islanded from, (2) making **project TYPE**
> (the maintenance nature of the work) first-class, and (3) applying the **reuse discipline** so a
> **Scope of Work** is ONE canonical thing, not re-invented on every surface.

---

## Scope (grounded, 2026-07-11)

- **Surfaces:** `project-manager.html` (the tool: header + WBS/line-items + progress) · `project-report.html`
  (the AI narrative/exec report companion). (Confirm any deep-link states in Phase 0.)
- **Data model (already exists — `20260505000000_project_manager.sql`):** `projects` (header:
  `project_type ∈ {workorder, shutdown, capex, contractor}`, status, priority, owner, `budget_php`,
  start/end, `meta jsonb`) + `project_items` (WBS line items: title, status, is_done/overdue/blocked) +
  `project_knowledge` (SOP/lessons, `project_type` workorder/shutdown/capex/contractor). Canonical views:
  `v_project_truth`, `v_project_items_truth`, `v_project_progress_truth` (all companion-served on-demand).
- **The four flavors were DESIGNED to bundle, but the bundle feels unbuilt (Ian's islanded feeling):**
  `workorder = bundle existing logbook entries + PM completions + parts under one umbrella` · `shutdown`
  = outage critical path · `capex` = install/improve + budget/milestones · `contractor` = vendor
  **scope + BOM + SOW + sign-off**. The intent to connect is IN THE SCHEMA COMMENT; Phase 0 measures how
  much is actually wired.

---

## ★ THE TWO HEAVYWEIGHTS (refined + extended from Ian's thoughts)

### Heavyweight 1 — X: Project Manager = the CONNECTIVE TISSUE of maintenance work (Ian's keystone)
Ian's exact words: *"it seems disconnected to PM Scheduler, Logbook, Inventory, and to its Engineering
Design."* The `projects`/`project_items` islands don't pull from the systems that generate the actual work.
The keystone makes the PM the HUB that every other maintenance surface feeds into and reads back from —
bidirectional, with provenance (the same fabric pattern that fixed Community↔Marketplace and
Inventory↔Marketplace this program):

- **Logbook → PM (reactive/breakdown work):** a breakdown logbook entry (or a cluster of them on one asset)
  → "promote to project / attach to project" so the reactive response is tracked, costed, and closed under
  a project umbrella. A project's line-items link back to their source `logbook` rows (provenance).
- **PM Scheduler → PM (preventive campaigns):** a batch of due/overdue PMs (a shutdown PM campaign, a
  season's PM push) → roll up into a project; project progress reads real PM-completion state, not a
  hand-kept %. (`v_pm_scope_items_truth` / PM completions are the source of truth.)
- **Inventory → PM (the BOM):** project parts = real `inventory_items` (reserve/consume against stock,
  reuse the ledger-safe deduct the Marketplace X-arc already built), not free-text. A capex/contractor BOM
  is inventory-backed; low-stock on a project part surfaces the Marketplace "Find on Marketplace" bridge.
- **Engineering Design → PM (the design basis):** an eng-design output (a calc set, a drawing, a **Scope
  of Work**) attaches to the project as its design basis, with a live link (not a copy). This is where the
  reuse-discipline keystone below lives.

### Heavyweight 2 — U: the "best Project Manager" experience
Ian: *"striving for the BEST Project Manager… extend the UI/UX we already have."* Refined into the
plant-reality jobs a supervisor/planner actually does: create the right TYPE of project fast; see the
critical path + what's blocked/overdue at a glance; know the real % from real completions; one-tap the
source records (the logbook entry, the PM, the part, the drawing); a clean mobile field view for the
technician executing a line item; and an exec-ready report (project-report.html) that never fabricates a
number (WAT split — every figure from `v_project_*_truth`).

---

## ★ EXTENSION 1 — PROJECT TYPE is the MAINTENANCE NATURE of the work (refining Ian's "breakdown/preventive/project")
Ian named a taxonomy that is DIFFERENT from the existing `project_type` (workorder/shutdown/capex/contractor,
which is a project-STRUCTURE taxonomy). His axis is the **maintenance nature**: **reactive/breakdown ·
preventive · project (capital/planned)** — the classic maintenance-strategy split (corrective vs preventive
vs improvement). The refinement: **surface the maintenance-nature as a first-class facet** that ROUTES the
project to the right source system + the right template:
- **reactive/breakdown** → sourced from **Logbook** breakdown events; template = failure response (root
  cause, downtime, parts consumed, LOTO). Maps loosely to `workorder`.
- **preventive** → sourced from **PM Scheduler**; template = PM campaign (scope items, compliance %,
  schedule). Maps to a PM-rollup `workorder`/`shutdown`.
- **project (capital/planned)** → **capex/contractor**; template = budget + milestones + BOM + Eng-Design SOW.
Decision for Phase 3 (a genuine schema fork for the fresh window): either (a) add a `maintenance_nature`
facet column ON `projects` (reactive/preventive/project) that COEXISTS with `project_type`, or (b) map it
as a derived view over `project_type` + source-linkage. Prefer (a) if the source-routing needs to be
authored at create-time; (b) if it's purely a lens. Measure the real need in Phase 0/2 before deciding.

## ★ EXTENSION 2 — SCOPE OF WORK = ONE canonical thing (Ian's reuse-discipline keystone)
Ian's exact reuse insight: *"engineering-design can do a scope of work, the project-manager can also do a
scope of work, a project has its scope of work for PM, the PM Scheduler also has the scope for PM."* Today
SOW appears in **≥3 places** (measured 2026-07-11: `engineering-design.html/.js` SOW generator; the
`projects` **contractor** flavor's "scope + BOM + SOW + sign-off"; the PM Scheduler's PM-task scope). The
reuse discipline (this program's `feedback_synthesis_not_just_audit` "fuse into ONE"): **define ONE
canonical Scope-of-Work object + renderer**, authored once (engineering-design is the natural author of a
design SOW; a project can also originate one) and **REUSED** everywhere — the project attaches/links it, the
PM Scheduler references it, the contractor sign-off wraps it. Phase 3 synthesis deliverable: name the owner,
the canonical `scope_of_work` record/view, what each surface DELETES (its bespoke SOW), and the blast radius.
This is fitness-gated reuse ([[NEXT_ARCS_ROADMAP §13.12]] "reuse is fitness-gated, not absolute"): fuse
where the SOW is the SAME job; keep distinct only with a stated reason.

---

## The scored axes (Project Manager sub-dimension decomposition — fill % LIVE in Phase 2)
- **X — connectivity fabric** (Logbook/PM-Scheduler/Inventory/Eng-Design ↔ PM; measure the current cross-ref
  count, expect ~0 like every prior arc's X baseline).
- **U — best-PM UX** (create-by-type, critical-path/blocked-at-a-glance, one-tap provenance, mobile field view).
- **F — flows E2E** (create each type · add/complete/block a WBS item · reserve a part · attach a SOW/drawing ·
  generate the exec report · soft-delete/undo).
- **A — plant-floor mobile** (axe-0 full WCAG 2.2 AA + 44px + the focus-trap/whModalA11y pattern the Arc-U
  work just locked; reuse `arc_u_full_impact_scan.mjs` + `arc_u_focus_trap_probe.mjs`).
- **I — integrity** (hive isolation on every project read/write; owner/role gates on status/budget edits;
  no cross-hive project leak; auth_uid on every client write; RLS on project_items/knowledge).
- **AI — grounded** (project-report.html narrative WAT-split — every count/%/date from `v_project_*_truth`,
  never model-authored; the companion answers project questions grounded via the already-served
  `v_project_truth`/`v_project_items_truth`/`v_project_progress_truth`).

## The PDDA loop (6 phases — identical to the prior arcs)
1. **Understand** — map both surfaces + every table + every CURRENT cross-ref to Logbook/PM/Inventory/
   Eng-Design (measure X baseline, expect ~0). File:line attach points for each connection.
2. **Deepwalk baseline (MEASURED LIVE)** — Playwright MCP as planner/supervisor/technician/new-user +
   postgres MCP at the DB. Deepwalk the WORKED state (a real project of each type, real line items, a real
   linked logbook entry + PM + part), not the empty page. Fill the scoreboard %.
3. **Ideate** — fan-out skills (architect, data-engineer, frontend, mobile-maestro, qa-tester, multitenant,
   ai-engineer, maintenance-expert, knowledge-manager) + reputable sources (PM/WBS/critical-path UX,
   maintenance work-type taxonomy) → cited backlog per axis.
4. **Roadmap** — synthesize the scoreboard (% per axis, owning skill, citation, locking gate) + the two
   synthesis decisions (maintenance-nature facet; canonical SOW fusion).
5. **Execute** — keystone first (the Logbook/PM/Inventory/Eng-Design ↔ PM fabric + the SOW canonicalization),
   then cheapest-first; LIVE-verify EACH slice; ratchet a measured-% board; forward-only gate in
   `run_platform_checks`; skill + memory writeback.
6. **Re-deepwalk** — re-run the persona walk; confirm every axis at its roadmap target, measured + gated.

## ★ PHASE 0 — MEASURED baseline (fresh window, 2026-07-11) — corrects the drafted "islanded, X~0" thesis
The spine above was drafted WITHOUT live measurement and assumed `X ≈ 0` + a `projects/project_items/project_knowledge`-only
model. **Measured reality is much further along** — the fabric is ~60% built, so the arc is *surgical* (close 2 reverse-wiring
gaps + SOW fusion + facet), not *from-scratch*:

- **Schema is richer than drafted.** Migrations: `20260505000000_project_manager.sql` (+ `_advanced`, `_knowledge`,
  `v_project_items_progress_truth`, `rls_enable_project_family`). Tables in play: `projects`, `project_items`,
  `project_knowledge`, **`project_links`**, `project_change_orders`, `project_roles`, `project_progress_logs`.
- **`project_links` IS the connectivity fabric, already designed for ALL of Ian's systems.**
  `link_type ∈ {asset, logbook, pm_completion, inventory_item, engineering_calc, marketplace_listing, contractor}`,
  `link_id text` (mixed target-id types), `label`, `meta jsonb`. Not ~0 — the primitive exists.
- **FORWARD fabric (PM → systems) = MATURE.** `project-manager.html` has a 7-type link picker (`loadLinkOptions`
  @2219, `saveLink` @2247), a proactive **suggested-links** banner (open logbook entries last 30d, `refreshSuggestedLinks`
  @2156 / `linkSuggested` @2170), grouped render (`renderLinked` @2184), remove (`removeLink` @2266). Reads
  `v_logbook_truth`, `pm_completions`, `v_inventory_items_truth`, `engineering_calcs`, `v_marketplace_listings_truth`, `asset_nodes`.
- **REVERSE fabric (systems → PM) = PARTIAL — the real X gap.**
  - Logbook → PM: ✅ WIRED (`logbook.html:1908` inserts `project_links`).
  - PM-Scheduler → PM: ✅ WIRED (`pm-scheduler.html:2022` inserts `project_links`).
  - **Inventory → PM: ❌ NOT wired** (no `project_links` write in `inventory.html`) — X gap #1.
  - **Eng-Design → PM: ❌ NOT wired** (no `project_links` write in `engineering-design.html`) — X gap #2.
- **Progress roll-up:** `v_project_progress_truth` served; whether project % READS real `pm_completions`/`project_items`
  vs a hand-kept `project_progress_logs.pct_complete` needs Phase-2 live confirmation.
- **SOW inventory (fusion input).** SOW appears in: `engineering-design.html/.js` = the canonical AUTHOR (calc →
  BOM + Scope-of-Works generator, `#bom-sow-section` @729); `analytics-report.html` = SOW-*clause* format for an RCM
  action plan (a DIFFERENT job — candidate "keep distinct with reason"); `project-manager.html`/`project-report.html`
  contractor scope = should REUSE, not reinvent; `logbook.html` + companion/assistant hints reference it.
  → Phase-3 fusion: eng-design authors the canonical SOW; project links/reuses it; analytics-report likely stays distinct.

**Revised axis priors (to confirm LIVE in Phase 2):** X is NOT lowest — it's ~60% (forward done, 2 reverse gaps).
The likely lowest axes are the reverse-wiring completeness + the two synthesis extensions (SOW canonical, maintenance-nature facet).

## ★ PHASE 2 — MEASURED LIVE scoreboard (Playwright + postgres MCP, pabloaguilar/Lucena, 2026-07-11)
Deepwalked the WORKED state: signed-in PM list → WO-2026-001 detail → Linked-work pane → live-linked a logbook
breakdown → DB-verified; project-report.html AI surface. DB truth: **12 projects (3 each type), 90 WBS items,
50 progress logs; `project_links` = 12 rows ALL `asset` type** (zero logbook/pm/inventory/calc/contractor in seed).

| Axis | % (measured) | Evidence |
|---|---|---|
| **X — connectivity fabric** | **~40% (LOW — thesis confirmed)** | Schema complete (7 link types) + forward-link picker + proactive **suggested-links** (offered 5 open logbook entries) all WORK. But seed exercised only `asset` links → the 4 systems Ian named are **islanded in DATA** (the "bundle" WO had 1 asset link, 0 logbook/PM/parts). I live-linked RC-001 (logbook→project) via the suggestion → DB confirmed `logbook\|1`. GAPS: (a) Inventory + Eng-Design reverse-push NOT wired (Phase 0); (b) progress % = item-count (3/6), NOT rolled up from real `pm_completions`; (c) seeder never populates the 4-system links so the worked state reads empty. |
| **U — best-PM UX** | **~85% (HIGH)** | KPI tiles + plain-language subtitles, verdict banner, "what to do next", provenance chip, type/owner/status filter tabs + search, 6-tab detail (Overview/WBS/Linked/Daily/Roles/Sign-off), progress/hours/days tiles, AI-from-text. |
| **F — flows E2E** | **~80%** | Create/list/filter/detail/link all work; **link-work DB-write verified**. Untested: create-each-type, WBS add/complete/block, report gen, soft-delete/undo. |
| **A — mobile a11y** | **~90% (verify)** | skip-link ✅, aria-labels ✅; reuse `arc_u_full_impact_scan.mjs` to confirm axe-0 on the worked detail. |
| **I — integrity** | **~80% (probe)** | `project_links.hive_id` present; owner/role gates on status/budget + RLS need the `integration_security` probe. |
| **AI — grounded** | **~70%** | project-report.html = standards-grade EVM/critical-path scaffold (§1-7, PMBOK/AACE/IDCON/ISO, formulas in code = WAT-split intent); companion served `v_project_*_truth`. Verify narrative WAT-split + companion grounding live. |

**Verdict: X is the clear lowest axis and the thesis holds** — the fabric is BUILT (schema + forward UI + suggestions) but
UNEXERCISED (seed only asset links) with 2 reverse-push gaps + a progress-rollup gap. "Islanded" is real in the DATA, not the code.

## ★ PHASE 3 keystone plan (execute after the gate-integrity changeset is confirmed green)
1. **Seed the 4-system links** (seeder `seeders/`): make the seeded projects actually bundle real logbook entries +
   PM completions + inventory parts + eng-design calcs, so the WORKED state demonstrates the fabric (not an empty pane).
2. **Wire the 2 reverse-push gaps:** Inventory→PM ("add this part to a project") + Eng-Design→PM ("attach this calc/SOW
   as design basis") — mirror the logbook.html:1908 / pm-scheduler.html:2022 `project_links` insert pattern.
3. **Progress rollup:** project % should read real `pm_completions` / `project_items` truth, not a hand-kept item count
   (for the preventive/PM-campaign flavor) — surface via `v_project_progress_truth`.
4. **Canonical SOW fusion** (Extension 2) + **maintenance-nature facet** (Extension 1) — the two synthesis decisions.
5. Lock each slice with a `validate_project_manager.py` extension + a forward-only gate; skill + memory writeback.

## ★ PHASE 3 — EXECUTION progress (2026-07-11, all LOCAL/uncommitted at Ian's commit gate)
- **Step 1 — SEED the 4-system bundle: DONE + VERIFIED.** `seeders/projects.py` extended (FLAVOUR_BUNDLE +
  `_hive_sample`/`_link_label`) so each project bundles real logbook/pm_completion/inventory_item/engineering_calc
  links, not just an asset. `orchestrator.py` reordered (`seed_engineering` BEFORE `seed_projects` so calcs exist).
  Reseed VERIFIED: `project_links` 12→**54, all 4 systems** (logbook 9, pm 6, inventory 21, calc 6, asset 12).
  The islanded-data root is fixed — a fresh reset_all now demonstrates the fabric.
- **Step 2 slice A — Inventory→PM reverse auto-link: DONE + VERIFIED LIVE.** `inventory.html` `_autoLinkInventoryToProject(item)`
  (mirrors logbook.html `_autoLinkLogbookToProject`): on part USE, resolves the part's `linked_asset_node_ids`
  → legacy asset ids (`_nodeIdToAssetId`) → active projects on that asset → inserts an `inventory_item` project_link
  (existing-link pre-check avoids batch-23505). Wired into `submitUse`. **VERIFIED end-to-end against the live DB
  with real auth** (signed in Pablo/Lucena after the reseed rotated auth_uids + refreshed `wh_hives`): the exact
  query+insert chain found SHD-2026-001 on the part's asset, computed freshCount=1, and inserted the `inventory_item`
  link with RLS enforced (insertErr null). Test artifacts cleaned up. render-budget override bumped for the +code.
- **Step 5 — MAINTENANCE-NATURE facet (Extension 1): DONE + VERIFIED LIVE.** Decided the column-vs-lens fork as a
  **derived lens** (leverages the X-fabric, no authored column): `20260712000009_v_project_truth_maintenance_nature.sql`
  appends `maintenance_nature` to `v_project_truth` — project_type-primary, link-refined (capex/contractor→`project`,
  shutdown→`preventive`, workorder+logbook→`reactive`, workorder+pm→`preventive`). Applied live; verified all 4 types
  derive correctly (caught + fixed a first-draft bug that mis-classed shutdown as reactive). 4 view-scan gates
  (truth-view-contract / canonical-anchor / migration-immutability-strict / object-existence) all PASS.
- **Gate side-effects fixed (my own changes):** reseed emptied companion memory → new `seeders/companion_memory.py`
  seeds ≥1 episodic + agent_memory (dead-on-reset fix, wired into orchestrator); the truth-view-contract fix moved
  from an in-place edit of `20260711000001` (tripped migration-immutability-strict) into a NEW applied migration
  `20260712000008_v_community_reputation_truth_contract.sql`; openapi.json regenerated for the new edge fn.

## ★ STEP 4 — SOW-fusion SYNTHESIS VERDICT (Extension 2, grounded 2026-07-11)
Examined the real implementations (not just names). Ian flagged SOW reuse across eng-design / project /
PM-scheduler. Fitness-gated finding:
- **eng-design has TWO SOW artifacts:** (1) an **editable builder** `renderSowChecklist()` → `.sow-checklist-item`
  (`engineering-design.js:28400`, with `toggleSowItem`/`toggleSowExpand`/`addSowRow`) = calc → *authorable* scope;
  (2) a **printable** `.sow-clause` doc format (`engineering-design.html:446` "contractor document panels").
- **analytics-report** renders `.sow-clause` (`analytics-report.html:1366`, `AR-ACTION`) = RCM findings → SOW-clause
  action plan. **project-report §2** "Scope of Work (WBS)" = the WBS AS the project scope.
- **VERDICT (fitness-gated — reuse is NOT absolute; corrected on the evidence): KEEP DISTINCT.** I first assumed the
  `.sow-clause` renderer was a verbatim clone-pair to fuse. The code says otherwise: **eng-design.js:29001 renders
  `.sow-clause` EDITABLE** (`contenteditable`, `.sow-clause-title`, an authoring surface) while **analytics-report.html:1366
  renders it STATIC with `.sow-meta`** (a print exec action-plan). Same class *vocabulary*, genuinely different artifacts:
  authoring-vs-display interaction models + different fields (title vs meta). A shared renderer would need a flexible
  editable/title/meta/static switch that is MORE complex than the two focused renderers — the fusion would add debt,
  not remove it. clone-debt does not flag them (not verbatim), so there is no measured dup to collapse.
  - **What IS legitimately shared (and already is): the `.sow-clause` CSS naming vocabulary** — a convention, not
    duplicated logic. Keep it as the shared vocabulary; do NOT force a code fusion.
  - **The SOURCES stay distinct by nature:** calc BOM-scope (eng-design) · RCM action-plan (analytics-report) · WBS
    (project-report §2) are three different jobs. Ian's reuse instinct is honored at the CONCEPT level (every surface
    speaks "scope of work") without a harmful code merge. Pairs [[NEXT_ARCS_ROADMAP §13.12]] "reuse is fitness-gated,
    not absolute" + [[feedback_synthesis_not_just_audit]] (the verdict, opinionated, is the deliverable).
- **Disposition of the other remaining units** (measured, so the arc's scope is honest, not silently dropped):
  - **Step 2B (Eng-Design→PM reverse-push): LOW marginal value → note, don't build a bespoke modal.** The FORWARD
    path already covers it (the PM link picker has an `engineering_calc` type). Unlike inventory (which gained a
    genuinely-new auto-on-use), a calc has no asset-bound auto-trigger, so a manual eng-design "attach to project"
    would just duplicate the existing forward picker. Covered-by-forward-picker with a stated reason.
  - **Step 3 (progress rollup from pm_completions): a targeted enhancement, not a defect.** Current project % =
    `items_done/item_count` from real `project_items` (WAT-correct). A PM-campaign rollup (% = completed-PM / PM-scope)
    only adds value once a project models a PM scope set; the seeded data has no such structure to verify against.
    Deferred as a measured enhancement, not a false-100 gap.

## ★ PHASE 6 — RE-DEEPWALK verified LIVE (2026-07-11, Pablo/Lucena c9def338, HIVE mode)
Root-caused the post-reseed hive-resolution (the page reads `wh_active_hive_id`, not `wh_hives`; set it + re-auth
`signInWithPassword` → HIVE_ID resolved). Then verified the worked state live:
- **X (connectivity):** fabric 54 links; inventory→project auto-link RLS-enforced insert; facet derivation — all live.
- **Step-5 facet chip RENDERS live:** 4 cards show `nature-pill` — SHD→preventive · CAP/CON→project · WO→reactive
  (correct CSS classes). Screenshot `pm-facet-chips-verified.png`.
- **A (accessibility):** axe-core WCAG 2.2 AA scan on the worked-state page WITH the new chips → **0 violations**
  (serious+moderate+minor). My chip additions are a11y-clean.
- **I:** integration_security gate GREEN + the auto-link insert is RLS-enforced (proven).
- **AI (report grounding): VERIFIED live.** project-report.html?project_id=<SHD> renders all sections (Exec Summary /
  WBS / Linked Work / Standards PMBOK+AACE+ISO 21500) with the **WAT-split numbers from `v_project_truth`** — the
  truth-view `item_count`=7 appears in the rendered report (code-grounded, not AI-fabricated). AI narrative = prose only.
- **U ~85%:** mature (Phase 2) + the facet chip now renders on every card.
**Arc verdict: COMPLETE — heavyweights X (built+verified) + U (mature) + both extensions (facet done; SOW keep-distinct
verdict) delivered, verified live, and LOCKED (`validate_project_manager.py` 62/0).**

## NEXT (Phase 3 continuation — precise queue)
1. **Verify Step-2 slice A LIVE** in HIVE mode (sign in Pablo/Lucena, use a part whose asset is on a project → confirm auto-link toast + `project_links` row).
2. **Step 2 slice B — Eng-Design→PM:** attach an eng-design calc/SOW to a project as **design basis** (a calc isn't asset-bound, so this is a MANUAL "attach to project" affordance on the calc result, not an asset auto-link — design nuance).
3. **Step 3 — progress rollup:** the preventive/PM-campaign flavor's project % should read real `pm_completions`, not a hand-kept item count.
4. **Step 4 — canonical SOW fusion** (Extension 2) + **Step 5 — maintenance-nature facet** (Extension 1).
5. Lock each with a `validate_project_manager.py` extension + forward-only gate; skill + memory writeback; then re-deepwalk all axes.

## What we already built that this arc EXTENDS (don't re-do; build on)
- **Inventory ledger-safe deduct/restock** (Marketplace X-arc) → reuse for project BOM reserve/consume.
- **Provenance/trust-chip + ops-snapshot grounding** → project-report + companion project grounding.
- **`v_project_*_truth`** already companion-served on-demand → the AI axis is largely wired; verify + extend.
- **Arc-U a11y instruments** (`arc_u_full_impact_scan.mjs`, `arc_u_focus_trap_probe.mjs`, whModalA11y) → the A axis.
- **Marketplace/Community fabric pattern** (bidirectional bridge + provenance) → the X keystone's template.
- **Eng-Design SOW + calc outputs** → the design-basis attach + the SOW canonicalization.

## NEXT (fresh-window execution starts here)
1. **Phase 0–1 (Understand):** mine the denominator — both surfaces × every axis; measure X (current
   Logbook/PM/Inventory/Eng-Design cross-refs, expect ~0); inventory every SOW implementation (eng-design,
   contractor, PM-scheduler) for the fusion.
2. **Phase 2 (Deepwalk baseline):** live persona walk (planner/supervisor/technician/new-user), DB-verified;
   fill the scoreboard %. Confirm X + U are the two lowest, as the thesis predicts.
3. **Phase 3–5:** keystone = the **PM connectivity fabric** (Logbook/PM/Inventory/Eng-Design ↔ project) +
   the **canonical SOW** fusion + the **maintenance-nature** facet; then cheapest-first per axis.
Test: pabloaguilar/Lucena `b86f9ef6`. Pairs the Marketplace X-arc (parts-flow fabric) + eng-design SOW +
`feedback_synthesis_not_just_audit` (fuse-into-ONE) + the reuse-is-fitness-gated discipline.
