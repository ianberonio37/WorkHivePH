# Release Gate + AI Self-Improvement Loop Integration

## Current Release Gate Structure

```
PRE-FLIGHT (Docker, Supabase, Flask reachable?)
    ↓
PHASE 1: Reseed (reset + seed_everything)
    ↓
PHASE 2: Static Validators (run_platform_checks.py --fast)
    ├─ 130+ schema/structure/logic validators
    └─ ~90 seconds, 0 cost
    ↓
PHASE 3: Data Tests (test-data-seeder/run_tests.py)
    ├─ INSERT/UPDATE/DELETE integrity
    └─ Trigger + RPC behavior
    ↓
PHASE 4: UI Tests (test-data-seeder/run_flows.py + flags)
    ├─ python run_flows.py                 (core UI smoke tests)
    ├─ python run_flows.py --with-ai       (AI surfaces only) ← YOU ARE HERE
    ├─ python run_flows.py --with-visual   (image analysis)
    └─ python run_flows.py --with-perf     (performance/metrics)
    ↓
VERDICT: PASS (safe to deploy) or BLOCK (fix before push)
```

---

## New: Release Gate Phase 4 Enhancement (AI Full)

When user clicks **"Release Gate + AI Full (Groq · ~5min · $0)"** in WorkHive Tester:

```
PHASE 4: UI Tests (test-data-seeder/run_flows.py --with-ai-deep)
│
├─ LAYER 0: Scenario Execution (Playwright)
│   ├─ Voice Journal (Rosa/James): 3 scenarios
│   ├─ Visual Defect: 2 scenarios
│   ├─ AMC (Anomaly Mgmt): 2 scenarios
│   ├─ Engineering Calc: 2 scenarios
│   └─ Other AI surfaces: 1+ scenario each
│   
├─ LAYER 1: Failure Analysis (Claude)
│   ├─ Analyze each scenario result
│   ├─ Extract finding_type (missing_context, format_error, etc)
│   └─ Root cause classification
│   
├─ LAYER 2: Auto-Remediation
│   ├─ Prompt updates (voice-handler.js, ai-gateway, etc)
│   ├─ Seeding corrections (reseed alerts, KB, defects, etc)
│   ├─ RPC/logic fixes (routing, suppression, etc)
│   └─ Re-validate fixes (re-run scenario)
│   
├─ LAYER 3: Validator Generation
│   ├─ Create new validators (validate_voice_alert_order.py, etc)
│   ├─ Extend existing validators (validate_voice_alert_formatting.py)
│   └─ Register in GATES list (dynamic registration)
│   
├─ LAYER 4: Meta-Validator
│   ├─ All findings have validators? ✓
│   ├─ No validators deferred? ✓
│   ├─ Seeding reproducible? ✓
│   └─ Loop metadata consistent? ✓
│   
└─ FINAL: Fast Mega Gate (Phase 2 re-run)
    ├─ run_platform_checks.py --fast
    ├─ Includes NEW validators from Layer 3
    └─ Must be 0 FAIL to continue
```

---

## All AI Surfaces Covered

| AI Surface | Tool/Page | Scenarios | Finding Types |
|---|---|---|---|
| **Voice Journal (Phase 3/5/8)** | voice-journal.html | Ask Rosa: KB query, alert query, combined | missing_kb_context, alert_not_prioritized, analytics_gap |
| **Visual Defect (Phase 4)** | visual-defect.html | Upload image → analyze, flag defect | missing_defect_category, confidence_too_low, missing_feedback |
| **AMC (Phase 5+)** | alert-hub.html | Fetch alerts, suppress, acknowledge | alert_suppression_missed, priority_wrong, description_truncated |
| **Engineering Calc** | engineering-design.html | Run calc → check formulas, BOM, SOP | formula_mismatch, unit_conversion_error, missing_standard_reference |
| **AI Assistant (Chat)** | (any page with chat) | Ask question → check response quality | hallucination, outdated_context, PII_exposure |

---

## Integration Points

### 1. Phase 4 Expansion: run_flows.py

**Current:**
```python
if WITH_AI:
    # Run a few hand-written AI scenarios
    run_voice_scenarios()
```

**New:**
```python
if WITH_AI_DEEP:  # NEW flag: --with-ai-deep
    # Run Playwright-driven self-improvement loop
    rc = subprocess.run([
        sys.executable,
        "tools/voice_ai_self_improvement_loop.py",
        "--all-surfaces",  # Voice, Visual, AMC, Calc, Chat
        "--release-mode"   # Stricter validation than daily loop
    ])
    
    if rc != 0:
        print("FAIL: AI scenarios found issues, fixes staged")
        print("Review: git diff")
        print("To proceed: git add -A && git commit -m '...'")
        return False
```

### 2. New Python Entry Point

**File**: `tools/voice_ai_self_improvement_loop.py` (enhanced)

Add flags:
```python
--all-surfaces     # Run scenarios for Voice + Visual + AMC + Calc + Chat
--release-mode     # Stricter findings classification (no deferral)
--surface VOICE    # Run single surface only (for faster iteration)
```

### 3. Scanner: All AI Surfaces

Replace the hardcoded `SCENARIOS` list with a registry that covers all surfaces:

```python
SURFACES = {
    "VOICE": {
        "pages": ["voice-journal.html"],
        "scenarios": [
            {"name": "KB Citation", ...},
            {"name": "Alert Surfacing", ...},
            {"name": "Analytics Logging", ...},
        ]
    },
    "VISUAL": {
        "pages": ["visual-defect.html"],
        "scenarios": [
            {"name": "Defect Classification", ...},
            {"name": "Confidence Scoring", ...},
        ]
    },
    "AMC": {
        "pages": ["alert-hub.html"],
        "scenarios": [
            {"name": "Alert Fetching", ...},
            {"name": "Suppression Logic", ...},
        ]
    },
    "CALC": {
        "pages": ["engineering-design.html"],
        "scenarios": [
            {"name": "Formula Validation", ...},
            {"name": "BOM Generation", ...},
        ]
    },
}

# Then: for surface, config in SURFACES.items(): run_scenarios_for_surface(surface, config)
```

---

## Validator Scope (Layer 3)

### Current Validators (Schema-Focused)
- `validate_voice_alert_formatting.py` → Schema + content checks
- `validate_voice_companion_phase1.py` → RPC existence
- `validate_persona_contract.py` → Persona fields

### New Validators (Behavior-Focused, Generated by Loop)
- `validate_voice_alert_order.py` → Alerts surface FIRST
- `validate_kb_context_inclusion.py` → KB chunks included in response
- `validate_visual_defect_confidence.py` → Confidence scores present
- `validate_calc_formula_accuracy.py` → Formulas match standards
- `validate_chat_pii_redaction.py` → No PII in responses

These validators are **generated** on-the-fly by Layer 3 when findings are detected.

---

## Data Flow: Scenario → Finding → Fix → Validator

### Example: "Rosa not surfacing alerts first"

```
LAYER 0: Playwright scenario
  Ask Rosa: "What are my five equipment alerts?"
  Rosa responds: "I found some alerts: [list]"
  Expected pattern: "[CRITICAL] first"
  Status: FAIL (pattern not found)

LAYER 1: Claude analyzes failure
  Input: {
    "scenario": "Critical Alert Surfacing",
    "expected": "[CRITICAL]",
    "actual": "I found some alerts",
    "evidence": "response text"
  }
  Analysis: "Alert instruction missing from system prompt"
  Output: {
    "finding_type": "wrong_order",
    "root_cause": "Prompt instruction not enforced",
    "suggested_fix_type": "prompt_update",
    "fix_target": "voice-handler.js:1601 alertsSection",
    "confidence": 0.95
  }

LAYER 2: Auto-fix applied
  File: voice-handler.js
  Change: Strengthen alert priority instruction
  "MANDATORY RULE: You MUST surface the alerts below FIRST..."
  
  Re-validate: Re-run scenario
  Result: PASS ✓

LAYER 3: Validator created
  New file: validate_voice_alert_order.py
  Check: "alertsSection appears BEFORE kbSection in system prompt"
  Register: GATES["voice-alert-order"]

LAYER 4: Meta-validator
  Verify: Finding → Validator registered ✓
  No defer: Validator not deferred ✓
  Coverage: 100% of findings have guards ✓

FINAL: Fast gate
  run_platform_checks.py --fast
  Including new validate_voice_alert_order.py
  Result: PASS ✓
```

---

## Cost & Performance

### Playwright Execution (Layer 0)
- ~10 scenarios per surface × 4 surfaces = 40 scenarios
- ~7s per scenario (Playwright + Claude call)
- Total: ~5 minutes (same as current --with-ai)
- Cost: ~$0 (Groq free tier, no paid API calls)

### Claude Analysis (Layer 1)
- Batch analyze all failures (10 calls max, ~2 min)
- Cost: Negligible (internal intelligence)

### Auto-Fixes (Layer 2)
- File edits: instant
- Re-validate: ~30s (re-run 5 scenarios)
- Cost: $0

### Validator Generation (Layer 3)
- Write Python files: instant
- Register in GATES: instant

### Meta-Validator (Layer 4)
- JSON file checks: <5s
- Cost: $0

### Fast Gate (Final)
- Already exist, just includes new validators
- ~90s (no slower than current fast gate)

**Total time**: ~5 minutes (same as current --with-ai)
**Total cost**: ~$0

---

## Decision Tree: When to Run

### Daily/Dev Loop (Lightweight)
```bash
python tools/voice_ai_self_improvement_loop.py --surface VOICE
# ~1.5 min, just Voice scenarios
# Find & fix issues daily
```

### Pre-Release (Full Validation)
```bash
release_gate.py --with-ai-deep
# Phase 4 runs ALL surfaces (Voice + Visual + AMC + Calc)
# Auto-fix + validator generation
# Fast gate passes before deploy
```

### Post-Deploy (Monitoring)
```bash
# Scheduled cron: 2 AM daily
# Catches regressions in production
# Auto-files PRODUCTION_FIXES.md if issues found
```

### Manual Investigation
```bash
# User finds a bug via Playwright test
# Runs loop immediately to prevent regression
python tools/voice_ai_self_improvement_loop.py --all-surfaces --fast-fail
```

---

## What This Means for Your Platform

### Before (Layer 0 validators only)
```
Release Gate → Schema checks → "Code is valid" → Deploy
                ↓
                User tests in Tester
                ↓
                "Rosa is returning IDs instead of descriptions"
                ↓
                Revert + debug cycle
```

### After (Layer 0-4 validators + self-improvement)
```
Release Gate → Schema checks ✓
             → Playwright scenarios (all surfaces) ✓
             → Claude finds issues ✓
             → Auto-fix + validator generation ✓
             → Meta-validator guards loop ✓
             → Fast gate passes (130+ validators) ✓
             → Deploy
                ↓
                User tests in Tester
                ↓
                (Regression not possible; validator would catch it)
```

---

## Implementation Checklist

### Phase 1: Framework (Today)
- [ ] Enhance `voice_ai_self_improvement_loop.py` with --all-surfaces flag
- [ ] Create SURFACES registry (Voice, Visual, AMC, Calc, Chat)
- [ ] Map scenarios to all surfaces

### Phase 2: Integration (Tomorrow)
- [ ] Add --with-ai-deep flag to release_gate.py
- [ ] Wire release_gate Phase 4 to call loop
- [ ] Test with single surface (Voice first)

### Phase 3: Multi-Surface (Next Day)
- [ ] Implement scenarios for Visual Defect
- [ ] Implement scenarios for AMC
- [ ] Implement scenarios for Calc
- [ ] Implement scenarios for Chat/Assistant

### Phase 4: Hardening (Next Week)
- [ ] Add meta-validator layer
- [ ] Test with deliberate bugs (remove alert instruction, break formula, etc.)
- [ ] Verify validators are created, not deferred
- [ ] Run on full Release Gate pipeline

### Phase 5: Production (Month 1)
- [ ] Add scheduled cron (2 AM daily)
- [ ] Monitor PRODUCTION_FIXES.md for regressions
- [ ] Integrate with AlertManager (notify on failures)
- [ ] Dashboard view of loop runs (health.json)

---

## Success Criteria

- ✅ All 4+ AI surfaces covered by scenarios
- ✅ Playwright runs in <5 minutes (same as current --with-ai)
- ✅ Cost remains $0 (Groq only, no paid calls)
- ✅ Auto-fixes verified before user review
- ✅ Validators created for every fix (0 deferral)
- ✅ Meta-validator shows 0 FAIL every run
- ✅ Release Gate Phase 4 gates the fix (blocks deploy if loop issues found)
- ✅ No regression possible (validator coverage = 100%)

This turns **Release Gate from a validation checkpoint into a self-healing system** that catches AI behavior bugs, fixes them, guards them, and only lets code through once all AI surfaces are verified.
