---
name: doc-AGENTIC_RAG_DEPLOY_RUNBOOK
type: doc
source: file:AGENTIC_RAG_DEPLOY_RUNBOOK.md
source_sha: 9ff76695f8ef2417
last_verified: 2026-07-13
supersedes: null
---
## doc · AGENTIC_RAG_DEPLOY_RUNBOOK

**You must run this against your live Supabase project.** All 8 phases + the integration wave (items 2/3/4/6) are merged to disk and validator-locked (20+16+9+10+17+12+9+10 = 113/113 L0 ratchets green

**Sections:** Agentic RAG Deploy + Backfill Runbook · Step 1 — Apply the 4 new migrations (Item 1, part 1) · From the project root: · Step 2 — Deploy the 6 new edge functions (Item 1, part 2) · Phase 1 — happy path (replace HIVE_ID) · Step 3 — Backfill hierarchical summaries (Item 5) · Dry-run preview — see exactly what will be invoked, no calls made · Production backfill (default: last 5 years + 4 quarters + 12 months per hive) · Or scope to specific hives · Step 4 — Smoke-test the integration wave · Item 2 + 3: long-horizon query should auto-delegate to temporal-rag-orchestrator · Item 4: ask one question, then ask "what's my preference?" in a fresh session — answer should reference any memory captured · wait 5 seconds for the fire-and-forget memory store · Item 6: voice-handler will auto-route on long-horizon questions. Open voice-journal.html, ask: · "compare last 5 years of failures on the chiller" · Status should read "<persona> (agentic-RAG) says:" instead of the default "<persona> says:". · Step 5 — Run validators against deployed state (optional but recommended) · Or the master sweep: · Rollback plan · What's next after deploy

(Deep source: `file:AGENTIC_RAG_DEPLOY_RUNBOOK.md` — retrieve this TOC to know WHICH section to read.)
