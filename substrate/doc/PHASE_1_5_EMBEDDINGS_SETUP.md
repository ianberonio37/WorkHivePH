---
name: doc-PHASE_1_5_EMBEDDINGS_SETUP
type: doc
source: file:PHASE_1_5_EMBEDDINGS_SETUP.md
source_sha: 60f8ddfce6ada8b7
last_verified: 2026-07-13
supersedes: null
---
## doc · PHASE_1_5_EMBEDDINGS_SETUP

**Status**: Optional phase. Voice companion works without this (recency-based RAG is fallback).

**Sections:** Phase 1.5 Setup Guide: Semantic RAG with pgvector Embeddings · What Phase 1.5 Adds · Step 1: Get Jina API Key (Free Tier) · Then embedding_helper.py falls back automatically · Step 2: Configure Environment · Edit .env and fill in JINA_API_KEY · Should output embedding dimensions (384 for Jina) · Step 3: Deploy Edge Functions · 1. Embeddings endpoint (Phase 1.5) · 2. Updated semantic RAG (Phase 1 + 1.5) · 3. Model orchestrator (Phase 2, optional) · 4. Platform scraper (Phase 1) · Should show all 4 functions with status "active" · Step 4: Backfill Existing Entries with Embeddings · From project root: · Fetch all entries without embeddings · Embed transcripts in batches of 25 · Step 5: Configure ai-gateway for On-Insert Embedding · Step 6: Verify Semantic Search Works · Call the edge function with a test query · Response should include: · - "method": "semantic" (if embeddings exist) or "recency" (fallback) · - "results": [ { transcript, reply, created_at, similarity }, ... ] · - "count": number of results · Troubleshooting · 1. Verify JINA_API_KEY · 2. Check embeddings in database · Should show with_embedding > 0 · 3. Redeploy edge function · Monitoring Phase 1.5 Usage

(Deep source: `file:PHASE_1_5_EMBEDDINGS_SETUP.md` — retrieve this TOC to know WHICH section to read.)
