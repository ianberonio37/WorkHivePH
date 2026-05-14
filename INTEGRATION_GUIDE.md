# Voice Companion Integration Guide (Edge Functions + Python Tools)

**Status**: All edge functions and Python tools are wired. This guide shows the complete integration.

---

## Architecture Overview

```
voice-handler.js (browser)
    ├─ 1. _classifySemanticRoute() → Groq Scout (20 tokens, ~50ms)
    │   └─ route: "platform" | "semantic" | "simple"
    │
    ├─ 2a. IF platform → _invokePlatformScraper()
    │   └─ Calls: /functions/v1/platform-scraper (edge function)
    │       └─ Returns: prose KPI summary (equipment, risk, PM, inventory, adoption)
    │
    ├─ 2b. IF semantic → _invokeRAGAgent()
    │   └─ Calls: /functions/v1/voice-semantic-rag (edge function)
    │       ├─ Step 1: Call /functions/v1/voice-embeddings (embed query)
    │       ├─ Step 2: search_voice_journal_entries() RPC (pgvector search)
    │       └─ Fallback: Time-based query (recency)
    │
    ├─ 3. Build system prompt with:
    │   ├─ routerBlock (router pre-classification)
    │   ├─ platformSection (KPI snapshot)
    │   ├─ ragSection (history context)
    │   ├─ canonicalSection (MTBF/MTTR data)
    │   ├─ memoryBlock (recent turns)
    │   └─ routingHint (unhandled command guidance)
    │
    └─ 4. Call AI with fallback chain:
        ├─ Primary: /functions/v1/voice-model-call (wrapper)
        │   ├─ Scout (Groq) → fastest
        │   ├─ Qwen (Cerebras) → fallback 1
        │   ├─ Mistral (Voyage) → fallback 2
        │   └─ Jina AI → fallback 3
        │
        └─ Fallback: Direct Groq call (if edge function down)
```

---

## File Locations

### Edge Functions

| Function | Path | Wraps | Purpose |
|----------|------|-------|---------|
| platform-scraper | `supabase/functions/platform-scraper/index.ts` | `tools/platform_scraper_agent.py` | KPI fetch (equipment, risk, PM, inventory, adoption) |
| voice-semantic-rag | `supabase/functions/voice-semantic-rag/index.ts` | `tools/rag_agent.py` | Voice journal search (recency + semantic) |
| voice-embeddings | `supabase/functions/voice-embeddings/index.ts` | `tools/embedding_helper.py` | Jina API embedding generation |
| voice-model-call | `supabase/functions/voice-model-call/index.ts` | `tools/model_orchestrator.py` | Multi-model with fallback chain |

### Python Tools

| Tool | Path | Called By | Purpose |
|------|------|-----------|---------|
| platform_scraper_agent.py | `tools/` | platform-scraper edge fn | KPI aggregation |
| rag_agent.py | `tools/` | voice-semantic-rag edge fn | Voice journal fetch |
| semantic_router.py | `tools/` | _classifySemanticRoute (JS) | Intent classification (20 tokens) |
| embedding_helper.py | `tools/` | voice-embeddings edge fn | Jina API + local embedding fallback |
| model_orchestrator.py | `tools/` | voice-model-call edge fn | Model switching + fallback chain |

### Browser Integration

| File | Function | Calls | Purpose |
|------|----------|-------|---------|
| voice-handler.js | `_classifySemanticRoute()` | Groq Scout (direct) | Route decision |
| voice-handler.js | `_invokePlatformScraper()` | platform-scraper edge fn | KPI data |
| voice-handler.js | `_invokeRAGAgent()` | voice-semantic-rag edge fn | History context |
| voice-handler.js | (LLM call) | voice-model-call edge fn OR Groq direct | Conversational response |

---

## Deployment Checklist

### Pre-Deployment

- [ ] All edge functions are ready:
  - [ ] `supabase/functions/platform-scraper/index.ts` ✓
  - [ ] `supabase/functions/voice-semantic-rag/index.ts` ✓ (updated)
  - [ ] `supabase/functions/voice-embeddings/index.ts` ✓
  - [ ] `supabase/functions/voice-model-call/index.ts` ✓

- [ ] Python tools are in place:
  - [ ] `tools/platform_scraper_agent.py` ✓
  - [ ] `tools/rag_agent.py` ✓
  - [ ] `tools/semantic_router.py` ✓
  - [ ] `tools/embedding_helper.py` ✓
  - [ ] `tools/model_orchestrator.py` ✓

- [ ] voice-handler.js is updated:
  - [ ] `_invokePlatformScraper()` calls edge function ✓
  - [ ] `_invokeRAGAgent()` calls edge function ✓
  - [ ] `_generateFallbackReply()` added (Phase 3) ✓

### Deploy Edge Functions

```bash
# Deploy all four edge functions
supabase functions deploy platform-scraper
supabase functions deploy voice-semantic-rag
supabase functions deploy voice-embeddings
supabase functions deploy voice-model-call

# Verify they're live
supabase functions list
# Should show all 4 as "active"
```

### Configure Environment

```bash
# Copy template
cp .env.voice-companion .env

# Fill in API keys:
# - GROQ_API_KEY (required for Phase 1-2)
# - CEREBRAS_API_KEY (optional, fallback)
# - SAMBANOVA_API_KEY (optional, fallback)
# - JINA_API_KEY (optional, Phase 1.5)

# Verify keys are loaded
echo $GROQ_API_KEY
# Should output your key, not empty
```

### Phase 1.5 Setup (Optional)

**Only if you want semantic embeddings enabled**:

```bash
# 1. Get JINA_API_KEY and add to .env

# 2. Deploy embeddings edge function
supabase functions deploy voice-embeddings

# 3. Backfill existing voice_journal_entries with embeddings
# (See PHASE_1_5_EMBEDDINGS_SETUP.md for detailed instructions)
python tools/backfill_voice_embeddings.py

# 4. Redeploy voice-semantic-rag to use embeddings
supabase functions deploy voice-semantic-rag
```

### Test Integration

**1. Test platform-scraper edge function**:
```bash
curl -X POST http://localhost:54321/functions/v1/platform-scraper \
  -H "Authorization: Bearer YOUR_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{"hive_id": "test-hive-id", "worker_name": "test"}'

# Should return: { "summary": "Equipment: 3 running...", "timestamp": "...", "hive_id": "..." }
```

**2. Test voice-semantic-rag edge function**:
```bash
curl -X POST http://localhost:54321/functions/v1/voice-semantic-rag \
  -H "Authorization: Bearer YOUR_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{"auth_uid": "YOUR_UUID", "query_text": "Why does pump fail?", "limit": 5}'

# Should return: { "results": [ ... ], "method": "semantic" or "recency", "count": N }
```

**3. Test voice-model-call edge function**:
```bash
curl -X POST http://localhost:54321/functions/v1/voice-model-call \
  -H "Authorization: Bearer YOUR_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "What is 2+2?"}
    ],
    "model_strategy": "scout",
    "max_tokens": 50
  }'

# Should return: { "answer": "4", "model_used": "scout", "latency_ms": N }
```

**4. Test voice-embeddings edge function**:
```bash
curl -X POST http://localhost:54321/functions/v1/voice-embeddings \
  -H "Authorization: Bearer YOUR_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{"texts": ["Hello world", "How is it going?"]}'

# Should return: { "embeddings": [[...], [...]], "method": "jina", "count": 2 }
```

---

## Call Flow Walkthrough

**Scenario**: Worker asks "Why does the pump keep failing?" on alert-hub page

### 1. Semantic Router Classification (20 tokens, ~50ms)

```javascript
// voice-handler.js: _classifySemanticRoute
// Calls Groq Scout (free tier, no charge against main 280-token limit)

Input: "Why does the pump keep failing?"
↓
Groq Scout (20 tokens)
↓
Output: { route: "semantic", confidence: 0.9, reasoning: "Why question, needs analysis" }
```

### 2. Invoke Appropriate Agents (Parallel)

```javascript
// Since route === "semantic", call:
Promise.all([
  _fetchRecentMemory(db, ctx.worker_name),        // Last 5 turns in DB/session
  _invokeRAGAgent(db, ctx.worker_name, ..., "Why does..."),  // Voice journal
  _fetchCanonicalData(db, hive_id, {...})         // MTBF/MTTR (if data intent)
])
```

#### 2a. _invokeRAGAgent flow:

```javascript
// voice-handler.js
await fetch(SUPABASE_URL + '/functions/v1/voice-semantic-rag', {
  auth_uid: ctx.user.id,
  query_text: "Why does the pump keep failing?",
  limit: 5
})

↓ Edge function (voice-semantic-rag/index.ts)

// Step 1: Get embedding for query
await fetch(SUPABASE_URL + '/functions/v1/voice-embeddings', {
  texts: ["Why does the pump keep failing?"]
})
→ Returns: [embedding_vector_384dim]

// Step 2: Search voice_journal_entries via pgvector
db.rpc('search_voice_journal_entries', {
  query_embedding: [384-dim vector],
  match_auth_uid: ctx.user.id,
  match_count: 5
})
→ Returns: [
  { transcript: "pump cavitation?", reply: "...", similarity: 0.82 },
  { transcript: "pump vibration", reply: "...", similarity: 0.78 },
  ...
]

// Fallback if no embeddings:
db.from('voice_journal_entries')
  .select(...)
  .order('created_at', desc)
  .limit(5)
→ Returns: [recent entries]

↓ Back to voice-handler.js
ragContext = "Your voice history (semantic match):\nAt 14:23 (match: 82%):\nYou: pump cavitation?\n..."
```

### 3. Build System Prompt with All Context

```javascript
// voice-handler.js: _buildVoiceSystemPrompt
const system = 
  personaBlock +
  routerBlock +           // "Router classified: semantic (90%)"
  routingBlock +          // (empty, since semantic is handled)
  memoryBlock +           // "Recent turns: ..."
  canonicalSection +      // (empty, not a data question)
  platformSection +       // (empty, route=semantic not platform)
  ragSection +            // "Your voice history (semantic match): pump cavitation..."
  HARD_RULES

// Result: 1200-1500 tokens total
```

### 4. Call LLM with Fallback Chain

```javascript
// Option A: Use voice-model-call edge function (Phase 2, optional)
await fetch(SUPABASE_URL + '/functions/v1/voice-model-call', {
  messages: [ { role: 'system', content: system }, ... ],
  model_strategy: 'scout',
  max_tokens: 280
})
→ Tries Scout → Qwen → SambaNova until one succeeds
→ Returns: { answer: "Pump cavitation happens when...", model_used: "scout", latency_ms: 150 }

// Option B: Direct Groq call (Phase 1-2, still supported)
await fetch('https://api.groq.com/openai/v1/chat/completions', {
  model: 'meta-llama/llama-4-scout-17b-16e-instruct',
  messages: [ ... ],
  max_tokens: 280
})
→ Returns: { choices: [{ message: { content: "..." } }] }
```

### 5. Save & Speak Reply

```javascript
_renderReplyBubble(answer, persona)           // Show in UI
speakPersona(answer, { persona: 'james' })    // TTS (browser SpeechSynthesis)
_appendSessionTurn(transcript, answer)        // Session memory (anon users)
_saveJournalTurn(db, ctx, transcript, answer) // Durable DB save (RLS-gated)
```

---

## Error Handling

**If platform-scraper fails** → Returns empty string, system prompt has no platformSection
- Model continues with other context (memory, canonical, routing hint)
- User still gets a good reply, just without KPI snapshot

**If voice-semantic-rag fails** → Falls back to recency-based query
- `method` field in response shows "recency" instead of "semantic"
- Still returns relevant history, just 30-day window instead of 2-year semantic match

**If voice-model-call fails** → Fallback to direct Groq call
- voice-handler.js catches error, retries with direct API
- Or returns error recovery message (Phase 3: _generateFallbackReply)

**If all LLM models fail** (rate limited / down) → Offline reply
- Phase 3: `_generateFallbackReply` generates intent-aware message
- Example: "I'm offline right now, but check Analytics for the exact MTBF you need."
- TTS still plays the reply (no voice = frustration)
- Transcript saved even on error

---

## Monitoring & Logging

### Edge Function Logs
```bash
# See real-time logs
supabase functions logs platform-scraper
supabase functions logs voice-semantic-rag
supabase functions logs voice-embeddings
supabase functions logs voice-model-call
```

### API Usage Metrics
```sql
-- Query for LLM call patterns (Groq Scout)
SELECT 
  DATE(created_at) as date,
  COUNT(*) as total_calls,
  AVG(latency_ms) as avg_latency_ms
FROM ai_cost_log  -- (if enabled)
WHERE model = 'meta-llama/llama-4-scout-17b-16e-instruct'
GROUP BY 1
ORDER BY 1 DESC;
```

### Free-Tier Rate Limit Monitoring
```bash
# Groq: 9,000 requests/day, 128 requests/minute
# Cerebras: 25 requests/minute
# SambaNova: ~50 requests/minute
# Jina: 8,000 requests/month

# Check today's Groq usage
# (Would query Groq dashboard or log from edge function)
```

---

## Production Readiness Checklist

**Code**:
- [ ] All edge functions deployed and tested
- [ ] Python tools integrated correctly
- [ ] voice-handler.js calls edge functions (not direct API)
- [ ] Error handling covers all edge function failures

**Configuration**:
- [ ] GROQ_API_KEY configured ✓
- [ ] CEREBRAS_API_KEY configured (optional)
- [ ] SAMBANOVA_API_KEY configured (optional)
- [ ] JINA_API_KEY configured (optional, Phase 1.5 only)

**Database**:
- [ ] voice_journal_entries table exists with embeddings column
- [ ] search_voice_journal_entries() RPC available
- [ ] ivfflat index on embedding column

**Monitoring**:
- [ ] Edge function logs accessible
- [ ] Jina API usage tracked (free tier: 8k/month)
- [ ] Fallback chain tested (Scout → Qwen → SambaNova)

**Testing**:
- [ ] Test scenarios pass:
  - [ ] Platform data question (test platform-scraper)
  - [ ] Analysis question (test voice-semantic-rag)
  - [ ] Simple greeting (test simple route)
  - [ ] Offline scenario (test Phase 3 fallback)

---

## Next Steps

1. **Deploy edge functions**: `supabase functions deploy` all 4
2. **Configure API keys**: Fill in `.env` with Groq + optional Cerebras/SambaNova/Jina
3. **Test integration**: Run curl tests from section above
4. **Phase 1.5 (optional)**: Get Jina key, backfill embeddings, redeploy voice-semantic-rag
5. **Go live**: Push voice-handler.js changes and monitor logs

---

**Questions?**

- **Which edge functions are required?** Only `platform-scraper` and `voice-semantic-rag` (Phase 1). `voice-model-call` and `voice-embeddings` are optional (Phase 2 + 1.5).
- **Can I use only Groq (no fallback)?** Yes, remove fallback chain logic from voice-model-call or skip it entirely and call Groq directly.
- **What if Jina API is down?** voice-semantic-rag falls back to recency-based search automatically.
- **How do I monitor free-tier usage?** Check Groq/Cerebras/SambaNova dashboards or edge function logs.

