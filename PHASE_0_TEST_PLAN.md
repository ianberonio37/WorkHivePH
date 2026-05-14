# Phase 0 Test Plan — Walkthrough Bug Fixes

**Validator Status**: 9/9 PASS ✓

## Test Case 1: Rosa Repetition (MTBF Question)

**Bug Observed**: Worker asks same MTBF question 3 times → Rosa gives identical answer all 3 times  
**Root Cause (Fixed)**: Router output discarded; regex classifier re-parsed independently; no memory context

**Phase 0 Fix**:
- Router intent now passed to _converseInline (routerIntents + routerNarration)
- routerBlock injected into system prompt: "Router classified: mtbf (95%)"
- Memory context fetched and injected (recent turns available for continuity)
- Hard Rule #11 now has grounding: "Do NOT repeat the same data point answer twice in a row"

**Test**: Ask "What's our average time between failures?" 3 times in succession  
**Expected**: 3 DIFFERENT answers using the same canonical MTBF value, varied phrasing  
**Pass Criteria**: All 3 answers reference the same MTBF number but different wording/context

---

## Test Case 2: Misrouted Intent ("How can I find it?")

**Bug Observed**: Worker asks follow-up from logbook page → "How can I find it?" gets no routing guidance  
**Root Cause (Fixed)**: Router classified asset lookup intent, but output discarded in conversational path

**Phase 0 Fix**:
- routerIntents now passed through to _converseInline
- Model can see router classified as 'asset.lookup' (from routerIntents[0].kind)
- routingHint generated from UNHANDLED_INTENT_GUIDANCE['asset.lookup']
- routingBlock injected: "the worker tried to speak a command this page can't execute: they want details on an asset — tell them to open Asset Hub"

**Test**: While on logbook page, ask "How can I find it?" after mentioning an asset name  
**Expected**: Model correctly identifies asset lookup intent and guides to Asset Hub  
**Pass Criteria**: Reply mentions Asset Hub without inventing UI ("click this button")

---

## Test Case 3: MTBF Answer Consistency

**Bug Observed**: Worker asks MTBF 2× on different pages → Different number both times  
**Root Cause (Fixed)**: dataIntentKind detection was via regex (slow); canonical fetch sometimes failed silently

**Phase 0 Fix**:
- dataIntentKind now determined from router's first intent.kind (line 962)
- Router provides high-confidence classification (Groq LLM) vs regex heuristic
- Canonical fetch tied to router intent: `['mtbf', 'mttr', 'downtime', 'risk_top', 'failures_count'].includes(firstIntent.kind)`
- routerContext tells model: "Router classified: mtbf (confidence%)" — unified signal

**Test**: Ask "What's our MTBF?" on hive page, then repeat on alert-hub page  
**Expected**: Same MTBF value both times (fetched from canonical_anchor baseline)  
**Pass Criteria**: Both answers cite the same MTBF number

---

## Phase 0 Completion Checklist

- [x] Router invocation + routerData storage exists
- [x] routerIntents/routerNarration/assetResolution passed to _converseInline
- [x] _classifyDataIntent removed from conversational path
- [x] routerContext extracted and passed to _buildVoiceSystemPrompt
- [x] routerBlock integrated into system prompt
- [x] dataIntentKind detection switched to router intent
- [x] Validator passes 9/9 checks
- [ ] Walkthrough Test #6 passes all 3 bug-fix test cases
- [ ] No new console errors or memory leaks

---

## Decision Gate for Phase 1

**If 2+ of 3 bugs fixed**: Proceed to Phase 1 implementation (Multi-Agent Orchestrator)  
**If 1 or fewer bugs fixed**: Debug root causes before Phase 1

---

## Next Steps After Phase 0 Validation

1. Launch walkthrough test #6 scenarios on hive.html + alert-hub + logbook (3 pages)
2. Record which bugs are fixed (expected: all 3)
3. If all fixed → Begin Phase 1: Multi-Agent Orchestrator (RAG Agent, Platform Scraper, Semantic Router)
4. If debugging needed → Check memory injection, route context passing, canonical data fetch
