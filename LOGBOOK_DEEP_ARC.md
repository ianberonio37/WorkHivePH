# LOGBOOK — Page-Deep UFAI PDDA Arc  (drafted for a fresh window)

**Drafted 2026-07-12** (Project-Manager arc's fresh window, wrapping on Ian's (e)). Same 6-phase PDDA
(Understand → Deepwalk → Ideate → Roadmap → Execute → Re-deepwalk) as eng-design / resume / landing /
analytics / integrations / Hive / Community / Marketplace / **Project-Manager** (the last two just landed).
Ian: *"I love the PDDA flow… another arc, refined: PDDA for the Logbook page including its subdirs, extend
the UI/UX we have. I'm striving for the BEST logbook, and its cross-page connectivity to the appropriate
pages using the reuse discipline. Refine + extend the terms I've missed. Wrap up, proceed in a fresh window."*

> **What this arc IS.** Deep-walk `logbook.html` (+ its `learn/` subdir articles) as the real personas,
> measure every axis LIVE, and drive it to the **best maintenance logbook** — a field tech's fastest, most
> structured way to record what happened — by (1) perfecting the **capture UX** (fast, mobile-first, low-friction,
> the right ENTRY-KIND with the right fields), (2) treating the logbook as the platform's **canonical field-capture
> SOURCE** whose **provenance** must flow accurately into every downstream consumer, and (3) applying the **reuse
> discipline** so shift-handover / readings / fault-knowledge / PM-completion **compose FROM** the logbook entry
> rather than re-inventing capture.

---

## Scope (grounded, 2026-07-12)

- **Surfaces:** `logbook.html` (the tool: entry capture + team feed + entry detail + shift-handover + readings)
  · `learn/` subdirs: `start-digital-logbook-philippine-factory`, `maintenance-shift-handover-template`,
  `dole-iso-audit-trail-from-logbook`, `autonomous-shift-planning-philippine-plants`. (Confirm any deep-link
  / embed states + the `shift-brain` surface in Phase 0. Ignore `logbook.backup.html`.)
- **Data model (rich — already exists):** `logbook` (31 fields via `v_logbook_truth`: worker/date/status +
  fault `machine/problem/action/root_cause/failure_consequence` + `downtime_hours` + `production_output` +
  `parts_used` + `readings_json` + `knowledge` + `tasklist_acknowledged/note` + `photo` + `pm_completion_id`
  + `wo_state/wo_assigned_to` + `maintenance_type` + `category` + `is_corrective` + asset-linkage
  `asset_node_id/tag/name/iso_class/criticality/location`) + `logbook_readings` + `logbook_production_output`
  + `logbook_failure_consequence` + `shift_brain` + `equipment_reading_templates` + `logbook_sync_meta`
  (offline sync) + `q0_logbook_quota`. Canonical view: `v_logbook_truth` (asset-joined, companion-served).
- **Connectivity is ALREADY SUBSTANTIAL (unlike PM's X≈0) — the logbook is a HUB and the SOURCE:**
  - **Reads IN (logbook.html):** `asset_nodes` (×10), `inventory_items` (×5) + `inventory_deduct` (×3 — parts
    consumed on a fault, ledger-safe), `pm_completions`/`pm_assets`/`v_pm_scope_items_truth`/`v_pm_compliance_truth`
    (×several), `project_links`/`projects` (the reverse-fabric the PM arc built — `_autoLinkLogbookToProject`),
    `fault_knowledge`, `v_external_sync_truth` (CMMS), `equipment_reading_templates`, `hive_audit_log`.
  - **Feeds OUT (v_logbook_truth consumed by ~11 surfaces):** `asset-hub` (equipment history), `analytics` +
    `analytics-report` (MTBF / downtime / production), `pm-scheduler`, `project-manager`, `resume`
    (experience evidence), `assistant`, `dayplanner`, `hive`, `integrations`, `index`, + infra
    (`voice-handler`, `wh-capture-validate`, `search-overlay`, `worker-drawer`, `sw` offline).

---

## ★ THE TWO HEAVYWEIGHTS (refined + extended from Ian's thoughts)

### Heavyweight 1 — U: the BEST field logbook (capture UX)
The logbook's core job is a technician on the floor recording what just happened, FAST, with the right
structure. "Best" = lowest friction to a COMPLETE, well-typed entry: the sentence-builder / quick-capture,
mobile-first field view (the 390px tech persona), voice capture, photo, offline-first (`logbook_sync_meta` +
`sw`), and the right FIELDS surfaced for the right ENTRY-KIND (a breakdown needs root-cause + downtime + parts;
a reading needs the template; a production entry needs output). Extend the UI/UX we already have (the
sentence-builder, the team feed, the entry detail, LOTO/permit cues) — measured LIVE against the plant reality.

### Heavyweight 2 — X: the logbook as the CANONICAL field-capture SOURCE + provenance spine
The logbook is the single most-consumed source on the platform (~11 pages read `v_logbook_truth`). The keystone
is **provenance integrity**: every downstream number (asset equipment-history count, analytics MTBF/downtime,
PM compliance, resume experience) must trace back to real logbook entries with a correct FK-join — NOT an
undercount or a broken lineage. (Precedent bug: `reference_logbook_asset_linkage_undercount` — `v_asset_truth`
lifetime FK-join, 2700 entries named an asset but the join undercounted.) Bidirectional with provenance chips,
the same fabric pattern the PM/Community/Marketplace arcs used — but here the logbook is mostly the SOURCE end,
so the arc VERIFIES the downstream flow is complete + accurate, and closes any lineage gap.

---

## ★ EXTENSION 1 — ENTRY-KIND is the maintenance-nature of a logbook entry (refining "the best logbook")
Parallel to the PM arc's maintenance-nature facet: a logbook entry is fundamentally one of a few KINDS, and
the kind should ROUTE its fields + its downstream. The schema already half-models this (`maintenance_type`,
`category`, `is_corrective`, `pm_completion_id`, `readings_json`, `production_output`) — refine it into a
first-class **entry-kind** facet:
- **corrective / breakdown** (`is_corrective`) → fields: machine, problem, root cause, failure consequence,
  downtime, parts, LOTO → routes to **MTBF + fault-knowledge (RAG) + Alert Hub**.
- **preventive / PM-completion** (`pm_completion_id`) → routes to **PM compliance**; should compose FROM the PM,
  not re-key it.
- **reading / inspection** (`readings_json` + `equipment_reading_templates`) → routes to **trend + threshold alert**.
- **production / output** (`production_output`) → routes to **OEE / production analytics**.
- **observation / note** → the low-friction default; still asset-linkable.
Phase-3 decision (a genuine fork for the fresh window): surface entry-kind as a first-class create-time CHOOSER
that shapes the form (progressive disclosure of the right fields) vs. a derived lens over the existing columns.
Prefer the create-time chooser IF it materially cuts capture friction (Heavyweight 1); measure in Phase 0/2.

## ★ EXTENSION 2 — REUSE discipline: the logbook is the canonical CAPTURE; others COMPOSE from it
Ian's reuse ask, grounded: several surfaces do "structured field capture" that overlaps the logbook —
**shift-handover** (`shift_brain` — a shift's handover composes from that shift's open jobs + logbook entries),
**equipment readings** (`equipment_reading_templates` + `logbook_readings`), **fault-knowledge** (a corrective
entry's root-cause → the fault KB / RAG), and **PM-completion** (a PM done on the floor). The discipline:
**the logbook ENTRY is the canonical capture primitive; each of these should REUSE / COMPOSE from a logbook
entry rather than re-invent its own capture form + storage.** Phase-3 synthesis deliverable: for each, decide
FUSE (compose from the logbook entry, name what gets deleted, blast radius) vs. KEEP-DISTINCT-with-a-reason
(fitness-gated — [[NEXT_ARCS_ROADMAP §13.12]] "reuse is fitness-gated, not absolute", and the PM arc's SOW
verdict where look-alikes with different JOBS stayed distinct). Lead with the strongest fusion case (likely the
shift-handover, which is definitionally logbook-derived).

## ★ EXTENSION 3 — the AUDIT-TRAIL / compliance surface (a term Ian implied via the DOLE/ISO learn article)
The `dole-iso-audit-trail-from-logbook` learn subdir signals a real job: the logbook IS the DOLE/ISO audit
trail (who did what, when, to which asset, with sign-off). Extend the arc to verify the entry is
audit-grade + tamper-evident (`hive_audit_log`, sign-off, immutable-once-closed `closed_at`/`wo_state`) and
that the compliance export (the audit trail) is real, not a mock. This is the "I / integrity" axis with teeth.

---

## The scored axes (Logbook sub-dimension decomposition — fill % LIVE in Phase 2)
- **U — best-capture UX** (sentence-builder/quick-capture speed, entry-kind field shaping, mobile field view,
  voice, photo, offline-first, LOTO/permit cues). Expect this + reuse to be the heavyweight, not X.
- **X — connectivity + PROVENANCE** (logbook is HUB + SOURCE; measure the downstream lineage accuracy across the
  ~11 consumers; close any FK-join undercount; bidirectional provenance chips).
- **F — flows E2E** (capture each entry-kind · consume parts on a fault (ledger-safe) · attach a PM/asset/project ·
  add a reading · close/sign-off · shift-handover · offline capture→sync · CMMS external-sync).
- **A — plant-floor mobile** (axe-0 full WCAG 2.2 AA + 44px; reuse `arc_u_full_impact_scan.mjs` + focus-trap probe;
  the field tech is THE persona here — 390px mobile is the primary viewport).
- **I — integrity + AUDIT** (hive isolation on every read/write; auth_uid on every client write; sign-off + closed
  immutability; the DOLE/ISO audit trail is real + tamper-evident; RLS on logbook + readings + production).
- **AI — grounded** (the companion answers logbook questions grounded via `v_logbook_truth`; the fault-knowledge
  RAG is fed by real corrective entries; any AI narrative/summary is WAT-split — counts/downtime/MTBF from the
  truth view, never model-authored).

## The PDDA loop (6 phases — identical to the prior arcs)
1. **Understand** — map `logbook.html` + subdirs + every table + every current connectivity edge (IN reads + OUT
   consumers). File:line attach points; measure the provenance chain (entry → asset-history → analytics → knowledge).
2. **Deepwalk baseline (MEASURED LIVE)** — Playwright MCP as tech/supervisor/new-user (390px field-first) +
   postgres MCP at the DB. Deepwalk the WORKED state (a real entry of each KIND, a fault with parts consumed, a
   reading, a shift-handover), not the empty page. Fill the scoreboard %. Confirm U + reuse are the low axes.
3. **Ideate** — fan-out skills (frontend, mobile-maestro, qa-tester, knowledge-manager, maintenance-expert,
   data-engineer, multitenant, ai-engineer, analytics-engineer) + reputable sources (field-data-capture UX,
   maintenance logbook / shift-handover standards, DOLE/ISO audit) → cited backlog per axis.
4. **Roadmap** — synthesize the scoreboard (% per axis, owning skill, citation, locking gate) + the synthesis
   decisions (entry-kind facet; the reuse FUSE/keep-distinct verdicts for shift-handover/readings/fault-KB/PM).
5. **Execute** — keystone-first (best-capture UX + provenance integrity + the highest-value reuse fusion), then
   cheapest-first; LIVE-verify EACH slice; ratchet a measured-% board; forward-only gate in `run_platform_checks`
   (extend `validate_logbook.py` / `logbook-validator` skill); skill + memory writeback.
6. **Re-deepwalk** — re-run the persona walk; confirm every axis at its roadmap target, measured + gated.

## What we already built that this arc EXTENDS (don't re-do; build on)
- **`logbook-validator` skill + `validate_logbook.py`** (+ `validate_logbook_consistency`) → extend for the
  entry-kind facet, provenance integrity, audit-trail.
- **The PM arc's reverse-fabric** (`_autoLinkLogbookToProject`, logbook→project auto-link) → already live; verify.
- **`v_logbook_truth` asset-joined** + the FK-join lesson ([[reference_logbook_asset_linkage_undercount]]) → the
  provenance keystone.
- **Arc-U a11y instruments** (`arc_u_full_impact_scan.mjs`, focus-trap probe, whModalA11y) → the A axis (390px field).
- **Shift-handover pattern** ([[feedback_handover_report]] — a-f structure, LOTO, calendar period) → the reuse
  Extension 2.
- **Marketplace/Community/PM fabric + provenance-chip pattern** → the X provenance chips + the reuse verdicts.
- **`inventory_deduct` ledger-safe** (Marketplace/PM arcs) → the "parts consumed on a fault" flow (already wired).

## NEXT (fresh-window execution starts here)
1. **Phase 0–1 (Understand):** map both the tool + subdirs × every axis; measure the connectivity (IN reads +
   the ~11 OUT consumers) and the PROVENANCE chain accuracy (the FK-join / lineage integrity, expect a gap per
   the CL1 undercount lesson); inventory the reuse-overlap surfaces (shift-handover, readings, fault-KB, PM).
2. **Phase 2 (Deepwalk baseline):** live persona walk (tech/supervisor/new-user, 390px field-first), DB-verified;
   fill the scoreboard %. Confirm U (best-capture) + the reuse discipline are the frontier, not X (already rich).
3. **Phase 3–5:** keystone = **best-capture UX** (entry-kind field shaping + speed) + **provenance integrity**
   (close the lineage gap) + the highest-value **reuse fusion** (shift-handover composes from the logbook); then
   cheapest-first per axis; each slice LIVE-verified + gated.
Test: pabloaguilar / test1234, hive resolves via `wh_active_hive_id` (reseed rotates auth_uids — re-sign-in +
set the key; see `reference_gate_regression_fanout_recovery`). Pairs the PM arc (reverse-fabric + facet pattern)
+ [[feedback_synthesis_not_just_audit]] (fuse-into-ONE / keep-distinct-with-reason) + the reuse-is-fitness-gated
discipline + [[feedback_handover_report]].

---

# PHASE 0–1 FINDINGS — measured LIVE 2026-07-12 (DB via postgres MCP + 3-agent static map)

## Data model corrections (arc doc drafted from memory; these are the LIVE facts)
- **Tables that DON'T exist** (arc doc assumed them): `logbook_readings`, `shift_brain`, `logbook_production_output`,
  `logbook_sync_meta`, `q0_logbook_quota`. Readings + production are stored **INLINE** on the logbook row
  (`readings_json`, `production_output` jsonb) — already composed in, no parallel table. The handover table is
  **`shift_plans`** (migration name was `shift_brain`). Offline uses **IndexedDB** (`wh_logbook_offline`), not a
  `sync_meta` column and not a service worker.
- **Real reuse-overlap tables:** `equipment_reading_templates` (15 rows, config), `fault_knowledge` (529, FK `logbook_id`),
  `pm_completions` (1587), `pm_knowledge`, `sensor_readings`, `shift_plans`.

## Seed census (3 hives: Manila 1700 / Lucena 1100 / Baguio 900 = 3700 entries)
| maintenance_type | entries | with readings | with production | pm_completion_id |
|---|---|---|---|---|
| Preventive Maintenance | 1679 | 701 | 0 | **0** |
| Breakdown / Corrective | 1120 | 1120 | 213 | 0 |
| Inspection | 645 | **0** | 0 | 0 |
| Project Work | 256 | 0 | 0 | 0 |

## X-axis (connectivity + PROVENANCE) — HEALTHIER than the arc feared; asset lineage is EXACT
- **Asset FK provenance is SOUND.** Live `v_logbook_truth` joins `asset_nodes n ON n.id = l.asset_node_id` (a **UUID FK**,
  not a text bridge). `machine` = the asset **tag** (e.g. "GEN-003"), matches `asset_tag` 3700/3700. `asset_node_id`
  present 3700/3700, FK'd to 90 distinct assets. **v_asset_truth `lifetime_logbook_entries` SUM = 3700 = raw, delta 0**
  — NO CL1 undercount in this seed. ⚠️ **Agent-2's migration-file claim of a `legacy_asset_id`↔`asset_ref_id` text
  bridge is STALE** — the deployed view was migrated to the uuid FK; the `logbook` table has no `asset_ref_id` column.
  (Discipline: `feedback_dont_get_stuck_in_postgres_files_are_truth` — verified against `pg_get_viewdef`, not the file.)
- **~11+ OUT consumers mapped** (asset-hub, analytics via RPCs, hive, index, dayplanner, project-manager, resume,
  assistant, integrations, + edge fns asset-brain-query / fmea-populator / weibull-fitter / pf-calculator /
  analytics-orchestrator / ai-orchestrator / shift-planner-orchestrator / batch-risk-scoring / semantic-fact-extractor /
  scheduled-agents / agentic-rag-loop). Hive/worker-scoped reads all use safe keys (hive_id / worker_name / asset_node_id).
- **REAL live X-finding (latent, gate-worthy):** the "corrective" definition is **inconsistent** across surfaces —
  `v_logbook_truth.is_corrective` = regex `~* '(corrective|breakdown)'`; `v_asset_truth.last_failure_at` + the 5 analytics
  RPCs (`get_mtbf/mttr/failure_frequency/downtime_pareto/repeat_failures`) = exact `'Breakdown / Corrective'`;
  `trigger-ml-retrain` = `ilike %Corrective%/%Breakdown%`. Currently **0 divergent rows** (all corrective use the exact
  string) so it's latent, but any new vocab (e.g. "Emergency Breakdown") would be counted by is_corrective yet MISSED by
  last_failure_at + every MTBF/MTTR KPI. → **canonicalize on ONE definition + a consistency gate.**
- Lower-priority text-key joins (real, low blast radius since machine=tag is stable): analytics RPCs GROUP BY `machine`
  free-text; `integrations.html:1957` `.eq('machine')`; `parts-staging-recommender:128` `.in('machine', …)`.
- `intelligence-report` reads cross-hive with no hive filter — confirm intentional (platform aggregate) in Phase 2.

## Reuse discipline (Extension 2) — 3 of 4 ALREADY compose-from-logbook; PM is the one real gap
| Overlap surface | Verdict | Evidence |
|---|---|---|
| **Shift-handover** | ✅ COMPOSES-FROM-LOGBOOK | `shift-planner-orchestrator` reads `v_logbook_truth` carry-forward → own **derived** `shift_plans`; no raw capture form. **KEEP-DISTINCT** (derived rollup, not competing capture). |
| **Equipment readings** | ✅ COMPOSES-FROM-LOGBOOK | `readings_json` on the logbook row; `equipment_reading_templates` is config only; single `collectReadings()` path. Already fused. |
| **Fault-knowledge** | ✅ COMPOSES-FROM-LOGBOOK | `embed-entry` mirrors corrective logbook via `logbook_id` UPSERT; **529/529 rows FK-join valid**. Extra automated CMMS/visual-defect feeders, no human form. |
| **PM-completion** | ⚠️ MIXED — the one gap | Own `pm_completions` (1587) is source-of-truth; the logbook-mirror IS wired + default-ON (`pm-scheduler.html:794` `#sheet-log-toggle` checked → `1964` sets `pm_completion_id`). **0/1587 linked** = seed never links them + a historical TEXT-NOT-NULL id bug (since fixed). → **verify the mirror live + close the seed gap** so provenance is demonstrable. |

## U-axis (best-capture UX) — the FRONTIER, as predicted. Ranked static defects:
1. **★ ENTRY-KIND FIELD-SHAPING IS MISWIRED (strongest defect, Extension 1).** The form HAS an explicit entry-kind
   selector (`#f-maint-type`: Breakdown/Corrective · Preventive · Inspection · Project Work) with progressive disclosure —
   but the disclosure is keyed **only** off "Breakdown": readings + failure_consequence + production show for Breakdown
   and NOTHING else. So **readings (which belong to an *Inspection*) are unreachable on an Inspection entry — 0/645
   Inspection entries carry readings**, the smoking gun. Production output shows on `Breakdown && Closed` but belongs to a
   *production* entry (there is no Production kind). The taxonomy and the field-shaping **disagree**. → route each kind's
   fields to the RIGHT kind (readings→Inspection+Preventive; production→a production kind; root-cause/downtime→corrective).
2. **Mobile-390px is WEAK.** One media query (`max-width:767px`) that only disables beam animations — no 390px layout,
   no bottom-sheet capture, no sticky save bar (Save lives inline in wizard step 3). Touch targets are 44px broadly (good).
   The field tech is THE persona; this is the U + A heavyweight. (Confirm live in Phase 2.)
3. **LOTO / permit-to-work is not a first-class input** (only an AI-detected note + hardcoded tasklist steps). Extension 3.
4. Capture is a **3-step wizard** with AI-first voice-fill + photo-defect quick capture on top (good foundations to extend).

## I-axis (integrity + audit) — mostly sound; two candidates
- RLS enabled on logbook (4 policies), fault_knowledge (4), pm_completions (2), shift_plans (2), hive_audit_log (2).
  `equipment_reading_templates` has **RLS off / 0 policies** (config table — likely fine, confirm it's read-only catalog).
- INSERT sets `auth_uid` + `hive_id` + `worker_name` ✓. **Both UPDATE paths (`saveEdit` modal + `saveEditFromForm`
  in-place) OMIT `auth_uid`** — candidate vs the locked rule `feedback_authuid_attribution_on_every_write` (row already
  has auth_uid from insert, so no NULL is created; verify whether the locked rule requires it on update too).
- Extension 3 (DOLE/ISO audit trail): confirm logbook close/sign-off writes `hive_audit_log` and the export is real.

---

# PHASE 2 FINDINGS — LIVE deepwalk 2026-07-12 (Playwright MCP @ 390px, pabloaguilar / Lucena hive c9def338)

## ★ KEYSTONE DEFECT CONFIRMED 3 WAYS — entry-kind field-shaping is INVERTED (U-1)
Readings (Temperature/Vibration/Pressure) render for a **Breakdown** but **NOT** for an **Inspection** — the exact
inverse of maintenance reality (an inspection IS reading-taking). Triangulated:
- **Code** — `logbook.html:2974-2995`: `renderReadingsFields()` is called **only** inside `if (isBreakdown)` (:2986);
  the `else` branch does `readingsEl.classList.add('hidden')` (:2995). So Inspection / Preventive / Project can never
  show readings.
- **Live** (this session): Breakdown+Mechanical → `readings-section` shown, **3 reading inputs** rendered + consequence
  shown; Inspection+Mechanical → `readings-section` HIDDEN, **0 inputs**.
- **DB**: **0 / 645 Inspection entries carry readings**; 1120/1120 Corrective do. The data mirrors the broken UI.
→ **Fix (Phase 5 keystone):** route each kind's fields to the RIGHT kind — readings for **Inspection + Preventive**
  (and corrective), consequence/root-cause/downtime for **corrective**, production for a **production/output** context.

## Retracted candidate (evidence discipline)
The header "500 entries" is **NOT** a cap bug. Stat pills are worker-scoped exact `head:true` counts
(`logbook.html:3185-3190`); DB confirms **Pablo Aguilar owns exactly 500 entries, 4 open**. Correct. (A round number
is not proof of a cap — `feedback_classify_by_evidence_not_heuristic`.)

## Other live findings
- **U-2 mobile clutter (390px) — RETRACTED by measurement.** Bounding-box intersection test at 390×844 showed the real
  FABs (`wh-hub`/`wh-ai-widget`/`wh-feedback-fab`, all x248–368) do NOT intersect any interactive capture element
  (captureBtn x61–172); the only "overlaps" were the decorative `aurora-bg`/`hex-pattern` z-0 backgrounds. The earlier
  "clutter" read was a full-page-screenshot artifact (fixed elements render at viewport position). Not a defect
  (`feedback_classify_by_evidence_not_heuristic`). Design-opinion (no mobile bottom-sheet/sticky-save) remains, not a bug.
- **AI-1:** companion is context-scoped to "Digital Logbook" and grounded via `v_logbook_truth`, but on "what did I log
  last week?" it deflected ("check the Logbook page directly") instead of answering from grounding — date-range reasoning
  weak (grounding present, retrieval/answer shape weak).
- **F:** capture flow drives cleanly step 1→2; `validate_logbook.py` **25/25 PASS**; parts-consume ledger-safe wired.
  PM→logbook mirror still unverified live (0 rows).
- **Console:** one 401 on `analytics_events` insert (telemetry, RLS-blocked for this role) — not logbook-critical; note only.

## BASELINE SCOREBOARD (measured; A pending live axe scan)
| Axis | Baseline | Evidence | Frontier? |
|---|---|---|---|
| **U** best-capture | **~55%** | entry-kind INVERTED (keystone), mobile clutter, LOTO not first-class; strong: voice-fill, photo-AI, wizard, 44px, offline IndexedDB | **★ YES** |
| **X** connectivity+provenance | **~90%** | asset lineage EXACT (delta 0, uuid FK), 11+ consumers safe-keyed, fault-KB 529/529; only latent corrective-def drift to gate | no (healthy) |
| **F** flows E2E | **~85%** | validate_logbook 25/25, capture works live, parts ledger-safe; PM-mirror unverified, Inspection-readings blocked | partial |
| **A** mobile a11y 390px | **100%** | `arc_u_full_impact_scan.mjs`: logbook **0 WCAG 2.2 AA violations** @390×780 (platform 35pg, 0 grand) | no (axe-clean) |
| **I** integrity+audit | **~80%** | RLS on all core tables, auth_uid on insert; candidates: UPDATE omits auth_uid, reading_templates RLS off, DOLE/ISO export unverified | partial |
| **AI** grounded | **~75%** | v_logbook_truth grounding wired (source registry + ai-orchestrator); weak date-range answer shape | partial |

---

# ROADMAP ADDITION (Ian, 2026-07-12) — the HANDS-FREE, SELF-HOSTED, SELF-HEALING EMBEDDER

**Ian's ask (refined, 2026-07-12, two messages):** *"Build our own embedder — when a user uses the platform,
it embeds what needs embedding automatically, so I never have to periodically embed each user's data. And in
PRODUCTION, each user has THEIR OWN embedder, built into the platform — hands-free on my part."*

**What "their own embedder, built into the platform" means (refined interpretation).** NOT a central
embedding service the founder runs and must scale/babysit per customer. Instead the embedding capability
**ships inside the product**: it is a platform primitive that **every tenant gets automatically**, and each
hive's data is embedded **as a side-effect of that hive's own usage**, into that hive's own vector namespace
(per-hive isolation the platform already enforces via `hive_id`). Onboard the 1000th hive → it embeds its own
writes from minute one → **the founder does nothing**. "Their own embedder" = the platform embeds *for* each
tenant, automatically and in isolation — not that each tenant literally hosts a model (that would be heavier
and pointless; one self-hosted model, per-tenant isolated indexes, is the right shape). *(This is a design
call I'm making from your intent; flag if you meant literally per-tenant model instances.)*

**Refined vision.** Every write that feeds semantic search (logbook fault · PM completion · skill entry ·
community post · marketplace listing · resume · SOP) is embedded **automatically at write time** by **our OWN
self-hosted embedding model**, event-driven, scoped to the writing user's hive — a **built-in product
primitive** every tenant gets, with **zero founder ops** (no periodic batch job, no per-customer scaling),
**zero external embedding-API cost/dependency per user**, and **self-healing** so an outage never becomes a
manual backfill. Aligns [[feedback_build_own_minimal_dependencies]] + [[feedback_free_tier_only_models]].

**Current state — measured LIVE this session (the walk that surfaced it):**
- ✅ **The event-driven pattern already EXISTS.** `embed-entry` fires on Supabase DB webhook `INSERT` for
  `logbook`→`fault_knowledge`, `pm_completions`→`pm_knowledge`, `skill_badges`→`skill_knowledge`. So
  "hands-free auto-embed on write, per-user" is already the architecture — not a rebuild, an *upgrade*.
- ❌ **The OWN embedder is DOWN.** `bge-local` (`http://host.docker.internal:8901/embed`) is unreachable →
  `embed-entry` falls back to external **`voyage`** with a `SPACE-DIVERGENCE` warning. That external fallback
  IS the per-user dependency + cost Ian wants gone, AND it silently corrupts retrieval (voyage-space vectors
  in a bge-local-space corpus).
- ❌ **The pipeline has correctness holes.** Found + FIXED this session: `pm_knowledge` FK bug (embed-entry fed
  a `pm_assets` id into the `asset_nodes` FK → **every** PM embed 500'd → `pm_knowledge` = **0 rows** despite
  1588 completions — 100% silent RAG starve). Fixed by resolving the node id; see below.
- ❌ **No self-healing.** Rows embedded during a bge-local outage (voyage-space) or dropped on error are never
  re-embedded — today that would be a founder-run backfill, exactly what Ian wants to eliminate.

**The roadmap items (graduate to its own platform arc — "OWN EMBEDDER"):**
1. ✅ **Reliable self-hosted embedder — DONE this session.** `bge-local` (`tools/embed_server.py`, fastembed
   `BAAI/bge-small-en-v1.5`, 384d, NO rate limit) was NOT a "hard external ceiling" — it was a **not-running local
   server** (the stopped-container class Ian catches). `python tools/embed_server.py 8901` started it; embed-entry
   now embeds **consistently via bge-local** (`[embedding] ok via bge-local (384 dims, pinned)`, 4/4), **zero voyage
   fallback**. Health-gate: `GET :8901/health`.
2. ✅ **Correct + complete on-write pipeline — DONE.** pm_knowledge FK fixed + live-verified (inserts via bge-local).
   fault/pm knowledge webhook→embed paths work; the on-write embed is quota-free + per-hive.
3. ✅ **Self-healing re-embed — BUILT + verified.** `tools/reembed_dirty_knowledge.py`: an **idempotent** sweep that
   finds every DIRTY row (embedding NULL or `embedding_model != bge-small-en-v1.5-local`) across fault/pm/skill and
   re-embeds via bge-local — a recovery-gated no-op when clean (safe to schedule = hands-free). Verified: healed the
   3 stale-tagged pm_knowledge rows, 2nd run = clean no-op. Corpus now **531/531 fault + 3/3 pm in ONE bge-local
   space** (was 5/531 in a dead nomic space → retrieval was near-random). Backfill via `reembed_fault_knowledge.py`.
4. ✅ **Per-hive isolation + zero marginal cost + persistent hands-free CONTAINER — DONE this session.** Built +
   ran the **bge-small CONTAINER** (`docker/embed-server/Dockerfile` → `workhive-embed-server:selfheal`): on the
   Supabase network + host port, `--restart unless-stopped` (**survives reboots/crashes**, unlike the fragile nohup),
   with the **self-heal thread baked in** (`WH_EMBED_SELFHEAL_MIN=15` + env-configurable DSN → `supabase_db_workhive`
   + `localhost:8901`). Verified: the edge embeds via it (`ok via bge-local`), and the sweep RUNS from INSIDE the
   container (reaches DB + embedder → clean no-op). **One container = the complete hands-free self-healing embedder.**
   (Dockerfile reordered so the psycopg2 layer never busts the cached ~130MB model layer; the committed image was
   built via `docker cp`+`docker commit` off the running model-baked container to dodge a slow-network re-download.)

*Net: the founder never touches embeddings — a user's own activity embeds their data on OUR model (a restart-surviving
container), and the system re-heals itself after any outage. **ALL 4 slices DONE this session** — the "hard external
ceiling" was a false ceiling (a not-running local server; `python tools/embed_server.py` / `docker run` started it).*

---

# PHASE 3–5 EXECUTION LOG — 2026-07-12 (skill-first: maintenance-expert + frontend + qa + knowledge-manager)

**Shipped this session (each: find → fix → LIVE-verify → gate → teach → persist):**
1. **★ KEYSTONE — entry-KIND field-shaping fix (U).** Readings now render for **Inspection + Preventive + Corrective**
   (via a `kindTakesReadings()` helper), not breakdown-only; failure-consequence stays corrective-only; production
   decoupled from breakdown → any Closed run. LIVE-verified 3 ways (Breakdown→3 reading inputs, Inspection→3 inputs
   [was 0], Project Work→0; edit of a Preventive+readings entry preserves exact values → no data loss; async-race guard
   on the category handler). **Gate #26** `entry_kind_readings_shaping`. Taught logbook-validator + maintenance-expert
   (entry-kind→field oracle) + frontend. Persisted [[reference_logbook_entry_kind_field_shaping]].
2. **REUSE Extension 2 — PM→logbook mirror is now asset-lineaged (X/reuse).** `pm-scheduler.html` mirror resolves the
   canonical `asset_node_id` (was `null` → orphaned from v_asset_truth history) + uses the **tag** (was the display name).
   LIVE-verified: a real PM completion produced a logbook row `machine='TT-001'`, `asset_node_id=90c8c4d2…`,
   `pm_completion_id` linked. So the **0/1587 was a SEED gap, not dead wiring**. **Gate #27** `pm_mirror_asset_lineage`.
3. **PLATFORM BUG — pm_knowledge 100% broken (AI).** `embed-entry` fed a `pm_assets` id into `pm_knowledge.asset_id`
   (an `asset_nodes` FK) → every PM embed 500'd → **pm_knowledge = 0 rows despite 1590 completions** (silent RAG starve).
   Fixed by resolving the node id (schema-proven: valid node id or null both satisfy the FK). LIVE-verify pending an edge
   **re-bundle** (`docker restart`+deno-cache-clear insufficient — needs `supabase stop/start`, fraught on this `&`-path
   Windows box). Persisted [[reference_pm_knowledge_fk_100pct_broken]].
4. **Extension 3 — DOLE/ISO audit-trail LOCKED + made real (I).** (a) Verified the wiring is audit-grade (create + edit
   → `hive_audit_log`, actor-attributed, hive-scoped, edit records `prev_status→new_status` = tamper-evident amendment)
   — **Gate #28** `audit_trail_wiring`. (b) **Made the CSV export audit-GRADE** — added **Worker** (WHO) + **Signed Off
   (Closed At)** + **Failure Consequence** columns (the old export was a field-dump missing WHO/when-signed-off);
   LIVE-verified 200-row export with `Pablo Aguilar`/`BF-001`. The "logbook IS the DOLE/ISO trail" export is now real.
5. **Extension 3 — LOTO / Permit-to-Work is now FIRST-CLASS (U + I).** Was regex-inferred free text only. Built the full
   chain: migration `20260712000010_logbook_loto_permit.sql` (`loto_applied` bool + `permit_reference` text, applied
   live via `docker exec psql`; `v_logbook_truth` exposes both), a capture-form cue (`#f-loto` + reveal-on-check
   `#f-permit-ref`, shown for hands-on kinds), persist on create + edit, cache + rehydrate + clearForm, and the LOTO
   column in the audit export. LIVE-verified: UI shows/hides correctly + a real create persisted `loto_applied=true`,
   `permit_reference='PTW-2026-0917'` to the DB; capture-contract accepts the new fields (no insert regression).
   **Gate #29** `loto_first_class`. (RA 11058 / DOLE DO 198-18 PTW; ISO 45001.)
6. **PLATFORM BUG — pm_knowledge 100% broken (AI).** (unchanged — schema-proven fix, live-verify pending edge re-bundle.)
7. **ROADMAP — the OWN-EMBEDDER arc** (self-hosted, per-tenant, hands-free, self-healing) refined from Ian ×2 (above).
8. **Retractions (evidence discipline):** U-2 mobile clutter (screenshot artifact); "500 entries" cap (worker-scoped
   exact count, correct); corrective-def drift (already contained by check #11's vocabulary lock, latent).

**Gate: `validate_logbook.py` 25 → 29 checks, all PASS.** Adjacent: logbook_consistency 4/0, validate_pm 13/13, no regressions.

## UPDATED SCOREBOARD (post-execution)
| Axis | Before → After | What moved |
|---|---|---|
| **U** best-capture | ~55% → **~85%** | entry-kind INVERTED keystone FIXED + gated; LOTO now a first-class capture field; U-2 retracted |
| **X** connectivity+provenance | ~90% → **~95%** | PM-mirror now asset-lineaged; asset lineage exact; corrective-def contained by check #11 |
| **F** flows E2E | ~85% → **~90%** | Inspection-readings now capturable; PM-mirror + LOTO create live-verified; parts ledger-safe |
| **A** mobile a11y 390px | **100%** | 0 WCAG 2.2 AA violations (unchanged) |
| **I** integrity+audit | ~80% → **~93%** | audit-trail wiring LOCKED (#28) + audit-GRADE export delivered + LOTO/permit first-class (#29) |
| **AI** grounded | ~75% → **~78%** | pm_knowledge FK fixed (schema-proven); bge-local-down + weak date-range answer are OWN-EMBEDDER/next items |

## NEXT (remaining LOCAL build units — the standing queue)
1. **Wire shift-handover to prefer the `loto_applied` column** over the `lotoRx` free-text regex
   (`shift-planner-orchestrator` — an edge fn, so it lands with the edge re-bundle; the column is already on
   `v_logbook_truth`). + seed a few `loto_applied=true` rows so the LOTO trail is demonstrable.
2. **OWN-EMBEDDER arc** (AI): stand up + supervise `bge-local` (:8901 is DOWN → external voyage fallback) + the
   self-healing re-embed worker + pm_knowledge live-verify on the edge re-bundle.
3. **Seed `hive_audit_log` logbook rows** so the amendment trail is demonstrable (the export already works off the
   3651 closed entries; this backfills the edit/amendment history).
4. **Phase 6 re-deepwalk**: full persona re-walk, confirm every axis at target (U ~85 / I ~93 / X ~95 / F ~90 / A 100).

---

## (superseded) NEXT → Phase 3 (Ideate) + Phase 4 (Roadmap), then Phase 5 keystone-first EXECUTE
Keystone = **entry-kind field-shaping fix** (route readings→Inspection/Preventive; add a Production/Reading context) — the
one defect confirmed 3 ways. Then cheapest-first: mobile capture polish (U-2), PM-mirror live-verify + seed link (reuse),
corrective-def canonicalization + gate (X), LOTO/audit-trail (I / Extension 3). Each slice LIVE-verified + gated via
`validate_logbook.py` / the logbook-validator skill.
