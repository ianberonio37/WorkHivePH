# Logbook Deepwalk — EXPANSION Arc (journeys × personas × states, + new LG dimension classes)

> **Ian, 2026-07-28:** *"achieve the Hive to 100% overall first then proceed to logbook roadmap next."*
> Hive closed at 100% on every §4 axis on 2026-07-28; this arc reuses the same canonical flow —
> GROUND → roadmap → state+scoreboard → register the gate → drive Phase 1 (Engine A walk seeds
> Engine B harvest). Same framework as `HIVE_DEEPWALK_EXPANSION_ROADMAP.md`, retargeted.

---

## §0 · WHY THIS ARC EXISTS — the honest depth gap (measured, not asserted)

`LOGBOOK_DEEP_ARC.md` (405 lines, closed 2026-07-12 at U~85 / X~95 / F~90 / A 100 / I~93 / AI~78)
drove logbook.html hard — but on the *page-deep capture-UX* axis. It fixed the inverted entry-kind
keystone, made LOTO first-class, made the DOLE/ISO export audit-grade, lineaged the PM mirror, and
spawned the own-embedder arc. Genuinely good work. **And its entire live walk was ONE persona
(pabloaguilar, worker, Lucena) at one moment.** The questions it cannot answer are this arc:

| Question the PDDA arc cannot answer | Why it needs an expansion arc |
|---|---|
| What happens across **offline capture → queue → reconnect → sync**? | The IndexedDB queue (`wh_logbook_offline`) is a **WRITE cache** — the hive arc's whole lesson ("a value painted from cache must reconcile with truth") in write form. Never walked. |
| Can a worker **edit/delete someone ELSE's entry** — and is the refusal data or CSS? | Boundary axis — needs a second persona in the SAME hive. The PDDA had none. |
| What does an edit **after close/sign-off** do downstream? | Lifecycle axis — `wo_state` immutability + amendment propagation. Export was verified; amendment was left as a seed backfill and never walked. |
| Does a **hive switch** with a draft / queued row / open filter bleed across tenants? | Transition axis — the P-multi fixture only EXISTS since the hive arc seeded it (2026-07-27). |
| Do **both edit paths** (`saveEdit` modal + `saveEditFromForm` in-place) apply the same contract? | Mutation-path parity — the PDDA *measured* that both UPDATE paths omit `auth_uid` and left it a "candidate". Never resolved. The hive arc's "7 writers → 1 adopter" shape, as write paths. |
| Does an entry's mutation **reconcile all ~11 consumers**? | `v_logbook_truth` feeds asset-hub, analytics, pm-scheduler, project-manager, resume, assistant, dayplanner, hive, integrations, index + infra — the **widest blast radius of any page walked so far**. A wrong write poisons MTBF, compliance and a person's resume evidence. |

**Immunity already banked (don't re-prove):** the hive arc forged a supervisor role on logbook.html
and the page overwrote it back at load — logbook re-derives role per load and renders once
(HIVE roadmap §7). The load-time role path is clean; the UNWALKED analogs are the offline queue and
the in-place edit paths, which mutate without a reload.

**PDDA leftovers folded into this arc** (its §NEXT, items never closed): shift-planner still prefers
the `lotoRx` free-text regex over the `loto_applied` column (→ LB12); `hive_audit_log` amendment
rows unseeded so the amendment trail is undemonstrable (→ LB16/LG4); the Phase-6 multi-persona
re-deepwalk never ran (→ this whole arc).

---

## §1 · FRAMEWORK (reused, not reinvented — anti-drift)

Nothing here is a new method. Reused verbatim from the hive/marketplace expansion arcs:

- **The 5 phases** `G → W → O → H → R` (Ground, Walk, Observe, Harvest, Resolve).
- **The two-engine loop** — Engine A (live Playwright-MCP journey walk) DRIVES Engine B
  (`tools/night_crawler.py` harvest at spoke ⑤ only, `--query` retrieve-first, never blind).
- **The measured %-board** — `tools/logbook_deepwalk_scoreboard.py` computes from
  `logbook_deepwalk_state.json`. No vibed percentages.
- **The forward-only ratchet** — registered gate; a walked cell cannot silently revert.
- **Evidence classification** — a cell is `done` only with cited live evidence.
- **The shallow-W guard** — W=done requires ≥2 personas AND ≥2 states.

### The surfaces in scope

`logbook.html` is the spine (capture wizard · team feed · entry detail · edit modal AND in-place
edit · the embedded ASSET MANAGER (`asset_nodes` upsert/update/delete live on this page) · offline
queue). In scope where a journey crosses into them: `pm-scheduler.html` (the PM→logbook mirror),
`asset-hub.html` (equipment history), `analytics.html` (MTBF/downtime lineage), `inventory.html`
(`inventory_deduct` parts round-trip), `shift-brain.html` + `shift_plans` (handover composes from
the logbook), `assistant.html` (grounded answers), `resume.html` (experience evidence), and the
edge fabric (`embed-entry`, `cmms-push-completion`, `voice-logbook-entry`). Ignore
`logbook.backup.html`.

---

## §2 · EXPANSION 1 — THE JOURNEY MATRIX (grow the JOURNEY denominator)

A journey is `done` on `W` only when walked in **≥2 personas AND ≥2 states**.

### Persona axis (5)
`P-worker` (field tech, own entries — pabloaguilar) · `P-teammate` (a second worker in the SAME
hive — the "someone else's entry" axis) · `P-supervisor` · `P-multi` (member of ≥2 hives — the
fixture the hive arc seeded) · `P-new` (first-run: signed in, no entries / fresh hive).
*(Anon is out of scope: the logbook is a signed-in tool; the door is index.html, walked in the hive arc.)*

### State axis (6)
`S-empty` (no entries / first run) · `S-populated` · `S-offline` (capture while disconnected,
queue non-empty) · `S-error` (network/RLS refusal mid-write) · `S-stale` (a painted value no longer
true server-side) · `S-closed` (signed-off entry — the immutable state).

### The journeys (LB1–LB20)

| # | Journey | Type | Personas that matter |
|---|---|---|---|
| LB1 | First run → empty logbook → first capture | T1-onboarding | new, worker |
| LB2 | Core capture: 3-step wizard → complete corrective entry (machine/problem/action/root-cause/downtime) | T2-core | worker, teammate |
| LB3 | Entry-KIND routing — each kind shapes the right fields (PDDA keystone, now cross-persona/state) | T2-core | worker, supervisor |
| LB4 | Readings capture via template (Inspection/Preventive) → trend consumers | T2-core | worker |
| LB5 | Parts consumed on a fault → `inventory_deduct` → inventory ledger round-trip | T6-fabric | worker + inventory view |
| LB6 | Voice / photo / OCR capture paths → same contract as typed capture | T2-core | worker |
| LB7 | **Offline capture → queue → reconnect → sync → server truth** | T4-transition | worker, multi; S-offline→S-populated |
| LB8 | Team feed — what each role sees; own-vs-others affordances | T3-collab | worker, teammate, supervisor |
| LB9 | Edit own entry — BOTH paths (modal + in-place) → same contract | T2-core | worker |
| LB10 | **Edit/delete boundaries on someone else's entry** — glass AND data | T3-collab | worker vs teammate, supervisor |
| LB11 | Close / sign-off → `wo_state` lifecycle → immutability + audit row | T5-lifecycle | worker, supervisor; S-closed |
| LB12 | Shift handover composes FROM the logbook (`shift_plans`, `loto_applied` over lotoRx) | T6-fabric | worker, supervisor |
| LB13 | PM completion → logbook mirror (`pm_completion_id` lineage, from the pm-scheduler side) | T6-fabric | worker |
| LB14 | Asset linkage — entry → asset-hub equipment history (FK lineage) | T6-fabric | worker |
| LB15 | Analytics lineage — a new corrective entry MOVES MTBF/downtime live | T6-fabric | worker + analytics view |
| LB16 | **Amendment propagation — edit/delete an existing entry → downstream consumers reconcile** | T4-transition | worker, supervisor; S-stale |
| LB17 | **Hive switch with logbook context (draft / queue / filters) → zero cross-tenant bleed** | T4-transition | multi; S-stale |
| LB18 | Feed search / filter / pagination (`loadMoreLogbook`) + deep-link `openDeep` | T2-core | worker, teammate |
| LB19 | External fabric: CMMS push (`cmms-push-completion`) + knowledge embed (`embed-entry`) | T6-fabric | worker; S-error |
| LB20 | Companion answers from `v_logbook_truth` incl. date-range ("what did I log last week?") | T5-insight | worker, supervisor |

---

## §3 · EXPANSION 2 — NEW DIMENSION CLASSES `LG*` (grow the DIMENSION denominator)

**Seeded SMALL, opened only on evidence** — the hive lesson, kept: the marketplace arc invented ten
classes up front and several stayed theoretical; the hive arc seeded two and grew to three through
walks. Here **LG1–LG2 open with already-measured evidence** (from the PDDA arc's own findings);
**LG3–LG10 are named candidates** with full specs, NOT in the board denominator until a walk earns
them (every earned one refills the queue with 6 stages).

| Class | The rule | Measure | Harvest (evidence) | Distinct from existing | Skill | Gate |
|---|---|---|---|---|---|---|
| **LG1 · Mutation-contract parity** (OPEN) | Every path that mutates a logbook row applies the SAME contract: `auth_uid`, `hive_id`, audit row, cache/queue invalidation. | Enumerate every mutation site (insert / both updates / delete / mirror writes) and diff their contracts. | **Measured 2026-07-12:** INSERT sets `auth_uid`; BOTH update paths (`saveEdit` + `saveEditFromForm`) omit it — vs locked rule `feedback_authuid_attribution_on_every_write`. Two edit paths = the hive "7 writers" shape. | `validate_logbook.py` checks the FORM contract, not path parity; the locked rule has no logbook-UPDATE detector. | multitenant + qa | new detector (extend `validate_logbook.py` or standalone) |
| **LG2 · Derived-definition single-sourcing** (OPEN) | A derived semantic ("corrective", "open", downtime window) has ONE canonical definition across every consumer. | Enumerate derived fields consumed downstream; count distinct definitions per field. | **Measured 2026-07-12:** three "corrective" definitions live at once (`is_corrective` regex / exact string in v_asset_truth + 5 RPCs / ilike in trigger-ml-retrain), latent at 0 divergent rows. | Check #11 locks vocab VALUES, not definition parity across views/RPCs/fns. | data-engineer + analytics | definition-parity check |
| **LG3 · Offline-queue reconciliation** (OPEN — earned by the LB7 walk, 2026-07-28) | A queued write is a CACHE. A drain that removes an item must confirm the write affected a row: PostgREST returns `error:null`/204 for a 0-row update or delete, so a bare `if (!error)` destroys the worker's only copy and reports success. | Walked LB7 live: deleted the row server-side mid-offline, then confirmed DB row absent + queue drained + "1 offline change synced." | web.dev offline-UX: "never silent-fail, never false-success"; "on reconnect tell the user what synced + surface any conflict… don't silently drop" | SW/offline checks exist for ASSETS, not the write queue's semantics | frontend + realtime | `validate_offline_queue_confirm.py` ✅ registered, teeth proven |
| LG4 · Close/sign-off immutability (candidate) | A closed entry is tamper-evident: post-close edits are AUDITED amendments, never silent rewrites. | Walk LB11/LB16; probe post-close UPDATE on glass and via RLS. | earns on LB11 | Gate #28 locks WIRING of audit writes, not post-close behaviour | security + knowledge-mgr | post-close probe/gate |
| **LG5 · Transition tenant-integrity** (OPEN — earned by the LB17 walk, 2026-07-28) | Data in flight carries CAPTURE-time identity: a switch must neither re-home it (data) nor display it outside that hive (glass). | Walked LB17 live as a multi-hive member: a Manila entry captured offline rendered as a live "Pending sync" card in the Lucena feed. | Same web.dev queue-visibility standard, plus the hive arc's cache-vs-truth lesson in write form | Hive arc locked the ROLE marker; this is the DATA-in-flight analog | multitenant | `validate_offline_queue_confirm.py` ✅ (`audit_queue_hive_scope`) — **sweep still partial** |
| LG6 · Amendment downstream propagation (candidate) | An edit/delete reconciles every consumer of `v_logbook_truth` (~11), not just the feed that made it. | Walk LB16; diff a consumer surface before/after an amendment. | earns on LB16 | MK12 post-action coherence is same-PAGE; this is cross-SURFACE | data-engineer | lineage re-derive check |
| LG7 · Fixture capability coverage (candidate) | Seeded state must be able to EXERCISE every shipped capability (closed entries, PM-linked, multi-hive, second worker, amendment history). | Census the fixtures against the journey matrix. | HK2 reapplied; hive arc proved the seeder decides what is testable | `validate_fixture_capability_coverage.py` covers HIVE shapes today | qa + data-engineer | extend fixture-coverage gate |
| **LG8 · Mirror integrity, both directions** (OPEN on measured evidence, 2026-07-28 — not yet walked) | Mirrors stay consistent under create AND amend/delete, not only create. | Measured live: `fault_knowledge.logbook_id` has **no foreign key at all** (the table's only FK is `hive_id`), so deleting an entry orphans its knowledge row, which stays in the RAG corpus citing an entry that no longer exists. **21 orphans live right now**, dated 2026-07-20/21, none from this session — pre-existing drift against the PDDA arc's 529/529-valid measurement. | pending | Gate #27 locks CREATE lineage only | data-engineer | orphan-scan gate (open) |
| LG9 · Role boundary on glass vs data (candidate) | Every role-gated affordance (edit-others, sign-off, delete) is RLS-backed, never CSS-only. | Walk LB10; forge + direct-write probes. | HK1 reapplied to logbook's write affordances | HK1 gate covers hive.html chrome | multitenant + security | RLS-parity probe |
| LG10 · Capture-path contract completeness (candidate) | Every capture path (wizard / voice / photo / OCR / offline / CMMS-in) lands a contract-valid row — no side door skips validation. | Walk LB6/LB7/LB19; diff resulting rows against the wizard's contract. | earns on LB6 | `wh-capture-validate` exists for SOME paths; parity unmeasured | ai-engineer + qa | capture-parity check |

---

## §4 · THE %-BOARD (anti-drift compass — MEASURED)

Two boards, both computed by `tools/logbook_deepwalk_scoreboard.py` from
`logbook_deepwalk_state.json`:

1. **Journey board** — `% = done_phases / (20 journeys × 5 phases)`, phase ∈ `done` / `partial` (0.5) / `todo`.
2. **Class board** — per OPENED LG class across 6 stages: `harvest → define → detect → sweep → fix → gate`.

Selftest pins the arithmetic (all-todo=0%, all-done=100%, all-partial=50%) and the shallow-W guard
(a 1-persona walk scores 0.5, never 1.0). Forward-only baseline in
`logbook_deepwalk_baseline.json`; `--accept` ratchets after real progress. **A green headline on one
board never means the arc is done** — both boards *plus* the §7 queue define "done".

---

## §5 · DRIVE ORDER (risk-first — blast radius over convenience)

1. **Write-cache + tenancy first** — LB7 (offline queue), LB17 (hive switch), LB10 (edit-others
   boundary), LB16 (amendment propagation). The logbook feeds ~11 surfaces; a wrong or re-homed
   write is the failure that poisons MTBF, compliance and someone's resume.
2. **Then the lifecycle** — LB11 (close/sign-off), LB9 (both edit paths — LG1's walk).
3. **Then the doors** — LB1/LB2/LB3 (capture across personas/states; the PDDA already proved the
   single-persona happy path).
4. **Then the fabric** — LB13/LB14/LB15/LB19/LB12/LB20.
5. **Then breadth** — every remaining journey to ≥2 personas × ≥2 states.

---

## §6 · SEED EVIDENCE (already earned — no cell starts done without citation)

No new H0 walk was needed; the seeds are prior MEASURED findings:

- **LG1 harvest** — PDDA Phase 0–1 (2026-07-12): both UPDATE paths omit `auth_uid`; INSERT sets it.
  Two distinct edit paths confirmed in code. Unresolved since.
- **LG2 harvest** — PDDA X-axis finding (2026-07-12): three simultaneous "corrective" definitions,
  0 divergent rows today, drift latent by luck of vocabulary.
- **Load-time role immunity** — hive arc (2026-07-27): forged supervisor role on logbook.html was
  overwritten back at load; the page renders once. (Why LB-journeys focus on the paths that mutate
  WITHOUT a reload: queue, in-place edit, switch.)
- **Fixture census** (2026-07-12): 3 hives / 3,700 entries; readings inline jsonb; fault_knowledge
  529/529 FK-valid; PM-mirror wiring fixed + gated (#27) but seed rows unlinked; `hive_audit_log`
  amendment rows unseeded. P-multi membership exists since 2026-07-27 (hive arc seeder fix).
- **G-phase credits** in the state file cite the PDDA map (file:line attach points) — only journeys
  whose surfaces/tables/handlers are genuinely mapped there start with G=done. The five §5-priority
  journeys (LB7/LB10/LB16/LB17 + LB1) start G=todo — their ground was never mapped, which is itself
  the measured gap.

---

## §7 · NEXT (the standing queue — drive top-down)

**Board after the first drive (measured, 2026-07-28): 56.0% overall** — journeys 31.5%, classes 80.6%
over a denominator that GREW from 2 classes to 6. Done: ~~scaffold + gate + shim~~,
~~LB7 offline walk~~ (2 personas × 3 states; silent-loss defect found, fixed across 7 drain sites,
gated with teeth proven), ~~LB17 switch walk~~ (cross-hive feed leak found, fixed, gated),
~~LG5 sweep~~ (came back clean — see below), ~~LB9 / the auth_uid trap~~ (backfilled + one honest
explainer shared by both write paths), ~~the stuck Save button~~ (an async race, fixed at the
source), ~~LB10 / LG9~~ (boundary proven real, glass made honest, gated), ~~LG8~~ (the knowledge
mirror finally has a foreign key).

1. **LG1 finish** — enumerate every logbook mutation site (saveEdit modal, saveEditFromForm,
   deleteEntry, the PM mirror, voice/photo capture) against one contract, then detect + gate the
   parity. Confirmation and explanation are single-sourced now; the enumeration is not.
2. ~~**LG9 sweep**~~ — done, and it found a worse instance than the one that earned the class: the
   asset manager on this same page was writing **audit-log entries for edits the database refused**,
   repainting the UI as if they had applied, and propagating the phantom name to `pm_assets`. Fixed
   and gated. The parts/inventory actions on this page are still unswept.
3. **LG8 sweep** — the sibling mirrors (`pm_knowledge.pm_completion_id`, `skill_knowledge`,
   `project_links`) have not been checked for the same missing-FK shape that let the knowledge
   corpus drift.
4. **LB16 amendment walk** — now that deletes cascade, walk edit+delete of a *consumed* entry and
   diff asset-hub / analytics / resume before and after (LG6 earn attempt).
5. **LB11 close/sign-off** — post-close immutability is still unwalked; gate #28 locks the audit
   *wiring*, not the behaviour (LG4 earn attempt).
6. Then §5 order downward; every ⑤-harvest that earns a class refills this queue.

**One decision left with you, deliberately not made in a migration:** one dangling
`fault_knowledge` row survives — the mirror of the entry this arc deleted to prove the silent-loss
defect. It holds that entry's full content (WLD-001, "Output current unstable, weld quality poor",
"Replaced 4 carbon brushes, cleaned commutator"). Either delete the knowledge row, or restore the
logbook entry from it; then run `ALTER TABLE fault_knowledge VALIDATE CONSTRAINT
fault_knowledge_logbook_id_fkey;` and the constraint becomes fully verified rather than
forward-only. I did not restore it myself because `date`, `status` and `downtime_hours` are not in
the mirror, and a row with those NULL would skew analytics more quietly than a missing row does.

**LG5's sweep came back clean, which is a real result and recorded as one:** every other queue
surface (community, dayplanner, inventory, pm-scheduler, skillmatrix, asset-hub FMEA) only
*enqueues* — none reads its queue back to render a list, so none can leak a queued row across
hives. `logbook.html` is the only page that merges pending items into its feed, which is exactly
why it was the only page with the defect. The same shape as the hive arc's finding that `hive.html`
was the only page mutating role without a reload.

**Fixture note (honest record, and a correction):** the LB7 walk consumed one real seeded row —
`log-3f8360c61f28` (Pablo Aguilar, WLD-001) was deleted to prove the silent-loss defect. Pablo is at
571 entries, was 572; `validate_fixture_capability_coverage.py` still passes on all 4 capabilities.
**A claim I made earlier in this arc was wrong and is corrected here:** I reported that none of the
21 orphaned `fault_knowledge` rows came from this session, but that check only examined the 10 most
recent orphans and missed mine. One of them *was* the deleted entry's mirror — which is how its
content turned out to be recoverable after I had already recorded it as lost. See §7 for the
decision that leaves.

---

## §8 · THE FLYWHEEL (standing SOP — momentum drive: one turn = one journey advanced)

① pick the lowest cell (§5 order) → ② **Engine A** live walk (full lens, ≥2 personas × ≥2 states)
→ ③ observe + record friction with evidence → ④ fix → ⑤ **Engine B** harvest a citable standard
*for the friction just observed* (`night_crawler --query` retrieve-first, 0 crawl tokens, before any
crawl) → ⑥ lock it with a gate → ⑦ ratchet the board → next cell.

Method lessons carried from the hive arc, in force here: **(a)** fix every path that mutates, not
just the walked one — centralize into ONE adopter, reveals are TOGGLES; **(b)** prove a test has
teeth by reverting the fix; **(c)** a walk can consume its own fixture — restore + re-verify
coverage after every walk; **(d)** verify the INSTRUMENT before the page — probe the state a real
user reaches via a real reload, never a hand-assembled one; **(e)** a red test may be the stale one
— A/B against the pre-session baseline and recall the disposition first; **(f)** don't bolt a
low-confidence detector onto a gate that isn't wrong — teach the gate or leave the shape to the walk.

---

## §9 · THE TWO DISCIPLINES (non-negotiable)

**1. ANTI-DRIFT.** The board is MEASURED from state, never asserted in prose. A cell moves only on
cited live evidence. The scoreboard is a REGISTERED GATE, forward-only. When a gate fires on code
that is genuinely correct, teach the gate — never bend the code. New DB functions, validators, RPCs
and write tables need their registration in the same change.

**2. MOMENTUM.** Authoring a `NEXT:` line is *executing its first item*, not describing it. An
Ian-gated outward step (commit / push / deploy) is never a stop — pivot to the remaining local
work. Only these end a turn: **(a)** a genuine fork needing Ian's decision, **(b)** a hard external
ceiling, **(c)** the irreversible action is the sole remaining item, **(d)** the local queue is
genuinely empty *and tested to be*, **(e)** Ian says wrap.
