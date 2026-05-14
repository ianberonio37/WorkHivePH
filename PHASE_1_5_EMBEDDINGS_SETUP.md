# Phase 1.5 Setup Guide: Semantic RAG with pgvector Embeddings

**Status**: Optional phase. Voice companion works without this (recency-based RAG is fallback).  
**Time to Deploy**: 30 min (embeddings setup) + 1 hour (backfill job)  
**Cost**: $0 (Jina free tier: 8k requests/month)

---

## What Phase 1.5 Adds

Current (Phase 1): RAG agent fetches **last 5 turns in last 30 days** (time-based)
- Pro: Fast, always returns something
- Con: Misses semantically similar entries from months ago

Phase 1.5: **Semantic search via pgvector** (similarity-based)
- Example: "Why does pump fail?" now finds "pump cavitation" from 2 months ago
- 2-year history without context inflation (top 5 matches by similarity)
- Fallback: still uses time-based if embedding fails

---

## Step 1: Get Jina API Key (Free Tier)

**Option A: Jina AI (Recommended)**

1. Go to https://jina.ai/embeddings
2. Sign up (free tier: 8,000 requests/month, 384-dimensional)
3. Copy API key from https://jina.ai/account

**Option B: Local Embedding (Advanced)**

Use sentence-transformers instead of Jina (requires Python):
```bash
pip install sentence-transformers
# Then embedding_helper.py falls back automatically
```

---

## Step 2: Configure Environment

Add to `.env`:
```bash
JINA_API_KEY=jina_YOUR_KEY_HERE
```

Or copy the template:
```bash
cp .env.voice-companion .env
# Edit .env and fill in JINA_API_KEY
```

Test the connection:
```bash
python tools/embedding_helper.py
# Should output embedding dimensions (384 for Jina)
```

---

## Step 3: Deploy Edge Functions

Deploy the three edge functions:

```bash
# 1. Embeddings endpoint (Phase 1.5)
supabase functions deploy voice-embeddings

# 2. Updated semantic RAG (Phase 1 + 1.5)
supabase functions deploy voice-semantic-rag

# 3. Model orchestrator (Phase 2, optional)
supabase functions deploy voice-model-call

# 4. Platform scraper (Phase 1)
supabase functions deploy platform-scraper
```

Verify deployment:
```bash
supabase functions list
# Should show all 4 functions with status "active"
```

---

## Step 4: Backfill Existing Entries with Embeddings

The database schema already has:
- `voice_journal_entries.embedding` column (vector(384))
- `search_voice_journal_entries()` RPC for semantic search
- ivfflat index on embedding column

But existing entries don't have embeddings yet.

**Option A: Batch Job (Recommended)**

Create a migration to backfill:
```sql
-- supabase/migrations/20260514000000_backfill_voice_embeddings.sql
-- Call embedding edge function for all entries without embeddings
-- (Requires running from Python, not pure SQL)
```

**Option B: Python Backfill Script**

```bash
# From project root:
python tools/embedding_helper.py < tools/backfill_voice_embeddings.py
```

Create `tools/backfill_voice_embeddings.py`:
```python
#!/usr/bin/env python3
import os
from supabase import create_client
from embedding_helper import embed_batch

db = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

# Fetch all entries without embeddings
entries = db.from_("voice_journal_entries").select("id, transcript").is_("embedding", "null").execute()

if not entries.data:
    print("All entries already have embeddings")
    exit(0)

# Embed transcripts in batches of 25
for i in range(0, len(entries.data), 25):
    batch = entries.data[i : i + 25]
    transcripts = [e["transcript"] for e in batch]
    embeddings = embed_batch(transcripts)

    # Update entries with embeddings
    for entry, embedding in zip(batch, embeddings):
        if embedding:
            db.from_("voice_journal_entries").update(
                {"embedding": embedding}
            ).eq("id", entry["id"]).execute()

    print(f"Embedded {min(i + 25, len(entries.data))}/{len(entries.data)}")

print("Backfill complete!")
```

**Cost**: 8k free requests/month from Jina.
- Backfill 2 years of data (e.g., 10,000 entries) = 10k requests
- New entries (~100/month) = 100 requests/month
- Total: Well within free tier

---

## Step 5: Configure ai-gateway for On-Insert Embedding

When a worker saves a voice journal entry, ai-gateway should:
1. Get the transcript
2. Call `voice-embeddings` edge function
3. Store the embedding in the database

**Update ai-gateway edge function**:

```typescript
// supabase/functions/ai-gateway/index.ts (simplified)

if (req_type === 'voice-journal-insert') {
  const { transcript, auth_uid } = body;
  
  // Get embedding for semantic search
  const embeddingResp = await fetch(
    `${SUPABASE_URL}/functions/v1/voice-embeddings`,
    {
      method: 'POST',
      headers: { /* auth */ },
      body: JSON.stringify({ texts: [transcript] }),
    }
  );
  
  const { embeddings } = await embeddingResp.json();
  const embedding = embeddings[0]; // nullable
  
  // Insert with embedding
  await db.from('voice_journal_entries').insert({
    auth_uid,
    transcript,
    embedding, // Now included
    // ...
  });
}
```

---

## Step 6: Verify Semantic Search Works

Test the semantic RAG edge function:

```bash
# Call the edge function with a test query
curl -X POST http://localhost:54321/functions/v1/voice-semantic-rag \
  -H "Authorization: Bearer YOUR_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "auth_uid": "YOUR_AUTH_UID",
    "query_text": "Why does the pump fail?",
    "limit": 5
  }'

# Response should include:
# - "method": "semantic" (if embeddings exist) or "recency" (fallback)
# - "results": [ { transcript, reply, created_at, similarity }, ... ]
# - "count": number of results
```

Expected behavior:
- First run: `"method": "recency"` (no embeddings yet, using time-based fallback)
- After backfill: `"method": "semantic"` (returns top 5 by similarity)

---

## Troubleshooting

**Problem**: `"method": "recency"` after backfill

**Causes**:
1. JINA_API_KEY not set → voice-embeddings returns null
2. Backfill didn't complete → no embeddings in DB
3. voice-semantic-rag edge function not redeployed

**Fix**:
```bash
# 1. Verify JINA_API_KEY
echo $JINA_API_KEY

# 2. Check embeddings in database
SELECT COUNT(*) as with_embedding, COUNT(*) FILTER (WHERE embedding IS NULL) as without
FROM voice_journal_entries;
# Should show with_embedding > 0

# 3. Redeploy edge function
supabase functions deploy voice-semantic-rag
```

**Problem**: `"method": "semantic"` but results not relevant

**Cause**: Query embedding distance metric (cosine vs Euclidean)

**Fix**: Update search function in schema to use correct metric:
```sql
-- Check which metric is used in search_voice_journal_entries RPC
-- Should be: 1 - (vje.embedding <=> query_embedding) AS similarity
-- (<=>, the spaceship operator, means cosine distance in ivfflat)
```

---

## Monitoring Phase 1.5 Usage

**Jina API rate limits**:
- Free tier: 8,000 requests/month
- With 100 new voice entries/month = 100 requests (well within limit)

**Monitor daily usage**:
```python
# Check Jina dashboard: https://jina.ai/account
# Should see ~3-4 requests/day (new entries + edge function tests)
```

**Monitor embedding quality**:
```sql
-- Check similarity scores of returned results
SELECT 
  similarity,
  COUNT(*) as count
FROM (
  SELECT 1 - (embedding <=> query_embedding) as similarity
  FROM voice_journal_entries
  -- (would be in search function)
) GROUP BY ROUND(similarity, 1)
ORDER BY similarity DESC;

-- Healthy distribution: most results 0.6-0.9 similarity
```

---

## When to Enable Phase 1.5

**Enable Now If**:
- Workers frequently ask follow-up questions ("how do I fix this?" after "why does this fail?")
- You want 2-year history without inflating context
- You have JINA_API_KEY available

**Defer If**:
- Recency-based RAG (Phase 1) is meeting user needs
- Don't have JINA_API_KEY yet
- Want to measure Phase 1 impact first, add Phase 1.5 later

Deferring Phase 1.5 is fine. Phase 1 RAG (last 5 turns, 30 days) is useful for most scenarios.

---

## Cost Breakdown

| Phase | Service | Requests/Month | Free Tier | Cost |
|-------|---------|---|---|---|
| 1 | Groq Scout (LLM) | 3,000 | 270,000 | $0 |
| 1.5 | Jina AI (embeddings) | 100 | 8,000 | $0 |
| 1.5 | Search (pgvector, local) | unlimited | - | $0 |
| **Total** | | | | **$0** |

---

## Next Steps After Phase 1.5

Once semantic embeddings are live, consider:

1. **Embedding quality monitoring**: Track similarity scores of returned results
2. **Backfill tuning**: Adjust ivfflat `lists=50` parameter if performance degrades
3. **2-year retention**: Archive old entries (optional, voice_journal_entries already has no TTL)
4. **Custom embedding model**: Replace Jina with fine-tuned model for maintenance domain (future)

---

**Questions?**

- **How do I know if semantic search is working?** Check the `method` field in response: "semantic" = working, "recency" = fallback
- **Can I use local embeddings instead of Jina?** Yes, install sentence-transformers; embedding_helper.py falls back automatically
- **Will this affect performance?** No, embedding + search happens in parallel with AI call (Promise.all)
- **Can I disable Phase 1.5 later?** Yes, just stop calling voice-embeddings; voice-semantic-rag falls back to recency

