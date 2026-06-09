# Companion Dev Tool — the AI Companion's Mega Gate

> **Hub doc.** Single source of truth for the **AI Companion Developer Tool**: one front
> door that develops, evaluates, and self-improves the WorkHive AI companion, structured
> as a **self-improving closed loop** modeled on the platform's **Unified Mega Gate**
> (`release_gate.py` + the 7-layer tester panel).
>
> Status: **Phase A + Phase B BUILT + MCP-verified (2026-06-09).** `tools/companion_dev.py`
> engine (mega PASS end to end) + a Companion Gate cockpit pane in the tester panel (all cards
> stream real jobs via SSE, no dead buttons). The full self-improving loop was exercised live
> (mine → harvest → cockpit reflects → dispose → promote, never locked-test). Created 2026-06-09. Owner: Ian.
> Related: [AI_SURFACE_MAP.md](AI_SURFACE_MAP.md) (Phase 8 hub), the Mega Gate
> ([release_gate.py](release_gate.py)), the 7-layer tester panel
> ([test-data-seeder/templates/index.html](test-data-seeder/templates/index.html)).

---

## 0. Why this exists

The companion's development capability today is **scattered** across ~10 Python tools, the
golden-capture Playwright specs, the live battery JS, and a read-only Phase-8 panel in
founder-console. Ian's directive: make it **"solely my AI Companion Developer Tool"** —
**one** front door, shaped like the **Unified Mega Gate**, running as a **self-improving
closed loop**.

The insight: the Mega Gate is a machine that (1) **mines** raw material, (2) **auto-discovers**
everything that must be checked, (3) **ratchets** forward-only gates, and (4) turns every
finding into a **new check** so the loop tightens itself. The Companion Dev Tool is **the
same machine pointed at the AI's behaviour** instead of the platform's code:

| Mega Gate (platform code) | Companion Dev Tool (AI behaviour) |
|---|---|
| Miners extract code/DB facts | **Live thumbs** (`ai_reply_feedback`) + live observables are the mine |
| Validators are the checks | **Golden sets + graders** per dimension are the checks |
| Forward-only baselines ratchet | **Locked-test split + per-dim baselines** ratchet (anti-overfit spine) |
| Sentinel/harden turns a bug into a validator | **Harvest** turns a thumbs-down into a golden candidate |

**~80% already exists** (Phase 8, see §4). This work *arranges* those parts into the
Mega-Gate shape behind one entrypoint — it is mostly orchestration + two small new pieces,
not a rebuild.

---

## 1. Layer mapping — Mega Gate → Companion Dev Tool

The Mega Gate runs 7 layers (G-1.5 Substrate → G-1 Auto-discovery → G0 Static → G1 Data →
G2 UI/Journeys → G3 UFAI Battery → Mega orchestration). The companion mirrors each:

| # | Mega Gate layer | Companion analog | Reuse / Build |
|---|---|---|---|
| **G-1.5** | **Substrate** (9 miners → `substrate_manifest.json`) | **Harvest substrate** — `companion_harvest.py` mines live thumbs-down + live observables (`companion_battery.js`: `model_chain` / `agent_memory` / `cited[]`) → `companion_substrate_manifest.json` | harvest ✅ · manifest 🔨 |
| **G-1** | **Auto-discovery** (333 validators) | **Dimension + golden discovery** — enumerate every dim (agent/rag/memory/persona/safety/cost), its golden set, grader, baseline; FAIL if any dim is orphaned/un-evaluated | partial (scorecard registry) 🔨 |
| **G0** | **Static** (`run_platform_checks --fast`, forward-only) | **Eval gate** — `ai_eval_gate.py companion-gate`: per-dim locked-test %, **n-aware blocking** (auto-enforces at n≥20 = ceil(100/tol)), forward-only baselines | ✅ |
| **G1** | **Data** (seeded correctness) | **Golden capture** — `tests/*-golden-capture.spec.ts` live runs → normalized graded observations | ✅ |
| **G2** | **UI / Journeys** (L2/L3) | **Live stack battery** — `companion_battery.js` / `__CSB` grades Agent·Memory·RAG·Safety on grounded observables | ✅ |
| **G3** | **UFAI Battery** (forward-only ratchet) | **Optimize / measured A-B** — `companion_optimize.py` GEPA reflect→propose→(opt-in) measured A/B, accept iff val↑ **and** locked-test holds | ✅ |
| **Mega** | **Orchestration** (`.last-gate-pass`, persist run) | **`companion_dev.py mega`** — runs all layers, writes `.last-companion-gate-pass`, persists run + scorecard snapshot | 🔨 |

Legend: ✅ exists · 🔨 to build · partial = exists but needs a thin wrapper.

---

## 2. The single front door — `tools/companion_dev.py`

Mirrors `release_gate.py`'s shape: one `mega` runs the pipeline; per-layer subcommands run
a slice. Everything is **$0** offline except `eval`/`optimize --ab` (live LLM calls).

```
python tools/companion_dev.py status         # scorecard + harvest queue + last A/B, one glance
python tools/companion_dev.py substrate       # G-1.5  harvest live signals + observables → manifest
python tools/companion_dev.py discover        # G-1    enumerate dims/golden/graders, flag orphans
python tools/companion_dev.py harvest         #        thumbs-down → candidates (human-disposed)
python tools/companion_dev.py dispose         #        triage queue (accept→dim / reject)
python tools/companion_dev.py eval [--dim D]    # G1+G2  grader self-tests ($0); --live = capture
python tools/companion_dev.py optimize          # G3     reflect → propose (measured A/B stays manual)
python tools/companion_dev.py gate              # G0     per-dim locked-test, n-aware, forward-only
python tools/companion_dev.py mega [--live] [--propose]  # run the whole loop, write pass marker + persist
python tools/companion_dev.py --self-test       # prove the orchestrator wiring (NO DB / NO model)
```

**Flag semantics (mirrors the Mega Gate's opt-in heavy phases):** `mega` default is the
**$0 offline closed loop** (substrate → discover → gate → graders self-test → scorecard verify
→ marker). `--live` adds capture instructions for the heavier G1/G2 live runs; `--propose`
adds the G3 reflect→propose arm. The **measured A/B** (which mutates a local edge fn + spends
LLM calls) is never automatic — run `companion_optimize.py ab` deliberately.

Design rules (carried from `release_gate.py`):
- The scattered `companion_*.py` tools **stay runnable** but `companion_dev.py` is **THE
  front door** — it imports/shell-calls them; it does not duplicate their logic.
- `mega` is the closed-loop runner; each layer returns `(ok, result)`; one FAIL blocks and
  prints a per-layer PASS/FAIL summary, exactly like the gate.
- `--self-test` proves the orchestrator wiring with NO DB / NO model.

---

## 3. The self-improving closed loop

```
 live thumbs (ai_reply_feedback)
        │  G-1.5 substrate / harvest
        ▼
   candidates ──dispose──► golden sets grow (train/val; locked-test only by deliberate act)
        │  G-1 discover                     │
        ▼                                   ▼
   G1/G2 capture + grade + battery ──► G3 optimize (propose → A/B; accept iff val↑ & locked-test holds)
        │                                   │
        └──────► G0 gate (forward-only, n-aware) ──► better companion ──► new thumbs ──┐
                                                                                        └─(loop)
```

Each turn: the corpus grows, baselines ratchet up, and at **n≥20** a dim's gate flips
WARN→BLOCK **with no flag to flip** — the loop completes itself, like the Mega Gate's
forward-only ratchets + sentinel feedback.

---

## 4. Reuse vs Build — component inventory

**Already built (Phase 8 — reuse as internal modules):**
| Component | File | Role |
|---|---|---|
| Harvest (substrate source) | [tools/companion_harvest.py](tools/companion_harvest.py) | thumbs-down → human-disposed candidates; `harvest`/`report`/`promote`/`--self-test` |
| Live feedback sink | [supabase/migrations/20260609000006_ai_reply_feedback.sql](supabase/migrations/20260609000006_ai_reply_feedback.sql) | the mine: client-writable thumbs carrying the question |
| Optimizer (G3) | [tools/companion_optimize.py](tools/companion_optimize.py) | GEPA reflect→propose→measured A/B |
| Per-dim eval | tools/companion_{agent,rag,memory,persona}_eval.py | self-test + observed grading |
| Independent grader | [tools/companion_rigorous_grader.py](tools/companion_rigorous_grader.py) | no-judge, no-companion-import graders |
| Gate (G0) | [tools/ai_eval_gate.py](tools/ai_eval_gate.py) | `companion-baseline` / `companion-gate`, n-aware |
| Splits + seal | [tools/gate_eval_splits.py](tools/gate_eval_splits.py) | train/val/locked-test + tamper seal |
| Scorecard registry | [companion_eval_scorecard.json](companion_eval_scorecard.json) + tools/companion_eval_scorecard.py | per-dim metric/grader/baseline/status |
| Live stack battery (G2) | [companion_battery.js](companion_battery.js) + [companion_stack_rubric.json](companion_stack_rubric.json) | Agent·Memory·RAG·Safety observables |
| Golden capture (G1) | tests/{agent,rag,memory,persona}-golden-capture.spec.ts | live capture through ai-gateway |
| Golden sets | companion_{agent,rag,memory,persona}_golden.json | the checks |
| Read-only dashboard | founder-console.html (Phase 8 panel) | 6-dim scorecard view |

**Built in Phase A (2026-06-09) ✅:**
| Component | What | Layer |
|---|---|---|
| [tools/companion_dev.py](tools/companion_dev.py) | the front door + `mega` closed-loop runner + `status` + `--self-test` | Mega |
| `companion_substrate_manifest.json` + `build_substrate_manifest()` | aggregate golden corpus + harvest counts + observable coverage + optimization state into one manifest | G-1.5 |
| `discover_check()` coverage check | enumerate dims↔golden↔grader↔baseline; FAIL on orphan (+ catches orphan golden files on disk) | G-1 |
| `.last-companion-gate-pass` + `companion_dev_runs.jsonl` | pass marker + append-only run log (mirror `.last-gate-pass`; both gitignored) | Mega |

Verified: `--self-test` PASS (tools resolve, scorecard well-formed, manifest builds, discover passes the repo + catches a synthetic orphan, n-aware math correct); `mega` PASS end to end (substrate · discover · gate · 4 graders self-test oracle-pass/blind-fail · scorecard verify); `status` renders the live 6-dim dashboard.

---

## 5. Anti-overfit guarantees (non-negotiable, from both systems)

- **Locked-test split + `test_seal` is the spine.** Harvest grows train/val only; the tool
  **never** auto-writes a golden file and **never** assigns the locked-test split.
- **Forward-only baselines** — a regression exits 1 (like `.last-gate-pass`).
- **Graders import no companion code**; deterministic-first, LLM-judge sparingly with a
  deterministic backstop; every grader proven against a BLIND oracle (rubber-stamp fails).
- **n-aware blocking** — a dim only BLOCKS once its locked-test n≥20, so noise on a tiny
  split can't hard-fail the loop.

---

## 6. Build phases (each gate-green, reversible, $0-first)

- **Phase A — the engine. ✅ BUILT 2026-06-09.** `tools/companion_dev.py`: `status` + `mega`
  + thin wrappers over the existing tools (the "one front door"); `companion_substrate_manifest.json`
  (G-1.5), the `discover` coverage check (G-1), and `.last-companion-gate-pass` + `companion_dev_runs.jsonl`
  run persistence. `mega` PASS end to end, `--self-test` green.
- **Phase B — web cockpit. ✅ BUILT + MCP-verified 2026-06-09.** A "🤖 AI Companion Dev Tool"
  pane in the tester panel ([test-data-seeder/templates/index.html](test-data-seeder/templates/index.html))
  with layer chips + cards (Status / Substrate / Discover / Gate / Eval / Optimize / Mega),
  driven by a generic `/api/companion/<layer>` SSE route in
  [test-data-seeder/app.py](test-data-seeder/app.py) (`_companion_job` → `_run_root_cmd` →
  `companion_dev.py <subcmd>`). The pane lives in the **Run Tests** sidebar pane. Verified live
  via Playwright MCP: Status/Mega/Optimize/Substrate cards all stream real jobs (Mega → PASS),
  no dead buttons; after a harvest the Status card's queue updated `none yet → 2 pending`.
  **GOTCHA:** new Flask routes need a manual server restart (`debug=True, use_reloader=False`)
  — GET on the POST-only route returns 404 until restart, 405 after.

---

## 7. Status / changelog

- **2026-06-09** — Plan agreed (this doc). Feedback-loop foundation shipped (the substrate
  source): `ai_reply_feedback` table + thumbs on all 3 typed surfaces (floating launcher,
  voice bubble, Chat tab) + `companion_harvest.py` + ai-quality.html repointed to read real
  thumbs.
- **2026-06-09 — Phase A BUILT + verified.** `tools/companion_dev.py` (status/substrate/
  discover/harvest/dispose/eval/optimize/gate/mega/--self-test). `mega` PASS end to end;
  `--self-test` green.
- **2026-06-09 — Phase B BUILT + MCP-verified.** Companion Gate cockpit pane (Run Tests pane)
  + `/api/companion/<layer>` SSE routes. All cards stream real jobs (Mega → PASS), no dead
  buttons. **Self-improving loop exercised live end to end:** seeded 2 thumbs-down →
  `harvest` (correctly routed asset-brain→rag, "remember…"→memory) → cockpit Status queue
  `none yet → 2 pending` → disposed 1 accepted → `promote` → staging skeleton marked
  `train_or_val_ONLY`/`_needs_labeling` (never locked-test) → cleaned up to baseline. All
  **local/uncommitted, deploy-PENDING**.
- **2026-06-10 — `--live` capture DONE + first real companion bug FIXED + domain/robustness ACTIVE.**
  New headless `tools/companion_live_capture.py` (anon `voice-journal` POST + psycopg2 counter reset +
  `.data.answer` unwrap — the no-browser twin of the golden-capture specs) captured all 4 new families
  **0/21 rate-limited**. Honest first scores (domain 3/6, robustness 4/7, doctrine 1/5, safety-gaps 0/3)
  → legit grader calibration (real-phrasing synonyms; oracle-all/blind-0 self-test still discriminates;
  `SEC-E2` anti-marker "ignore safety" was a quoted-attack FALSE-positive). Found + FIXED **DOC-H4**: the
  companion invented paid "Pro/premium plans" on a FREE platform because the prompt had **no pricing
  doctrine** — new `WORKHIVE_DOCTRINE` block in `_shared/persona.ts` (+ a grounding rule in
  `voice-journal-agent` for the DB-less surface; `AI_ASSET_VERSION` 1→2; `_shared` edit needs an
  edge-runtime restart); doctrine 1/5→**5/5**. Froze `domain` (🔒100% n=1) + `robustness` (🔒50% n=2)
  on the locked-test split, wired both into `gate_eval_splits.py` (new KINDS + enumerators), flipped
  pending→active. `mega` PASS, **8/8 dims active**. All local/uncommitted, deploy-PENDING. See §9 +
  memory `project_companion_live_capture_2026_06_10`.
- **2026-06-10 — §9 #2 perturbation-invariance generator BUILT + verified (`tools/companion_perturb.py`).**
  Write ONE golden Q → auto-spawn ~6 distinct surface variants (casing / STT-typo that SKIPS marker
  tokens / filler / distractor / clause-reorder / Taglish-wrap / Cebuano-wrap) → run seed + variants
  LIVE and require the SAME verdict; **invariance %** = the generalization score. Reuses
  `companion_live_capture` (runtime) + `grade_markers_unit` (verdict) — no new grader. `--self-test`
  (default, offline) proves the generator emits intent-preserving variants AND the metric DISCRIMINATES
  a simulated generalizer (100%) from a memorizer (0%); **green on all 4 families** (21 seeds → 135
  variants, ~6.4/seed). `--samples K` (§9 #4 rider) multi-samples each call + reports run-to-run
  VARIANCE. **Live smoke (safety_gaps):** SEC-E2 stable (71%); SEC-E5 *consistently* FAILs (inv 100% /
  pass 0% — a flat correctness gap, NOT a robustness one — the metric separates "wrong everywhere" from
  "brittle to phrasing"); SEC-E7 flagged **brittle + `noisy`** under `--samples 3` (verdict flips
  run-to-run on the SAME input → the harmful-LOTO refusal is not reliably produced; exactly the §9 #4
  de-noise case). Local/uncommitted at build time.
- **NEXT (when desired):** confirm SEC-E5 (flat gap) + SEC-E7 (noisy refusal) with a doctrine line, then
  re-freeze; run `--live` perturb across all families with `--samples 3` to harvest stable PASS variants
  (`--emit` → `.tmp/companion_perturb_candidates.json`, train/val ONLY, never locked-test) toward the
  n≥20 gate threshold; add §9 #3 (train−locked_test gap column) to `companion_dev.py status`; wire
  `companion_perturb --self-test` into the mega gate; ROB-F4/F5 + DOM-G2/G4 remain optimization targets.

---

## 8. Open questions / decisions log

- **Phase B form** — confirm whether the web cockpit is wanted now or after Phase A proves out (Ian leaned "same structure as the Mega Gate," which has both CLI + panel).
- **Deploy posture** — the whole loop runs LOCALLY (capture/optimize via local Supabase + edge runtime). Deploy is only ever "go live," never "to verify" (per [[feedback_local_runtime_verify_no_deploy]]).

---

## 9. Grokking-informed practices (2026-06-10)

Source: a session discussion of **grokking** — delayed generalization (Power et al. 2022,
[arXiv:2201.02177](https://arxiv.org/abs/2201.02177); Nanda et al. mechanistic-interpretability
follow-up, arXiv:2301.05217; Grokfast [arXiv:2405.20233](https://arxiv.org/pdf/2405.20233),
repo `ironjr/grokfast`).

**The honest reframe.** Grokking is a **training-time / weights** phenomenon (train accuracy
saturates early while held-out accuracy stays at chance, then *suddenly* generalizes as weight
decay drives the net off the memorizing solution onto the rule). Our companion is a **frozen API
model** (Groq `llama-4-scout`) — we do **not** train its weights, so we cannot "induce grokking"
in it. Chasing that would be a category error.

**Why the principle still steers us.** The generalization is already paid for by the foundation
model's pretraining — that is *why* we don't enumerate a million scenarios. Our job is to supply
the few things it can't know (**principles/doctrine + grounding**) and then **measure
generalization** the way grokking taught us to: on **held-out / perturbed / multi-sampled**
inputs, never on the data we authored against. This is the philosophy of the whole tool, and it
answers the standing constraint *"millions of scenarios, no time to hand-write them."*

**The boundary that must stay honest** (WAT): deterministic CODE for anything that must be exact
(numbers from `v_*_truth`, safety steps, hive isolation) = *good* memorization that must never
hallucinate; LLM + doctrine for the open-ended. Today's `DOC-H4` / KPI-fabrication bug was a
**misplaced boundary** — `voice-journal` was told to "quote KPIs verbatim" but had no DB access,
so it fabricated. The fix moved the boundary ("you can't see records here — don't invent them").

| # | Grokking principle | Companion-dev practice | Status |
|---|---|---|---|
| 1 | Train acc lied; held-out told the truth | **Locked-test pass-rate is THE number**; train/val are diagnostics; never tune the prompt against locked-test | ✅ have (`gate_eval_splits`) |
| 2 | A memorizer fails on rephrased inputs | **Perturbation-invariance generator** — write ONE golden Q, auto-spawn k variants (typo/Taglish/Cebuano/distractor/reorder), require the SAME verdict; "invariance %" = the generalization score. Scales the corpus multiplicatively FROM PRINCIPLES (the answer to "millions of scenarios") | ✅ **BUILT** `tools/companion_perturb.py` (self-test green ×4 fams; live smoke caught SEC-E7 noisy refusal) |
| 3 | The signal is the train–test GAP closing | Track `train_pass − locked_test_pass` per dim as an **overfitting gauge**; flag a large gap | 🔨 cheap — a column in `status` |
| 4 | One good measurement ≠ understanding | **Multi-sample the locked-test** (k=3–5/unit), gate on worst-case/majority, report per-unit variance (high variance = not robustly learned). De-noises the `ROB-F6` flip we hit | ✅ **BUILT** `--samples K` + `--gate worst\|majority` in `companion_perturb.py` (caught SEC-E7 noisy) |
| 5 | Generalization found by looking INSIDE (circuits) | Can't see weights, but grade the **process**: `model_chain` / `cited[]` / `agent_memory`. Right-answer-wrong-reason (grounded-but-uncited) is a memorization smell — grade faithfulness, not just correctness | ✅ partial (RAG `cited[]`) → extend |
| 6 | Regularization drives the SIMPLEST rule | Our regularizer = a **principle-based, SHORT prompt**. Fix a failed probe with a general doctrine line, NOT a per-scenario patch (scenario rules in the prompt = overfitting the prompt). `DOC-H4` fix was the right shape: one doctrine line | ✅ process rule — make explicit |

**Build status:** #2 `tools/companion_perturb.py` (perturbation-invariance generator) ✅ **BUILT
2026-06-10** with #4 (`--samples`/`--gate`) folded in — it reuses `companion_live_capture.py` + the
marker graders, and its `--emit` writes PASSing variants as train/val candidates (NEVER locked-test)
toward the n≥20 gate threshold. Still queued: #3 (the train−locked_test gap column in
`companion_dev.py status`) and wiring `companion_perturb --self-test` into the mega gate.

**One place real grokking WOULD apply:** if we ever fine-tune a small open model (e.g. a LoRA on
maintenance Q&A to cut the Groq dependency), then weight decay + the train/val/test discipline +
Grokfast become directly usable on the weights.
