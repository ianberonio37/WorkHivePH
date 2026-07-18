---
name: doc-INTEGRATION_GUIDE
type: doc
source: file:INTEGRATION_GUIDE.md
source_sha: 3676ff0b110d1c3d
last_verified: 2026-07-13
supersedes: null
---
## doc · INTEGRATION_GUIDE

**Status**: All edge functions and Python tools are wired. This guide shows the complete integration.

**Sections:** Voice Companion Integration Guide (Edge Functions + Python Tools) · Architecture Overview · File Locations · Edge Functions · Python Tools · Browser Integration · Deployment Checklist · Pre-Deployment · Deploy Edge Functions · Deploy all four edge functions · Verify they're live · Should show all 4 as "active" · Configure Environment · Copy template · Fill in API keys: · - GROQ_API_KEY (required for Phase 1-2) · - CEREBRAS_API_KEY (optional, fallback) · - SAMBANOVA_API_KEY (optional, fallback) · - JINA_API_KEY (optional, Phase 1.5) · Verify keys are loaded · Should output your key, not empty · Phase 1.5 Setup (Optional) · 1. Get JINA_API_KEY and add to .env · 2. Deploy embeddings edge function · 3. Backfill existing voice_journal_entries with embeddings · (See PHASE_1_5_EMBEDDINGS_SETUP.md for detailed instructions) · 4. Redeploy voice-semantic-rag to use embeddings · Test Integration · Should return: { "summary": "Equipment: 3 running...", "timestamp": "...", "hive_id": "..." } · Should return: { "results": [ ... ], "method": "semantic" or "recency", "count": N }

(Deep source: `file:INTEGRATION_GUIDE.md` — retrieve this TOC to know WHICH section to read.)
