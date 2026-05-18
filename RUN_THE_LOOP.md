# Ready to Run: AI Self-Improvement Loop

## Pre-Flight Summary

```
[PASS] tools/playwright_scenario_executor.py       ✓ Layer 0
[PASS] tools/analyze_scenario_findings.py          ✓ Layer 1
[PASS] tools/auto_fix_findings.py                  ✓ Layer 2
[PASS] tools/generate_and_register_validator.py    ✓ Layer 3
[PASS] tools/validate_improvement_loop_integrity.py ✓ Layer 4
[PASS] tools/ai_self_improvement_loop.py           ✓ Orchestrator
[PASS] tools/loop_helpers.py                       ✓ Helpers
[PASS] groq (for free AI)                          ✓ (or cerebras/sambanova/openrouter)
[PASS] playwright (installed)                      ✓
[PASS] supabase (installed)                        ✓
[PASS] Flask Tester (running on 127.0.0.1:5000)   ✓
[PASS] Local Supabase (running on 127.0.0.1:54321) ✓
[PASS] Git repository                              ✓
[PASS] Test images                                 ✓

[OPTIONAL] Free AI Provider Key (pick ONE)         ← RECOMMENDED: Set GROQ_API_KEY
```

---

## Step 1: Set a Free AI Provider Key

Choose ONE free tier provider (no credit card required):

| Provider | Key Variable | Free Tier | Setup URL |
|----------|--------------|-----------|-----------|
| **Groq** (Recommended) | `GROQ_API_KEY` | Yes, unlimited | https://console.groq.com |
| Cerebras | `CEREBRAS_API_KEY` | Yes, unlimited | https://cerebras.ai |
| SambaNova | `SAMBANOVA_API_KEY` | Yes, unlimited | https://sambanova.ai |
| OpenRouter | `OPENROUTER_API_KEY` | Yes, $5 credits | https://openrouter.ai |

### Get Groq API Key (Easiest):
1. Go to https://console.groq.com
2. Sign up (free)
3. Create API key
4. Copy the key

### Set Environment Variable:

**Windows PowerShell:**
```powershell
$env:GROQ_API_KEY = "gsk_your-key-here"
```

**Windows Command Prompt:**
```cmd
set GROQ_API_KEY=gsk_your-key-here
```

**macOS/Linux:**
```bash
export GROQ_API_KEY="gsk_your-key-here"
```

### Verify it's set:
```bash
python -c "import os; print('Free AI:', 'SET' if os.getenv('GROQ_API_KEY') else 'NOT SET')"
```

---

## Step 2: Run Pre-Flight Check Again

```bash
python tools/preflight_check.py
```

Expected output:
```
[PASS] All checks passed! Ready to run the loop.

Quick start:
  python tools/ai_self_improvement_loop.py --fast --surface=VOICE
```

---

## Step 3: Run the Loop

### Option A: Quick Test (3 min, Voice only)
```bash
python tools/ai_self_improvement_loop.py --fast --surface=VOICE
```

### Option B: Full Loop (5 min, all surfaces)
```bash
python tools/ai_self_improvement_loop.py
```

### Option C: Via Release Gate (10 min, includes full validation)
```bash
python release_gate.py --with-ai-deep
```

---

## What to Expect

### Successful Run Output:

```
======================================================================
AI SELF-IMPROVEMENT LOOP (Playwright-Driven)
======================================================================

[Pre-requisites Check]
  [PASS] Flask seeder reachable (127.0.0.1:5000)
  [PASS] Local Supabase reachable (127.0.0.1:54321)

[Layer 0] Scenario Execution
  Running: Phase 3: KB Citation Retrieval... [PASS]
  Running: Phase 5: Critical Alert Surfacing... [PASS]
  Running: Phase 8: Analytics Logging... [PASS]

  Results: 10 PASS | 0 FAIL

  All scenarios passing! Skipping to meta-validator.

[Layer 4] Meta-Validator (Loop Guardian)
  [PASS] Loop integrity OK. Safe to continue.

[FINAL] Fast Mega Gate
  Results: 130 PASS | 0 FAIL

======================================================================
LOOP PASS — Ready for deployment
======================================================================

Staged changes ready.
  git diff --stat

To review all changes:
  git diff

To approve and commit:
  git add -A
  git commit -m "Auto-improvement from AI self-learning loop"
  git push origin master
```

### If Scenarios Fail:

The loop will automatically:
1. Analyze failures with Claude
2. Extract findings (missing context, format errors, etc)
3. Auto-fix the issues (update prompts, reseed data, fix logic)
4. Create validators to prevent regression
5. Re-run scenarios to verify fixes work
6. Run fast gate with new validators

Output will show:
```
[Layer 0] Scenario Execution
  Results: 8 PASS | 2 FAIL

[Layer 1] Failure Analysis
  → FINDING-20260517120000-V-00: missing_alert (confidence: 0.95)
  → FINDING-20260517120001-V-01: wrong_order (confidence: 0.88)

[Layer 2] Auto-Remediation
  → Fixed alert priority instruction in voice-handler.js
  → Marked for reseeding: voice_companion_phase5_alerts.py

[Layer 3] Validator Generation
  → Generated validator: validate_voice_alert_order.py
  → Registered in GATES: voice-alert-order

[Layer 4] Meta-Validator
  [PASS] Loop integrity OK

[FINAL] Fast Mega Gate
  Including new validators...
  Results: 131 PASS | 0 FAIL

LOOP PASS — Ready for deployment
```

---

## Troubleshooting

### "No free AI provider configured"
- Set ONE of: `GROQ_API_KEY`, `CEREBRAS_API_KEY`, `SAMBANOVA_API_KEY`, `OPENROUTER_API_KEY`
- Groq recommended (free, unlimited): https://console.groq.com
- Verify: `echo $GROQ_API_KEY` (should show key starting with `gsk_`)

### "Groq API error: 401 Unauthorized"
- Check API key is correct: `echo $GROQ_API_KEY`
- Regenerate at https://console.groq.com/keys if needed
- Make sure it starts with `gsk_`

### "Model not found" (from Groq/Cerebras)
- Groq free models: `mixtral-8x7b-32768` (available)
- These are constantly available free tier options
- Try a different free provider if one is down

### "playwright timeout (no response from AI)"
- Check Flask is running: http://127.0.0.1:5000/workhive/tester
- Check browser can load voice-journal.html
- Check Supabase is running: `docker ps`

### "Services not running"
```bash
# Start Supabase
supabase start

# Start Flask (in new terminal)
cd test-data-seeder
python app.py
```

### "anthropic not installed"
```bash
pip install anthropic
```

### "playwright install failed"
```bash
pip install --upgrade playwright
playwright install chromium
```

---

## Files That Will Be Created/Modified

After first successful run:

**New files** (Layer 0-4 outputs):
```
SCENARIO_RESULTS.json              # Layer 0: all scenario results
SCENARIO_FINDINGS.jsonl            # Layer 1: extracted findings (append mode)
FIX_LOG.json                       # Layer 2: fixes applied
VALIDATOR_REGISTRY.json            # Layer 3: validators created
LOOP_METADATA.json                 # Metadata for this run
test-images/defect-example.jpg     # Test image (if created)
```

**Generated validators** (one per unique finding):
```
tools/validate_voice_alert_order.py
tools/validate_voice_kb_context.py
tools/validate_visual_defect_confidence.py
tools/validate_calc_formula_accuracy.py
tools/validate_chat_pii_redaction.py
# ... etc (only if findings detected)
```

**Modified files**:
```
run_platform_checks.py             # Layer 3: new validators registered
voice-handler.js                   # Layer 2: prompt/logic fixes (if needed)
# ... other files based on findings
```

**Git status**:
```
git status
# Shows modified files, staged changes ready to commit
git diff
# Shows exactly what was fixed
```

---

## Next Steps After First Successful Run

1. **Review changes**:
   ```bash
   git diff
   git diff --stat
   ```

2. **Commit**:
   ```bash
   git add -A
   git commit -m "Auto-improvement from AI self-learning loop"
   ```

3. **Push** (if approved):
   ```bash
   git push origin master
   ```

4. **Optional: Schedule daily runs**:
   ```bash
   # Add to crontab for 2 AM daily
   crontab -e
   # 0 2 * * * cd /path/to/repo && python tools/ai_self_improvement_loop.py
   ```

5. **Optional: Add to CI/CD**:
   - Post-deploy validation
   - Block deploy if loop finds regressions

---

## Quick Reference

| Command | Purpose | Time |
|---------|---------|------|
| `python tools/preflight_check.py` | Verify all systems ready | <1m |
| `python tools/ai_self_improvement_loop.py --fast --surface=VOICE` | Quick smoke test (Voice only) | 3m |
| `python tools/ai_self_improvement_loop.py` | Full loop (all surfaces) | 5m |
| `python release_gate.py --with-ai-deep` | Full Release Gate with AI loop | 10m |
| `git diff` | Review all changes made | <1m |
| `git add -A && git commit -m "..."` | Commit fixes | <1m |

---

## You're Ready!

```
Command to run now:

python tools/ai_self_improvement_loop.py --fast --surface=VOICE
```

This will:
1. Run Voice scenarios (Playwright)
2. Show results
3. If failures found → auto-fix + validator generation
4. Run meta-validator + fast gate
5. Show exact git changes

Good luck! 🚀
