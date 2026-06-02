# Self-Improving Mega Gate — Roadmap

**Created:** 2026-06-01
**Status:** Architecture-of-record + phased plan (design only; no engine built yet)
**Companion docs:** [UNIFIED_MEGA_GATE.md](UNIFIED_MEGA_GATE.md) (the 6 gate layers), [SENTINEL_ARCHITECTURE.md](SENTINEL_ARCHITECTURE.md) (the two bridges), [COMPREHENSIVE_STUDY_FULLSTACK_GATE.md](COMPREHENSIVE_STUDY_FULLSTACK_GATE.md) (the 13×6 matrix)
**Engine today:** [tools/flywheel_orchestrator.py](tools/flywheel_orchestrator.py) — now a *driver*, not just an observer. **P1 (efficacy ledger) + P2 (promotion engine) are built.** Each turn it discovers + drafts a ranked `promotion_queue.md` (recurring L-1 miner patterns → rule candidates; load-bearing L0 validators → sentinel candidates), gated by `promotion_dispositions.json` (the human's one-pass approval). Its docstring is now true. **P3 (decay/freshness sense) is built** as `validate_validator_freshness.py` (a G-1 meta-validator): author-declared `FRESHNESS_ANCHORS` must still match their target file (FAIL), plus a ledger-cross-referenced decay-suspect census (INFO). **P4 (noise quarantine) is built**: `_classify_regression()` re-runs each flagged validator before scoring, so adoption-floor rises / stale reports / env-down are quarantined and only `real` regressions reach `L0_regressions` (what the board blocks on). **C1 (verdict contract) + P6 (held-out split) are built (2026-06-01):** the efficacy ledger tags every validator `{domain, dimension}` (`gate_efficacy_ledger.py` heuristic + `gate_domain_dimension_map.json` override + a per-domain/dimension scorecard in `report`), and `tools/gate_eval_splits.py` freezes the eval corpus (115 L2 specs + 18 companion probes + 18 golden eval fixtures = 151 units) into train/val/🔒locked-test in `gate_eval_splits.json` with a tamper-evident `test_seal`; `companion_rigorous_grader.py --split test` scores the locked set separately. **C2 (AI eval gate) is built (2026-06-01):** NEW `tools/ai_eval_gate.py` scores persisted eval results against a frozen golden on the locked-test split per `{domain,dimension}` (functionality/safety/cost) and **exits 1 on a locked-test regression** — the eval-based, paid-call-free regression gate on top of the existing `ai-eval-runner`/`ai_quality_log` LLM-judge framework.

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

## 1. The three tracks

- **Track A — Self-Improving Gate:** give the gate the four missing senses (efficacy, decay, noise
  classification, promotion) so it reshapes itself.
- **Track B — SkillOpt-style skill-doc optimization:** apply the same rigour to the `SKILL.md` files
  (and validator/baseline edits) — the three transferable ideas from the SkillOpt pipeline:
  **(i) held-out validation split, (ii) edit accept/reject gate + `best_skill.md` checkpoint +
  rejected-edit buffer, (iii) helped/failed efficacy ledger.**
- **Track C — Domain instantiation (one spine, three faces):** the same self-improving spine,
  instantiated as **distinct-but-interconnected** gates — **General · SaaS · AI** — each a rule/eval
  pack with its own reweighted scorecard, stitched at the seams by a meta-gate. Full design in §8.

They converge: Track A's efficacy ledger *is* Track B's "which edits helped" meta-signal, Track
B's held-out split *is* the validation rigour Track A's promotion gate needs, and Track C is what
both A and B run *across* — three domains sharing one engine and one ledger.

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
| **P1** | A | **Efficacy ledger** (`gate_efficacy_ledger.json`) | The foundational sense organ — everything hangs off "which rules matter" | **DONE** |
| **P2** | A | **Promotion engine** in `flywheel_orchestrator.py` | Convert the scorer into a driver (make its own docstring true) | **DONE** |
| **P3** | A | **Decay/freshness detector** at G-1 | The #1 real rot vector (validator-lag) — catch it cheap | **DONE** |
| **P4** | A | **Noise quarantine** (classify "regression") | Make the orchestrator trustworthy so its signal is actionable | **DONE** |
| **P5** | A | **Retirement loop** (Rule D, ledger-driven) | Shedding — keep the gate lean/fast/credible | 0% |
| **P6** | B | **Held-out validation split** | SkillOpt's #1 idea; the anti-overfit foundation for Track B | **DONE** |
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
- **✅ Status: BUILT (2026-06-01).** `_compute_promotions()` + queue writer live in
  `flywheel_orchestrator.py`; each turn writes `promotion_queue.md` and scaffolds
  `promotion_dispositions.json`. Two bridges, mechanized:
  - **L-1 → L0 (rule candidates):** mines `substrate_manifest.json` for outlier patterns in the
    promotable conformance band (0.80–0.995) or explicit anti-patterns; **recurrence-gated** (must
    recur ≥2 turns, tracked in `state.promotion_tracking`) so a one-off blip never queues; fuzzy-dedups
    against existing L0 baselines (skip-if-enforced + a soft "possibly already enforced by" hint);
    ranked by predicted yield (outlier count).
  - **L0 → L2 (sentinel candidates):** ledger-ranked (`true_catches·100 + times_fail·5 + min(base,20)`)
    load-bearing validators lacking a sentinel; emits paste-ready `check_*` stubs; defensive coverage
    parse with hyphen/underscore id-normalization (covered + infra excluded; "coverage unverified"
    label when the coverage map can't be parsed).
  - **Human-in-the-loop:** nothing auto-promotes; a key listed in `promotion_dispositions.json`
    (`approved|rejected|snoozed`) drops off the queue. The orchestrator never overwrites that file.
  - **Verified:** turn N tracks candidates below the gate; turn N+1 queues them (15 rule + 7 sentinel
    candidates on first real run). Tool stays exit-0 / best-effort (a promotion bug can't break a turn).

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
- **✅ Status: BUILT (2026-06-01).** `validate_validator_freshness.py` (root, registered G0/Platform
  as `validator-freshness`, `skip_if_fast=False`). Two tiers, chosen so the meta-gate can never emit a
  *false* FAIL (a noisy gate gets `--no-verify`'d — the rot P4 guards against):
  - **L1 — declared anchors (FAIL):** a validator opts in with a module-level
    `FRESHNESS_ANCHORS = [(target_file, regex, note), …]`. The meta-gate reads them via
    `ast.literal_eval` (never imports/executes the validator — keeps it ~0.5s) and checks each target
    exists AND the pattern still matches. A miss = "asserting a shape the code moved past — refresh or
    retire." Author-curated ⇒ zero false positives ⇒ safe to FAIL on. Regex with a plain-substring
    fallback for un-escapable patterns. **Seeded** on the two clean-fit incident validators:
    `validate_model_router.py` (3 anchors: `TASK_PROFILES`/`reorderChain`/loop `taskProfile`) +
    `validate_agent_memory_store.py` (3: shared-module import + `MEMORY_TYPES` + `PER_WORKER_CAP`).
  - **L2 — decay-suspect census (INFO, never FAIL):** the discovery half — a *never-fired* validator
    (per `gate_efficacy_ledger.json`) whose code-under-test (resolved from its `os.path.join`/path
    literals) has an mtime newer than the validator file itself. Gated on ledger maturity
    (`times_run ≥ 3`), so today it honestly surfaces **nothing** (ledger has 1 run) and sharpens as
    P1 accrues history. Ledger is keyed by gate-id → joined to the script filename via the registry.
  - **Verified:** renaming `reorderChain`→`reorderProviderChain` in `ai-chain.ts` trips L1 in **0.41s**,
    naming the exact stale anchor; restored cleanly. Self-coverage (registered + report-name match) and
    cp1252-guard both green on the new file; the 2 seeded validators still pass (anchors are inert
    constants). The `FRESHNESS_ANCHORS` declaration is the extensible surface — any validator can add
    anchors over time; the seed covers the known rot-prone ones.
  - **schema_coverage flavor deferred:** its decay was a *self-regex* (`RE_CREATE_VIEW` couldn't span
    `WITH (...) AS`), not a target-shape literal — a different anchor kind (validator-self-test). Noted
    as a P3 follow-on; the two seeded validators already satisfy the "any of the 3" acceptance.

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
- **✅ Status: BUILT (2026-06-01).** `_classify_regression()` + `_classify_regressions()` +
  `env_probe()` in `flywheel_orchestrator.py`. Every baseline-increase the naive `_diff_L0` flags is
  re-classified **before scoring** by *re-running the regressed validator* (the source of truth) and
  reading its exit code + refreshed count:
  - **real** — validator still FAILs at the new count (a violation ceiling genuinely loosened). The
    ONLY bucket kept in `turn_record["L0_regressions"]` — i.e. the only thing the canonical board's
    "Flywheel turns" gate blocks on.
  - **adoption-ratchet** — validator PASSes and the fresh count rose (an adoption FLOOR legitimately
    increased, e.g. `envelope_return_shape 1→2` when a new edge fn adopts the envelope). Quarantined.
  - **stale-report** — re-run shows the count back at `from` (the snapshot read a stale/half-written
    report); the re-run also *refreshes* that report. Quarantined.
  - **env-down** — re-run errored on a Docker/connection signature (`WinError 10061` /
    `dockerDesktopLinuxEngine` / `httpx.ConnectError`) or timed out. Quarantined.
  - **unknown** (no `validate_<name>.py` to re-run) → kept scored, *conservatively* (never silently
    drop a real regression); **infra-baseline** (`platform`) → not scored.
  - Quarantined deltas surface in a separate **🟡 Quarantined** block in the terminal + turn report
    with their class + reason — transparent, not hidden. Best-effort + isolated: a classifier bug
    falls back to scoring ALL regressions (fail-loud).
  - **Verified:** all 6 branches unit-tested (synthetic env-down + real-fail validators); end-to-end,
    a forced `envelope_return_shape 0→2` lands in Quarantined with `L0_regressions` EMPTY → board's
    Flywheel-turns gate reads 0 regression (the exact recurring phantom-block, now neutralized);
    `flywheel_state.json` restored; clean turn #64 → board green.

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
- **✅ Status: BUILT (2026-06-01).** `tools/gate_eval_splits.py` (4 subcommands: `build` /
  `report` / `verify` / `resolve`) + `gate_eval_splits.json`. Corpus = **115 L2 specs**
  (`tests/*.spec.ts`; RAG evals ride in as their journey specs) **+ 18 companion probes**
  (`companion_probe_bank.json` baseline+adversarial+held-out-templates) = 133 units, each
  tagged with the SAME C1 `{domain, dimension}` taxonomy (imported from `gate_efficacy_ledger`).
  - **Frozen like a migration hash:** split = a salted sha1(`SALT:kind:id`) % 100 bucket
    (train<60 / val<80 / 🔒test≥80). `build` PRESERVES existing assignments and only assigns
    NEW units, so the corpus grows without reshuffling and the locked set is stable. Verified:
    delete + rebuild reproduces the **identical** `test_seal` (`27189b6c…`).
  - **Tamper-evident locked test:** `test_seal` = sha256 over the sorted test-set ids. `verify`
    recomputes it and **exits 1 on drift** — silently moving a unit OUT of test to flatter a score
    is caught (verified: flipping one test spec → `LOCKED-TEST SEAL DRIFT`, exit 1). Legit corpus
    growth re-`build`s + commits the new seal (a git trail), same discipline as migration hashes.
  - **`--split` on a runner, paid-call-free:** `companion_rigorous_grader.py --split {train,val,test}`
    filters to a split's probe membership before scoring (default `all` = unchanged; non-breaking
    for the turn runner). `test` = the honest locked score. Held-out generated ids
    (`H02-safety-template-t5`) prefix-match their bank template id. `resolve --split train --kind spec`
    emits the membership list any runner consumes (e.g. `playwright test $(…)`).
  - **Not gate-wired yet (by design):** like P1's ledger, this ships as a standalone tool. Promoting
    `verify` to a G0 validator (so a locked-seal drift blocks the board) is the natural P6 follow-on.

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

---

## 8. Track C — Domain instantiation: one spine, three faces

The General Mega Gate is the *base*. The platform also needs gates tailored for the **Full-Stack
SaaS** domain and the **AI** domain — distinct, but interconnected. The failure mode to avoid is
building **three gates that fork and rot independently** (triple maintenance, conflicting verdicts, a
shared fix that lands in one and not the others). The correct shape is **one spine, three faces.**

```
                 ┌─────────── META-GATE (composition + seams) ───────────┐
                 │   rolls up 3 scorecards · guards the boundaries        │
                 └──────┬───────────────┬───────────────┬────────────────┘
         ┌──────────────▼──┐  ┌─────────▼────────┐  ┌───▼──────────────┐
         │  GENERAL gate   │  │   SaaS gate      │  │    AI gate       │
         │  (rule-pack)    │  │  (rule-pack)     │  │  (EVAL-pack)     │
         └──────────────┬──┘  └─────────┬────────┘  └───┬──────────────┘
                 ┌──────▼──────────────────▼───────────────▼──────┐
                 │  SHARED SPINE (the self-improving engine, P1–P8)│
                 │  efficacy ledger · promotion · decay · noise ·  │
                 │  macro-loop · scorecard · held-out splits       │
                 └─────────────────────────────────────────────────┘
```

- **One spine** = the P1–P8 engine. Built once, domain-agnostic.
- **Three packs** plug in, each with its **own reweighted scorecard** and **own verdict source**, but
  emitting the **same verdict shape** (`{id, status, elapsed, domain, dimension}`) into **one shared
  efficacy ledger** and **one promotion queue.**
- **Interconnection** = cross-gate promotion edges + a **meta-gate** that guards the seams. That is
  what makes them *distinct-but-interconnected* rather than three silos.

### Existing assets already map to all three
| Gate | Scope | You already have |
|---|---|---|
| **General** | cross-cutting invariants | the 330 G0 validators + canonical board |
| **SaaS** | tenant isolation, billing/entitlements, migrations, compliance, SLOs | multitenant/RLS validators, enterprise-compliance (audit logs, PDPA), marketplace, `RELEASE_GATE_*`, Grafana/Sentry MCPs |
| **AI** | evals, grounding, drift, cost, safety | companion/RAG flywheel probes, `ai-eval-runner`, `cost-log`, `provider-health`, held-out split (P6) |

Not three new things — **three faces of what's already built.**

### The scorecard reweights per domain (and AI gets two more axes)
| Dimension | General | SaaS | AI |
|---|---|---|---|
| Usability | ●● | ●● | ● |
| Functionality | ●●● | ●● | ●●● |
| Adaptability | ●● | ●●● (migrations) | ●● (model-swap) |
| Internal control | ●● | ●●● (isolation, compliance) | ●●● |
| **+ Safety/Trust** (AI) | — | ● | ●●● (hallucination, jailbreak, grounding, bias) |
| **+ Cost/Efficiency** (AI) | — | ● | ●●● (token cost, latency, provider fallback) |

### Eight design notes (what a naive "copy the gate 3×" would miss)
1. **The AI gate is eval-based, not assert-based** — a category difference. You don't assert
   "correct"; you **score against a golden set with a tolerance and track the delta** (LLM-as-judge +
   deterministic metrics). The held-out split (P6) is *optional* for General/SaaS but the **native
   unit** for AI. The companion/RAG probes are proto-evals — graduate them.
2. **AI degrades with zero code change** — drift (provider silently updates the model, data shifts,
   prompts rot). A change-triggered gate can't catch it → the AI gate must also run **on a clock**
   (Retrospection on a schedule) with a periodically-refreshed golden set.
3. **The gate must extend past the deploy line** — SaaS SLOs and AI quality live in production.
   Add **runtime fitness functions** (tenant-isolation canaries, SLO monitors, AI-drift + cost-anomaly
   alarms) on the Grafana/Sentry substrate. Pre-deploy static checks can't see a model that degraded
   overnight.
4. **The seams are the highest-risk, least-covered surface.** SaaS→AI calls, AI→tenant-data reads,
   billing→entitlement→AI-quota. A seam bug passes all three domain gates individually and breaks the
   composition → **consumer-driven contract tests** at each seam, owned by the meta-gate.
   **Per-domain green ≠ system green.**
5. **AI's non-code assets aren't versioned like schema is.** Prompts, model IDs, eval sets, skill
   docs are the "trainable" artifacts (the SkillOpt insight) — give them the **same baseline /
   version / rollback discipline** migrations already have.
6. **Two extra AI dimensions, named explicitly:** **Safety/Trust** (hallucination, injection/jailbreak
   resistance, grounding/citation, bias) and **Cost/Efficiency** (token cost, latency, provider
   fallback economics). Don't bury them inside the original four.
7. **A composition policy for conflicting verdicts.** When SaaS says "ship" and AI says "eval
   regressed 3%," the meta-gate decides by **blast radius** (AI-eval regression blocks an AI-feature
   deploy, not a CSS-only SaaS change).
8. **One efficacy ledger, tagged `{domain, dimension}`** — never three siloed ledgers. That preserves
   the cross-gate signal (an AI PII-leak finding promoting a SaaS security rule) and lets the
   scorecard rebalance globally.

### Prior art to borrow (you're reinventing named patterns)
- **Fitness functions / evolutionary architecture** (Neal Ford) — the whole gate is a fitness-function
  suite; the dimensions are its quality attributes; "compute fitness at deploy, roll back if not
  improving" is your macro-loop's readiness stage.
- **Eval harnesses** — promptfoo, OpenAI evals, ragas, deepeval, LangSmith (golden sets, LLM-as-judge,
  CI regression gates, Recall@k/MRR/NDCG, hallucination/cost/latency). The AI gate.
- **Policy-as-code** — OPA/Rego, conftest, Semgrep. The internal-control dimension.
- **Data contracts / expectations** — Great Expectations, dbt tests, Soda. The SaaS data layer.

### Track C phases (layered on the spine; P1–P8 unchanged)
| Phase | Goal | Acceptance |
|---|---|---|
| **C1** ✅ **DONE** | Verdict contract + tag the efficacy ledger with `{domain, dimension}` (small extension of P1) | every validator/eval emits a domain+dimension tag; the ledger reports per-domain — **built 2026-06-01** alongside P6 (shared taxonomy in `gate_efficacy_ledger.classify_domain_dimension`; 348 validators tagged general 219 / saas 48 / ai 81; `gate_domain_dimension_map.json` override + `reclassify` command). C2 (AI eval gate) now unblocked. |
| **C2** ✅ **DONE** | Stand up the **AI eval gate** as a real harness — golden sets + LLM-as-judge + regression deltas + cost/latency; add Safety + Cost dimensions | an AI eval regression (vs golden set) is detected with a delta + blocks the AI-feature path — **built 2026-06-01**: NEW `tools/ai_eval_gate.py` scores persisted eval results vs a frozen golden on the 🔒locked-test split per `{domain,dimension}`, surfaces functionality/safety/cost deltas, and **exits 1 on a locked-test regression** (verified: a regressed run trips functionality+safety+cost and BLOCKS; clean run exits 0; degrades to SKIP without data). Reuses the existing LLM-judge framework (`ai-eval-runner` cron writes `ai_quality_log`; `evals/canonical_questions.json` golden fixtures now in the P6 split). Offline/paid-call-free to run+verify. |
| **C3** Phase 1 ✅ **DONE** / Phase 2 pending | **Scheduled + runtime fitness functions** (drift, SLO, cost anomaly) via Grafana/Sentry | the AI gate runs on a clock and flags drift with no code change; a SaaS SLO breach surfaces a finding — **Phase 1 built 2026-06-03** (commit `aa4be10`): `validate_ai_eval_regression.py` thin-wraps `tools/ai_eval_gate.py gate` and runs at G0/Platform (352 validators). Degrade-to-SKIP semantics preserved end-to-end (no baseline / no fresh results = exit 0 with explanatory message; locked-test regression = exit 1). Mirrors P1/P6/C5's standalone-tool-first → G0-promotion-second pattern. **Phase 2 pending** = the "clock + prod" half: run the same locked-test policy continuously off `ai_quality_log` in production (Grafana drift alarm + Sentry release-gate finding). Needs edge-fn deploy — deferred until user OKs the deploy step. |
| **C4** Phase 1 ✅ + Phase 2a ✅ + Phase 2b ✅ + Phase 2c ✅ **DONE** / Phase 2d (verdict override) deferred | **Seam contract tests + the meta-gate** (composition policy + boundary guards) | a seam bug (SaaS→AI / AI→tenant data) is caught even when both domain gates are green — **Phase 1 built 2026-06-03** (commit `c86ecf8`): catalog layer in `tools/mine_ai_seams.py` + `ai_seams_catalog.json` (118 seams: 15 saas→ai · 1 ai→ai · 74 ai→tenant · 28 ai→quota; 33 AI fns hardcoded). Heuristic broadened mid-build after initial 0 ai→tenant — real hive-scoped tables are `v_*_truth` / `voice_*` / `canonical_*` / `agentic_rag_*` / `agent_*`. `validate_ai_seams_inventory.py` ratchets the inventory forward-only. **Phase 2a built 2026-06-03** (commit `4f79f37`): contract-coverage ratchet. NEW `ai_seam_contracts.json` (sidecar `seam_id → test path`) read by the miner to attach a `contract_test:` field on every seam. NEW `validate_ai_seam_coverage.py` (G0/Platform, 354th validator) is forward-only on the uncovered count — gap rises = FAIL with two-option fix (wire a contract OR explicitly raise floor); gap drops = baseline auto-lowers. Floor today = 118 uncovered (every seam); pays down to 0 as Phase 2a payoff work wires contracts. Verified all three branches: first-run seeds (118), synthetic wire 118→117 (auto-lower), revert 117→118 (FAIL with fix), restore. **Phase 2b built 2026-06-03** (commit `4592687`): NEW `tools/meta_gate.py` (`decide` + `policy`). Offline + read-only — reads `gate_efficacy_ledger.json` (C1: 219 general / 48 saas / 81 ai), `ai_seams_catalog.json`, `ai_asset_baseline.json`, and `git diff <base>..<head>`. Composition policy: (1) general FAIL always blocks (no override), (2) saas FAIL blocks only on saas blast radius, (3) ai FAIL blocks only on ai blast radius **with seam-sharpening** — when every touched saas→ai seam has a `contract_test`, the ai FAIL downgrades to warn-only (this gives Phase 2a's coverage ratchet teeth: each wired contract converts ai FAILs from block to warn on PRs touching only verified seams). Verified 5 scenarios end-to-end (synthetic ai FAIL injected into ledger copy then restored): (A) CSS-only → SHIP warn-only, (B) ai-fn touched → BLOCK, (C) AI asset touched → BLOCK, (D) assistant.html seam uncovered → BLOCK naming touched seam, (E) same diff with contract wired → SHIP via seam-sharpening downgrade. **Phase 2c built 2026-06-03** (commit `f553f54`): NEW `validate_meta_gate.py` thin wrapper at G0/Platform (355th validator). **Honest framing required mid-build** — the meta-gate's composition policy is strictly MORE PERMISSIVE than the monolithic gate (it converts FAILs to warn-only via blast-radius + seam-sharpening, never ADDS blocks), so promoting it as a hard-blocker would be a no-op for ship/block. The honest promotion is **observation-mode**: clamp the meta-gate's exit 1 → 0, surface the would-have-blocked reasoning as a NOTE in the gate log, and append a structured decision line to `meta_gate_decisions.jsonl` every gate run. That jsonl IS the macro-loop input P2's promotion engine will later mine — exact analogue of P1's efficacy ledger for individual validators ("observer first, driver later"). Architect SKILL captured the rule: when promoting a more-permissive tool, don't manufacture a fake assertion — recording IS the value. Phase 2d (deferred) = flip semantics so the meta-gate's verdicts OVERRIDE the monolithic gate (a deliberate architectural choice, not a side effect of promotion). |
| **C5** ✅ **DONE** | **Version/baseline the AI assets** (prompts, model IDs, eval sets, skill docs) like migrations | a prompt/model change carries a versioned baseline + rollback, gated like a schema change — **built 2026-06-02**: NEW `tools/ai_asset_baseline.py` (manifest of 5 assets × `build/verify/report` commands) + `validate_ai_asset_versioning.py` (G0/Platform, 351st validator). Each asset declares a content version (`_meta.ai_asset_version` for JSON, `// AI_ASSET_VERSION:` marker for TS) + sha256 recorded in `ai_asset_baseline.json`. Policy: hash moved + version unchanged = silent-change FAIL; version up + hash unchanged = no-op-bump FAIL; version down = downgrade FAIL; both move together = record + PASS. Optional assets (e.g. `ai_eval_baseline.json` until first real run) skip cleanly. Verified positive (exit 0 on clean state) + negative (mutated canonical_questions.json without bumping → exit 1 naming the offender + emitting fix instruction; reverted). Bug caught: TS marker regex needed `\r?$` for Windows CRLF files (persona.ts LF matched, ai-chain.ts CRLF silently didn't — lesson written to devops + qa skills). |

**Recommended order:** C1 → C2 → C5 → C3 → C4. (C2 is the highest-value/most-different piece; C1 is a
tiny prerequisite; C5 protects the assets C2 depends on; C3/C4 extend past deploy and across seams.)
**C1 ✅ + C2 ✅ + C5 ✅ + C3 Phase 1 ✅ + C4 Phase 1 ✅ + C4 Phase 2a ✅ + C4 Phase 2b ✅ +
C4 Phase 2c ✅ DONE.** C4 Phase 2c (commit `f553f54`) shipped the meta-gate as an observation-
mode recorder at G0 (355 validators). Track C local work is COMPLETE — **7 of 8 sub-phases live
across 6 in-session shipments today**. Remaining: **C3 Phase 2** (clock + prod off
`ai_quality_log` via Grafana/Sentry — only deploy-gated item left) and a deferred **C4 Phase 2d**
(flip meta-gate to override the monolithic gate — a deliberate architectural choice, not yet
worth doing). Spine engines P0–P4 + P6 untouched.

### Definition of done (Track C)
Three domain gates run off one spine and one ledger; the AI gate scores against held-out goldens on a
clock and in production; the meta-gate catches seam failures the per-domain gates miss and resolves
conflicting verdicts by blast radius; and a single tagged scorecard shows where each domain is weak so
the loop rebalances **across** domains, not just within one.
