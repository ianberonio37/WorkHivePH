# AI Self-Improvement Loop — Quick Start

## Architecture Complete ✓

All 4 layers + orchestrator are built and wired to Release Gate:

1. **Layer 0**: `tools/playwright_scenario_executor.py` — Run Playwright scenarios (all surfaces)
2. **Layer 1**: `tools/analyze_scenario_findings.py` — Claude analyzes failures
3. **Layer 2**: `tools/auto_fix_findings.py` — Auto-fix issues (prompt, seeding, logic)
4. **Layer 3**: `tools/generate_and_register_validator.py` — Create validators dynamically
5. **Layer 4**: `tools/validate_improvement_loop_integrity.py` — Guard the loop itself
6. **Orchestrator**: `tools/ai_self_improvement_loop.py` — Ties all layers together
7. **Release Gate**: Updated with `--with-ai-deep` flag

---

## Test 1: Quick Smoke Test (5 min)

**Goal**: Verify all layers work and loop completes without errors.

```bash
# Start services (if not already running)
docker start supabase_edge_runtime_workhive  # Local Supabase
python test-data-seeder/app.py              # Flask Tester

# Open WorkHive Tester: http://127.0.0.1:5000/workhive/tester

# Wait for dashboard to load, then click:
# "Release Gate + AI Full (Groq · ~5min · $0)" button

# OR run from command line:
python tools/ai_self_improvement_loop.py --fast

# Expected output:
# [✓] Scenarios: X PASS | Y FAIL
# [✓] Layer 0: Scenario Execution
# [✓] Layer 1: Failure Analysis (if failures found)
# [✓] Layer 2: Auto-Remediation (if failures found)
# [✓] Layer 3: Validator Generation (if failures found)
# [✓] Layer 4: Meta-Validator
# [✓] Final: Fast Mega Gate
# LOOP PASS — Ready for deployment
```

---

## Test 2: Single Surface (2 min each)

Test each AI surface independently:

```bash
# Voice only
python tools/ai_self_improvement_loop.py --surface=VOICE --fast

# Visual only
python tools/ai_self_improvement_loop.py --surface=VISUAL --fast

# AMC only
python tools/ai_self_improvement_loop.py --surface=AMC --fast

# Calc only
python tools/ai_self_improvement_loop.py --surface=CALC --fast

# Chat only
python tools/ai_self_improvement_loop.py --surface=CHAT --fast
```

---

## Test 3: Full Loop with All Surfaces (5 min)

```bash
python tools/ai_self_improvement_loop.py  # (no --fast, all surfaces)

# This will:
# 1. Run ~15 scenarios across all 5 surfaces
# 2. Find any failures
# 3. Analyze with Claude
# 4. Auto-fix issues
# 5. Create validators
# 6. Run meta-validator
# 7. Run fast mega gate
# 8. Output: PASS or FAIL
```

---

## Test 4: Introduce a Deliberate Bug (10 min)

**Goal**: Verify the loop CATCHES and FIXES real bugs.

```bash
# Step 1: Introduce a bug
# Edit voice-handler.js, find alertsSection (around line 1601)
# Change: const alertsSection = (proactiveAlerts && proactiveAlerts.length)
# To:     const alertsSection = false  // Intentionally break alert surfacing

# Step 2: Run the loop
python tools/ai_self_improvement_loop.py --surface=VOICE

# Expected:
# Layer 0: Scenario fails (alerts not surfacing)
# Layer 1: Finds: "wrong_order" or "missing_alert"
# Layer 2: Auto-fixes the bug (restores alertsSection)
# Layer 3: Creates validate_voice_alert_order.py
# Layer 4: Meta-validator: all checks PASS
# Final: Fast gate PASS (new validator prevents regression)

# Step 3: Verify fix
git diff voice-handler.js   # Should show the fix
git diff run_platform_checks.py  # Should show new validator registration
```

---

## Test 5: Via Release Gate (10 min)

**Goal**: Verify Release Gate integration works.

```bash
# With AI loop enabled
python release_gate.py --with-ai-deep

# Expected output:
# ✓ Pre-flight
# ✓ Phase 1: Reseed
# ✓ Phase 2: Static validators
# ✓ Phase 3: Data tests
# ✓ Phase 4: UI tests
# ✓ Phase 4b: AI Self-Improvement Loop
# GATE PASS — safe to deploy
```

---

## Troubleshooting

### "Flask seeder not running"
```bash
python test-data-seeder/app.py
# Or click the shortcut in /test-data-seeder
```

### "Local Supabase not running"
```bash
docker start supabase_edge_runtime_workhive
# Or: supabase start (from project root)
```

### "anthropic not installed"
```bash
pip install anthropic
# Or: pip install -r test-data-seeder/requirements.txt
```

### "playwright not installed"
```bash
pip install playwright
playwright install chromium
```

### "Scenario timeout (no response from AI)"
- Check that voice-journal.html is loading
- Verify Claude API key in environment
- Check browser console (F12) for JS errors

### "Loop completed but no findings extracted"
- This is normal if all scenarios are passing
- The loop skips auto-fix and validator generation
- Fast gate still runs to verify nothing broke

---

## Expected File Changes After First Run

```
SCENARIO_RESULTS.json         # Layer 0 output: scenario results
SCENARIO_FINDINGS.jsonl       # Layer 1 output: extracted findings (one per line)
FIX_LOG.json                  # Layer 2 output: fixes applied
VALIDATOR_REGISTRY.json       # Layer 3 output: validators registered
LOOP_METADATA.json            # Metadata for audit trail

tools/validate_voice_alert_order.py       # Layer 3: generated validator
tools/validate_voice_kb_context.py        # Layer 3: generated validator
tools/validate_visual_defect_confidence.py # Layer 3: generated validator
# ... etc (one per finding)

run_platform_checks.py        # Layer 3: updated with new validators
git diff                      # All staged changes (fixes + new validators)
```

---

## Success Criteria

- ✅ All layers execute without errors
- ✅ Playwright runs in <5 min (same as current --with-ai flag)
- ✅ Cost $0 (no paid API calls, Groq only)
- ✅ Scenarios detect real failures (Voice, Visual, AMC, Calc, Chat)
- ✅ Claude analyzes findings with >80% confidence
- ✅ Auto-fixes are staged (git diff shows changes)
- ✅ Validators created for all findings (0 deferral)
- ✅ Meta-validator shows all checks PASS
- ✅ Fast gate passes (all validators including new ones)
- ✅ Release Gate integration works (--with-ai-deep flag)

---

## Next Steps After Test

Once you confirm the loop works:

1. **Commit the layer implementations**
   ```bash
   git add tools/*.py
   git commit -m "Layer 0-4: AI self-improvement loop (Playwright + Claude)"
   ```

2. **Set up scheduled runs** (optional)
   ```bash
   # Daily at 2 AM
   crontab -e
   # Add: 0 2 * * * cd /path/to/repo && python tools/ai_self_improvement_loop.py
   ```

3. **Add to CI/CD** (optional)
   - Post-deploy validation
   - Run on every release candidate
   - Block deploy if loop finds regressions

4. **Monitor loop health**
   - Check LOOP_METADATA.json after each run
   - Watch SCENARIO_FINDINGS.jsonl for recurring issues
   - Review auto-generated validators (validate_improvement_loop_integrity.py)

---

## Full Loop Flow (Reference)

```
USER CLICKS "Release Gate + AI Full"
        ↓
RELEASE_GATE.PY --with-ai-deep
        ↓
PHASE 4b: AI_SELF_IMPROVEMENT_LOOP.PY
        ├─ LAYER 0: playwright_scenario_executor.py
        │         → Run 10-15 scenarios (all surfaces)
        │         → SCENARIO_RESULTS.json
        ├─ CHECK: All passing?
        │         YES → Skip to Layer 4
        │         NO  → Continue to Layer 1
        ├─ LAYER 1: analyze_scenario_findings.py
        │         → Claude analyzes failures
        │         → SCENARIO_FINDINGS.jsonl
        ├─ LAYER 2: auto_fix_findings.py
        │         → Stage file changes
        │         → FIX_LOG.json
        ├─ LAYER 3: generate_and_register_validator.py
        │         → Create validate_*.py files
        │         → Update run_platform_checks.py
        │         → VALIDATOR_REGISTRY.json
        ├─ LAYER 4: validate_improvement_loop_integrity.py
        │         → Check: findings → validators
        │         → Check: no deferral
        │         → Check: metadata consistent
        └─ FINAL: run_platform_checks.py --fast
                → All validators (130+ + new ones)
                → PASS → LOOP COMPLETE
                → FAIL → LOOP BLOCKED
        ↓
USER REVIEW
        git diff          # See all staged changes
        git status        # See which files changed
        ↓
USER APPROVAL
        git add -A
        git commit -m "Auto-improvement: AI scenarios found and fixed..."
        git push origin master
        ↓
DEPLOY (safe, all validators passed)
```

Good luck! Run Test 1 first to make sure everything's wired up correctly.
