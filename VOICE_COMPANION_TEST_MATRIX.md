# Voice Companion Comprehensive Test Matrix

**Purpose**: Validate all dimensions of Voice Companion (James/Rosa) across Phases 0-3  
**Coverage**: Routing, agents, RAG, models, error recovery  
**Expected Outcome**: Overall status scorecard for all subsystems

---

## Test Dimension 1: Router Intent Classification (Phase 0)

Tests whether router correctly classifies intent and passes context through.

| Question | Expected Intent | Expected Behavior | Status |
|----------|-----------------|-------------------|--------|
| What's our MTBF this month? | platform-data | Should invoke platform scraper for canonical MTBF | [ ] |
| Why does the pump keep failing? | semantic-depth | Should fetch voice journal history for pump failures | [ ] |
| Thanks for the help | simple-reply | Should respond conversationally, no agents needed | [ ] |
| What preventive maintenance is due? | platform-data | Should fetch PM status from dashboard | [ ] |
| Tell me about our equipment failures from last month | semantic-depth | Should search voice journal for historical failures | [ ] |
| How much inventory do we have? | platform-data | Should fetch inventory alerts/stock status | [ ] |
| I appreciate it | simple-reply | Should acknowledge conversationally | [ ] |
| What are the top 5 risk assets? | platform-data | Should fetch risk assets from platform | [ ] |

---

## Test Dimension 2: Platform Data Integration (Phase 1)

Tests whether platform scraper correctly fetches and integrates real-time KPI data.

| Question | Data Source | Expected Content | Status |
|----------|-------------|------------------|--------|
| How many equipment are currently running? | v_asset_truth | Current equipment count + status breakdown | [ ] |
| What's our equipment downtime this month? | v_asset_truth | Down equipment list with durations | [ ] |
| How many PMs are overdue? | v_pm_truth | Overdue PM count + list | [ ] |
| What PMs are due this week? | v_pm_truth | Due date, frequency, last completed date | [ ] |
| Do we have critical inventory alerts? | v_inventory_truth | Low-stock items, reorder flags | [ ] |
| What's the adoption rate of this tool? | v_adoption_truth | Adoption percentage, active workers | [ ] |
| Which assets are flagged as high risk? | v_risk_truth | Risk score, risk level, mitigation status | [ ] |
| What's our mean time between failures? | v_pm_truth + canonical | Historical MTBF calculation | [ ] |

---

## Test Dimension 3: Memory & Recency (Phase 1)

Tests whether RAG agent correctly retrieves voice journal history.

| Sequence | Question 1 | Question 2 | Expected Behavior | Status |
|----------|-----------|-----------|-------------------|--------|
| Memory Chain 1 | "What's MTBF?" | "How did we calculate that?" | Q2 should reference Q1's answer | [ ] |
| Memory Chain 2 | "Why does pump fail?" | "Have we fixed that before?" | Q2 should find past pump failures in journal | [ ] |
| Memory Chain 3 | "What inventory is low?" | "When was the last restock?" | Q2 should find restock entries | [ ] |
| Repetition Test | "What's MTBF?" (1st time) | "What's MTBF?" (2nd time) | Should give different answer (not repeated) | [ ] |
| Cross-Turn Context | "Tell me about pump failures" | "How can we prevent that?" | Q2 should build on Q1 context | [ ] |

---

## Test Dimension 4: Semantic RAG (Phase 1.5)

Tests whether semantic search finds old entries by topic similarity, not just recency.

| Question | Expected Match | Notes | Status |
|----------|---|---|---|
| Why does the pump keep cavitating? | Old pump failure notes (even if 2+ weeks old) | Tests pgvector semantic search | [ ] |
| How can we improve equipment reliability? | All historical reliability/MTBF discussions | Semantic depth, not just recency | [ ] |
| What caused the previous motor failure? | Old motor failure root causes | Should find even if not in last 30 days | [ ] |
| Tell me about seal failures we've had | All historical seal-related issues | Semantic matching across topics | [ ] |
| How do we handle cavitation issues? | Old cavitation prevention notes | Tests semantic similarity matching | [ ] |

---

## Test Dimension 5: Multi-Model A/B Testing (Phase 2)

Tests whether different models are being called and produce reasonable responses.

| Prompt | Scout | Qwen | Voyage | Jina | Notes |
|--------|-------|------|--------|------|-------|
| What's MTBF? | [ ] OK | [ ] Fallback? | [ ] Fallback? | [ ] Fallback? | Primary model should respond |
| Explain pump cavitation | [ ] OK | [ ] Fallback? | [ ] Fallback? | [ ] Fallback? | Tests reasoning depth |
| How do I reduce downtime? | [ ] OK | [ ] Fallback? | [ ] Fallback? | [ ] Fallback? | Tests structured advice |
| Why does equipment fail? | [ ] OK | [ ] Fallback? | [ ] Fallback? | [ ] Fallback? | Tests semantic understanding |

**Model Strategy**: Currently set to `scout` (primary only)
- To test fallback: Kill Groq API key and observe fallback chain
- To test round-robin: Set `MODEL_STRATEGY=round-robin` and run again

---

## Test Dimension 6: Consistency Across Pages (Phase 0)

Tests whether router and agents provide consistent data across different pages.

| Question | Hive Page | Alert Hub | PM Scheduler | Logbook | Expected |
|----------|-----------|-----------|--------------|---------|----------|
| What's MTBF? | [ ] | [ ] | [ ] | [ ] | Same value (canonical source) |
| PMs due this week? | [ ] | [ ] | [ ] | [ ] | Same list (canonical source) |
| Equipment downtime? | [ ] | [ ] | [ ] | [ ] | Same status (canonical source) |
| Our adoption rate? | [ ] | [ ] | [ ] | [ ] | Same percentage (canonical source) |

**Note**: Should use unified v_*_truth views, not per-page caching

---

## Test Dimension 7: Error Recovery & Fallback (Phase 3)

Tests whether offline scenarios and API failures are handled gracefully.

| Scenario | Expected Behavior | Status |
|----------|-------------------|--------|
| Kill Groq API key, ask MTBF question | Should fallback to Qwen/Voyage/Jina (or offline reply if all fail) | [ ] |
| Network unavailable (simulated), ask question | Should show intent-aware fallback reply (e.g., "check Analytics for MTBF") | [ ] |
| Kill all API keys, ask question | Should show offline fallback reply + save transcript | [ ] |
| Ask question when Supabase down | Should preserve transcript in _sessionTurns (anon worker) | [ ] |
| Retry after network recovers | Should send saved transcript on reconnect | [ ] |

---

## Test Dimension 8: Intent-Aware Fallback (Phase 3)

Tests whether error messages are context-aware (not generic "we're offline").

| Intent | Fallback Question | Expected Reply | Status |
|--------|-------------------|---|---|
| MTBF question offline | "What's MTBF this month?" | "Check Analytics > KPI dashboard for MTBF data" (not generic) | [ ] |
| PM question offline | "What PMs are due?" | "Open PM Scheduler to see due dates" (not generic) | [ ] |
| Logbook offline | "How do I log an entry?" | "Open Logbook page to create entry" (not generic) | [ ] |
| Equipment offline | "Which equipment is down?" | "Check Hive dashboard for equipment status" (not generic) | [ ] |

---

## Test Dimension 9: Anon Worker Memory (Phase 3)

Tests whether session-only memory works for Tester walkthrough (no auth).

| Step | Action | Expected | Status |
|------|--------|----------|--------|
| 1 | Log in as Tester (anon worker) | No auth, session starts | [ ] |
| 2 | Ask "What's MTBF?" | Session-local memory created | [ ] |
| 3 | Ask "How did we calculate that?" | Should reference Q2 answer (from session) | [ ] |
| 4 | Refresh page, ask Q3 | Memory GONE (session reset) — expected behavior | [ ] |
| 5 | Log in as real user | Full DB-backed memory available | [ ] |

**Note**: Anon memory is intentional (session-only, not persistent)

---

## Test Dimension 10: TTS & Voice Output (Phase 3)

Tests whether text-to-speech works for both success and error paths.

| Scenario | Expected TTS Behavior | Status |
|----------|-----|---|
| Normal response | Reply spoken aloud via browser SpeechSynthesis | [ ] |
| Offline fallback | Fallback reply spoken aloud (even if AI down) | [ ] |
| Long response | Chunked into sentences, natural pauses | [ ] |
| Special characters | Properly pronounced (e.g., "MTBF" → "M-T-B-F") | [ ] |
| Multi-turn | Previous answers not re-read (only new reply) | [ ] |

---

## Test Dimension 11: Transcript Preservation (Phase 3)

Tests whether user questions are never lost, even on API failure.

| Scenario | Expected | Status |
|----------|----------|--------|
| Ask question, AI fails | Transcript saved in voice_journal_entries | [ ] |
| Ask question, Supabase RLS denied | Transcript saved in _sessionTurns (fallback) | [ ] |
| Ask question, network lost | Transcript queued in IndexedDB, sent on reconnect | [ ] |
| Worker logs out then back in | All transcripts still available in journal | [ ] |

---

## Test Dimension 12: Router Guidance on Unhandled Commands (Phase 0)

Tests whether unhandled intents receive helpful guidance.

| Unhandled Command | Expected Guidance | Status |
|---|---|---|
| "Open the PDF report" | "Try Shift Handover Report page to generate PDFs" | [ ] |
| "Send this to John" | "Use Report Sender to email this" | [ ] |
| "What's the safety checklist?" | "Check Engineering Design Calculator for safety items" | [ ] |
| "I need help with math" | "Try Engineering Design Calculator for calculations" | [ ] |
| "Show me the graph" | "Check Analytics page for dashboards" | [ ] |

---

## Test Dimension 13: Latency & Performance

Tests response time across different scenarios.

| Scenario | Target | Actual | Status |
|----------|--------|--------|--------|
| Simple reply (no agents) | <500ms | [ ] | [ ] |
| Platform data (1 agent) | <1s | [ ] | [ ] |
| Semantic search (embedding + query) | <2s | [ ] | [ ] |
| Full multi-agent (platform + RAG) | <2s | [ ] | [ ] |
| Fallback chain (3 model retries) | <5s | [ ] | [ ] |

---

## Test Dimension 14: Edge Cases

| Question | Expected Behavior | Status |
|----------|---|---|
| Empty question (just hit record+send) | Should prompt to try again | [ ] |
| Gibberish noise | Should ask to clarify | [ ] |
| Too-long transcription | Should truncate to context budget | [ ] |
| Offensive/inappropriate question | Should respond professionally or decline | [ ] |
| Same question 5 times in a row | Should vary answers (not repeat) | [ ] |

---

## Scoring Rubric

### Overall Status Dimensions

**Green** (✓): Working correctly, expected behavior  
**Yellow** (⚠): Partial, has minor issues but functional  
**Red** (✗): Broken, needs fixing  

---

## Summary Scorecard

| Dimension | Status | Notes |
|-----------|--------|-------|
| 1. Router Intent Classification | [ ] Green / [ ] Yellow / [ ] Red | |
| 2. Platform Data Integration | [ ] Green / [ ] Yellow / [ ] Red | |
| 3. Memory & Recency | [ ] Green / [ ] Yellow / [ ] Red | |
| 4. Semantic RAG (Phase 1.5) | [ ] Green / [ ] Yellow / [ ] Red | |
| 5. Multi-Model A/B Testing (Phase 2) | [ ] Green / [ ] Yellow / [ ] Red | |
| 6. Consistency Across Pages | [ ] Green / [ ] Yellow / [ ] Red | |
| 7. Error Recovery & Fallback | [ ] Green / [ ] Yellow / [ ] Red | |
| 8. Intent-Aware Fallback | [ ] Green / [ ] Yellow / [ ] Red | |
| 9. Anon Worker Memory | [ ] Green / [ ] Yellow / [ ] Red | |
| 10. TTS & Voice Output | [ ] Green / [ ] Yellow / [ ] Red | |
| 11. Transcript Preservation | [ ] Green / [ ] Yellow / [ ] Red | |
| 12. Router Guidance | [ ] Green / [ ] Yellow / [ ] Red | |
| 13. Latency & Performance | [ ] Green / [ ] Yellow / [ ] Red | |
| 14. Edge Cases | [ ] Green / [ ] Yellow / [ ] Red | |
| **OVERALL** | [ ] Ready for Production / [ ] Needs Fixes / [ ] Major Issues | |

---

## Quick Start: Recommended Test Sequence

**Phase A (20 min): Core Functionality**
1. Start on Hive page
2. Ask: "What's our MTBF this month?" (Test: platform data + routing)
3. Ask: "Why does the pump keep failing?" (Test: RAG + semantic depth)
4. Ask: "Thanks for the help" (Test: simple reply)
5. Ask: "What's MTBF?" again (Test: memory, not repetition)
6. Switch to Alert Hub, ask: "What's our MTBF?" (Test: consistency)

**Phase B (10 min): Error Scenarios**
1. Disable Groq API key in .env
2. Ask: "What's MTBF?" (Test: fallback chain + offline reply)
3. Check browser console for error logs

**Phase C (5 min): A/B Models**
1. Set `MODEL_STRATEGY=round-robin`
2. Ask: "What's MTBF?" 4 times (Test: different models each time)
3. Compare latency and quality

---

## Recording Results

As you test, fill in the matrix above and note:
- ✓ Green: What worked perfectly
- ⚠ Yellow: What worked with minor issues (describe)
- ✗ Red: What broke (describe error)

Then share the summary scorecard to see overall health.

