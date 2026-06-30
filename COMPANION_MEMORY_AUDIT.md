# Companion Memory Audit — does the Companion have the Memento M-series disciplines?

> **Question (Ian):** extend the memory-system moat to the AI Companion. What can the Companion
> GET from the memory system, and what can it SHARE back? **Decision: audit first, then decide coupling.**
> Grounded 2026-06-24 by a 2-agent scout (substrate map + discipline audit), then hand-verified
> because the discipline scout initially conflated the dev's Memento tools with the Companion's own.

---

## TL;DR — the surprising shape

The naive assumption ("the Companion needs a memory system like Memento") is **wrong**. The Companion
already has a **richer memory substrate than Memento** (embeddings, 4 durable memory types, per-hive
RLS, LRU eviction, retention cron, a semantic procedure matcher, persona-scoped knowledge) **and a
richer eval layer** (LongMemEval-style: recall + temporal + knowledge-update + multi-session +
**abstention/anti-fabrication**, plus rag/persona/domain/safety/robustness graders and a self-improvement flywheel).

What the Companion's memory is MISSING is the M-series' **enforcement + durability + store-hygiene**
layer. So the transplant is narrow and high-value, and the exchange is genuinely **two-way**:
Memento donates *governance*; the Companion's *eval dimensions* (abstention, temporal) flow back to Memento.

---

## Grounded verdict — each M-series discipline vs the Companion

| M-series discipline | Companion | Evidence (grounded) |
|---|---|---|
| **M1.1 Backup + restore DRILL** of the memory tables | **NONE** | Only the dev's `memory_db_backup.py` (Memento). No pg_dump/PITR **drill** proving `agent_episodic_memory`/`agent_memory` restore. Supabase PITR exists platform-wide but is never drilled per-hive. |
| **M1.2 Bloat management** | **HAS (native)** | `_shared/episodic-memory.ts:140-171` `evictIfOverCap()` LRU (200/worker, 1000/hive) + `20260511000010_agent_memory_retention_cron.sql` (turns 90d / summaries 180d). Different mechanism than VACUUM, but the need is met. |
| **M2.1 Recall eval** | **HAS — richer — but NOT a gate** | `tools/companion_memory_eval.py` + `companion_memory_golden.json` + `tests/memory-golden-capture.spec.ts` drive a live 2-phase capture and grade recall/temporal/knowledge-update/multi-session/**abstention**. **But it is an eval, not a gate** (its own docstring: "Exit: 0 normally (eval, not a gate)") and is **not in `run_platform_checks`** — a tuning regression does not FAIL CI. |
| **M2.2 Health-regression GATE** | **PARTIAL** | `agent_memory.response_time_ms`, `use_count`, `last_used_at` are tracked; **no thresholded gate** on companion-memory silent_rate / latency / grounding %. |
| **M3.1 Write-quality** | **PARTIAL** | `persistEpisodic` (`episodic-memory.ts:187-218`) clamps content≤600, importance∈[0,1], filters invalid `memory_type`. **No dedup** (exact or semantic) and **no usefulness lint** — near-duplicate facts accumulate. |
| **M3.2 supersedes / contradiction (at the STORE)** | **NONE at store; tested-only** | The `knowledge-update` eval dimension *tests* whether the model updates, but the **store has no retrieval-time down-rank of an obsoleted fact**. An outdated procedure can co-surface as current = a **maintenance-safety hazard**. (`persona_knowledge` has `content_hash` for idempotent refresh — not the same thing.) |
| **M4.1 Eviction-quality measurement** | **NONE** | LRU (`memScore = importance·log(1+use_count) + importance·0.5`) is deterministic but **unmeasured** — no check that it isn't dropping high-value facts. The substrate scout found **10 retrieval knobs tuned by eyeball / by-incident** (recall windows, similarity floors 0.25/0.30/0.55, caps, GRADER_THRESHOLD "relaxed 0.5→0.4 for Lucena") with no ablation tying them to the recall eval. |
| **M4.2 Observability** | **PARTIAL** | Metrics exist; **no per-hive memory-health tile** on founder-console (recall miss-rate, eviction events, use_count skew). |

**Also found (substrate scout, worth fixing regardless):** `dialog_state` is written but **never read** in ai-gateway (intent/context_slots dead); procedural embeddings are **nullable and never re-embedded** (a failed embed makes that procedure invisible to semantic search forever); `hierarchical-summarizer` has no confirmed cron trigger.

---

## The two-way exchange, grounded (this is the answer to Ian's question)

### A. Memento → Companion (governance the Companion lacks)
1. **Wire the existing evals as GATES.** The Companion already *measures* recall/abstention; the M-series move is to make `companion_memory_eval` (and rag/persona) **fail CI on regression** with frozen floors, exactly like Memento M2.1/M2.2. Biggest leverage, smallest build — the eval already exists.
2. **Store-level `supersedes` (M3.2).** A correction down-ranks the obsolete stored fact at retrieval. Safety-critical here in a way it never was for Memento.
3. **Backup + restore DRILL (M1.1)** of `agent_episodic_memory`/`agent_memory`, per-hive — a customer-trust + enterprise-compliance asset.
4. **Eviction-quality measurement (M4.1)** + tie the 10 eyeball knobs to the recall eval so tuning is ablation-checked, not vibes.
5. **Write-side DEDUP (M3.1)** — semantic near-dup collapse before insert.

### B. Companion → Memento (the reverse direction is real)
The Companion's eval is **richer than Memento's M2.1** in two dimensions Memento should adopt:
- **Abstention / anti-fabrication control** — does the retriever correctly return *nothing* when nothing matches? Memento has a `MIN_FINAL_SCORE` honesty gate but **no test that it abstains correctly**. Port the Companion's abstention controls into `memory_recall_eval.py`.
- **Knowledge-update / temporal** golden units — Memento's `supersedes` (M3.2) has a mechanism but no *behavioral* eval; the Companion's knowledge-update units are the template.

### C. The "share knowledge back" correction
Ian's phrasing was "share back to **my** memory system." Pointing customer facts at **Memento is wrong** (Memento is the *builder's* single-tenant memory; ingesting per-hive PII violates tenancy and is useless to the build). The correct contribute-back target is the **hive knowledge base** (SOP / fault-KB): Companion conversation → extracted procedural fact → human-reviewed promotion → retrievable by every technician *and* the Companion next time. The Companion already has flywheel machinery (`companion_harvest`, `companion_self_improvement_analyzer`, `companion_flywheel_*`); the open question is whether it promotes into a durable, per-hive **shared** KB.

---

## Coupling implication (Ian deferred this to "after the audit")

The audit points **away from a shared code library** and toward **shared patterns, ported natively**:
- The substrates differ (Companion = Postgres + pgvector embeddings, multi-tenant, prod; Memento = local SQLite FTS5/TF-IDF, single-tenant). Each chose **the right substrate for its corpus** (NL field-talk wants embeddings; dev-jargon wants lexical) — do **not** cross-port substrate.
- The Companion already owns a mature grader stack (`companion_rigorous_grader`, `companion_judge`) — a shared eval lib would fight it.
- So: extract the **disciplines as templates** (gate-wrapping, supersedes-down-rank, backup-drill, eviction-measure, abstention-control) and implement each **natively** on each side. Low coupling, no shared-library drift.

---

## Recommended next step

Turn the five Memento→Companion gaps into a scoped **`COMPANION_MEMORY_ROADMAP.md`** (M-series style, per-item % scoreboard, measure-before-build), prioritised:
1. **★ Wire `companion_memory_eval` as a regression gate** (floors frozen) — the recall keystone, smallest build, biggest leverage.
2. **★ Store-level `supersedes`** down-rank — the safety gap.
3. Backup + restore drill of the companion memory tables.
4. Eviction-quality measurement + ablation-tie the 10 knobs.
5. Write-side semantic dedup.
Plus the reverse: **port abstention + knowledge-update controls into Memento's `memory_recall_eval.py`.**

_Spine for the build if approved. Grounded by scout (substrate map `_shared/memory.ts`+`episodic-memory.ts`+migrations; discipline audit corrected for the Memento/Companion conflation)._
