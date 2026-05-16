# AI Self-Improvement Loop — Quick Start Guide

Your fully automated Playwright-driven AI self-improvement loop is now live. It runs on free-tier AI providers (Groq, Cerebras, SambaNova, OpenRouter) with zero paid API calls.

## What It Does

In one command, the loop:
1. **Runs Playwright UI scenarios** across your AI surfaces (Voice, Visual, AMC, Calc, Chat)
2. **Captures actual failures** and response data
3. **Calls free-tier AI (Groq)** to analyze each failure and extract findings
4. **Auto-generates validators** based on the findings
5. **Registers validators** in your platform gate
6. **Validates the loop itself** (meta-validator ensures coverage)
7. **Runs mega gate** to confirm everything passes

## Quick Start

### Run the loop (fast mode, Voice surface only):
```bash
python tools/ai_self_improvement_loop.py --fast --surface=VOICE
```

### Run all surfaces (full mode):
```bash
python tools/ai_self_improvement_loop.py
```

### Run specific surface:
```bash
python tools/ai_self_improvement_loop.py --surface=VISUAL
python tools/ai_self_improvement_loop.py --surface=CHAT
```

## Expected Output

### Success Flow
```
Layer 0: Scenario Execution       → 0 PASS | 2 FAIL
Layer 1: Failure Analysis         → 4 findings extracted
Layer 2: Auto-Remediation         → suggestions logged
Layer 3: Validator Generation     → 4 validators created + registered
Layer 4: Meta-Validator           → 5/5 PASS (integrity confirmed)
Final: Fast Mega Gate             → all validators pass
```

### If Meta-Validator Fails
If check `[Check 1] Finding -> Validator Coverage` fails, it means some findings don't have validator templates. Add the missing templates in `generate_and_register_validator.py` → `VALIDATOR_TEMPLATES` dict.

## Output Files

After each run, the loop creates:

| File | Purpose |
|------|---------|
| `SCENARIO_RESULTS.json` | All scenarios, pass/fail, capture data |
| `SCENARIO_FINDINGS.jsonl` | AI-extracted findings (1 per line) |
| `FIX_LOG.json` | Auto-remediation log |
| `VALIDATOR_REGISTRY.json` | Validators created this run |
| `LOOP_METADATA.json` | Timing, counts, layer results |

## Validator Mapping (Finding Type → Validator)

Currently mapped:
- `latency_high` → `voice_response_latency`
- `format_error` → `response_format_validation`
- `incomplete_data` → `data_completeness`
- `missing_alert` → `voice_alert_order`
- `missing_kb_context` → `voice_kb_context`
- `wrong_order` → `voice_alert_order`
- `confidence_low` → `visual_defect_confidence`
- `schema_mismatch` → `calc_formula_accuracy`

To add new finding types, add a template and mapping:

```python
# In generate_and_register_validator.py

VALIDATOR_TEMPLATES = {
    "your_finding_type": '''#!/usr/bin/env python3
...your validator code...
''',
}

type_to_validator = {
    "your_finding_type": "your_validator_key",
}
```

## How the Loop Works

### Layer 0: Playwright Scenarios
Predefined scenarios in `playwright_scenario_executor.py` → `SCENARIOS` dict.
Each surface has test steps, validations, and capture rules.
Current: 2 Voice scenarios (KB citation, critical alerts).

### Layer 1: Failure Analysis
Groq analyzes each failed scenario using `call_claude_free()`.
Returns structured JSON: `{finding_type, description, root_cause, suggested_fix_type, confidence}`.

### Layer 2: Auto-Remediation
Routes findings to fix modules:
- `prompt_update` → updates prompts in voice-handler.js
- `seeding` → marks test data for regeneration
- `rpc_change` → suggests RPC modifications
- `logic_fix` → applies logic changes
- `migration` → suggests schema migrations

### Layer 3: Validator Generation
Creates new validator files dynamically.
Maps finding types to validator templates.
Auto-registers in `run_platform_checks.py` GATES list.

### Layer 4: Meta-Validator
Checks loop health:
- Finding → Validator coverage
- Deferral tracking (PRODUCTION_FIXES.md)
- Test data reproducibility
- Metadata consistency
- Fast gate registration

Exit code:
- `0` = loop complete, validators pass
- `1` = loop error, check logs
- `2` = meta-validator found issues

## Environment Setup

Requires `.env` with one of:
```
GROQ_API_KEY=...              # Free tier (recommended)
CEREBRAS_API_KEY=...          # Fallback #1
SAMBANOVA_API_KEY=...         # Fallback #2
OPENROUTER_API_KEY=...        # Fallback #3
```

Groq free tier: 30 RPM, 6000 TPM, 14,400 req/day (per model).
With your 2 scenarios, you'll use ~20 requests per loop run.

## What to Expect

First run: Loop will likely extract findings around:
- **Latency issues** (UI timeouts, slow API calls)
- **Missing data** (KB not fetched, alerts not surfaced)
- **Format problems** (response structure issues)

Loop will auto-generate validators for each. Run again, and your new validators will catch regressions in those areas.

## Next Steps

1. Run once: `python tools/ai_self_improvement_loop.py --fast --surface=VOICE`
2. Check `SCENARIO_FINDINGS.jsonl` for extracted insights
3. Review generated validators in `tools/validate_*.py`
4. Look at `LOOP_METADATA.json` for timing and coverage stats
5. Run again: loop learns from previous findings

## Integrating with Release Gate

To run the loop as part of your release gate:

```bash
python release_gate.py --with-ai-deep
```

This will:
1. Run all normal gates (L0 validators)
2. Run the AI self-improvement loop (4 layers)
3. Include loop result in final verdict

## Troubleshooting

| Issue | Fix |
|-------|-----|
| No API key found | Set `GROQ_API_KEY` in `.env` and reload |
| Scenario timeouts | Increase `wait_until="networkidle"` timeout in Layer 0 |
| Validator template error | Check `type_to_validator` mapping matches finding types |
| Meta-validator fails | Run `python tools/validate_improvement_loop_integrity.py` to see detail |
| Fast gate timeout | Pre-existing gate issues (unrelated to loop) |

## Free-Tier Cost

Entire loop runs on **$0/month**:
- Groq: 30k+ req/day free (you use ~20 per loop)
- No database writes for findings (JSON files only)
- No paid APIs ever called

---

**Built:** 2026-05-17 | **AI Provider:** Groq (llama-3.3-70b-versatile) | **Fallback Chain:** Cerebras → SambaNova → OpenRouter
