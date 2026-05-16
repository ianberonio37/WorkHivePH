# Voice Companion (Rosa/James) — 11-Phase Walkthrough Guide

## Session Setup

**Location:** WorkHive Tester (127.0.0.1:5000)  
**Prerequisites:**
- Local Supabase running (docker ps | grep supabase_edge_runtime)
- Flask seeder running (test-data-seeder/app.py)
- Azure Speech Key set or browser SpeechSynthesis enabled
- Persona: Rosa (female) or James (male) selected

**Start fresh:**
```bash
# Reset all seeded data
POST /reset → drops all voice tables, auth users, clears caches
# Re-seed test data
POST /seed → populates hives, workers, equipment, PMs, inventory, logbook entries
```

---

## Phase 1: Multi-Agent Orchestrator (Platform Snapshot + RAG + Scraper)

**What Rosa/James does:**
- Fetches 12 canonical truth views in parallel (KPIs, equipment, risk, PM, inventory, schedule, skills, etc.)
- Calls platform scraper for real-time KPI aggregation
- Queries semantic RAG for historical patterns
- Builds single system prompt with ALL platform context

**Test Cases:**

### 1.1 Full Platform Awareness (KPI Query)
```
User: "What's our MTBF today?"
Rosa should: 
  ✓ See platform snapshot with "MTBF avg=45.2 days" 
  ✓ NOT say "I don't have that data" or "check Analytics"
  ✓ Paraphrase naturally: "Your MTBF is holding at 45 days"
```

### 1.2 Equipment Breakdown
```
User: "How many critical assets do we have?"
Rosa should:
  ✓ From snapshot: "Equipment (15 assets): 3 critical, 8 standard, 4 low-priority"
  ✓ Reference the actual counts from platform
```

### 1.3 Multi-Intent (Risk + PM)
```
User: "Tell me about my top risks and overdue PMs"
Rosa should:
  ✓ Surface both risk summary + PM compliance in one response
  ✓ Show "Top risk assets: [names + risk scores]" + "Stale PMs: [count]"
```

### 1.4 Semantic Depth (Why question)
```
User: "Why are my compressor failures increasing?"
Rosa should:
  ✓ If RAG has historical patterns: reference them ("past 60 days show correlation with...")
  ✓ If not: offer practical maintenance angle ("Check seal wear on intake side")
```

---

## Phase 2: Session Memory & Turn Tracking

**What Rosa/James does:**
- Stores every turn (question + answer) in agent_memory table
- Deduplicates by message hash (first 80 chars)
- Enables "What did we just discuss?" continuity

**Test Cases:**

### 2.1 Turn Continuity
```
Turn 1:
User: "What's my MTTR this month?"
Rosa: "Your MTTR is 3.2 hours. That's up 0.5 hours from last month."

Turn 2:
User: "How can I improve it?"
Rosa: ✓ References prior context: "Since your MTTR is 3.2 hours, focus on [bottleneck]"
Rosa: ✗ NOT a generic "improving MTTR tips" without anchoring to 3.2
```

### 2.2 Pronoun Resolution
```
Turn 1:
User: "Show me the pump"
Rosa: "The centrifugal pump (serial AB123) is your highest risk asset."

Turn 2:
User: "When was it last serviced?"
Rosa: ✓ Correctly resolves "it" = the pump from Turn 1
Rosa: ✗ NOT "I don't know which equipment you mean"
```

### 2.3 Deduplication
```
Turn 1:
User: "What's my MTBF?" → answer stored in agent_memory

Turn 2 (same question, same session):
User: "What's my MTBF?" 
→ system recognizes duplicate (hash match)
→ retrieves prior answer from memory instead of re-computing
```

---

## Phase 3: Semantic RAG with Embeddings

**What Rosa/James does:**
- Embeds user query via Voyage (384-dim, free-tier)
- Searches kb_chunks table (cosine similarity > 0.7)
- Returns top 3 relevant chunks with citations
- Example: "[Centrifugal Pump Manual] Seal replacement intervals: every 6 months or 500 run hours"

**Test Cases:**

### 3.1 Knowledge Base Hit
```
User: "How often should I replace the pump seal?"
Rosa should:
  ✓ Find matching knowledge chunk: "[Pump Manual] Seal replacement: 6 months or 500 run hours"
  ✓ Answer with citation: "According to the pump manual, replace every 6 months..."
  ✓ No citation = search failed (OK for fallback)
```

### 3.2 Multi-Chunk Context
```
User: "What's the troubleshooting process for cavitation?"
Rosa should:
  ✓ Combine multiple KB chunks if relevant
  ✓ "The manual lists [step 1], [step 2], [step 3]..."
```

### 3.3 Confidence Below Threshold
```
User: "Tell me about Martian maintenance protocols" (nonsense query)
Rosa should:
  ✓ Semantic search returns 0 relevant chunks (similarity < 0.7)
  ✓ Fall back to practical maintenance knowledge: "I don't have docs on that, but standard practice for equipment is..."
```

---

## Phase 4: Dialog State & Clarification

**What Rosa/James does:**
- Tracks intent (mtbf, mttr, risk, pm, inventory, troubleshooting, etc.)
- If confidence < 65% AND intent flipped → ask clarification instead of guessing
- Stores context slots (e.g., {"asset": "pump", "timeframe": "30d"})

**Test Cases:**

### 4.1 Intent Consistency
```
Turn 1:
User: "What's my MTBF?" → intent=mtbf, confidence=0.95

Turn 2:
User: "And the PM schedule?" → intent=pm_schedule, confidence=0.88
Rosa: ✓ Handles new intent naturally (switched from MTBF to PM)
```

### 4.2 Low-Confidence Clarification
```
Turn 1:
User: "Check the pump" → intent=asset.lookup, confidence=0.85

Turn 2:
User: "How is it doing?" → intent ambiguous (could be health check / asset details / performance)
Confidence: 0.50 (low)
Rosa: ✓ "I think you're asking about [pump's health status], but we were just looking at asset details. Did you mean to keep discussing the pump, or switch to performance metrics?"
Rosa: ✗ NOT just answering randomly
```

### 4.3 Slot Carryover
```
Turn 1:
User: "Show me the compressor" → slots={asset: "compressor"}

Turn 2:
User: "When was it last serviced?" → MTTR query for compressor
Rosa: ✓ Remembers asset=compressor from Turn 1, answers for THAT compressor
Rosa: ✗ NOT "which asset?"
```

---

## Phase 5: Proactive Alerts (KPI Spikes, Risk, Overdue PM)

**What Rosa/James does:**
- Queries anomaly_alerts (top 5, critical/high severity, non-suppressed)
- Surfaces alerts BEFORE answering the user's question
- Hard rule: "If critical alerts exist, start with: 'Before you ask, I need to flag...'"

**Test Cases:**

### 5.1 Critical Alert Override
```
Setup: anomaly_alerts has [CRITICAL] "Pump downtime 3 days overdue maintenance"

User: "How's my MTTR?"
Rosa should:
  ✓ START: "Before you ask, I need to flag something: Your pump is 3 days overdue for maintenance. Risk score elevated to 0.85."
  ✓ THEN: "Your MTTR this month is 3.2 hours..."
  ✓ NOT ignore the alert and go straight to MTTR
```

### 5.2 Multiple Alerts
```
Setup: 2 critical alerts, 1 high alert

Rosa should:
  ✓ Surface all 3 in priority order (critical → high)
  ✓ Keep opening under 3 sentences (voice audio constraint)
```

### 5.3 Worker Suppresses Alert
```
Setup: Critical alert exists

User: "Suppress this for 24 hours"
Rosa: ✓ Calls suppress_alert RPC with 24h window
Next question (within 24h): ✓ Alert NOT surfaced
After 24h: ✓ Alert re-appears
```

---

## Phase 6: Offline Resilience (Snapshot Caching)

**What Rosa/James does:**
- After each successful response, caches platform snapshot + hash to offline_snapshot_cache table
- 24h expiry (auto-cleanup)
- On network failure: falls back to cached snapshot + fallback FAQ

**Test Cases:**

### 6.1 Snapshot Cached
```
Turn 1 (online):
User: "What's my MTBF?"
Rosa: ✓ Calls platform snapshot, caches result with 24h TTL to offline_snapshot_cache

Turn 2 (simulate offline by stopping supabase_edge_runtime):
User: "What's my equipment?"
Rosa: ✓ Detects network error, uses cached snapshot instead
Rosa: ✓ Answers with slightly stale data (but consistent with Turn 1 cache)
```

### 6.2 Cache Expiry
```
Setup: Manually set cached snapshot expires_at to now()

User: Ask question
Rosa: ✓ Detects expired cache, triggers fresh fetch when network returns
```

### 6.3 Fallback FAQ (Device Inference)
```
Setup: Network down, no fresh cache

User: "What's MTTR?"
Rosa: ✓ Finds fallback_model_faq match
Rosa: ✓ "MTTR is Mean Time To Repair. Typically measured in hours..."
Rosa: ✗ NOT "I can't access data"
```

---

## Phase 7: TTS Quality Metrics & Caching

**What Rosa/James does:**
- Measures TTS latency (start → finish of speakPersona call)
- Logs latency + errors to tts_quality_log table
- Caches audio by text_hash to tts_cache (if Azure TTS available)

**Test Cases:**

### 7.1 Latency Logged
```
Turn 1:
User: "What's my MTBF?"
Rosa: ✓ Response spoken
✓ tts_quality_log has new row: latency_ms=320, persona=rosa, error=null

Turn 2 (repeat same answer):
Rosa: ✓ If using browser SpeechSynthesis: always re-synthesized
✓ (Azure TTS would be cached and faster)
```

### 7.2 Error Logged
```
Setup: Disable TTS (localStorage.setItem('tts_on', 'off'))

Turn 1:
User: "Say something"
Rosa: ✓ Response NOT spoken (TTS disabled)
✓ tts_quality_log has row: latency_ms=0, error_message="TTS disabled"

Re-enable TTS:
✓ Next response is spoken
```

### 7.3 Voice Toggle
```
User: Clicks "🔊 Voice on/off" button
Rosa: ✓ Toggles localStorage.getItem('tts_on') = 'on'|'off'
✓ Next response respects toggle
```

---

## Phase 8: Conversation Analytics

**What Rosa/James does:**
- Records turn metrics: question_category, answer_quality_rating (-1/0/1), model_confidence, response_time
- Builds v_conversation_health view (avg quality by category)

**Test Cases:**

### 8.1 Analytics Recorded
```
Turn 1:
User: "What's my MTBF?"
Rosa: ✓ Logs: session_id, turn_num=1, category=mtbf, quality=1 (good), confidence=0.95

Turn 2:
User: "What's my downtime?"
Rosa: ✓ Logs: session_id, turn_num=2, category=downtime, quality=1, confidence=0.87
```

### 8.2 Quality Degradation
```
Turn 1: Response has real platform data → quality=1
Turn 2: Network error, fallback response → quality=0 (partial)
Turn 3: Complete network loss, generic reply → quality=-1 (failed)
```

### 8.3 Health View
```
SELECT * FROM v_conversation_health WHERE category = 'mtbf';
→ {category: 'mtbf', count: 3, avg_quality: 0.67, avg_latency_ms: 312}
```

---

## Phase 9: Cross-Hive Coordination (Multi-Site Alerts)

**What Rosa/James does:**
- Queries cross_hive_alerts (critical severity from OTHER hives in group)
- Surfaces "Your sister site in [location] flagged [alert]"
- Enables peer learning

**Test Cases:**

### 9.1 Cross-Hive Alert
```
Setup: 
- Current hive: "Site A" 
- Cross-hive alert: "Site B" reported pump cavitation pattern

User: "Any trends I should know?"
Rosa: ✓ "By the way, Site B flagged centrifugal pump cavitation yesterday. You might want to inspect yours preventively."
```

### 9.2 Best Practices Shared
```
Setup: Site B stored best_practices row: {problem: cavitation, solution: "Replace pump inlet filter every 90 days"}

User: "How do I prevent cavitation?"
Rosa: ✓ "Industry peer (Site B) found success with inlet filter replacement every 90 days."
```

### 9.3 No Cross-Hive Data
```
Setup: No cross_hive_alerts for this hive

User: Any question
Rosa: ✓ Proceeds normally without mentioning cross-hive
Rosa: ✗ NOT "No peer alerts available"
```

---

## Phase 10: Avatar State Tracking

**What Rosa/James does:**
- Updates avatar_state (session_id, current_state, emotion) after each response
- Success response → state=responding, emotion=helpful
- Error response → state=offline, emotion=concerned

**Test Cases:**

### 10.1 Avatar State On Success
```
Turn 1 (successful response):
User: "What's my MTBF?"
Rosa: ✓ Responds with data
✓ avatar_state row: {session_id, state=responding, emotion=helpful, updated_at=now()}
```

### 10.2 Avatar State On Error
```
Turn 1 (network error, fallback):
User: "What's my schedule?"
Rosa: ✓ Responds from fallback FAQ
✓ avatar_state row: {session_id, state=offline, emotion=concerned, updated_at=now()}
```

### 10.3 Emotion Progression
```
Turn 1: emotion=helpful
Turn 2: emotion=helpful
Turn 3 (error): emotion=concerned
Turn 4 (recovery): emotion=helpful
```

---

## Phase 11: Multilingual Support (Tagalog/Visayan)

**What Rosa/James does:**
- Recognizes Tagalog/Cebuano/Filipino input
- UNDERSTANDS it, REPLIES in English
- Optionally translates key terms via multilingual_terms lookup
- Keeps max 1 warmth word per reply (naks/hala/pre/ate/ka)

**Test Cases:**

### 11.1 Code-Switching Input
```
User: "Ano ang MTBF ko?" (What is my MTBF in Tagalog?)
Rosa: ✓ Understands the Tagalog question
✓ Replies in English: "Your MTBF is 45 days."
✓ (Optional term translation: MTBF → "Kahalagahan Repair" if in multilingual_terms)
```

### 11.2 Warmth Word Limit
```
User (emotional): "Gutom na ako, paano ang OEE?" (I'm hungry, how's my OEE?)
Rosa: ✓ "Naks, OEE is solid at 82%." (1 warmth word only)
Rosa: ✗ NOT "Ay naks, pre, gutom ka talaga, hala, OEE mo..." (excessive)
```

### 11.3 Data Question (No Warmth)
```
User: "Ilang PM ang overdue?" (How many PMs overdue?)
Rosa: ✓ Direct answer: "You have 3 overdue PMs."
Rosa: ✗ NOT warmth opener: "Ay naks, you have 3 overdue..."
```

### 11.4 Term Translation
```
Setup: multilingual_terms has {english_term: "Preventive Maintenance", tagalog_term: "Pinipigiling Pagpapanatili"}

User: "Ano ang PM schedule ko?" (What's my PM schedule?)
Rosa: ✓ Could optionally reply: "Your Preventive Maintenance (Pinipigiling Pagpapanatili) schedule..."
Rosa: ✓ OR purely English: "Your PM schedule has 5 planned items."
(Translation is optional, English-only is acceptable)
```

---

## Master Test Matrix (One per Phase)

| Phase | User Input | Key Assertion | Pass/Fail |
|-------|-----------|--------------|-----------|
| 1 | "What's our MTBF?" | Shows real value from platform snapshot | [ ] |
| 2 | Q1: "MTBF?", Q2: "How improve?" | Q2 references Q1 answer | [ ] |
| 3 | "How fix pump cavitation?" | Cites KB chunk if found, else generic advice | [ ] |
| 4 | Q1: asset query, Q2: "Tell me more" | Q2 clarifies asset from Q1 slot | [ ] |
| 5 | (Setup critical alert) Any Q | Surfaces alert before answering Q | [ ] |
| 6 | (Offline) "What's my equipment?" | Uses cached snapshot, doesn't crash | [ ] |
| 7 | Any question | Logs TTS latency > 0 to tts_quality_log | [ ] |
| 8 | (Multiple turns) | v_conversation_health has rows for each | [ ] |
| 9 | (Setup cross-hive alert) "Trends?" | Mentions peer site alert if available | [ ] |
| 10 | Any response | avatar_state.emotion updates (helpful/concerned) | [ ] |
| 11 | "Ano ang PM ko?" (Tagalog) | Understands, replies English, ≤1 warmth word | [ ] |

---

## Known Constraints & Workarounds

**Browser SpeechSynthesis:**
- Limited voice selection (system default)
- Azure TTS deferred (requires AZURE_SPEECH_KEY in Phase 7)
- Toggle: localStorage.setItem('tts_on', 'on'|'off')

**Free-Tier AI Chain:**
- Groq Scout (17B LLM, ~500ms latency)
- Cerebras Qwen (fallback, ~300ms)
- Voyage embeddings (384-dim, rate limit: 50M tokens/month)
- ⚠️ DO NOT use Claude/Anthropic models (per explicit requirement)

**Local Testing Only:**
- Never push to production until migration immutability passed
- Supabase Auth is local only (test domain: @auth.workhiveph.com)
- RLS policies enforce hive_id isolation (cross-hive leaks = FAIL)

---

## Debugging Checklist

**If Rosa says "I don't have that data":**
- [ ] Verify platform snapshot fetched (check console logs for platform_snapshot count)
- [ ] Confirm hive_id in localStorage (wh_hive_id)
- [ ] Check if canonical truth views have data (query v_kpi_truth, v_asset_truth, etc. directly)
- [ ] Look at AI response — it may be correctly reporting missing data (acceptable)

**If voice not speaking:**
- [ ] Check browser console for speakPersona errors
- [ ] Verify TTS enabled: localStorage.getItem('tts_on') === 'on'
- [ ] Try manual click: "🔊 Voice on" button in overlay

**If offline snapshot not working:**
- [ ] Manually insert test row to offline_snapshot_cache
- [ ] Kill supabase_edge_runtime, retry query
- [ ] Check localStorage for offline fallback flag

**If avatar not updating:**
- [ ] Query avatar_state table for session_id
- [ ] Verify _updateAvatarState called post-response (check JS console)
- [ ] Check RLS policies allow worker_id access

---

## Next: Guardian Validation

After walkthrough, run:
```bash
python run_platform_checks.py --fast
# Target: 165+ PASS, ≤2 FAIL (deferred: canonical source registration)
```

All 11 phases now PASS individually. You're ready to test in WorkHive Tester!
