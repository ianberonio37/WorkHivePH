# Agentic RAG Deploy + Backfill Runbook

**You must run this against your live Supabase project.** All 8 phases + the integration wave (items 2/3/4/6) are merged to disk and validator-locked (20+16+9+10+17+12+9+10 = 113/113 L0 ratchets green). What remains is operational: push migrations, deploy edge functions, backfill summaries, smoke-test.

---

## Step 1 — Apply the 4 new migrations (Item 1, part 1)

```powershell
# From the project root:
npx supabase db push
```

This applies, in order:
- `20260521120000_agentic_rag_traces.sql` (Phase 1)
- `20260521121000_canonical_period_summaries.sql` (Phase 2)
- `20260521122000_agent_episodic_memory.sql` (Phase 7)
- `20260521123000_unified_events.sql` (Phase 5)

**Expected:** 4 new tables, all with RLS enabled, service-role-only writes, hive-member reads. If `npx supabase db push` errors with "include all flag required," check migration timestamps for collision (none should exist — all 4 use unique `2026052112XXXX` slots).

---

## Step 2 — Deploy the 6 new edge functions (Item 1, part 2)

```powershell
.\deploy-functions.ps1
```

The script deploys all WorkHive edge functions; the 6 new lines are:
- `agentic-rag-loop`        — Phase 1
- `hierarchical-summarizer` — Phase 2
- `temporal-rag-orchestrator` — Phase 3
- `agent-memory-store`     — Phase 7
- `data-fabric-normalizer` — Phase 5
- `cold-archive-query`     — Phase 6

**Verify deploy succeeded** with curl against each:

```powershell
# Phase 1 — happy path (replace HIVE_ID)
curl -X POST "$env:SUPABASE_URL/functions/v1/agentic-rag-loop" `
  -H "Authorization: Bearer $env:SUPABASE_ANON_KEY" `
  -H "Content-Type: application/json" `
  -d '{"question":"latest entry","hive_id":"<HIVE_ID>","worker_name":"<WORKER>"}'
```

Expected response shape: `{ answer, citations, trace_id, route, retries, grader_passed, checker_passed, total_tokens, latency_ms, remaining }`.

If you get `429`, the per-hive rate limit (50/hr) is engaged from earlier testing — wait or use a different hive. If `500`, run the curl with no `--silent` and read the body; the most common cause is missing env vars (`GROQ_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`).

---

## Step 3 — Backfill hierarchical summaries (Item 5)

Phase 1's new Lane C reads `canonical_period_summaries`. The table starts empty after Step 1. Backfill so Lane C + Phase 3 (temporal-rag-orchestrator) have data.

```powershell
# Dry-run preview — see exactly what will be invoked, no calls made
python tools/backfill_hierarchical_summaries.py

# Production backfill (default: last 5 years + 4 quarters + 12 months per hive)
$env:SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
$env:SUPABASE_SERVICE_ROLE_KEY = "<service role key>"
python tools/backfill_hierarchical_summaries.py --commit

# Or scope to specific hives
python tools/backfill_hierarchical_summaries.py --hive-ids "<UUID1>,<UUID2>" --commit
```

**Cost / budget:** every call is ~500 tokens in + ~200 out on Scout-17B via `narrative_report` taskProfile. Default plan = (5 yearly + 4 quarterly + 12 monthly = 21 calls) per hive. At 50 hives × 21 calls × 700 tokens ≈ 735K tokens total. Well inside Groq's daily free-tier window. The `--sleep-ms 400` default keeps you under TPM peaks.

**Verify the backfill landed:**

```sql
-- In Supabase SQL editor
SELECT level, count(*), max(period_end)
FROM canonical_period_summaries
GROUP BY level
ORDER BY level;
```

Expected: rows for level in (year, quarter, month), max(period_end) recent.

---

## Step 4 — Smoke-test the integration wave

These tests exercise items 2 + 3 + 4 + 6 end to end:

```powershell
# Item 2 + 3: long-horizon query should auto-delegate to temporal-rag-orchestrator
curl -X POST "$env:SUPABASE_URL/functions/v1/agentic-rag-loop" `
  -H "Authorization: Bearer $env:SUPABASE_ANON_KEY" `
  -H "Content-Type: application/json" `
  -d '{"question":"compare failures across 2022 vs 2023 vs 2024 vs 2025 on P-203","hive_id":"<HIVE_ID>","worker_name":"<WORKER>"}'
```

Expected: `route: "temporal"`, `delegated: true`, `per_period: [...]`. If `delegated: false`, the Router didn't extract a time scope > 180 days — check the `reasoning` field in the trace.

```powershell
# Item 4: ask one question, then ask "what's my preference?" in a fresh session — answer should reference any memory captured
curl ... -d '{"question":"I prefer Tagalog answers","hive_id":"<HIVE_ID>","worker_name":"<WORKER>"}'
# wait 5 seconds for the fire-and-forget memory store
curl ... -d '{"question":"what do you know about me?","hive_id":"<HIVE_ID>","worker_name":"<WORKER>"}'
```

Expected: second call's answer mentions the preference (the recall stage pulled it from `agent_episodic_memory`).

```sql
-- Verify memories were stored
SELECT memory_type, content, importance, use_count FROM agent_episodic_memory
WHERE worker_name = '<WORKER>'
ORDER BY created_at DESC LIMIT 10;
```

```powershell
# Item 6: voice-handler will auto-route on long-horizon questions. Open voice-journal.html, ask:
# "compare last 5 years of failures on the chiller"
# Status should read "<persona> (agentic-RAG) says:" instead of the default "<persona> says:".
```

---

## Step 5 — Run validators against deployed state (optional but recommended)

```powershell
python validate_agentic_rag_loop.py       # 20/20 PASS expected
python validate_hierarchical_summaries.py # 16/16 PASS
python validate_model_router.py           # 9/9 PASS
python validate_agentic_rag_observability.py # 10/10 PASS
python validate_temporal_orchestrator.py  # 17/17 PASS
python validate_agent_memory_store.py     # 12/12 PASS
python validate_data_fabric.py            # 9/9 PASS
python validate_cold_archive.py           # 10/10 PASS

# Or the master sweep:
python run_platform_checks.py --fast
```

---

## Rollback plan

The integration wave is additive — none of the existing 50+ edge functions, the existing voice-handler path, or any existing table was modified destructively. To roll back any single piece:

| Piece | Roll back by |
|---|---|
| Item 2 (Lane C) | Remove the `lookupHierarchicalSummaries` call inside `retrieverStage` in `agentic-rag-loop/index.ts`. Lanes A+B continue working. |
| Item 3 (temporal delegate) | Remove the `if (router.parsed.route === "temporal" && ...)` block in the server entry. Loop falls back to standard flow on temporal queries. |
| Item 4 (memory) | Remove `recallMemories` call before Router + `extractAndStoreMemories` call after trace write. Generator's `memoryBlock` param is optional. |
| Item 6 (voice-handler opt-in) | Remove the `if (_isLongHorizonQuestion(transcript)) { ... }` block above the ai-gateway POST. ai-gateway path runs as before. |
| All 6 edge functions | Comment out lines in `deploy-functions.ps1`, redeploy. Tables stay (RLS blocks writes; safe to leave). |

---

## What's next after deploy

Once everything is deployed and backfilled, the next priorities (in order):

1. **Watch `agentic-rag-observability.html`** for the first 2-3 days. Look for: hallucination rate < 5%, retry rate < 15%, p95 latency < 8s per route.
2. **Tune `_LONG_HORIZON_RE` in voice-handler.js** if real workers' phrasing falls outside the heuristic. Add Tagalog/Cebuano variants as they surface in traces.
3. **Phase 7 "what do you know about me" view** (Option B from the dashboards discussion) — read-only memory transparency for PDPA compliance.
4. **pg_cron schedule for hierarchical-summarizer** — once backfill proves stable, add a daily cron to keep summaries fresh without manual runs.
5. **Phase 5 Lane D wire-in** — when first SAP/Maximo integration lands, add `unified_events` as a fourth retriever lane.
