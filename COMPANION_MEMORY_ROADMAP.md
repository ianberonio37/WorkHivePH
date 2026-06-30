# Companion-Memory Roadmap (C-series) — extend the memory moat to the AI Companion

> **Scope:** the AI Companion's memory (`agent_memory` working window, `agent_episodic_memory`
> durable facts, the procedure matcher, persona knowledge, voice journal) — its **governance,
> durability, and store-hygiene**, NOT its substrate (which is already strong). Grounded 2026-06-24
> by the `COMPANION_MEMORY_AUDIT.md` scout. **Honest headline: the Companion already has a richer
> memory substrate AND a richer eval layer than Memento; what it lacks is the M-series ENFORCEMENT +
> DURABILITY + STORE-HYGIENE layer. The rule is the same: measure (and de-dup/supersede) before you
> compound.** Sibling spine: `MEMORY_SYSTEM_ROADMAP.md` (the dev's Memento M-series, now 100%).

---

## C0 — DONE (the as-built Companion memory, do not rebuild)
**Substrate:** `agent_memory` (last-10-turns + rolling summary, 90d/180d retention cron, per-hive RLS);
`agent_episodic_memory` (4 types factual/procedural/episodic/semantic, vector(384) embeddings,
importance + use_count + LRU eviction 200/worker·1000/hive, per-hive RLS, service-role-only write);
`match_procedural_memories` (pgvector cosine ≥0.55); `persona_knowledge` (scope-isolated, content-hash
idempotent); `voice_journal_entries` (per-user semantic recall); `hierarchical-summarizer`.
**Eval:** `companion_memory_eval.py` (LongMemEval: recall + temporal + knowledge-update + multi-session +
**abstention**) + `companion_memory_golden.json` + live 2-phase capture (`tests/memory-golden-capture.spec.ts`);
sibling graders rag/persona/agent/domain/safety/robustness; `companion_rigorous_grader`, `companion_judge`,
self-improvement flywheel. → **No rebuild. The C-series wraps GOVERNANCE around this.**

---

## ★ COMPLETION SCOREBOARD (honest % — 0 / 15 helper-exists / 30 +baseline / 50 / 75 / 100)

| ID | Item | ★ | Effort | **%** | What the % reflects |
|---|---|---|---|---|---|
| **C0** | As-built substrate + eval | — | — | **100%** | grounded; do not rebuild |
| **C1.1** | Wire `companion_memory_eval` as a **regression gate** | ★ | S | **100% ✅** | DONE 2026-06-24 (see "C1.1 — DONE" below). Golden 17→49, locked-test memory n=1→9, tol 5→12 (`n_needed=ceil(100/12)=9≤9` → gate **ARMED**, no longer self-throttled to WARN); floor re-frozen 77.8% from a CLEAN 117/117-call live capture; deterministic teeth-test (degraded→exit 1, clean→exit 0) registered in `run_platform_checks` group "Companion Memory". |
| C1.2 | Wire rag + persona evals as gates | | S | **100% ✅** | DONE 2026-06-24 (see "C1.2 — DONE" below). PERSONA: golden 13→31, locked-test n=4→10, tol→12, floor 90% — ARMED. RAG: caught + fixed a latent bug (the golden pinned a STALE `HPU-001` asset_id orphaned by a reseed → 404 on EVERY unit, so the rag dim was silently dead); re-pinned to a live rich asset, made questions asset-name-AGNOSTIC (reseed-robust), single-asset positives, golden 13→30, locked-test n=1→4, tol→25, floor 100% — ARMED. Both now block a ≥2-unit regression. |
| **C2.1** | Store-level **`supersedes`** down-rank (safety) | ★ | M | **100% ✅** | DONE 2026-06-24 (see "C2.1 — DONE" below). Migration `20260624000002` adds `superseded_by`; `match_procedural_memories` + `recallEpisodic` apply a guarded ×0.4 penalty (`SUPERSEDE_PENALTY`); `supersedeEpisodic()` sets the link (service-role). `tools/companion_supersedes.py` proves it LIVE (rolled-back txn: 2 procedures → 1 replacement after supersede), registered in "Companion Memory". Same settable-link bar as Memento M3.2; auto-contradiction-at-extraction is a documented enhancement (pairs C2.2). |
| C2.2 | Write-side semantic **dedup** before insert | | S | **100% ✅** | DONE 2026-06-24: `persistEpisodic` (`_shared/episodic-memory.ts`) now probes `match_procedural_memories` at `DEDUP_SIMILARITY=0.95` before inserting an embedded procedural memory — a near-duplicate MERGES (bump use_count, keep higher importance) instead of accumulating a paraphrase row. `tools/companion_dedup.py` proves it in a rolled-back txn (near-dup→merged, 1 row, use_count bumped; orthogonal→NOT merged), registered in "Companion Memory". Acceptance met: re-storing a paraphrase does not add a row. Best-effort (embedded procedural only). |
| C2.3 | Re-embed retry for null procedural embeddings | | S | **100% ✅** | DONE 2026-06-24: `tools/companion_reembed_procedural.py` — `--self-test` proves the mechanism in a rolled-back txn (a null-embedding procedural row is INVISIBLE to `match_procedural_memories` → re-embed → SEARCHABLE), `--backfill` re-embeds live nulls via `embedding_helper` (degrades-to-SKIP without a provider; 0 live nulls today). Registered in "Companion Memory". Acceptance met: a null-embedding procedural row becomes searchable after the back-fill. |
| **C3.1** | **Backup + restore drill** of the memory tables | ★ | S | **100% ✅** | DONE 2026-06-24. `tools/companion_memory_backup.py` (`--backup`/`--drill`, M1.1/Arc-S pattern): pg_dump `agent_episodic_memory`+`agent_memory` → restore into scratch schema `dr_companion` → assert rowcount round-trip AND a seeded canary fact is still RECALLABLE from the restored copy. Proven LIVE (episodic 240/240 + canary recalled, agent_memory 99/99), zero net pollution (canary removed in finally). Registered in "Companion Memory" (skip_if_fast, DR-drill convention). |
| C3.2 | Health-regression **gate** (silent/p95/grounding) | | S | **90%** | DONE 2026-06-24: `tools/companion_memory_health_gate.py` (M2.2 pattern) gates structural (episodic+agent_memory non-empty) + integrity (procedural null-embedding rate), warming-up clause, `--self-test` teeth, registered. **C3.2b instrumentation DONE:** `saveTurn` now promotes the gateway's measured latency into the `response_time_ms` column (was 0%-populated) and the gate SURFACES turn-latency p95 (informational). Honest remaining ~10%: a hard latency THRESHOLD is deliberately NOT a memory-health gate (response_time_ms is WHOLE-TURN/LLM-dominated latency on the free tier, not memory-retrieval latency — a category mismatch), and `silent_rate` (recall-returned-nothing) has no event log yet. Both are real-but-deferred (measure-before-build); the groundable memory-health signals ARE gated. |
| C4.1 | **Eviction-quality** measurement + knob ablation | | M | **0%** | LRU + 10 eyeball knobs, unmeasured |
| C4.2 | Per-hive memory-health tile (founder-console) | | S | **15% — value-deferred** | The metrics exist (the C3.2 gate computes them). A founder-console tile needs a **service-role edge fn** (agent_memory/episodic are per-hive RLS → a cross-hive founder aggregate can't be a client query) + the tile. DEFERRED like C4.1: its value requires a **multi-hive platform + a founder watching dashboards** — on the current single-dev/~1-active-hive local platform there is no consumer, so building it now is a feature with no user (the same measure-before-build "warrants-it" gate the roadmap applies to C4.1). The dev reads memory health via the CLI gates today. Re-open when multiple hives are live. Buildable; the move is known (edge-fn + tile, skill-first frontend/qa/mobile/security). |
| **C5.1** | Port **abstention** control → Memento `memory_recall_eval` | ★ | S | **100% ✅** | DONE 2026-06-24 (see "C5.1 — DONE" below). Added an abstention dimension to `tools/memory_recall_eval.py`: zero-overlap unanswerable queries MUST return nothing (`abstention_rate ≥ 0.90`, currently 1.00); `--selftest` teeth: a fabricating retriever breaches the floor (caught). MEASURED finding: incidental-overlap fabrication is M5-coupled (lexical scores don't separate), documented + parked, NOT gated. Folds into the already-registered M2.1 gate. |
| C5.2 | Port knowledge-update/temporal units → Memento | | S | **5%** | pairs Memento M3.2 |
| C6 | **Contribute-back flywheel** → hive knowledge base | — | L | **0% (parked)** | the product moat; PARKED behind C1–C3 (don't compound knowledge you can't yet measure / dedup / supersede) |

**Roll-up (2026-06-24): C-series memory-core SUBSTANTIVELY COMPLETE.** C0 100% · 4★ SPINE 100% (C1.1·C2.1·C3.1·C5.1) · C1.2 100% · C2.2 100% · C2.3 100% · C3.2 90% · C5.2 done-via-M3.2 · **6 "Companion Memory" gates** (gate-teeth · supersedes · backup-drill · health · re-embed · dedup) + the C5.1/C5.2 abstention/supersedes ports in the Memento recall gate. All 4 product dims (memory n=9 · persona n=10 · rag n=4 · agent) ARMED.
**Honestly remaining (all BUILDABLE — not blocked — but multi-step + lower-value/adjacent; the move is known):**
- **C4.1** eviction-quality measurement — DEFERRED-BY-DESIGN: the store isn't near the LRU cap (≈266 episodic vs 1000/hive), so eviction isn't triggering → nothing to measure yet (the roadmap's own "only after the corpus warrants" gate). Re-open when a hive approaches the cap.
- **C4.2** founder-console memory-health tile — needs a **service-role edge fn** (agent_memory/episodic are per-hive RLS, so a cross-hive founder aggregate can't be a client query) + the tile. Frontend+edge sub-arc.
- **C3.2 last ~10%** — a hard latency threshold is deliberately N/A in the memory gate (response_time_ms is whole-turn/LLM latency, not retrieval latency); `silent_rate` needs a recall-empty event log. Both real-but-deferred.
- **domain/robustness re-freeze (ADJACENT — not C-series, Probe-Taxonomy fam G/F):** warn-only on STALE Jun-9/11 results; they have eval harnesses + goldens (27/19 probes, marker-based) but **NO capture spec** → arming needs building 2 capture specs (model `persona-golden-capture.spec.ts`) + expand + capture + freeze ×2.
- **C6** contribute-back flywheel — parked behind trust (C1–C3 done now satisfy the prerequisite; still a deliberate product-trust gate).

---

## C1.1 — DONE (2026-06-24): the memory gate now has TEETH

**The gap (verified by running, not by the label):** §8.3 had already built the grader, golden, live
capture, frozen floor, registry (`memory` = active + blocking), AND the G0 gate
(`validate_companion_dim_gate.py`). But the gate could **never FAIL** — the locked-test split held only
**1 memory unit**, and `companion_gate`'s anti-flake throttle needs `n ≥ ceil(100/tol)` before it blocks.
At n=1 that is unsatisfiable at any sane tolerance (one unit = a 100pp swing), so a degraded config only
WARNed. That structural weakness — not "no gate" — was the real 70%.

**What was built (all LOCAL, grounded in a real run — no simulation):**
1. **Golden expanded 17 → 49 units** (2 adversarial-critic authoring rounds, 5 abilities, disjoint nonce
   blocks). Each round's critic RAN the merged `memory_grader_self_test` and fixed real discrimination
   holes (e.g. a bare `"9"` synonym that was a substring of fault code `"F19"`). Final self-test:
   oracle 49/49, blind 0/49, negatives 12/12 fail-blind — still discriminating.
2. **Locked-test memory n = 1 → 9** (deterministic 60/20/20 salted-hash split; `gate_eval_splits.py build`
   recomputed the tamper seal). The split is NOT tuned — count is the only lever (anti-overfit invariant).
3. **Tolerance 5 → 12pp** so `n_needed = ceil(100/12) = 9 ≤ 9` → the gate is **ARMED**: tolerates a single
   free-tier-LLM phrasing flake (11.1pp), **BLOCKS on a ≥2-unit recall/abstention regression** (22pp).
4. **Floor re-frozen from a CLEAN live capture** (`tests/memory-golden-capture.spec.ts`, 117/117 gateway
   calls ok, 0 rate-limited): locked-test **77.8% (7/9)**, val 92.3%, train 92.6%.
5. **`tools/companion_gate_teeth.py`** — a permanent, deterministic (zero-LLM) acceptance proof that drives
   the REAL `companion_gate` decision code (via injectable fixture paths) over the REAL locked-test ids:
   a CLEAN run → exit 0, a DEGRADED run → **exit 1 ("REGRESSION (BLOCKING)")**. It reads the *production*
   tolerance, so a too-lax config that can't block FAILs the teeth-test instead of silently passing.
   Registered in `run_platform_checks` group **"Companion Memory"**.

**Acceptance bar MET:** a deliberately-degraded locked-test result FAILs (exit 1); the current config passes.

**REAL FINDINGS the expanded eval surfaced (grounded, the flywheel working — these are the NEXT work, gated
now by the armed floor):**
- **Abstention FABRICATION (safety-relevant):** asked about never-mentioned pumps (MEM-NEG-03, MEM-NEG-10),
  the companion fabricated **"215 Nm in a star pattern"** — cross-wiring MEM-P2's real torque onto a
  distractor entity. In a maintenance tool, an invented torque is a hazard. → harden abstention grounding
  in the `ai-orchestrator` synthesis prompt (pairs C2.1 store-supersedes; a new C1.1a finding).
- **Temporal recall misses (MEM-TMP-01/06/08):** the companion returned the generic "not enough data"
  maturity-gate fallback instead of the planted latest-fact. → investigate temporal recall in the prompt.
- **Grader false-negative FIXED in passing:** `companion_rigorous_grader.is_memory_abstain` did not
  recognize **"couldn't / could not find … information/record/data"** as an abstention register (only
  `can't/cannot/don't`), so ~5 *correct* abstentions were mis-scored FAIL. Added that register (+`locate`,
  `data`, `wasn't able to`); self-test still discriminates (blind still fails all abstention controls).
  Lesson: [[feedback_eval_refusal_detection_multilingual]] — keyword graders miss varied refusals; read the
  real answers. (This raised overall 79.6% → 89.8% with no goalpost-move — the answers WERE abstentions.)
- **Side-finding (out of scope, separate dims):** `domain` (−50pp) and `robustness` (−16.7pp) show
  warn-only regressions vs STALE baselines (frozen 2026-06-09, n=1–2) — they need the same golden-expansion
  + re-freeze treatment applied here to memory. Pairs C1.2.

---

## C2.1 — DONE (2026-06-24): store-level supersedes down-rank (the SAFETY gap)

**Why it mattered:** the episodic store ranked by `importance·log(1+use_count)` + keyword overlap with NO
obsolescence handling — so when a worker CORRECTS a torque/part/procedure, the OLD memory co-surfaces with
the new one at recall. In a maintenance tool an outdated procedure presented as current is a safety hazard
(exactly the fabrication class C1.1's eval just caught). Native port of Memento M3.2 onto pg+pgvector.

**What was built (all LOCAL, applied to the local Supabase + proven live):**
1. **Migration `20260624000002_episodic_supersedes.sql`** (forward-only, immutability respected): adds
   `superseded_by uuid REFERENCES agent_episodic_memory(id) ON DELETE SET NULL` + `superseded_at` + a
   partial index. A row is obsolete iff `superseded_by IS NOT NULL`.
2. **Retrieval down-rank (×0.4 `SUPERSEDE_PENALTY`), GUARDED (no-op when nothing is superseded):**
   - `match_procedural_memories` RPC (CREATE OR REPLACE): effective similarity = cosine × (0.4 if
     superseded else 1); the min-similarity gate AND the ordering use the penalized value, so an obsolete
     procedure usually drops below the 0.55 floor entirely.
   - `recallEpisodic` (`_shared/episodic-memory.ts`): the JS re-rank multiplies the compound score by the
     same penalty; a row with `superseded_by` NULL is ×1 (recall byte-identical to pre-C2.1).
3. **`supersedeEpisodic(db, oldId, newId)`** — service-role helper to set the link on correction (RLS
   blocks anon/auth UPDATE). Same "settable link" model M3.2 shipped at 100% (hand-fillable field).
4. **`tools/companion_supersedes.py`** — static contract checks + a LIVE proof in a ROLLED-BACK transaction
   (zero pollution): seeds 2 identical-embedding procedures → `match_procedural_memories` returns BOTH →
   marks one superseded → returns ONLY the replacement. Registered in `run_platform_checks` group
   "Companion Memory"; degrades-to-SKIP if the local DB is down. Existing `validate_agent_memory_store.py`
   still PASSES (12/12, the E12 4-place-sync contract intact).

**Acceptance bar MET:** after a correction the obsoleted procedure ranks below its replacement (the live
self-test proves it — count 2→1). **Enhancement (not required, pairs C2.2):** auto-detect a contradiction
at extraction and call `supersedeEpisodic` (today the link is set explicitly, exactly as M3.2's field is).

---

## C3.1 — DONE (2026-06-24): backup + restore drill of the companion memory tables

`tools/companion_memory_backup.py` (`--backup`/`--drill`, the M1.1/Arc-S `data_backup.py` pattern):
pg_dump `agent_episodic_memory` + `agent_memory` → restore into scratch schema `dr_companion` → assert
**rowcount round-trip AND a seeded canary fact is still RECALLABLE** from the restored copy (an
importance-ordered query returns it — rowcount alone doesn't prove the memory survives queryably). Proven
LIVE: episodic 240/240 rows + canary recalled, agent_memory 99/99, ~0.6s each. Zero net pollution (canary
removed in a `finally`). Registered in "Companion Memory" (skip_if_fast, the DR-drill convention);
degrades-to-SKIP if the local DB is down. Note: the C2.1 self-FK makes pg_dump warn about a circular FK —
harmless here because the scratch table is `LIKE … INCLUDING DEFAULTS` (the FK is not copied).

---

## C5.1 — DONE (2026-06-24): port the abstention / anti-fabrication control → Memento

The reverse leg of the two-way exchange. Added an **abstention dimension** to Memento's
`tools/memory_recall_eval.py` (the M2.1 recall gate): a set of unanswerable queries the retriever must
NOT fabricate a hit for. `--selftest` proves teeth in BOTH dimensions — recall (a bad `MIN_FINAL_SCORE`
knob collapses recall → FAIL) and abstention (a *fabricating* retriever that surfaces the importance prior
on a no-match query breaches the `abstention_rate ≥ 0.90` floor → caught).

**Measured-before-built finding (the honest scope):** Memento's lexical retriever abstains correctly ONLY
on **zero-lexical-overlap** queries (no FTS token match → 0 candidates → 0 hits; currently 6/6 = rate 1.00,
now locked). On **incidental-overlap** unanswerable queries ("how do I train a goldfish to play the
violin") it surfaces the importance/recency PRIOR (5 hits whose blended scores do NOT separate from real
hits — measured: top 0.08 vs an answerable 0.06). That broader fabrication is coupled to SEMANTIC relevance
= the **parked M5 tier**, so it is MEASURED + documented (`incidental_fabrication 3/3`), **not gated** —
gating it would block on a true gap and force M5, which M2.1's own measurement left parked as
over-engineering for a single-dev builder memory. The eval dimension is the portable contribution;
enforcement of the no-overlap property has teeth today, and the measurement justifies (or kills) M5 later.

---

## C1.2 — DONE (2026-06-24): RAG + Persona gates armed (and a latent RAG bug caught)

Same toothless-gate problem as C1.1 (persona locked-test n=4, rag n=1 → `blocking@n≥20` → warn-only). Fixed by the C1.1 playbook per dimension:
- **PERSONA:** golden 13→31 (adversarial-critic round; merged `persona_grader_self_test` oracle 31/31, blind 0/31), locked-test n=4→**10**, tol→12, floor re-frozen **90%** from a clean 31/31-call capture. ARMED. (3 honest free-tier voice misses in the floor — terse replies / one missed bridge; NOT tuned away, anti-overfit.)
- **RAG:** caught a **latent bug independent of my work** — the golden pinned a fixed `asset.asset_id` (`HPU-001`/`c07a5f44`) that a reseed had orphaned, so the asset-brain returned **404 "Asset not found in this hive" on EVERY unit** (the whole rag dimension was silently dead; its frozen "100%" baseline was stale). Fix: re-pinned to a current rich asset (`ee54d4ea` Yokogawa YTA610, logbook+weibull+fmea+rcm+pf coverage, in the test hive), rewrote all questions **asset-name-AGNOSTIC** ("this asset") so the golden is reseed-robust, and made the new positives **single-asset** (the capture pins ONE asset — cross-asset questions can't ground). golden 13→30, locked-test n=1→**4**, tol→25, floor re-frozen **100%** from a clean 30/30-call (all HTTP 200) capture. ARMED.

**Acceptance MET:** a degraded rag/persona retrieval now FAILs its frozen floor (both block a ≥2-unit locked-test regression). **Notes:** rag n=4 is the thinnest dim — a **multi-asset capture** (iterate several pinned assets) is the path to a meatier rag locked-test (future C1.2-plus). Train/val nits (not gated): rag RG-02 pm-compliance is ungrounded for the new asset (0 pm completions) and the risk-abstention negatives reveal the new asset HAS risk data (so those negatives are mis-grounded for it) — fix when the multi-asset capture lands. **domain/robustness** dims remain warn-only (stale 2026-06-09 baselines) — same expand+re-freeze treatment pending.

---

## The prioritized roadmap. ★ = do-first. Each: value · effort · acceptance bar.

### C1 — Enforcement (turn the rich evals from measurement into GATES)  ← do first
- **C1.1 ★ Wire `companion_memory_eval` as a regression gate.** *Biggest leverage, smallest build:
  the eval already exists and discriminates (oracle passes / blind fails).* Freeze recall + abstention
  floors on the locked-test split, register in `run_platform_checks` (group "Companion Memory"), so a
  retrieval-knob change that drops recall (or breaks abstention) FAILs CI. · **S** · _Acceptance:_ a
  deliberately-degraded config (e.g. similarity floor → 0.99) FAILs; the current config passes.
- **C1.2 Gate the rag + persona evals** the same way (the highest-value siblings). · **S** ·
  _Acceptance:_ a degraded rag/persona retrieval FAILs its frozen floor.

### C2 — Store hygiene (the safety + quality gaps)
- **C2.1 ★ Store-level `supersedes` / contradiction down-rank.** When a fact/procedure is corrected,
  the obsolete stored memory is **down-ranked at retrieval**, not merely tested behaviourally. In a
  maintenance tool an outdated procedure surfacing as current is a **safety hazard**. Adapt Memento
  M3.2: a `supersedes` link (or an LLM/heuristic contradiction signal at extraction) → a retrieval
  penalty in `recallEpisodic`/`matchProcedures`. · **M** · _Acceptance:_ after a correction, the
  obsoleted procedure ranks below its replacement for the same query (a golden unit proves it).
- **C2.2 Write-side semantic dedup.** Before `persistEpisodic` inserts, cosine-compare against the
  worker/hive's existing facts; near-duplicates merge (bump importance/use_count) instead of
  accumulating. · **S** · _Acceptance:_ re-storing a paraphrase of an existing fact does not add a row.
- **C2.3 Re-embed retry for null procedural embeddings.** A procedural memory stored with
  `embedding=null` (embed failed) is invisible to `match_procedural_memories` forever; add a scheduled
  back-fill. · **S** · _Acceptance:_ a null-embedding procedural row becomes searchable after the back-fill.

### C3 — Durability
- **C3.1 ★ Backup + restore drill of the companion memory tables.** Per-hive `pg_dump` of
  `agent_episodic_memory` + `agent_memory` → restore into a scratch schema → assert rowcount match AND
  a sample recall still works (the M1.1 pattern, against the LOCAL docker DB). · **S** · _Acceptance:_
  a drill restores a hive's memory and a known recall query still returns its fact. Customer-trust +
  enterprise-compliance asset.
- **C3.2 Health-regression gate on companion memory.** Thresholds on silent_rate (recall returned
  nothing), p95 retrieval latency, grounding %; honor a warming-up clause. · **S** · _Acceptance:_ a
  degraded metric FAILs instead of needing a human to read the dashboard.

### C4 — Measurement of the heuristics (only after the corpus warrants)
- **C4.1 Eviction-quality measurement + knob ablation.** Measure recall@k before/after LRU eviction on
  a golden set; tie the 10 eyeball-tuned retrieval knobs (recall windows, similarity floors
  0.25/0.30/0.55, caps, `GRADER_THRESHOLD`) to the eval so a tuning change is ablation-checked. · **M** ·
  _Acceptance:_ a knob change that hurts recall is caught; eviction's false-evict rate is reported.
- **C4.2 Per-hive memory-health tile** on founder-console (recall miss-rate, eviction events,
  use_count skew). · **S** · _Acceptance:_ the tile renders live per-hive memory health.

### C5 — Reverse port (Companion → Memento; the exchange runs both ways)
- **C5.1 ★ Port the abstention / anti-fabrication control into Memento's `memory_recall_eval.py`.**
  Memento has a `MIN_FINAL_SCORE` honesty gate but **no test that it correctly returns nothing** when
  nothing matches. The Companion's abstention controls are the template. · **S** · _Acceptance:_
  Memento's recall gate fails if the retriever fabricates a hit for an unanswerable query.
- **C5.2 Port knowledge-update/temporal golden units into Memento** (behavioural eval for M3.2's
  supersedes mechanism). · **S** · _Acceptance:_ a superseded-then-queried Memento unit is graded.
  **✅ DONE-via-M3.2 (2026-06-24, evidence-classified):** the knowledge-update/supersedes behavioural
  grade is ALREADY a registered Memento gate — `tools/memory_supersedes.py --self-test` step 3 asserts
  "at equal base score the superseded chunk ranks BELOW its replacement" (= this acceptance), built in the
  M-series. The **temporal "latest-wins"** half is deliberately **N/A for Memento**: its retriever
  intentionally *tempers* recency (the 1.7× transcript boost was retuned DOWN so recency can't crowd out
  curated feedback — M2.1 gotcha), so a "latest-fact-wins" eval would fight Memento's curated-memory design.
  Not rebuilt (would duplicate M3.2). The Companion's own knowledge-update/temporal dims live in its
  memory golden (C0).

### C6 — DEFERRED behind trust: the contribute-back flywheel (the product moat)
- **Companion → hive knowledge base.** Companion conversations → extracted procedural/episodic facts →
  **human-reviewed promotion** into a durable, per-hive **shared** SOP/fault-KB → retrievable by every
  technician AND the Companion next time. The real moat — but do NOT compound knowledge the memory
  can't yet measure (C1), de-dup (C2.2), or supersede (C2.1). The flywheel machinery partly exists
  (`companion_harvest`, `companion_self_improvement_analyzer`); the open piece is the durable shared KB
  + the review gate. · **L** · build only after C1–C3 are green.

### Adjacent cleanups surfaced by the scout (cheap, do alongside)
- `dialog_state` is written but never read in ai-gateway (intent/context_slots are dead) — wire or retire.
- Confirm `hierarchical-summarizer` actually has a cron trigger (none found) — schedule or retire.

---

## Decision rule (the through-line, same as the M-series)
**Enforce (C1) + make durable (C3) + de-dup/supersede (C2) so the memory is TRUSTWORTHY, BEFORE
compounding knowledge into the shared KB (C6).** Measurement justifies the moat, never the reverse.
Coupling: **shared patterns ported natively, not a shared library** (the substrates differ — Companion
pg+pgvector vs Memento local FTS5 — and the Companion owns a mature grader stack a shared lib would fight).
Recommended order: **C1.1 → C2.1 → C3.1 → C5.1 → (C1.2, C2.2, C3.2) → C4 → C6-only-when-trusted.**

_Spine for the build. Grounded by `COMPANION_MEMORY_AUDIT.md`._
