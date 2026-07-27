# Hive Deepwalk — EXPANSION Arc (journeys × personas × states, + new HK dimension classes)

> **Ian, 2026-07-27:** *"I love this flow we just had in marketplace"* — GROUND → roadmap →
> state+scoreboard → register the gate → drive Phase 1 (Engine A walk seeds Engine B harvest).
> Page chosen after measuring the candidates; the reasoning (and a correction to it) is in §0.

---

## §0 · WHY THIS ARC EXISTS — the honest depth gap (measured, not asserted)

`HIVE_BOARD_DEEP_ARC.md` (683 lines, opened 2026-07-10) already drove hive.html hard — but on a
**different axis**. It is a *page-deep UI/UX quality* arc: U1 five-second comprehension, U2 hierarchy,
U3 microcopy, U4 affordance, U5 iconography, U6 pleasantness, U7 cognitive load. It asks *"is this board
well-designed?"* and answers it per-element, at one moment, for one signed-in persona.

It does **not** ask the questions this arc exists for:

| Question the PDDA arc cannot answer | Why it needs an expansion arc |
|---|---|
| What does an **invited-but-not-joined** person see? | Persona axis — the PDDA arc walked supervisor + worker only |
| What happens across **join → welcome → board**? | Journey axis — a multi-step flow, not a page state |
| Does a **hive switch** carry the previous hive's role/data across? | Transition axis — the stale-state class |
| What does a **removed member** still hold client-side? | Lifecycle axis — the revocation class |
| Is a role boundary a **real** boundary or a CSS one? | Tenancy-integrity axis |

**The honest gap, measured 2026-07-27:** hive.html has 7 distinct views
(`onboard / create / code / join / welcome / board / shell`) and writes to `hives`, `hive_members` and
`hive_audit_log` — a genuine multi-step, multi-role lifecycle. The PDDA arc scored the **board** view.
Six of seven views and every transition between them are unwalked.

**A correction recorded on purpose** (the arc's own honesty discipline applies to its own justification):
this page was first recommended on "168 role-gates, 7× the next page." That number was wrong — **164 of
those are the word *supervisor* in CSS comments and layout rules**; the real count is 2 `role ===`, 1
`isSupervisor`, 1 `WHRoles`. The recommendation survives on better grounds (7-view lifecycle + membership
writes + the highest-consequence failure class on the platform: cross-hive isolation), but the original
headline was softer than presented. See §6 for what the first walk actually found.

---

## §1 · FRAMEWORK (reused, not reinvented — anti-drift)

Nothing here is a new method. This arc reuses, verbatim:

- **The 5 phases** `G → W → O → H → R` (Ground, Walk, Observe, Harvest, Resolve) — same as the
  marketplace expansion arc.
- **The two-engine loop** — Engine A (live Playwright-MCP journey walk) DRIVES Engine B
  (`tools/night_crawler.py` harvest). **Never crawl blind:** a harvest happens at spoke ⑤, *after* a
  real observed friction, so the citation answers a defect we can prove we have.
- **The measured %-board** — `tools/hive_deepwalk_scoreboard.py` computes from
  `hive_deepwalk_state.json`. No vibed percentages ([[feedback_measured_percent_not_qualitative_done]]).
- **The forward-only ratchet** — the board is a FLOOR; a cell that was walked cannot silently revert.
- **Evidence classification** — a cell is `done` only with cited live evidence
  ([[feedback_classify_by_evidence_not_heuristic]]).

### The surfaces in scope

`hive.html` (the 7 views) is the spine. In scope where a journey crosses into them:
`index.html` (the join/sign-in door), `nav-hub.js` + `utils.js` (the hive accessors and caches),
`community.html` (hive-scoped reputation), and any page reading `whHiveId()` — because a hive switch
must be correct **everywhere**, not just on the board that switched it.

---

## §2 · EXPANSION 1 — THE JOURNEY MATRIX (grow the JOURNEY denominator)

A journey is `done` on `W` only when walked in **≥2 personas AND ≥2 states**. One-persona/one-state is
the shallowness this arc exists to kill.

### Persona axis (7) — *the axis this page is actually about*
`P-anon` · `P-invited` (has a code, not yet a member) · `P-worker` · `P-supervisor` · `P-owner` ·
`P-multi` (member of ≥2 hives) · `P-removed` (was a member, no longer is)

> `P-multi` and `P-removed` are the two that seeded data could not express at all before this arc — see §6.

### State axis (5)
`S-empty` (no hive / first run) · `S-populated` · `S-single-member` · `S-error` (bad code, network) ·
`S-stale` (cached hive/role no longer true server-side)

### The journeys (H1–H14)

| # | Journey | Type | Personas that matter |
|---|---|---|---|
| H1 | First run → onboard choice (create vs join) | T1-onboarding | anon, invited |
| H2 | Create a hive → become owner → welcome → board | T1-onboarding | anon→owner |
| H3 | Join by code (valid) → welcome → board | T1-onboarding | invited |
| H4 | Join by code (invalid / expired / already-member) | T1-onboarding | invited, S-error |
| H5 | Board first paint — what each role sees | T2-core | worker, supervisor, owner |
| H6 | Invite a teammate → code generation → regeneration | T3-collab | supervisor, owner |
| H7 | Change a member's role | T3-collab | supervisor, owner |
| H8 | Remove a member → what they hold afterwards | T3-collab | supervisor + removed |
| H9 | Leave a hive → audit trail → where you land | T3-collab | worker, owner |
| H10 | **Switch hive** → does role/data/caches re-derive? | T4-transition | multi |
| H11 | Hive settings / rename → propagation to other surfaces | T3-collab | owner |
| H12 | Member list + presence ("on shift now") | T2-core | worker, supervisor |
| H13 | Hive health / maturity panel — backing + role scope | T5-insight | supervisor, worker |
| H14 | Cross-surface hive identity (any page reading whHiveId) | T6-fabric | multi, removed |

---

## §3 · EXPANSION 2 — NEW DIMENSION CLASSES `HK*` (grow the DIMENSION denominator)

**Deliberately seeded SMALL, and only where evidence already exists.** The marketplace arc invented
MK1–MK10 up front and several stayed theoretical until a walk gave them content — while the three classes
that mattered most (MK11 error-remedy, MK12 post-action coherence, MK13 reachable capability) were all
**born from observed friction** at spoke ⑤. This arc starts with the two classes the first walk earned,
and grows the rest the same way.

| Class | The rule | Seed evidence (§6) |
|---|---|---|
| **HK1 · Boundary is real, not cosmetic** | A role/tenancy boundary must be enforced by data (RLS / server-derived role), never by CSS visibility alone. A hidden element must be EMPTY, not merely `display:none` over real data. | Walked 2026-07-27: PASS with a caveat |
| **HK2 · Testability of a built capability** | If the product ships a capability, seeded state must be able to EXERCISE it. A capability no fixture can reach is untested by construction, and its bugs are invisible to every walk. | Walked 2026-07-27: FAIL → fixed |

**Candidate classes, NOT yet opened** (each needs a walk to earn it, per the rule above): revocation
completeness (what a removed member still holds), transition atomicity (a switch that half-applies),
invite-code lifecycle, and cross-surface identity coherence.

---

## §4 · THE %-BOARD (anti-drift compass — MEASURED)

Two boards, both computed by `tools/hive_deepwalk_scoreboard.py` from `hive_deepwalk_state.json`:

1. **Journey board** — `% = done_phases / (journeys × 5 phases)`, phase ∈ `done` / `partial` (0.5) / `todo`.
2. **Class board** — per HK class across 6 stages: `harvest → define → detect → sweep → fix → gate`.

Everything starts `todo` except the cells §6 already earned. **A green headline on one board never means
the arc is done** — both boards *plus* the §7 NEXT queue define "done"
([[feedback_seed_resolved_is_not_roadmap_done]]).

---

## §5 · DRIVE ORDER (lowest-first / risk-first)

1. **Tenancy-integrity first** — H8 (removal), H10 (switch), H14 (cross-surface identity). A boundary
   defect is the one that costs a real plant its privacy.
2. **Then the doors** — H3/H4 (join, valid + invalid), H1/H2 (first run). A broken door blocks everything.
3. **Then collaboration** — H6/H7/H9/H11.
4. **Then breadth** — remaining journeys to ≥2 personas × ≥2 states.

---

## §6 · SEED EVIDENCE (already earned, 2026-07-27 — the H0 baseline)

Walked live as `christinedizon` (role `worker`, Manila Electronics Assembly) before this roadmap existed;
recorded here rather than discarded.

- **HK1 — PASS, with a structural caveat.** `#supervisor-summary` IS present in a *worker's* DOM
  (9,699 chars) hidden by `class="hidden"` — but it contains **template only: zero filled numeric nodes**
  ("Computing hive health…"). No data leak. Then the stronger probe: I **forged** `wh_hive_role` to
  `supervisor` in localStorage and reloaded — the page **overwrote it back to `worker`** and granted
  nothing. hive.html re-derives role from the server, which is the *opposite* of the marketplace's
  `wh_last_worker` / `wh_hive_id` staleness. **Caveat:** the pattern is fragile — if a future change fills
  that panel before checking role, CSS would be the only thing hiding it. HK1's detector exists to hold
  that line.
- **HK2 — FAIL, fixed.** Seeded data was strictly **1:1 worker→hive** (15 memberships, 15 workers, none
  in two hives) because `hives_workers.py` built exactly one `member_row` per worker. Meanwhile hive.html
  carries ~28 hive-switcher references. So **H10 (switch hive) was unwalkable by construction** — every
  test saw a switcher whose list was always length 1. Fixed in the seeder: one worker now gets a second
  membership in a different hive **with a different role**, so the switch is observable (the board must
  re-derive supervisor affordances rather than carry the old role across). Same lesson as the marketplace
  trust columns in a new shape: **the seeder decides what can be tested**, and under-generating a
  relationship is the quieter failure because nothing looks wrong.
- **Cache inventory (for H10/H14):** a hive switch must invalidate `wh_hive_id`, `wh_hive_name`,
  `wh_hive_role`, `wh_active_hive_id`, `wh_hives`, and the per-hive `wh_hive_lastseen_<id>` keys. A
  `lastseen` key for a hive the current user is not in was observed on a shared browser — benign, but it
  is the shape H14 must check.

---

## §7 · NEXT (the standing queue — drive top-down)

1. **H10 `W`+`O` as `P-multi`** — now walkable after the §6 seeder fix. Switch hive; assert role, name,
   id and every dependent surface re-derive. Seeds the transition-atomicity candidate class.
2. **H8 `W`+`O` as `P-supervisor` + `P-removed`** — remove a member, then walk as them. What still
   renders? Seeds the revocation-completeness candidate class.
3. **HK1 `detect`** — build the static/live detector for "hidden element must be empty, not hiding data".
4. **HK2 `gate`** — assert seeded fixtures can exercise every shipped capability (start: multi-hive).
5. **Engine B harvest** on whichever friction H10/H8 actually surfaces (never crawl blind).

---

## §8 · THE FLYWHEEL — the standing SOP (momentum drive: one turn = one journey advanced)

① pick the lowest cell (§5 order) → ② **Engine A** live walk (full lens, ≥2 personas × ≥2 states) →
③ observe + record friction with evidence → ④ fix → ⑤ **Engine B** harvest a citable standard *for the
friction just observed* → ⑥ lock it with a gate → ⑦ ratchet the board → next cell.

**Why the crawler sits at ⑤ and nowhere else:** harvesting *before* a walk produces generic best-practice
noise we cannot act on; harvesting *after* a real friction produces a citable standard for a defect we can
prove we have.

### The queue can only look empty if you stopped harvesting
Every ⑤ that yields a new class **refills** the queue with 6 new stages. That is the structural cure for
"only forks and ceilings remain" — in the marketplace arc it produced MK11, MK12 and MK13 *after* the
board first read 100%, and MK13 found the deepest defect of that entire arc.

---

## §9 · THE TWO DISCIPLINES (non-negotiable)

**1. ANTI-DRIFT.** The board is MEASURED from state, never asserted in prose. A cell moves only on cited
live evidence. The scoreboard is a REGISTERED GATE (`run_platform_checks`), forward-only, so a walked cell
cannot silently revert. When a gate fires on code that is genuinely correct, **teach the gate** — never
bend the code — and pin the false-positive shape as a named self-test
([[feedback_teach_the_gate_not_bend_the_code]]). New DB functions, validators, RPCs and write tables need
their **registration in the same change**, or the gate finds them at push time.

**2. MOMENTUM.** Authoring a `NEXT:` line is *executing its first item*, not describing it. An Ian-gated
outward step (commit / push / deploy) is **not** a stop — pivot to the remaining local work. Only these
end a turn: **(a)** a genuine fork needing Ian's decision, **(b)** a hard external ceiling, **(c)** the
irreversible action is the sole remaining item, **(d)** the local queue is genuinely empty *and tested to
be*, **(e)** Ian says wrap. "The next unit is large/risky/bespoke" is never one of them — chip its first
slice.
