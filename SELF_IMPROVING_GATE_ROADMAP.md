# Self-Improving Mega Gate — Roadmap

**Created:** 2026-06-01
**Status:** Architecture-of-record + phased plan (design only; no engine built yet)
**Companion docs:** [UNIFIED_MEGA_GATE.md](UNIFIED_MEGA_GATE.md) (the 6 gate layers), [SENTINEL_ARCHITECTURE.md](SENTINEL_ARCHITECTURE.md) (the two bridges), [COMPREHENSIVE_STUDY_FULLSTACK_GATE.md](COMPREHENSIVE_STUDY_FULLSTACK_GATE.md) (the 13×6 matrix)
**Engine today:** [tools/flywheel_orchestrator.py](tools/flywheel_orchestrator.py) — an *observer/scorer*, not a driver (its own docstring promises "PROMOTIONS" that `_run_turn()` never computes)

---

## 0. The reframe (why this roadmap exists)

The Mega Gate is a **self-*measuring*** system that is **manually self-*improving***. The bridges
the docs call "self-improving" (GH Hardening L2→L0, GS Sentinel L0→L2) are **agent rituals**
(`/harden`, `/sentinel-review`); `flywheel_orchestrator.py` only **scores** progress.

A layer is genuinely self-improving only when it has FOUR properties. The gate has the first three
almost everywhere and the fourth almost nowhere:

1. **Input** it consumes ✅
2. **Transform** it applies ✅
3. **Output** that feeds the next layer ✅
4. **A feedback signal that changes the layer's own behaviour over time** ❌ ← *this roadmap*

Four feedback signals are missing — and every painful moment of the 2026-05-31 session was a symptom
of one being absent:

| Missing signal | Symptom we actually hit |
|---|---|
| **Efficacy / yield** (which validators ever catch a real bug) | 330 validators, zero idea which are load-bearing vs dead weight; gate only accretes, never sheds |
| **Freshness / decay** (validator asserting a shape the code moved past) | model_router / schema_coverage / agent_memory_store — 3 validators lagging refactors, invisible until a full-gate run |
| **Noise vs signal** (real regression vs weather) | stale `*_report.json` phantom-block; adoption-ratchet logged as "regression"; Docker-down `httpx 10061` flipped 4 data validators |
| **Honest-metric pull** (check/behavioural coverage, not topic) | `SENTINEL_ARCHITECTURE.md` itself warns topic-coverage looks healthy while check-coverage is the truth |

**North star:** drive **behavioural/check-level coverage** (the honest number) up while keeping gate
runtime and false-positive noise *down*. A gate that only grows eventually collapses under its own
runtime and gets `--no-verify`'d into irrelevance.

---

## 1. The two tracks

- **Track A — Self-Improving Gate:** give the gate the four missing senses (efficacy, decay, noise
  classification, promotion) so it reshapes itself.
- **Track B — SkillOpt-style skill-doc optimization:** apply the same rigour to the `SKILL.md` files
  (and validator/baseline edits) — the three transferable ideas from the SkillOpt pipeline:
  **(i) held-out validation split, (ii) edit accept/reject gate + `best_skill.md` checkpoint +
  rejected-edit buffer, (iii) helped/failed efficacy ledger.**

They converge: Track A's efficacy ledger *is* Track B's "which edits helped" meta-signal, and Track
B's held-out split *is* the validation rigour Track A's promotion gate needs.

---

## 1.5 The two governing axes (dimensions × macro-loop)

The engines (Tracks A/B, phases P0–P8) are the **machinery**. Above them sit two orthogonal axes
that say *what the machinery is for*. Hold all three levels in mind: **dimensions** (what "good"
means) × **macro-loop** (the rhythm of evolution) × **engines** (the parts that do the work).

### Axis 1 — The four quality dimensions (the balanced scorecard: WHAT we measure)

The gate must report coverage on **four** dimensions, not one number. Today it over-indexes on the
two that static analysis is good at and under-covers the two that need real interaction + time:

| Dimension | The question it asks | Covered today by | Honest coverage | Strengthened by |
|---|---|---|---|---|
| **Usability** | Can a real (mobile, field, loud-environment) user actually complete the task? | Mobile Maestro / Designer / Community skills; L0 aria/tap-target/heading; L2 mobile scenarios | **Structural OK, behavioural THIN — biggest gap** | P6 held-out behavioural probes; GS sentinel scenarios |
| **Functionality** | Does it do the right thing, correctly? | G0 (bulk of 330 validators), G2 E2E, canonical board, calc/KPI validators | **Strong** | P4 noise quarantine keeps it honest |
| **Adaptability** | Can it change/extend without breaking — *and can the gate itself adapt?* | G-1 auto-discovery; schema/migration validators; multitenant per-hive | **Partial — the self-improving engines literally ARE this dimension** | P2 promotion, P3 decay, P5 retirement |
| **Internal control** | Is it governed, secure, isolated, auditable, non-bypassable — *including the gate's control over itself?* | Security / Multitenant / Enterprise-compliance skills; RLS-open + canonical + audit baselines | **Reasonable** | P1 efficacy provenance; Rule D; "no `--no-verify`" |

**The rebalancing insight:** a gate optimized only for functionality + internal control produces a
platform that is *correct and governable but rigid and unusable*. Replace the single north-star
metric with this **4-axis scorecard**, and have the locked test split (P6) report **per dimension**
so the loop is pulled toward the weak axes (usability behaviour, adaptability) instead of padding the
strong ones. Note the recursion: **internal control applies to the gate itself** — baselines can't be
gamed, provenance is tracked (P1), bypass is forbidden.

### Axis 2 — The macro-loop (the outer lifecycle: HOW the gate evolves)

The four-stage cycle — **Retrospection → Capability Building → Continuous Improvement → Platform
Readiness → (loop back)** — is the **outer epoch** that drives the inner engines. It mirrors
SkillOpt's epoch-wise slow update (and the OODA/PDCA family), but in your terms:

| Macro-stage | The question | Inner engines + artifacts it runs | Dimensions it advances |
|---|---|---|---|
| **Retrospection** | "What did the last cycle teach us?" | efficacy ledger (P1), flywheel diff, G-1.5 miners, epoch reflection (P8), regressions/drift | reads all 4 |
| **Capability building** | "Build the muscle to handle what we learned." | promotion engine (P2), GH harden (L2→L0), GS sentinel (L0→L2), skill-edit gate (P7), new features | functionality, usability, adaptability |
| **Continuous improvement** | "Refine and keep it clean." | ratchets, decay detector (P3), noise quarantine (P4), retirement (P5) | adaptability, internal control |
| **Platform readiness** | "Are we shippable on data we never tuned against?" | canonical board, `RELEASE_GATE_AI_INTEGRATION.md`, held-out **test** split (P6), the 4-axis scorecard | all 4, gated |
| **↻ loop back** | readiness *gaps* become the next retrospection's agenda | (feeds Retrospection) | — |

**Readiness is a checkpoint, not a finish line.** Each time the platform passes, the bar rises and
the unmet scorecard cells (esp. the thin usability/adaptability axes) seed the next retrospection.
That "loop back" is what makes it a flywheel rather than a one-time certification.

### How the three levels compose

```
        ┌─────────────────── MACRO-LOOP (rhythm) ───────────────────┐
        │  Retrospect → Build capability → Improve → Readiness → ↻   │
        └────────┬───────────────────────────────────────┬──────────┘
                 │ each stage runs ↓ engines              │ each stage scores ↓
        ┌────────▼───────────────┐            ┌───────────▼─────────────────┐
        │ ENGINES (P0–P8)         │  measured  │ SCORECARD (4 dimensions)     │
        │ efficacy · promotion ·  │  against → │ usability · functionality ·  │
        │ decay · noise · split   │            │ adaptability · internal ctrl │
        └─────────────────────────┘            └──────────────────────────────┘
```

The engines DO the work; the macro-loop sets WHEN; the scorecard says WHETHER it counts as better.
A phase that improves an engine but doesn't move a scorecard dimension on the held-out split is motion
without progress — the loop should surface that, not reward it.

---

## 2. Standing Rule D (new — the shedding rule)

The current three Standing Rules (every change lands a gate change · baselines only fall · fixes
update ≥3 skills) all govern **growth**. A living system must shed as fast as it grows:

> **Rule D — Every validator must justify its existence or be retired.** It must have an origin
> (a bug it was born from, or a miner pattern), OR a true catch in the last N turns. A validator
> that has never fired and has no origin is dead weight: retire it (move to a `retired/` registry,
> keep the code for audit).

---

## 3. Phase overview (sequenced smallest-leverage-first)

| Phase | Track | Deliverable | Why this order | Honest % today |
|---|---|---|---|---|
| **P0** | — | This roadmap + `SELF_IMPROVING_GATE.md` principles | Write the model down before building | **30%** (this doc) |
| **P1** | A | **Efficacy ledger** (`gate_efficacy_ledger.json`) | The foundational sense organ — everything hangs off "which rules matter" | 0% |
| **P2** | A | **Promotion engine** in `flywheel_orchestrator.py` | Convert the scorer into a driver (make its own docstring true) | 0% |
| **P3** | A | **Decay/freshness detector** at G-1 | The #1 real rot vector (validator-lag) — catch it cheap | 0% |
| **P4** | A | **Noise quarantine** (classify "regression") | Make the orchestrator trustworthy so its signal is actionable | 0% |
| **P5** | A | **Retirement loop** (Rule D, ledger-driven) | Shedding — keep the gate lean/fast/credible | 0% |
| **P6** | B | **Held-out validation split** | SkillOpt's #1 idea; the anti-overfit foundation for Track B | 0% |
| **P7** | B | **Skill-edit accept/reject gate + `best_skill.md` + rejected buffer** | Make skill-file evolution rigorous instead of vibes | 0% |
| **P8** | B | **Epoch-wise meta-reflection** (helped/failed edit kinds) | Optional/advanced — improves the optimizer itself | 0% |

Recommended build order: **P0 → P1 → P2 → P3 → P4 → P6 → P7 → P5 → P8.** (P5 retirement waits
until P1's ledger has enough turns of history to retire safely.)

---

## 4. Phase detail

### P0 — Architecture-of-record `(this doc + SELF_IMPROVING_GATE.md)`
- **Goal:** one canonical statement of the four-property model, the two tracks, Rule D, and the
  honest north-star metric, linked from `UNIFIED_MEGA_GATE.md`.
- **Deliverables:** this file; a short principles section appended to `UNIFIED_MEGA_GATE.md` §v3.
- **Acceptance:** `UNIFIED_MEGA_GATE.md` links here; Rule D is in the Standing Rules list.
- **Persists via:** roadmap doc + memory entry.

### P1 — Efficacy ledger  `gate_efficacy_ledger.json`
- **Goal:** give the gate the sense it most lacks — *which of its own rules matter.*
- **Mechanism:** `run_platform_checks.py` appends, per validator per run:
  `{ id, origin: bug|miner|manual, first_seen_turn, last_run_turn, times_run, times_green,
  last_fired_turn, true_catches }`. A **true catch** = the validator went green→red on a turn where
  the red was caused by a real code change (not env-down/stale — see P4), and was then fixed. Start
  by recording green/red transitions; refine "true catch" attribution in P4.
- **Deliverables:** ledger writer hooked into the runner; `tools/gate_efficacy_report.py` (top
  catchers / never-fired / no-origin lists).
- **Acceptance:** after 10 turns, the report names the never-fired-no-origin validators (the
  retirement candidates for P5). Honest baseline of validator yield exists.
- **Persists via:** `gate_efficacy_ledger.json` (append-only, like `flywheel_state.json`).
- **Effort:** S–M. **Depends on:** nothing.

### P2 — Promotion engine  `flywheel_orchestrator.py`
- **Goal:** implement the PROMOTIONS the orchestrator already promises — turn the observer into a
  driver that moves rules **L-1 → L-1.5 → L0 → L2** on its own.
- **Mechanism:** when an L-1 miner pattern recurs ≥N turns, auto-draft an L-1.5 rule / L0 validator
  stub into a **promotion queue** (`promotion_queue.md`) for one-pass approval. When a new L0
  validator lands with no L2 sentinel, auto-draft a sentinel scenario into `sentinel_drafts.md`
  (the GS bridge, mechanized). The agent rituals become *"approve the queue,"* not *"discover from
  scratch."*
- **Deliverables:** `_compute_promotions()` in the orchestrator; `promotion_queue.md`.
- **Acceptance:** a recurring miner pattern produces a queued candidate without a human mining it;
  `/harden` and `/sentinel-review` consume the queue.
- **Persists via:** `flywheel_state.json` (promotion history) + `promotion_queue.md`.
- **Effort:** M. **Depends on:** P1 (queue ranks candidates by predicted efficacy).

### P3 — Decay / freshness detector  (extends G-1 auto-discovery)
- **Goal:** catch the #1 rot vector — a validator asserting a literal/shape the code already moved
  past — at the cheap layer, before a 13-min full-gate run does.
- **Mechanism:** for each grep/regex-literal validator, verify its asserted token still exists in
  its target file(s). When it doesn't (the `for (const entry of reorderChain(` case), flag
  **"asserting a shape the code moved past — refresh or retire."** Cross-reference the efficacy
  ledger: a never-fired validator whose target changed recently is a prime decay suspect.
- **Deliverables:** `validate_validator_freshness.py` (a meta-validator) registered at G-1.
- **Acceptance:** re-introducing any of the 3 session bugs (rename a target shape) trips it
  *standalone in <5s*, not at full-gate time.
- **Persists via:** its own baseline (Rule B applies to meta-validators too).
- **Effort:** M. **Depends on:** P1.

### P4 — Noise quarantine  (wraps the orchestrator's regression classifier)
- **Goal:** never let weather masquerade as rot. Classify every "regression" before scoring.
- **Mechanism:** before `flywheel_orchestrator` labels a baseline delta a regression, bucket it:
  `real` (baseline loosened by a code change) · `adoption-ratchet-miscounted` (the
  `envelope_return_shape 1→2` case — an increase that's an improvement) · `stale-report` (recompute
  the underlying validator, then recheck — the recurring Turn-3 lesson) · `env-down`
  (`httpx 10061` / Docker pipe missing → quarantine, don't score). Only `real` blocks/scores.
- **Deliverables:** `_classify_regression()` in the orchestrator; an `env_probe()` guard.
- **Acceptance:** a Docker-down run produces **0** false regressions; an adoption-floor increase is
  logged as a ratchet, not a regression; a stale report is auto-refreshed once before scoring.
- **Persists via:** `flywheel_state.json` (classification per regression).
- **Effort:** M. **Depends on:** P1 (true-catch attribution feeds off this).

### P5 — Retirement loop  (Rule D, ledger-driven)
- **Goal:** the shedding mechanism. Keep the gate lean, fast, and credible.
- **Mechanism:** `tools/gate_efficacy_report.py` lists never-fired-no-origin validators; a quarterly
  (or every-N-turn) pass proposes retirements into `promotion_queue.md` (reuse P2's queue, reverse
  direction). Retired validators move to a `retired/` registry — code kept, deregistered from the
  gate. Track gate runtime as a first-class metric so retirement has a visible payoff.
- **Deliverables:** retirement proposer; `retired/` registry; gate-runtime line in the turn report.
- **Acceptance:** at least the never-fired-no-origin set surfaces as retirement candidates; gate
  runtime is tracked turn-over-turn.
- **Persists via:** efficacy ledger + `retired/` registry.
- **Effort:** S. **Depends on:** P1 (≥N turns of history before retiring anything).

### P6 — Held-out validation split  (SkillOpt's core idea)
- **Goal:** stop overfitting the gate/skills to the same evidence used to declare success. A set the
  gate is **never allowed to tune against.**
- **Mechanism:** partition existing rollout evidence — L2 Playwright specs + the RAG/companion probe
  banks — into **train** (used to author rules/skill edits), **validation** (the accept/reject gate),
  and a **locked test** set (touched only for a periodic honest-score report). Lock the test split
  the way SkillOpt does (🔒 "locked until final report").
- **Deliverables:** `gate_eval_splits.json` (which probes/specs are train/val/test); a `--split`
  flag on the eval runners; a locked-test honesty report.
- **Acceptance:** a skill/validator edit can be accepted on validation and *separately* scored on the
  locked test; the test split is provably never used during authoring.
- **Persists via:** `gate_eval_splits.json` (frozen assignment, like a migration hash).
- **Effort:** M–L. **Depends on:** nothing (but most valuable after P1).

### P7 — Skill-edit accept/reject gate + `best_skill.md` + rejected buffer
- **Goal:** make `SKILL.md` evolution rigorous — the structure SkillOpt has and the hand-edit ritual
  lacks: **rollout → reflect → bounded edit → held-out gate → checkpoint → keep negatives.**
- **Mechanism:** when a session proposes skill edits (the current "write to QA/Frontend/…" ritual),
  run the relevant agent probes on the **validation split** with the edited skill vs the current
  one; **accept** only if it doesn't regress (→ update skill, snapshot prior to `best_skill/<skill>.md`
  checkpoint); **reject** → append to a `rejected_edit_buffer.md` that informs future proposals.
  Bound edits per session (an "edit budget," SkillOpt's LR) so skills don't thrash.
- **Deliverables:** `tools/skill_edit_gate.py`; `best_skill/` checkpoint dir; `rejected_edit_buffer.md`.
- **Acceptance:** a skill edit that *worsens* agent behaviour on the validation split is rejected and
  buffered, not silently committed.
- **Persists via:** `best_skill/` checkpoints + rejected buffer.
- **Effort:** L. **Depends on:** P6.

### P8 — Epoch-wise meta-reflection  (optional/advanced)
- **Goal:** improve the optimizer itself — learn *which kinds of edits help vs fail.*
- **Mechanism:** periodically diff prior-epoch vs current-epoch skill/validator sets on the same
  validation sample; bucket into improvements / regressions / persistent-failures / stable-successes
  (SkillOpt's epoch update); feed a short "edit-kind efficacy" note that biases future proposals
  (e.g. "ADD-rule edits to QA stick; REPLACE edits to Frontend get rejected 60% of the time").
- **Deliverables:** `tools/edit_kind_efficacy.py`; a meta note consumed by the skill-write ritual.
- **Acceptance:** the report names which edit kinds/skills have the best accept-rate over time.
- **Persists via:** efficacy ledger (extended with edit-kind dimension).
- **Effort:** M. **Depends on:** P1, P7. **Caution:** don't over-build the optimizer-of-the-optimizer
  for a solo/local loop — this is the steal-the-structure-not-the-apparatus line.

---

## 5. Per-layer: static → self-improving (what each phase adds where)

| Gate layer | Static today | Becomes self-improving via |
|---|---|---|
| **G-1.5 Substrate** | miners *report* into `substrate_manifest.json` | **P2** — recurring patterns auto-graduate into rule candidates |
| **G-1 Auto-discovery** | catches *new* surfaces | **P3** — also catches *aged* surfaces (decay); discovery becomes bidirectional |
| **G0 Guardian** | ratchets down, only grows | **P1 + P5** — efficacy ledger lets it *retire*, not just accrete |
| **GH Hardening (L2→L0)** | human ritual `/harden` | **P2** — G2 reds auto-emit hardening drafts; human approves the queue |
| **GS Sentinel (L0→L2)** | human ritual `/sentinel-review` | **P2** — new L0 validators auto-draft sentinel scenarios |
| **G2 E2E** | static suite | **P4 + P6** — reds classified (not noise); evidence split train/val/test |
| **Skill files (Track B)** | hand-edited on vibes | **P6 + P7 + P8** — held-out gate, checkpoints, negative buffer, edit-kind efficacy |

---

## 6. Guardrails / anti-patterns (do NOT)

- **Don't let the gate become its own maintenance burden.** More validators than features, gate
  slower than the build, false-positives that get `--no-verify`'d — that's rot in the other
  direction. P5 retirement + P4 noise-quarantine are the antibodies.
- **Don't optimize the theatre metric.** Topic-coverage will always look healthy first; the
  north-star is behavioural/check-coverage. The locked test split (P6) is what keeps the number honest.
- **Don't build the optimizer-of-the-optimizer (P8) before the basics.** Steal SkillOpt's *structure*,
  not its full K-minibatch/LR-schedule/meta apparatus — you're a solo human-in-the-loop flywheel,
  not an automated training run.
- **Don't auto-promote or auto-retire without one-pass human approval.** The engine *discovers and
  drafts*; the human *judges*. Keep the human on judgment, off discovery.

---

## 7. Definition of done (the whole roadmap)

The Mega Gate is self-improving when, **without a human mining or authoring from scratch**:
1. a recurring code-shape pattern becomes a queued rule candidate (P2),
2. a validator that no longer protects anything surfaces for retirement (P1+P5),
3. a validator asserting a stale shape is flagged before full-gate time (P3),
4. a "regression" is never a false alarm from weather/stale reports (P4),
5. a skill or validator edit is accepted only if it improves behaviour on data it wasn't tuned on
   (P6+P7),
6. the **4-axis scorecard** (usability · functionality · adaptability · internal control) rises
   turn-over-turn on the locked test split — with the historically-thin axes (usability behaviour,
   adaptability) closing fastest — while gate runtime does **not** grow, and
7. the **macro-loop runs unattended** — Retrospection → Capability Building → Continuous Improvement →
   Platform Readiness → ↻ — surfacing a ranked queue each turn, with the human only **approving and
   judging the forks**, never mining or authoring from scratch.

That last point is the whole goal: human attention moves entirely to judgment, which is exactly where
it is worth most.
