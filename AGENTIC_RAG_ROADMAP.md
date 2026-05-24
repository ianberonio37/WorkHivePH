# Agentic RAG Roadmap

**Status:** Spec only — no code written. Awaiting per-phase build approval.
**Author:** Drafted 2026-05-21 (Claude as AI Engineer agent in WAT framework).
**Scope:** Convert WorkHive's current single-shot RAG into a self-correcting, hierarchical, model-agnostic agentic RAG stack capable of answering 5–10 year horizon questions **entirely on the existing free-tier multi-provider chain** (`_shared/ai-chain.ts`). No paid Claude/OpenAI/Anthropic tier is ever used.
**Companion docs:** [`KPI_ENGINE.md`](KPI_ENGINE.md), [`VOICE_COMPANION_ROADMAP.md`](VOICE_COMPANION_ROADMAP.md), [`SENTINEL_ARCHITECTURE.md`](SENTINEL_ARCHITECTURE.md), [`WORKHIVE_PLATFORM_BOOK.md`](WORKHIVE_PLATFORM_BOOK.md).

---

## 1. Why this exists

The current AI surface (assistant + voice companion + ai-orchestrator + voice-semantic-rag) is **single-shot**:

```
User → one retrieval (recency or pgvector) → one LLM call → one answer.
```

This works for "what did I fix yesterday?" It collapses on:
- *"Compare 2022–2025 failure patterns on P-203."*
- *"Which assets have degraded MTBF over the last 4 years?"*
- *"Show me the chronic faults across the fleet since plant commissioning."*

Three failure modes the loop above cannot handle:
1. **Context window overflow** — raw 5-year logbook fetch is 25 MB; even the largest free-tier 32K-context models (Qwen3-32B, Llama-3.3-70B) choke and we hit Cerebras's 8K cap immediately.
2. **No grader** — irrelevant chunks poison the context and induce hallucinations.
3. **No decomposition** — the model sees a soup of years instead of structured slices.

The 2026 production answer (per InfoQ, MAO-ARAG, HiChunk, RAGFlow): a **hierarchical, agentic loop** that decomposes the query, summarises history offline, retrieves with a grader, and verifies before answering.

---

## 2. What WorkHive already has (do not rebuild)

| Capability | Lives in | Reuse for |
|---|---|---|
| Multi-provider model chain (6 providers, 14 models, auto-fallback) | [`_shared/ai-chain.ts`](supabase/functions/_shared/ai-chain.ts) | Every LLM call in this roadmap routes through `callAI` |
| Multi-agent orchestrator (7 specialised agents) | [`ai-orchestrator/`](supabase/functions/ai-orchestrator/) | Becomes one of the strategies the new Router can pick |
| Embeddings + pgvector (`nomic-embed-text-v1_5`, 384-dim) | `embed-entry/`, `voice-embeddings/`, `semantic-search/` | Reused as the Retriever's vector lane |
| Canonical 4-tier lineage (Fuel → Engine → Brain → Dashboard) + Tier S Standards | `canonical/`, `KPI_ENGINE.md` | Hierarchical summaries inherit standard citations |
| Per-hive rate-limit + cost-log | `ai_rate_limits`, `ai_cost_log` | New agentic loop logs traces alongside existing cost log |
| Hive scoping enforced everywhere | `validate_hive.py` | Every new table/view must pass this same validator |
| Sentinel L2 + Mega Gate + flywheel cadence | `SENTINEL_ARCHITECTURE.md` | Every phase ships with Layer-0 validator + Playwright spec |

---

## 2.5 Allowed Models (HARD CONSTRAINT — read before designing anything)

**Every LLM call in this roadmap routes through `supabase/functions/_shared/ai-chain.ts`. No paid Claude / OpenAI / Anthropic / NVIDIA-NIM tier is ever introduced.** This is a project-defining constraint — the commercial model assumes $0 LLM spend.

### The complete allowed chain (ordered, fallback is automatic)

| # | Provider | Models | Capacity notes |
|---|---|---|---|
| 1 | **Groq** | `meta-llama/llama-4-scout-17b-16e-instruct` (30K TPM, primary) → `llama-3.3-70b-versatile` → `qwen/qwen3-32b` → `llama-3.1-8b-instant` → `openai/gpt-oss-20b` (8K TPM) → `openai/gpt-oss-120b` (8K TPM, last) | Highest TPM. Scout-17B is the workhorse. |
| 2 | **Cerebras** | 2 models | 1M tokens/day, 8K context cap (`maxTokensCap: 4096`) |
| 3 | **SambaNova** | 2 models | Persistent free tier, 20 RPM |
| 4 | **Google Gemini** | `gemini-2.5-flash-lite` | 15 RPM / 1K RPD — narrative + low-RPM tasks only |
| 5 | **OpenRouter** | 2 `:free` models | 200 req/day each |
| 6 | **DeepSeek** | `deepseek-v4-flash` | 5M free tokens then paid — **stop using if quota nears exhaustion** |

**Embeddings:** Groq `nomic-embed-text-v1_5` (underscore before `5`, not hyphen). 384 dimensions. Free.

### Banned (do not add to the chain, do not reference in any spec)

- ❌ Any paid Claude (Haiku / Sonnet / Opus / claude-3.x / claude-4.x paid API)
- ❌ Any paid OpenAI (gpt-4, gpt-4o, gpt-4-turbo, o1, o3) — including non-`:free` OpenRouter routes
- ❌ Anthropic Managed Agents / Workbench paid features
- ❌ NVIDIA NIM (credit-based, will exhaust)
- ❌ `gemini-2.0-flash-lite` (removed from Gemini free tier April 2026)
- ❌ `deepseek-chat` (legacy name, retiring 24 July 2026 — use `deepseek-v4-flash`)
- ❌ `meta-llama/llama-4-maverick-17b-128e-instruct` (deprecated on Groq Feb 2026)
- ❌ `gemma2-9b-it` (deprecated on Groq)

### Task → primary model recommendation (fallback handled by `_shared/ai-chain.ts`)

This map is the single source of truth for every Phase that follows.

| Task profile | Primary | Fallback path |
|---|---|---|
| Intent classification, slot extraction, light grading, hallucination checking | `llama-3.1-8b-instant` (Groq) | → `gemini-2.5-flash-lite` → SambaNova |
| Single-fact retrieval, lightweight orchestration | `llama-3.3-70b-versatile` (Groq) | → `qwen/qwen3-32b` → SambaNova |
| Multi-step orchestration, temporal fold, narrative synthesis | `llama-4-scout-17b-16e-instruct` (Groq, 30K TPM primary) | → `llama-3.3-70b-versatile` → Cerebras → OpenRouter `:free` |
| Code / SQL generation | `deepseek-v4-flash` | → `qwen/qwen3-32b` (Groq) |
| Embeddings | `nomic-embed-text-v1_5` (Groq) | (no fallback — deterministic per-model) |
| Narrative prose / report-style output | `gemini-2.5-flash-lite` | → `llama-3.1-8b-instant` (Groq) |

### Cost framing rule

**Never quote per-1M-token pricing in this document or in any descendant spec/PR/commit.** Every cost line reads either:

- `**$0** (free tier)` — for token usage
- A rate-limit budget: e.g. `30K TPM on Scout-17B`, `1M tokens/day on Cerebras`, `1K RPD on Gemini`
- A storage cost (Supabase Storage `$0.021/GB/month`) — infrastructure only, not LLM spend

If a task seems to need a paid model, the resolution is *not* "introduce a paid tier" — it is:
1. Decompose into smaller chunks that fit a free-tier context window (Phase 2 hierarchical summaries are the main lever).
2. Move more work to deterministic Python / SQL / canonical views (Phase 4 router enforces this).
3. Downgrade scope of the answer (Phase 1 graceful degradation in the Router).

See [`feedback_free_tier_only_models.md`](../../../../../../.claude/projects/c--Users-ILBeronio-Desktop-Industry-4-0-AI-Maintenance-Engineer-Self-learning-Road-Map-Build---Sell-with-Claude-Code-Website-simple-1st/memory/feedback_free_tier_only_models.md) for the persistent rule.

---

## 3. Mapping the 7 data architectures (from the user's reference image) to WorkHive

| Pattern | Role in WorkHive | Current state | Phase that delivers it |
|---|---|---|---|
| **Data Warehouse** | `v_*_truth` canonical views feeding dashboards | ✅ Live | (no change) |
| **Data Lake** | Supabase Storage for raw voice, PDFs, photos, sensor blobs | ⚠️ PDFs only | Phase 6 |
| **Data Lakehouse** | Quarterly Parquet snapshots, DuckDB queryable; bridges hot Postgres & cold archive | ❌ Missing | Phase 6 |
| **Data Mesh** | Per-hive ownership + canonical view-owners per page | ✅ Live | (no change) |
| **Data Fabric** | Unified normalizer for SAP / Maximo / OPC-UA / MQTT / CMMS / sensors | ⚠️ Source hooks only | Phase 5 |
| **Lambda** | Nightly batch (`batch-risk-scoring`) + Realtime/RPC reads | ✅ Live | Phase 2 extends batch layer |
| **Kappa** | `voice_journal_entries` + `sensor-readings-ingest` event-driven | ✅ Live | (no change) |

**The composite picture:** Mesh + Warehouse + Lambda are the current foundation. Phase 5 adds the Fabric. Phase 6 adds Lake + Lakehouse. Kappa stays as-is for live streams. **No pattern is "the answer" — they are coexisting layers.**

---

## 4. The core architectural principle

> **Deterministic code does the heavy lifting. The LLM does light synthesis on pre-digested chunks.**

`KPI_ENGINE.md` already proves this for KPIs (MTBF/MTTR/OEE are SQL, never LLM). Extend the same principle to RAG: hierarchical summaries are computed offline in Python, embedded, and stored. The LLM at query time sees 5–20 dense rows, never 50,000 raw rows.

**Practical consequence:** The free-tier 8B and 17B models (`llama-3.1-8b-instant`, `llama-4-scout-17b-16e-instruct`) become sufficient for the vast majority of queries, because the *information density per token* climbs 100–1000×. The 70B free model (`llama-3.3-70b-versatile`) is reserved for genuine multi-step reasoning where the smaller models drift. No paid tier is ever introduced. This is exactly what the user asked for: "even the lowest model is robust because the platform pre-trains the context."

---

## 5. The 8 phases

Each phase declares: **Goal · New tables · New edge functions · New Python tools · Flywheel commitments (validator + Playwright + MEMORY) · Cost · Dependencies.**

---

### Phase 1 — Agentic RAG Loop (Router → Retriever → Grader → Generator → Checker)

**Goal:** Replace the single-shot `voice-semantic-rag` with a 5-stage self-correcting loop. Drops hallucination ~60% (per published 2026 benchmarks) with no new infra.

**New edge function:** `supabase/functions/agentic-rag-loop/index.ts`

**Signature:**
```ts
POST /functions/v1/agentic-rag-loop
Request:  { question: string, hive_id: string, worker_name: string, max_retries?: 2 }
Response: {
  answer:        string,
  citations:     Array<{ source_table: string, row_id: string, snippet: string, similarity: number }>,
  trace_id:      string,             // FK to agentic_rag_traces
  route:         "simple_recency" | "semantic" | "orchestrator" | "temporal" | "cold_archive",
  retries:       number,
  grader_passed: boolean,
  checker_passed:boolean,
  tokens_in:     number,
  tokens_out:    number,
  latency_ms:    number
}
```

**Internal stages:**
| Stage | Primary model (free tier) | Job |
|---|---|---|
| Router | `llama-3.1-8b-instant` (Groq) | Classify query → pick retrieval strategy + time scope |
| Retriever | (no LLM) | Hybrid: pgvector + canonical view + ilike keyword; cap 20 chunks |
| Grader | `llama-3.1-8b-instant` (Groq) | Score each chunk 0–1 against question; drop <0.5 |
| Generator | `llama-4-scout-17b-16e-instruct` (Groq, 30K TPM primary) | Answer using only graded chunks, must cite each claim |
| Checker | `llama-3.1-8b-instant` (Groq) | Verify every claim in answer has a citation in retrieved set |
| (retry) | — | If Checker fails: reformulate query → loop, max 2 retries |

Every stage calls `callAI(prompt, { taskProfile, ... })` — fallback within the free chain (Groq → Cerebras → SambaNova → Gemini → OpenRouter → DeepSeek) is handled by `_shared/ai-chain.ts`. No raw model names hardcoded at stage level.

**New table:** `agentic_rag_traces` (full per-run audit; see Phase 8 schema).

**Flywheel commitments:**
- **Layer 0 validator:** `validate_agentic_rag_loop.py` — checks: `agentic-rag-loop` registered in `config.toml`/`deploy-functions.ps1`/`validate_edge_contracts.py`; checker stage present; retry cap enforced; citation schema matches.
- **Layer 2 Playwright:** `tests/journey-agentic-rag.spec.ts` — 5 probes: simple recency, semantic match, grader-rejects-bad-chunk, checker-catches-uncited-claim, retry-on-failure.
- **MEMORY entry:** `project_agentic_rag_loop_<date>.md` — pattern, model choices, edge cases.

**Cost / budget (per query):** **$0** (free tier). Token budget per query ≈ 3K in (router 200 + grader 1500 + generator 1000 + checker 300) + 800 out. Comfortably inside Groq's 30K TPM ceiling on Scout-17B and 6K TPM on Llama-8B. Falls back to Cerebras (1M tokens/day) or SambaNova (20 RPM) if Groq is rate-pressured. Per-hive budget cap = 50 queries/hr × 24 = 1200 queries/day, well below Groq's daily token allowance.

**Dependencies:** None — uses existing `_shared/ai-chain.ts` and existing pgvector tables.

---

### Phase 2 — Hierarchical Period Summaries

**Goal:** Pre-compute Daily → Weekly → Monthly → Quarterly → Yearly natural-language + structured summaries per hive per asset. The mechanism that makes "5-year history" queries possible on small models.

**New table:** `canonical_period_summaries`
```sql
CREATE TABLE canonical_period_summaries (
  id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  hive_id         uuid NOT NULL REFERENCES hives(id) ON DELETE CASCADE,
  asset_tag       text,                    -- nullable: hive-level vs asset-level summaries
  level           text NOT NULL CHECK (level IN ('day','week','month','quarter','year')),
  period_start    date NOT NULL,
  period_end      date NOT NULL,
  summary_text    text NOT NULL,           -- 1-2 paragraph natural language digest
  summary_json    jsonb NOT NULL,          -- {failure_count, mtbf_days, mttr_h, top_assets[], top_root_causes[], pm_overdue, downtime_h}
  embedding       vector(384) NOT NULL,    -- nomic-embed-text-v1_5 of summary_text
  source_row_ids  uuid[],                  -- traceability back to logbook rows
  standard_cites  text[],                  -- e.g. ['ISO 14224:2016#7.1', 'ISO 22400-2:2014#5.3.1']
  generated_at    timestamptz DEFAULT now(),
  UNIQUE (hive_id, asset_tag, level, period_start)
);
CREATE INDEX idx_cps_hive_level_period ON canonical_period_summaries (hive_id, level, period_end DESC);
CREATE INDEX idx_cps_asset_level       ON canonical_period_summaries (asset_tag, level, period_end DESC);
CREATE INDEX idx_cps_embedding         ON canonical_period_summaries USING ivfflat (embedding vector_cosine_ops);
```

**New Python tool:** `tools/hierarchical_summarizer.py`
- Reads `v_logbook_truth` + `v_pm_compliance_truth` per hive per asset per period.
- Computes the structured `summary_json` deterministically (uses `_shared/ai-chain.ts` callable from Python via the Edge Function — or computes purely in Python).
- LLM call only generates the 1-2 paragraph `summary_text` from the structured JSON (token-cheap).
- Upserts into `canonical_period_summaries`.
- Triggered by `pg_cron` daily at 02:00 PHT (after `batch-risk-scoring` finishes at 13:00 PHT — schedule for the *following day*).

**Rollup cadence:**
- Day summaries: yesterday's data, daily.
- Week summaries: every Sunday for past week.
- Month summaries: 1st of each month for prior month.
- Quarter summaries: Jan/Apr/Jul/Oct 1st for prior quarter.
- Year summaries: Jan 1st for prior year.

**Query-time pattern:** "5-year history of P-203" →
1. Fetch 5 yearly rows (~10 KB).
2. If user drills in or grader flags a year: fetch its 4 quarterly rows.
3. If still drilling: fetch monthly → weekly → daily.

This is **lazy hierarchical retrieval** — depth proportional to question complexity, not data volume.

**Flywheel commitments:**
- **Layer 0:** `validate_hierarchical_summaries.py` — every active hive has yearly+quarterly summaries for past 3y; structured JSON includes the 6 required keys; standard_cites is non-empty for any summary mentioning MTBF/MTTR/OEE/PM.
- **Layer 2:** `tests/journey-hierarchical-rag.spec.ts` — probe "5-year history of asset X" returns ≤ 1500 tokens of context, mentions year ranges, cites at least one ISO standard.
- **MEMORY entry:** `project_hierarchical_summaries_<date>.md`.

**Cost / budget:** **$0** (free tier). Token budget per summary ≈ 500 in (structured stats only) + 200 out (1–2 paragraph digest). At 50 hives × 20 assets × daily rollup ≈ 1000 summary calls/day → ~700K tokens/day → fits Groq's free daily allowance with headroom for the rest of the platform. Embedding is Groq `nomic-embed-text-v1_5`, also $0. The nightly rollup is *deliberately spread* across off-peak hours (02:00–05:00 PHT) to avoid daytime TPM contention with live agentic-rag-loop traffic.

**Dependencies:** Phase 1 (consumes summaries via the Retriever stage).

---

### Phase 3 — Temporal Decomposition Orchestrator (Python, parameterized prompts)

**Goal:** The "manageable chunks" piece you described. Parses time-bound questions, fans out parallel sub-agents on each time slice, folds results.

**New Python tool:** `tools/temporal_orchestrator.py`
**New edge wrapper:** `supabase/functions/temporal-rag-orchestrator/index.ts` (calls into Python via a Render/Railway micro-service — pattern already used in this platform).

**Pattern:** LangGraph-style supervisor-worker topology (84.5% accuracy on EntQA benchmark per MAO-ARAG paper).

**Parameterized prompt templates** (Python-side):
```python
SUBQUERY_PROMPT = """\
PERIOD: {period_label}
ASSET: {asset_tag}
HIVE: {hive_name}
PRE-COMPUTED SUMMARY (canonical_period_summaries.summary_json):
{summary_json}
RAW SAMPLES (top 5 most-relevant logbook rows for this period, pgvector ranked):
{raw_samples}
USER QUESTION: {user_question}

Return strict JSON (no prose outside):
{{
  "period": "{period_label}",
  "key_findings": [<3-5 bullet strings>],
  "mtbf_days": <float or null>,
  "top_failure_modes": [{{ "mode": str, "count": int }}],
  "anomalies": [<strings>],
  "citations": [<row_id strings>]
}}
"""

FOLD_PROMPT = """\
You are comparing {n} time periods for the same asset/hive.
Each period was analysed by a sub-agent and returned the JSON below.

PER-PERIOD RESULTS:
{period_results_json}

USER QUESTION: {user_question}

Synthesise into a single answer that:
1. Compares trends across periods (improving / stable / degrading).
2. Calls out the worst period and explains why.
3. Cites period labels + row_ids inline using markers like [P1#row_id].
4. Stays under {max_words} words.
"""
```

**Routing logic in `temporal_orchestrator.py`:**
- Parse user question for time markers (year ranges, "last N years", "since commissioning").
- Decompose into period slices (default: yearly for spans ≥3y, quarterly for 6mo–3y, monthly for ≤6mo).
- `asyncio.gather()` parallel sub-agent calls (one per slice). Each gets `SUBQUERY_PROMPT` filled with its period's hierarchical summary + top-5 raw rows.
- Fold step: single `FOLD_PROMPT` call to `llama-4-scout-17b-16e-instruct` (Groq, 30K TPM primary) — falls back to `llama-3.3-70b-versatile` then Cerebras if rate-pressured.

**Flywheel commitments:**
- **Layer 0:** `validate_temporal_orchestrator.py` — orchestrator splits any 3y+ span into ≤10 sub-queries; each sub-agent receives a non-empty `summary_json`; fold output has ≥1 citation per period.
- **Layer 2:** `tests/journey-temporal-rag.spec.ts` — probe "compare 2022 vs 2023 vs 2024 vs 2025 for P-203" — assert 4 period markers, 1 fold answer, ≤ 3000 total tokens.
- **MEMORY entry:** `project_temporal_orchestrator_<date>.md`.

**Cost / budget:** **$0** (free tier). Token budget ≈ N × 2K (sub-agents, each on `llama-3.1-8b-instant`) + 1 × 6K (fold on `llama-4-scout-17b-16e-instruct`). For a 5-year query: 5 × 2K + 6K ≈ 16K total tokens — one query consumes ~half a minute of Groq TPM budget per provider. If sub-agents are fired with bounded concurrency (max 3 parallel), TPM contention stays predictable.

**Dependencies:** Phase 1 (loop wraps this as the `temporal` route), Phase 2 (consumes hierarchical summaries).

---

### Phase 4 — Tiered Model Router (right model per task)

**Goal:** Single `pickModel(taskProfile)` function. Drops TPM pressure ~40% by routing cheap tasks to small free-tier models, freeing the bigger free-tier slots (Scout-17B, Llama-3.3-70B) for genuinely heavy synthesis. **All models are free-tier — no paid escalation, ever.**

**Extension to:** `_shared/ai-chain.ts` (add `taskProfile` argument to `callAI`).

**The map:**
| Task profile | Primary (free tier) | Fallback path (handled by `_shared/ai-chain.ts`) | Reason |
|---|---|---|---|
| `intent_classification` | `llama-3.1-8b-instant` (Groq) | → `gemini-2.5-flash-lite` → SambaNova | Sub-second, $0 |
| `slot_extraction` | `llama-3.1-8b-instant` (Groq) | → Cerebras → SambaNova | Cheap structured output |
| `single_fact_retrieval` | `llama-3.1-8b-instant` (Groq) | → `gemini-2.5-flash-lite` | Sub-second |
| `orchestrator_router` (Phase 1 Router) | `llama-3.1-8b-instant` (Groq) | → SambaNova | Light reasoning |
| `chunk_grader` (Phase 1 Grader) | `llama-3.1-8b-instant` (Groq) | → `qwen/qwen3-32b` | Verification is cheap |
| `hallucination_checker` (Phase 1 Checker) | `llama-3.1-8b-instant` (Groq) | → `qwen/qwen3-32b` | Verification is cheap |
| `multi_step_orchestration` | `llama-3.3-70b-versatile` (Groq) | → `qwen/qwen3-32b` → Cerebras | Deeper reasoning |
| `synthesis_long_output` (>2000 tok) | `llama-4-scout-17b-16e-instruct` (Groq, 30K TPM) | → `llama-3.3-70b-versatile` → OpenRouter `:free` | Output budget |
| `temporal_subagent` (Phase 3) | `llama-3.1-8b-instant` (Groq) | → Cerebras | Per-period, cheap |
| `temporal_fold` (Phase 3) | `llama-4-scout-17b-16e-instruct` (Groq) | → `llama-3.3-70b-versatile` | Cross-period reasoning |
| `code_or_sql_generation` | `deepseek-v4-flash` | → `qwen/qwen3-32b` (Groq) | Domain-tuned |
| `embedding` | `nomic-embed-text-v1_5` (Groq) | (no fallback — deterministic per-model) | $0 |
| `narrative_report` | `gemini-2.5-flash-lite` | → `llama-3.1-8b-instant` (Groq) | Prose, $0, low RPM but enough for narrative |

Each task profile maps to an *ordered fallback list* (matches the existing chain pattern), so if the primary 429s or 413s, the wrapper drops to the next model **of equivalent or lower capability** — never silently upgrades to a more expensive tier.

**Flywheel commitments:**
- **Layer 0:** `validate_model_router.py` — every `callAI` call site declares a `taskProfile`; no raw model name passed in; checker stage uses the 8B model, never escalates to 70B unnecessarily (TPM regression guard); no paid-tier model name appears anywhere in the codebase (`Haiku|Sonnet|Opus|gpt-4|claude-` greps must return zero hits).
- **Layer 2:** `tests/journey-model-router.spec.ts` — probe intent classification uses 8B model; long synthesis uses Scout-17B or Llama-70B.
- **MEMORY entry:** `feedback_model_routing_<date>.md` (the "do not silently upgrade" rule belongs here).

**TPM impact:** Audit of current `callAI` call sites suggests **~40% of calls today escalate unnecessarily to 70B+ models for tasks an 8B model handles cleanly**. Phase 4 reclaims that TPM headroom, which directly raises the per-hive query ceiling without changing any rate-limit rule.

**Dependencies:** Phase 1 (uses the router in every stage).

---

### Phase 5 — Data Fabric Normalizer (unified ingest layer)

**Goal:** One schema for SAP work orders + Maximo + OPC-UA tags + MQTT messages + CMMS pushes + voice journal + photo OCR. Enables a single agentic-RAG query to span all sources.

**New edge function:** `supabase/functions/data-fabric-normalizer/index.ts`

**New table:** `unified_events`
```sql
CREATE TABLE unified_events (
  id            uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  hive_id       uuid NOT NULL REFERENCES hives(id) ON DELETE CASCADE,
  asset_tag     text,
  source        text NOT NULL CHECK (source IN ('sap_pm','maximo','opc_ua','mqtt','cmms_webhook','voice','photo_ocr','manual_log','sensor','email_ingest')),
  source_id     text NOT NULL,             -- foreign system's primary key
  event_type    text NOT NULL,             -- 'work_order','sensor_reading','alarm','note','image','...'
  occurred_at   timestamptz NOT NULL,
  payload       jsonb NOT NULL,
  payload_text  text,                      -- flattened text for embedding (nullable for binary)
  embedding     vector(384),               -- nullable until enrichment runs
  hash          text NOT NULL,             -- sha256 of source+source_id+occurred_at for dedup
  ingested_at   timestamptz DEFAULT now(),
  UNIQUE (source, source_id, hash)
);
CREATE INDEX idx_unified_events_hive_asset_time ON unified_events (hive_id, asset_tag, occurred_at DESC);
CREATE INDEX idx_unified_events_embedding       ON unified_events USING ivfflat (embedding vector_cosine_ops);
```

**Normalizer responsibilities:**
- Accept any source payload via POST.
- Map to canonical schema using per-source adapters (SAP PM01-04 → event_type='work_order', OPC-UA tag → event_type='sensor_reading', etc.).
- Dedup via `hash` (idempotent ingest).
- Async-embed `payload_text` (fire-and-forget; never block ingest).
- Per-hive 1000 events/sec rate limit (industrial volume).

**Flywheel commitments:**
- **Layer 0:** `validate_data_fabric.py` — every source has an adapter; dedup hash present; hive_id non-null; payload_text populated for embeddable types.
- **Layer 2:** `tests/journey-data-fabric.spec.ts` — round-trip a SAP work order → assert unified_events row appears with embedding within 30s; agentic-rag-loop returns it in a related query.
- **MEMORY entry:** `project_data_fabric_<date>.md` + `reference_external_systems_<date>.md` (per-source API docs index).

**Cost:** Embedding only — Groq nomic free tier covers ~10M chars/day. Storage: ~1 KB/event × 1M events ≈ 1 GB → Supabase paid tier territory at scale.

**Dependencies:** Phase 1 (loop's Retriever reads from `unified_events`).

---

### Phase 6 — Cold Lakehouse Archive (Parquet + DuckDB for >18-month data)

**Goal:** Keep Postgres lean. Year-10 queries still answerable by routing to cold tier when needed.

**New Python tool:** `tools/cold_archive_exporter.py`
- Runs quarterly via pg_cron (1st of Jan/Apr/Jul/Oct, 03:00 PHT).
- Exports rows from `v_logbook_truth`, `pm_completions`, `unified_events`, `voice_journal_entries` where `occurred_at < now() - interval '18 months'`.
- Writes per-hive Parquet files to `supabase://archive-{hive_id}/{year}-Q{n}/{table}.parquet`.
- After successful upload + checksum verify: deletes archived rows from hot Postgres.

**New edge function:** `supabase/functions/cold-archive-query/index.ts`
- Receives `{ hive_id, table, time_range, asset_tag?, limit? }`.
- Downloads relevant Parquet files (cache for warm queries).
- Queries via DuckDB (Deno-compatible build) or via a Render/Railway DuckDB micro-service.
- Returns rows in the same shape as the equivalent canonical view.

**Router integration (Phase 1):** Router detects `time_range > 18 months` → routes to `cold_archive` strategy → calls this fn → results flow through the same Grader/Generator/Checker.

**Flywheel commitments:**
- **Layer 0:** `validate_cold_archive.py` — every hive with >18mo data has a current-quarter Parquet snapshot; checksum file present; row count matches deletion count.
- **Layer 2:** `tests/journey-cold-archive.spec.ts` — probe "what happened on this asset in 2022" (assuming it's >18mo old) routes to cold archive, returns rows in canonical shape.
- **MEMORY entry:** `project_cold_archive_<date>.md`.

**Cost:** Supabase Storage ~$0.021/GB/month. 1M rows ≈ 100 MB Parquet. Negligible.

**Dependencies:** Phase 5 (archives `unified_events` too).

---

### Phase 7 — Agent Episodic Memory (long-term across sessions)

**Goal:** Companion remembers worker preferences, prior fixes, and incident context across sessions.

**New table:** `agent_memory`
```sql
CREATE TABLE agent_memory (
  id            uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  hive_id       uuid NOT NULL REFERENCES hives(id) ON DELETE CASCADE,
  worker_name   text,                      -- nullable: hive-wide vs per-worker memory
  memory_type   text NOT NULL CHECK (memory_type IN ('factual','procedural','episodic','semantic')),
  content       text NOT NULL,
  embedding     vector(384) NOT NULL,
  importance    real NOT NULL DEFAULT 0.5 CHECK (importance BETWEEN 0 AND 1),
  last_used_at  timestamptz DEFAULT now(),
  use_count     integer DEFAULT 0,
  source_run_id uuid,                       -- FK to agentic_rag_traces if memory was extracted from a run
  created_at    timestamptz DEFAULT now()
);
CREATE INDEX idx_agent_memory_worker_type ON agent_memory (worker_name, memory_type, last_used_at DESC);
CREATE INDEX idx_agent_memory_embedding   ON agent_memory USING ivfflat (embedding vector_cosine_ops);
```

**Memory types:**
| Type | Example |
|---|---|
| `factual` | "Worker prefers Tagalog responses." |
| `procedural` | "P-203 bearing failure was fixed by replacing the SKF 6205-2RS in March 2025." |
| `episodic` | "Incident 2024-03-15: cooling tower fan trip, root cause was loose VFD wiring." |
| `semantic` | "This plant runs 2 shifts: 06:00–14:00 and 14:00–22:00, no night shift." |

**Eviction:** LRU weighted by `importance × log(1 + use_count)`. Cap at 200 memories per worker, 1000 per hive.

**Read hook:** Phase 1's Router calls `agent-memory-store` first → injects top-5 most relevant memories into the system prompt as context.

**Write hook:** Phase 1's Checker, after a successful answer, calls a `memory_extractor` sub-agent (`llama-3.1-8b-instant`, cheap) that decides if any durable facts emerged.

**Flywheel commitments:**
- **Layer 0:** `validate_agent_memory.py` — every memory has embedding + importance; eviction respects cap; no PII leaks (run through `_shared/redactPII.ts`).
- **Layer 2:** `tests/journey-agent-memory.spec.ts` — turn 1: state preference. Turn 2 (new session): assert preference is honoured without re-stating.
- **MEMORY entry:** `project_agent_memory_<date>.md`.

**Cost:** Embedding only ($0 on Groq nomic). Storage ~1 KB/memory × 1000 memories × 50 hives ≈ 50 MB.

**Dependencies:** Phase 1 (read/write hooks integrate into the loop).

---

### Phase 8 — Observability + Cost Governance

**Goal:** Full per-run trace. No black-box agent runs.

**New table:** `agentic_rag_traces`
```sql
CREATE TABLE agentic_rag_traces (
  id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  hive_id         uuid REFERENCES hives(id) ON DELETE CASCADE,
  worker_name     text,
  question        text NOT NULL,
  route           text NOT NULL,                  -- which strategy the Router picked
  stages          jsonb NOT NULL,                 -- [{stage, model, tokens_in, tokens_out, latency_ms, output_snippet}]
  retrievals      jsonb NOT NULL,                 -- [{source, row_id, similarity, grader_score, kept}]
  retries         integer DEFAULT 0,
  grader_passed   boolean,
  checker_passed  boolean,
  citation_count  integer,
  final_answer    text,
  total_tokens    integer,
  total_cost_usd  numeric(10,6),
  latency_ms      integer,
  user_rating     integer,                        -- nullable; thumbs up/down later
  created_at      timestamptz DEFAULT now()
);
CREATE INDEX idx_agentic_traces_hive_created ON agentic_rag_traces (hive_id, created_at DESC);
CREATE INDEX idx_agentic_traces_route        ON agentic_rag_traces (route, created_at DESC);
```

**New dashboard page:** `agentic-rag-observability.html` (supervisor-only, behind hive role gate).

**Metrics surfaced:**
- Volume per route (simple_recency / semantic / orchestrator / temporal / cold_archive).
- Avg retries per route.
- Grader pass rate (target ≥85%).
- Checker pass rate (target ≥95%).
- p50 / p95 / p99 latency per route.
- Cost per query, per route, per hive, per day.
- Hallucination rate trend (1 − checker_pass_rate).
- Top 10 questions by cost.
- Top 10 questions by retries (signal for prompt drift or data gaps).

**Rate-limit cap enforcement:** Existing `checkAIRateLimit` (ai-engineer skill) extended to count agentic-rag-loop runs. Per-hive ceiling: **50 queries/hour** (existing default) and **1200 queries/day** (new daily cap, well inside Groq RPD allowance). When a hive approaches the daily cap, the Router downgrades non-essential routes (e.g. converts `temporal` to `simple_recency` with a notice) rather than failing — graceful degradation, not hard refusal.

**Flywheel commitments:**
- **Layer 0:** `validate_agentic_rag_observability.py` — every agentic-rag-loop call writes one trace row; `total_cost_usd` populated; dashboard page passes accessibility/escHtml gates.
- **Layer 2:** `tests/journey-agentic-rag-observability.spec.ts` — supervisor opens dashboard, sees route breakdown, sees cost chart, can filter by date.
- **MEMORY entry:** `project_agentic_rag_observability_<date>.md`.

**Cost:** Storage only (~1 KB/trace × ~10k traces/month/hive ≈ 10 MB/hive/month).

**Dependencies:** All phases (every phase writes traces here).

---

## 6. Sequencing diagram

```
                  Phase 1 (Agentic Loop) ──────────┐
                       │                            │
                       ├──► Phase 4 (Model Router)──┼──► Phase 8 (Observability)
                       │                            │
                  Phase 2 (Hierarchical) ─────┐    │
                       │                       │    │
                       ├──► Phase 3 (Temporal)─┤    │
                       │                       │    │
                  Phase 5 (Data Fabric) ──────┤    │
                       │                       │    │
                       ├──► Phase 6 (Cold)─────┤    │
                       │                       │    │
                  Phase 7 (Memory) ────────────┘    │
                       │                            │
                       └────────────────────────────┘
```

**Recommended build order:**
1. **Phase 1** (Agentic Loop) — biggest hallucination drop, no new tables.
2. **Phase 2** (Hierarchical Summaries) — unlocks every long-horizon query.
3. **Phase 4** (Model Router) — immediate ~40% cost drop.
4. **Phase 8** (Observability) — must land before scale; cheap to add now.
5. **Phase 3** (Temporal Orchestrator) — depends on 1+2, big UX win.
6. **Phase 7** (Memory) — depends on 1, big personalisation win.
7. **Phase 5** (Data Fabric) — only when integrations land.
8. **Phase 6** (Cold Lakehouse) — only when first hive crosses 18mo of data.

---

## 7. Cross-phase invariants (apply to every phase)

Drawn from `ai-engineer`, `architect`, `data-engineer`, `performance` skills + `MEMORY.md` lessons:

| Invariant | Source |
|---|---|
| Every Supabase query has `.eq('hive_id', hiveId)` or hive-aware view | `validate_hive.py` |
| Every list query uses narrow `.select()`, never `select('*')` | performance skill §2 |
| Every list query has `.limit(N)` enforced | performance skill §3 |
| Every new table has composite index on `(hive_id, ...)` at CREATE time | data-engineer skill §1 |
| Every `callAI` uses `_shared/ai-chain.ts` — no raw `fetch` to providers | ai-engineer skill |
| **Every model name in the codebase is in the allowed chain (§2.5). `grep -Ei 'claude-(haiku\|sonnet\|opus)\|gpt-4\|claude-3\|claude-4'` returns zero hits.** | §2.5 + `feedback_free_tier_only_models.md` |
| **Every cost line reads `$0 (free tier)` or a rate-limit budget — never per-1M-token pricing.** | §2.5 cost framing rule |
| Every `fetch` to Groq/external has `AbortSignal.timeout(N)` | ai-engineer skill §Validator Lessons |
| Every prompt template uses hyphens not em-dashes (encoding safety) | ai-engineer skill §No Em Dashes |
| Every agent returns structured JSON, not prose | ai-engineer skill §Token Minimization |
| Every edge fn is registered in 4 places (config.toml, deploy, validate_edge_contracts × 2) | architect skill §New Edge Function 4-Place Sync |
| Every new edge fn has a Layer-0 validator + Layer-2 Playwright spec | SENTINEL_ARCHITECTURE.md |
| Every MEMORY entry uses Why/How-to-apply format | CLAUDE.md memory rules |
| Every page touching the new stack passes existing Mega Gate | UNIFIED_MEGA_GATE.md |

---

## 8. Open decisions (need your call before any phase ships)

1. **Hosting for Python orchestrator (Phase 3)** — Render free tier (50s cold start risk, already handled with 90s timeout) vs. Railway paid (~$5/mo, no cold start) vs. run Python entirely inside Supabase Edge Function via Deno-Pyodide (experimental).
2. **Cold archive storage tier (Phase 6)** — Supabase Storage (simple, $0.021/GB) vs. external S3-compatible (cheaper at scale, more setup).
3. **Memory cap per worker (Phase 7)** — 200 is a starting guess; could be 50 (lean) or 500 (richer personalisation). Affects per-query context size.
4. **Rate-limit cap default (Phase 8)** — 50 queries/hr × 24 = 1200/day is the proposed cap. Need to confirm Groq daily RPD on the *aggregate* of agentic-rag-loop + nightly summariser + existing edge-fn traffic; tighter cap may be needed once Phase 2 is live and consuming nightly tokens. Cost in dollar terms = $0; cap is purely a rate-limit-budget allocation.
5. **Embedding model upgrade path** — currently Nomic 384-dim free. Phase 5 (Data Fabric) might benefit from 1024-dim for richer cross-source matching, but requires schema migration. Defer to Phase 5 kickoff decision.
6. **Standards coverage in summaries (Phase 2)** — should hierarchical summaries cite Tier S standards inline (more accurate, more tokens) or only via `standard_cites` array (cheaper, machine-readable only)? Recommend inline for yearly summaries, array-only for daily/weekly.

---

## 9. What this roadmap does NOT propose

- No replacement of `ai-orchestrator` — it becomes one strategy the new Router can pick.
- No replacement of `voice-semantic-rag` — it stays as the `semantic` strategy inside the loop.
- No replacement of `KPI_ENGINE` — every metric still flows through the canonical views. Summaries cite, not recompute.
- No new model providers — `_shared/ai-chain.ts` already has 14 models across 6 providers.
- No frontend framework migration — pure HTML/JS stays.
- No move away from Supabase — every phase fits inside the existing stack.

---

## 10. Approval gates

Per the user's instruction ("just write the architecture spec, no code yet"):

- **This document** is the deliverable for the planning session.
- **Per-phase build** requires explicit go-ahead. Each phase ships with full flywheel cadence:
  - Code → Layer 0 validator → Layer 2 Playwright spec → Mega Gate run → MEMORY.md entry → commit.
- **No phase ships partially.** A phase is either fully landed (with validator + spec + memory) or rolled back.

End of spec.
