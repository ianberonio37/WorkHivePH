# PM Scheduler Deepwalk — EXPANSION Arc (journeys × personas × states, + new PM dimension classes)

> **Ian, 2026-07-28:** *"let's now plan for another page, what's next?"* → PM Scheduler, chosen after
> measuring the candidates (§0). Then: *"always use the framework with anti-drift discipline and
> momentum drive. maximize the nightcrawler."*
> Same canonical flow as the marketplace / hive / logbook expansion arcs: GROUND → roadmap →
> state+scoreboard → register the gate → drive Phase 1, with Engine A (live walk) seeding Engine B
> (night-crawler harvest) at spoke ⑤.

---

## §0 · WHY THIS ARC EXISTS — the honest depth gap (measured, not asserted)

`PM_SCHEDULER_DEEP_ARC.md` (2026-07-12) closed at **100% on every axis it named**, and it was real
work: three cross-hive write holes found and fixed (migration `20260712000012`, gate
`validate_pm_write_isolation.py` 4/4), the frequency-drop keystone that had hidden ~224/416 scope
items, worst-first triage, SMRP parity between page and analytics, and a cross-page write bug where
asset-hub turned a 7-day RCM interval into a Monthly PM.

It does **not** answer the questions this arc exists for:

| Question the PDDA arc cannot answer | Why it needs an expansion arc |
|---|---|
| Does the compliance number distinguish **on-time** from **merely done**? | Nobody asked. Measured below: **27% of PM intervals ran late** and the RPC calls every one compliant. |
| What does a **tech at the asset** see vs a **supervisor planning the week**? | Persona axis. The PDDA arc *names* these two as its heavyweight and then walked as one signed-in user. |
| What happens across **overdue → complete → next_due recompute**? | Transition axis — a multi-step flow, not a page state. |
| Is a **completion** amendable after the fact, and would anyone know? | Lifecycle axis. `pm_completions` has **no audit trigger** (measured). |
| Does changing an asset's **frequency** re-derive everything downstream? | Transition axis — the schedule is derived, and derived values drift. |

**A correction recorded on purpose** (the same honesty this arc will demand of its cells): PM was
first pitched to Ian partly on "6 of 7 update/delete calls don't confirm their writes." That number
was wrong — it was measured with a regex that counted `url.searchParams.delete()` as a database
write. The real figure is **2 unconfirmed DB writes** (`pm_assets` update + delete at ~L2640). The
recommendation survives on its actual grounds (compliance is the regulated artifact, the audit gap,
two genuinely distinct personas, 1,591 completions feeding four downstream surfaces), but the
headline was softer than presented. Same class of error as the hive arc's "168 role-gates."

---

## §1 · FRAMEWORK (reused, not reinvented — anti-drift)

- **The 5 phases** `G → W → O → H → R` (Ground, Walk, Observe, Harvest, Resolve).
- **The two-engine loop** — Engine A (live Playwright-MCP walk) drives Engine B
  (`tools/night_crawler.py`) at spoke ⑤. **Retrieve-first is still the rule** (`--query` / `--ensure`
  cost 0 crawl tokens on a hit); "maximize the crawler" means *crawl where the bag genuinely misses*,
  which for this domain it did — see §6.
- **The measured %-board** — `tools/pm_deepwalk_scoreboard.py` computes from `pm_deepwalk_state.json`.
  No number is ever asserted in prose.
- **Forward-only ratchet** — registered gate; a walked cell cannot silently revert.
- **The shallow-W guard** — `W=done` requires **≥2 personas AND ≥2 states**. It has already earned its
  keep twice: on the logbook arc it correctly refused two journeys until the *fixture* could express
  a second persona.
- **Evidence classification** — a cell moves only on cited live evidence.

### Surfaces in scope
`pm-scheduler.html` (3 screens: `dashboard` / `add` / `detail`, plus the scope-item sheet and the
completion capture). In scope where a journey crosses: `logbook.html` (the completion→logbook mirror,
now demonstrable — the logbook arc seeded it), `analytics.html` + `v_pm_compliance_truth` (the
compliance consumer), `hive.html` (PM Health), `shift-brain.html` (PMs-Due), `asset-hub.html` (the
RCM interval → frequency writer), and `get_pm_compliance_smrp` (the RPC every surface reads).

---

## §2 · EXPANSION 1 — THE JOURNEY MATRIX (grow the JOURNEY denominator)

### Persona axis (5)
`P-tech` (completes at the asset, mobile 390px) · `P-supervisor` (plans the week, triages overdue) ·
`P-multi` (member of ≥2 hives — the fixture the logbook arc doubled) · `P-teammate` (a second worker
in the same hive: whose completion is whose?) · `P-new` (a hive with a PM program but no completions).

### State axis (6)
`S-overdue` · `S-due-soon` · `S-compliant` · `S-never-completed` · `S-late-but-done` (the state the
compliance number cannot see) · `S-error` (RLS refusal / offline / failed write).

### The journeys (PM1–PM18)

| # | Journey | Type | Personas that matter |
|---|---|---|---|
| PM1 | First run — a hive with assets but no PM program | T1-onboarding | new, supervisor |
| PM2 | Register a PM asset → scope items → frequency | T2-core | supervisor |
| PM3 | The triage dashboard — worst-first, per role | T2-core | supervisor, tech |
| PM4 | Complete a PM at the asset (checklist, readings, sign-off) | T2-core | tech, teammate |
| PM5 | **Complete → `next_due_date` recompute → the card moves state** | T4-transition | tech; overdue→compliant |
| PM6 | Completion → logbook mirror (`pm_completion_id` lineage) | T6-fabric | tech |
| PM7 | **On-time vs late completion — what the number says either way** | T5-insight | supervisor |
| PM8 | Change an asset's frequency → whole schedule re-derives | T4-transition | supervisor; stale |
| PM9 | Skip / defer a PM — is a skip honest in the numbers? | T3-collab | tech, supervisor |
| PM10 | Compliance rollup: page ↔ analytics ↔ hive PM Health parity | T6-fabric | supervisor |
| PM11 | **Amend or delete a completion after sign-off** | T5-lifecycle | tech, supervisor |
| PM12 | Delete a PM asset → what happens to its scope items and history | T4-transition | supervisor |
| PM13 | Cross-hive boundary: a foreign completion cannot inflate our compliance | T7-tenancy | multi, teammate |
| PM14 | Parts / readings on a PM (the reuse boundary with logbook) | T6-fabric | tech |
| PM15 | Mobile 390px at-the-asset completion | T2-core | tech |
| PM16 | Templates + scope-item reuse across assets | T3-collab | supervisor |
| PM17 | Shift-brain "PMs Due" + AI companion grounding read the same truth | T6-fabric | supervisor |
| PM18 | Offline completion at the asset (no signal in the plant) | T4-transition | tech; offline |

---

## §3 · EXPANSION 2 — NEW DIMENSION CLASSES `PMK*` (grow the DIMENSION denominator)

Seeded **small and only where evidence already exists** — the discipline the hive and logbook arcs
proved. Two open on measured evidence; the rest are named candidates that must be *earned* by a walk.

| Class | The rule | Measure | Harvest | Distinct from existing | Skill | Gate |
|---|---|---|---|---|---|---|
| **PMK1 · On-time is not the same as done** (OPEN) | A compliance metric must distinguish a PM done *on schedule* from one done *late*, or it flatters the program. | Count intervals where the gap between consecutive completions exceeds `frequency_days`. | **Crawled 2026-07-28** (bag miss → teleport): PM compliance = completed ÷ scheduled × 100, world-class 90%, and it *"does not account for late PMs"* — `substrate/external/external-pm-schedule-compliance-metric.md` | `validate_pm.py` checks the formula's plumbing and SMRP parity, never on-time-ness | maintenance-expert + analytics | new detector |
| **PMK2 · A derived schedule must be derived from a real denominator** (OPEN) | The scheduled-count in a compliance window must reflect how often the PM is actually due, not a floor of 1. | Compare `GREATEST(1, period/freq)` against `period/freq` per frequency band. | Same SMRP source | `freq_render_robust` locks the frequency *vocabulary*, not the arithmetic | analytics + data-engineer | parity check |
| PMK3 · Completion immutability (candidate) | A signed-off completion is tamper-evident: post-hoc amendment is audited, never silent. | Walk PM11; probe a direct update. | earns on PM11 | LG4 solved this for logbook; `pm_completions` has **no** audit trigger | security | trigger + gate |
| PMK4 · Schedule re-derivation completeness (candidate) | Changing frequency/anchor re-derives due dates, badges and rollups everywhere at once. | Walk PM8; diff page vs analytics vs hive. | earns on PM8 | the PDDA arc verified ONE reschedule loop, not a frequency CHANGE | data-engineer | re-derive check |
| PMK5 · Skip honesty (candidate) | A skipped PM is neither silently compliant nor silently overdue; the number says which. | Walk PM9; census `status='skipped'`. | earns on PM9 | nothing models skip today | maintenance-expert | detector |
| PMK6 · Write confirmation (candidate) | A PM write whose success path mutates the UI or the audit log must confirm it landed. | The 2 unconfirmed `pm_assets` writes. | the logbook arc's LG3/LG9 | proven class, unswept here | qa + frontend | extend `validate_offline_queue_confirm` |
| PMK7 · At-the-asset reachability (candidate) | Everything a tech needs at 390px with one hand and no signal. | Walk PM15 + PM18. | mobile-maestro corpus | A-axis was axe-only | mobile-maestro | probe |

---

## §4 · THE %-BOARD (anti-drift compass — MEASURED)

1. **Journey board** — `% = done_phases / (18 journeys × 5 phases)`, phase ∈ `done`/`partial`(0.5)/`todo`.
2. **Class board** — per OPENED PMK class across 6 stages: `harvest → define → detect → sweep → fix → gate`.

`--selftest` pins the arithmetic and the shallow-W guard. Forward-only baseline in
`pm_deepwalk_baseline.json`; `--accept` ratchets after real progress. **A green headline on one board
never means the arc is done** — both boards *plus* the §7 queue define it.

---

## §5 · DRIVE ORDER (risk-first — consequence over convenience)

1. **The number that a plant acts on** — PM7/PMK1 (on-time vs done), PM10 (rollup parity), PMK2.
   A compliance figure that flatters reality is the one defect here that reaches a regulator.
2. **The signed-off record** — PM11/PMK3 (amendment evidence), PM9 (skip honesty).
3. **The transitions** — PM5 (recompute), PM8 (frequency change), PM12 (asset delete).
4. **The tech's reality** — PM4, PM15, PM18 at 390px and offline.
5. **Then breadth** — every remaining journey to ≥2 personas × ≥2 states.

---

## §6 · SEED EVIDENCE (already earned, 2026-07-28 — measured before the roadmap was written)

- **PMK1 — 27% of PM intervals ran LATE, and the compliance number cannot see it.** Across 1,224
  measured intervals, 331 (**27.0%**) were completed after `frequency_days` had elapsed and 14.5%
  at more than 1.5× the interval — while `get_pm_compliance_smrp` reports **85.7–87.5%** per hive,
  which reads as near-world-class against the crawled 90% benchmark. The RPC counts a completion
  whenever it lands in the period, regardless of whether it was on schedule. This is the same shape
  as the logbook arc's theme — *a record that flatters what actually happened* — and it is the
  strongest candidate for this arc's keystone.
- **PMK2 — the denominator is inflated for long-frequency PMs, but the effect is currently small.**
  `GREATEST(1, 90/frequency_days)` charges Semi-annual (31 items) and Annual (91 items) a full
  scheduled event per 90-day window when they are truly due 0.5 and 0.25 times. That is **122 of 416
  scope items (29%)** structurally over-counted. Measured impact on the headline today: **under one
  point** (85.7→85.3, 85.7→86.1, 87.5→87.1). **Recorded as latent-and-contained, not as "compliance
  is wrong"** — the honest disposition is a gate, exactly as LG2 handled the three "corrective"
  definitions.
- **PMK3 — `pm_completions` has no audit trigger.** Measured during the logbook arc's LG4 sweep: 6
  user triggers on the table, none of them audit. So a completion amended by any path that skips the
  page leaves no record — the weakness the logbook arc closed with `trg_logbook_post_close_audit`.
- **PMK6 — 2 unconfirmed DB writes** (`pm_assets` update + delete, ~L2640), the corrected figure.
- **Already hardened, do not re-litigate:** the three cross-hive write holes are fixed and gated
  (`validate_pm_write_isolation.py` 4/4); frequency vocabulary is canonical (`canonFreq` + gate);
  the completion→logbook mirror is wired, gated (#27) and — since the logbook arc — actually seeded.
- **Engine B, this arc's first harvest.** The external corpus held **144 chunks and not one on
  maintenance**: retrieve-first for PM/SMRP/schedule-compliance returned a genuine bag miss, which is
  the legitimate trigger to crawl. Three standards bagged and indexed:
  `external-pm-schedule-compliance-metric`, `external-planned-maintenance-percentage`,
  `external-maintenance-backlog-metric`. Two candidate sources were **refused by the crawler's own
  quality guard** (a link-inflated SMRP index page and two 404s) — the guard working, and worth
  recording as evidence that the harvest was real rather than nominal.

---

## §7 · NEXT (the standing queue — drive top-down)

1. ~~Ground, author this roadmap, harvest the missing domain standards.~~ (this turn)
2. **Build** `pm_deepwalk_state.json` + `tools/pm_deepwalk_scoreboard.py` with `--selftest`, register
   the gate + the `validate_pm_deepwalk.py` flywheel shim **in the same change** (the third arc hit a
   phantom block for want of that shim; the fourth should not).
3. ~~**PM7 / PMK1** — walked, measured, harvested, gated, and now SURFACED.~~ Done: the on-time
   figure is on the PM Scheduler card and the analytics KPI card, both from one RPC
   (`get_pm_ontime_delivery`, migration `20260728000005`); `get_pm_compliance_smrp` untouched. The
   sibling sweep found the sharper defect — analytics called the SMRP counts "PMs **on time**" —
   plus an un-swept `LOW` tag and a static "30 days" label on a 90-day number.
4. ~~**PM11 / PMK3** — probe a post-sign-off amendment; if it is silent, port the logbook trigger.~~
   Done: back-dating a completion by 400 days was silent; migration `20260728000004` records it,
   `validate_pm_write_isolation` grew a fifth check, teeth proven by dropping the trigger.
5. ~~**PM8** — the frequency-change transition.~~ Done, and the defect was upstream of the change:
   two writers converted an interval in days into the frequency WORD that derives the schedule, with
   different rules and neither matching the view. The CMMS import had no Daily bucket, so a 1-day
   PM was scheduled weekly. One shared `whFreqFromDays` (utils.js), gated by
   `validate_pm_frequency_mapping`; earned class **PMK4**.
6. ~~**PM5** — the recompute transition.~~ Done. The arithmetic is clean: `next_due_date` is derived
   in the view and every consumer reads the derived columns, so a completion re-derives everywhere by
   construction (recorded as a real clean result). The defect was the OTHER half of the transition —
   analytics replays a saved snapshot under a chip hardcoded to "Live recomputation each refresh",
   so a tech who completes a PM sees compliance unmoved with nothing saying the number predates
   their work. Chip now reports snapshot-vs-live per phase; gated by
   `validate_source_chip_freshness`.
7. ~~**PM12** — asset delete and its history.~~ Done, and the sharpest finding of the arc: a WORKER
   could delete a supervisor's PM asset, cascading **31 completion records and 8 scope items** away
   with no database record, because the supervisor-only rule lived only in the page. Migration
   `20260728000006` adds a restrictive DELETE policy and a BEFORE DELETE trigger recording what the
   cascade cost; `validate_pm_write_isolation` grew 5 → 8 checks.
8. ~~**PM9** — skip/defer honesty.~~ Done, and the answer is that the numbers ARE honest: a skip
   credits no compliance and does not move `next_due_date` (proven, and now asserted against the
   three `status='done'` filters it depends on). Two things recorded rather than papered over: the
   seeder was drawing status and note independently, so 78 skips carried completion notes (fixed);
   and **no UI can create a skip** — a tech who cannot do a PM must either leave it overdue or mark
   it done. Building that flow is a product decision, so it is written here, not invented mid-arc.
9. ~~**PM18** — the offline completion path.~~ Done. The good result first: pm-scheduler queues
   through the SHARED helper, so it inherited the logbook arc's 0-row confirmation with no change
   here. The defect was the mirror image — a retry after a LOST RESPONSE hit the dedup index's
   23505, was dead-lettered, and the widget told the worker their saved PM was **stuck**. Fixed in
   the shared drain as an OPT-IN (`insertDedupIndexed`), because it is only sound where the unique
   index is a true idempotency key; gated three ways.
10. ~~**PM15** — the mobile-390px completion path.~~ Done, with an instrument correction that
    matters: `browser_resize(390)` was yielding `innerWidth` **585** (the browser runs at dpr 0.667,
    so every width came back 1.5x). Re-measured at a true 390 via a 260-wide window. The dashboard
    scored **0** usability defects; the asset DETAIL scored **10** — the worked state is where they
    live. All page-owned targets fixed (`.complete-btn` 36→44, edit/delete 40→44, Back 20→44, Load
    More 38→44) and CLS 0.13 → **0.092** by reserving the two growing sub-lines. 10 → 0 on both
    screens.
11. ~~**PM10** — compliance rollup parity.~~ Done. The NUMBERS agree across pm-scheduler, analytics
    and the hive board (87.5 / 72.5 for Lucena, matching the DB) — worth checking precisely because
    this arc had just changed the analytics card. The defect was the NOUN: the hive board's
    deliberately ASSET-scoped overdue count was labelled "PM tasks" / "PMs" in four places against
    only one correct "assets", under-stating the work 29-vs-40. Six sites fixed in EN and FIL.
12. ~~**PM13** — the cross-hive boundary.~~ Done, and it found a REAL hole `xcomp` could not catch:
    `hive_id` your own + `scope_item_id` theirs was ACCEPTED, crediting the foreign hive's compliance
    (502→503 measured) and clearing its overdue PM via `last_completed_at`. Migration
    `20260728000007`; `validate_pm_write_isolation` now 9 checks.
13. ~~**PM6** — the completion→logbook mirror lineage.~~ Clean: 40 mirrors, 0 dangling, 0 cross-hive,
    40/40 with node lineage, and `SET NULL` correctly keeps the technician's record when a completion
    goes. Gated on the DATA (a payload check cannot see a dangling or cross-hive mirror). Recorded
    gap: `logbook.html` never links a mirrored entry back to its PM.
14. ~~**PM4** — the core at-the-asset completion.~~ Sound: it confirms with `.select().single()`,
    already treats 23505 as exactly-once (the same reasoning PM18 applied offline, reached
    independently here months earlier), has no hidden-field leak, and reports a failed logbook mirror
    honestly instead of claiming both wrote.
15. ~~**PM14** — the parts/readings reuse boundary.~~ KEEP-DISTINCT, and deliberately so: the PM
    sheet signs off (findings + action) while parts and readings live in the logbook entry the
    mirror creates. Duplicating a parts picker into the PM sheet would put a second writer on
    `inventory_transactions` — the ledger-tamper class two arcs have been closing. Recorded friction:
    nothing tells the tech the mirrored entry is where parts go.
16. ~~**PM17** — shift-brain + AI grounding parity.~~ Found the PM10 noun defect again, in the
    grounding: `agentic-rag-loop` counts DISTINCT assets (and says "Matches the tiles"), while
    `ai-gateway`'s proactive briefing head-counted scope-item rows and said "40 PM tasks overdue"
    where every screen says 29. Fixed to the canonical asset count. The companion is the surface a
    user can least verify, so it is the worst place to hold the minority definition.
17. Then §5 order downward — **PM1, PM2, PM3, PM16** remain (onboarding, registration, triage,
    templates); every ⑤-harvest that earns a class refills this queue.

**Carried out of the PM7 walk, CLOSED by PM15:** the summary cards shared a first-paint reserve
deficit — each `.sc-sub` placeholder is one line and fills to two or three, which was most of the
page's 0.13 CLS. Closed with scoped per-card reserves (`.sc-sub` is shared across ~17 pages, so the
fix is per-card, never a change to the shared class). CLS now **0.092**.

---

## §8 · THE FLYWHEEL (standing SOP — one turn advances a journey)

① pick the lowest cell (§5 order) → ② **Engine A** live walk (≥2 personas × ≥2 states) → ③ observe
with evidence (a clean walk is a real result; record it) → ④ fix → ⑤ **Engine B** harvest a citable
standard *for the friction just observed* (`--query`/`--ensure` first; crawl on a genuine bag miss)
→ ⑥ lock with a gate → ⑦ ratchet → next cell.

Method lessons carried in from the logbook arc: **fix every path that mutates**; **prove a test has
teeth by reverting the fix**; **a walk can consume its own fixture** — restore it; **verify the
INSTRUMENT before the page** (it cost six false readings last arc, and one is already recorded in
§0); **a red gate may be the stale one** — A/B against the pre-session baseline; **read a suite log
to its EXIT line**, never a prefix; **rebuild the substrate LAST**, it indexes skills as well as docs.

---

## §9 · THE TWO DISCIPLINES (non-negotiable)

**1. ANTI-DRIFT.** The board is MEASURED from state, never asserted. A cell moves only on cited live
evidence. The scoreboard is a REGISTERED, forward-only gate. When a gate fires on correct code,
**teach the gate** — never bend the code — and pin the false-positive shape as a named self-test. New
DB functions, validators, RPCs and write tables need their registration **in the same change**.

**2. MOMENTUM.** Authoring a `NEXT:` line is *executing its first item*. An Ian-gated outward step
(commit / push / deploy) is never a stop — pivot to the remaining local work. Only these end a turn:
**(a)** a genuine fork needing Ian's decision, **(b)** a hard external ceiling, **(c)** the
irreversible action is the sole remaining item, **(d)** the local queue is genuinely empty *and
tested to be*, **(e)** Ian says wrap.
