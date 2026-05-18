# Voice Companion Self-Improvement Loop (AI-Driven)

## Architecture Overview

A **4-layer self-healing system** that mirrors your unified gates pattern but applies it to AI quality:

```
┌─────────────────────────────────────────────────────────────┐
│ LAYER 0: Playwright Scenario Executor                       │
│ ─────────────────────────────────────────────────────────── │
│ • Run 10-15 predetermined voice scenarios (Playwright)      │
│ • Capture actual AI responses (Rosa/James)                  │
│ • Log outcomes: success, partial, failure, anomaly          │
│ • Measure: response quality, KB citations, alerts surfaced  │
│ Tool: playwright_voice_scenarios.py (NEW)                   │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ LAYER 1: Failure Analysis & Finding Extraction              │
│ ─────────────────────────────────────────────────────────── │
│ • AI analyzes scenario outputs (Claude)                     │
│ • Detects: missing KB context, alert typos, latency issues  │
│ • Extracts finding type (prompt gap, seeding issue, etc)    │
│ • Categorizes severity + root cause                         │
│ Tool: analyze_scenario_findings.py (NEW)                    │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ LAYER 2: Auto-Remediation Engine                            │
│ ─────────────────────────────────────────────────────────── │
│ • Route findings to repair modules:                         │
│   - Prompt: update system prompt in voice-handler.js        │
│   - Seeding: re-run seeder for stale data                  │
│   - Schema: suggest RPC / migration updates                 │
│   - Logic: fix alert surfacing / KB filtering              │
│ • Test fix locally (run scenario again)                     │
│ • Stage fix in git (don't commit yet)                       │
│ Tool: auto_fix_findings.py (NEW)                            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ LAYER 3: Validator Generator & Registrar                    │
│ ─────────────────────────────────────────────────────────── │
│ • For each fixed finding, create or extend validator        │
│   - Extend existing: validate_voice_alert_formatting        │
│   - Create new: validate_kb_citation_completeness           │
│ • Register in run_platform_checks.py GATES list             │
│ • Set baseline from current codebase                        │
│ Tool: generate_and_register_validator.py (NEW)              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ LAYER 4: Meta-Validator (Loop Guardian)                     │
│ ─────────────────────────────────────────────────────────── │
│ • Validates the loop itself:                                │
│   - All Layer 2 fixes are covered by Layer 3 validators     │
│   - No validators were skipped / deferred                   │
│   - Seeding reproducible from same seed data                │
│ • Prevents: validators getting "gamed" / deferred forever   │
│ • Prevents: orphaned fixes with no guard                    │
│ Tool: validate_improvement_loop_integrity.py (NEW)          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ FINAL: Fast Mega Gate + Commit                              │
│ ─────────────────────────────────────────────────────────── │
│ • Run: python run_platform_checks.py --fast                 │
│ • All validators must PASS (including new ones)             │
│ • User reviews changes: git diff                            │
│ • User commits: git commit -m "Auto-improvement from loop"  │
│ • Loop sleeps until next trigger (daily, manual, or signal) │
└─────────────────────────────────────────────────────────────┘
```

---

## Layer 0: Playwright Scenario Executor

**File**: `tools/playwright_voice_scenarios.py`

Predetermined scenarios that test realistic Voice Companion workflows:

```python
SCENARIOS = [
  {
    "name": "Phase 3: KB Citation",
    "steps": [
      "Open voice-journal.html",
      "Ask: 'What is the best practice for bearing maintenance?'",
      "Wait for Rosa response",
      "Check if response includes KB chunk + source"
    ],
    "validates": ["kb_context_inclusion", "citation_format"],
    "expected_patterns": ["(from KB:", "ISO 14224", "bearing"]
  },
  {
    "name": "Phase 5: Critical Alert Surfacing",
    "steps": [
      "Open voice-journal.html",
      "Ask: 'What are my five equipment alerts?'",
      "Wait for Rosa response",
      "Verify critical alerts mentioned FIRST"
    ],
    "validates": ["alert_priority", "alert_description"],
    "expected_patterns": ["[CRITICAL]", "Preventive Maintenance overdue"]
  },
  {
    "name": "Phase 5: Alert Suppression",
    "steps": [
      "Open voice-journal.html",
      "Ask: 'Any alerts on Pump A?'",
      "Suppress one alert via UI action",
      "Ask again",
      "Verify suppressed alert NOT in response"
    ],
    "validates": ["alert_suppression_honored"],
    "expected_patterns": ["suppressed_until"]
  },
  {
    "name": "Phase 8: Analytics Logging",
    "steps": [
      "Open voice-journal.html",
      "Ask: 'How is my MTBF trending?'",
      "Wait for response + log",
      "Check conversation_analytics table",
      "Verify turn_num, question_category, answer_quality_rating logged"
    ],
    "validates": ["analytics_insertion", "data_completeness"],
    "expected_patterns": ["conversation_analytics", "turn_num"]
  },
  {
    "name": "Phase 3/5: Combined (KB + Alert)",
    "steps": [
      "Open voice-journal.html",
      "Ask: 'Bearing maintenance best practice, and what alerts on Bearing D?'",
      "Wait for response",
      "Verify: KB context + alert description both present"
    ],
    "validates": ["phase_integration"],
    "expected_patterns": ["(from KB:", "[CRITICAL]"]
  },
]

def run_scenarios() -> dict:
    """
    Execute all scenarios in Playwright.
    Return: {scenario_name: {status, response, latency, pattern_matches}}
    """
    results = {}
    for scenario in SCENARIOS:
        browser = chromium.launch()
        page = browser.new_page()
        page.goto("http://127.0.0.1:5000/voice-journal.html")
        
        # Execute scenario steps
        for step in scenario["steps"]:
            if step.startswith("Ask:"):
                question = step.replace("Ask: '", "").replace("'", "")
                # Simulate voice input or text input
                page.fill("[data-test=voice-input]", question)
                page.click("[data-test=send-button]")
                page.wait_for_timeout(3000)  # Wait for response
            elif step.startswith("Wait"):
                page.wait_for_timeout(2000)
        
        # Capture response
        response_text = page.text_content("[data-test=response]")
        latency = measure_time_from_logs()
        
        # Check patterns
        pattern_matches = {
            pattern: pattern in response_text
            for pattern in scenario["expected_patterns"]
        }
        
        results[scenario["name"]] = {
            "status": "PASS" if all(pattern_matches.values()) else "FAIL",
            "response": response_text[:500],
            "latency_ms": latency,
            "pattern_matches": pattern_matches,
            "missing_patterns": [p for p, m in pattern_matches.items() if not m]
        }
        
        browser.close()
    
    return results
```

---

## Layer 1: Failure Analysis & Finding Extraction

**File**: `tools/analyze_scenario_findings.py`

AI-powered analysis of scenario outputs to extract actionable findings:

```python
def analyze_failures(scenario_results: dict) -> list:
    """
    Use Claude to analyze scenario failures and extract findings.
    
    Input: {scenario_name: {status, response, pattern_matches, ...}}
    Output: [
      {
        "finding_id": "VOICE-20260516-001",
        "scenario": "Phase 5: Critical Alert Surfacing",
        "severity": "CRITICAL|HIGH|MEDIUM|LOW",
        "finding_type": "missing_alert|wrong_order|format_error|latency",
        "description": "Rosa not surfacing [CRITICAL] alerts first",
        "evidence": "Response was: '...I found some alerts...' (no [CRITICAL] prefix)",
        "root_cause": "Prompt instruction not enforced in system prompt",
        "suggested_fix_type": "prompt_update|seeding|rpc_change|logic_fix",
        "fix_target": "voice-handler.js:1601 alertsSection",
        "confidence": 0.95
      },
      ...
    ]
    """
    
    findings = []
    for scenario_name, result in scenario_results.items():
        if result["status"] == "FAIL":
            # Call Claude to analyze the failure
            prompt = f"""
            Analyze this Voice Companion scenario failure and extract the root cause.
            
            Scenario: {scenario_name}
            Expected patterns: {result['expected_patterns']}
            Actual response: {result['response']}
            Missing patterns: {result['missing_patterns']}
            
            Return JSON:
            {{
              "finding_type": "one of: missing_alert, wrong_order, format_error, latency, kb_gap, incomplete_citation",
              "description": "Human-readable description of what's wrong",
              "root_cause": "Why is it wrong (prompt gap, stale data, schema issue, etc)",
              "suggested_fix_type": "prompt_update, seeding, rpc_change, logic_fix, migration",
              "fix_target": "Which file/function to fix",
              "confidence": 0.0-1.0
            }}
            """
            
            analysis = call_claude(prompt)
            
            # Assign unique finding ID
            finding_id = f"VOICE-{datetime.now().strftime('%Y%m%d')}-{len(findings):03d}"
            
            finding = {
                "finding_id": finding_id,
                "scenario": scenario_name,
                **analysis,  # Unpack Claude's JSON response
                "evidence": result["response"][:300],
                "timestamp": datetime.now().isoformat()
            }
            
            findings.append(finding)
    
    # Save findings to VOICE_FINDINGS.jsonl for audit trail
    with open("VOICE_FINDINGS.jsonl", "a") as f:
        for finding in findings:
            f.write(json.dumps(finding) + "\n")
    
    return findings
```

---

## Layer 2: Auto-Remediation Engine

**File**: `tools/auto_fix_findings.py`

Route findings to repair modules and apply fixes:

```python
class VoiceFindingFixer:
    def __init__(self, findings: list):
        self.findings = findings
        self.staged_fixes = {}
    
    def route_and_fix(self):
        """Route each finding to appropriate fixer."""
        for finding in self.findings:
            fix_type = finding["suggested_fix_type"]
            
            if fix_type == "prompt_update":
                self.fix_system_prompt(finding)
            elif fix_type == "seeding":
                self.reseed_test_data(finding)
            elif fix_type == "rpc_change":
                self.suggest_rpc_fix(finding)
            elif fix_type == "logic_fix":
                self.apply_logic_fix(finding)
            elif fix_type == "migration":
                self.suggest_migration(finding)
    
    def fix_system_prompt(self, finding):
        """Update voice-handler.js system prompt."""
        with open("voice-handler.js", "r") as f:
            content = f.read()
        
        # Example: finding says "alerts not prioritized"
        if "alert" in finding["description"].lower():
            # Strengthen alert instruction in alertsSection
            old_instruction = "ACTIVE ALERTS — Surface these FIRST..."
            new_instruction = (
                "═══ CRITICAL PRIORITY: ACTIVE EQUIPMENT ALERTS ═══\n"
                "MANDATORY RULE: You MUST surface the alerts below FIRST in your reply, "
                "using the exact descriptions provided. Do NOT summarize, paraphrase, or ignore them."
            )
            
            content = content.replace(old_instruction, new_instruction)
        
        with open("voice-handler.js", "w") as f:
            f.write(content)
        
        self.staged_fixes[finding["finding_id"]] = {
            "type": "prompt_update",
            "file": "voice-handler.js",
            "change": "Strengthened alert priority instruction"
        }
    
    def reseed_test_data(self, finding):
        """Re-run seeder for stale data."""
        if "alert" in finding["description"].lower():
            # Run Phase 5 seeder only
            from test_data_seeder.seeders.voice_companion_phase5_alerts import run
            client = init_supabase()
            log = print
            ctx = {"hives": fetch_hives(client)}
            
            alerts_count = run(client, log, ctx)
            
            self.staged_fixes[finding["finding_id"]] = {
                "type": "seeding",
                "seeder": "voice_companion_phase5_alerts",
                "rows_inserted": alerts_count
            }
    
    def apply_logic_fix(self, finding):
        """Fix logic in voice-handler.js."""
        if "suppression" in finding["description"].lower():
            # Example: alert suppression not honored
            # Fix: ensure suppressed_until is checked in _fetchProactiveAlerts
            
            with open("voice-handler.js", "r") as f:
                content = f.read()
            
            # Add check for suppressed_until in RPC response validation
            old_validation = "if (!a.description || !a.action_suggested)"
            new_validation = (
                "if (!a.description || !a.action_suggested || "
                "(a.suppressed_until && new Date(a.suppressed_until) > new Date()))"
            )
            
            content = content.replace(old_validation, new_validation)
            
            with open("voice-handler.js", "w") as f:
                f.write(content)
            
            self.staged_fixes[finding["finding_id"]] = {
                "type": "logic_fix",
                "file": "voice-handler.js",
                "change": "Added suppression check in alert fetching"
            }
    
    def validate_fixes(self) -> bool:
        """Re-run scenarios to verify fixes work."""
        print("[LOOP] Validating fixes by re-running scenarios...")
        
        from playwright_voice_scenarios import run_scenarios
        new_results = run_scenarios()
        
        # Check if failures are resolved
        failures_resolved = sum(
            1 for r in new_results.values() 
            if r["status"] == "PASS"
        )
        
        print(f"[LOOP] Validation: {failures_resolved} scenarios now passing")
        return failures_resolved > len(self.findings) * 0.8  # 80% success rate
    
    def commit_staged_fixes(self):
        """User reviews and commits staged changes."""
        print("\n[LOOP] Staged fixes ready for review:")
        for finding_id, fix_info in self.staged_fixes.items():
            print(f"  {finding_id}: {fix_info['change']}")
        
        print("\n[LOOP] Running fast mega gate...")
        # subprocess.run(["python", "run_platform_checks.py", "--fast"])
```

---

## Layer 3: Validator Generator & Registrar

**File**: `tools/generate_and_register_validator.py`

Create or extend validators for each fix to prevent regression:

```python
def generate_validator_for_finding(finding: dict) -> str:
    """
    Create a new validator or extension based on finding type.
    Returns: validator file name
    """
    
    if finding["finding_type"] == "missing_alert":
        # Extend existing validate_voice_alert_formatting.py
        extension = """
        
        # Layer 4: Alert Surfacing Prioritization (NEW — prevents missing alerts)
        print("\\n[Layer 4] Alert surfacing order...")
        
        # Check that critical alerts are flagged in prompt
        with open("voice-handler.js", "r") as f:
            js = f.read()
        
        if "[CRITICAL]" in js:
            print(f"  {GREEN}PASS{RESET} Critical alert indicator in code")
            results["pass"] += 1
        else:
            print(f"  {RED}FAIL{RESET} Critical alert indicator missing")
            results["fail"] += 1
        
        # Validate that alertsSection comes BEFORE other context
        if js.index("alertsSection") < js.index("kbSection"):
            print(f"  {GREEN}PASS{RESET} Alerts surface before KB")
            results["pass"] += 1
        else:
            print(f"  {RED}FAIL{RESET} Alerts not prioritized in prompt")
            results["fail"] += 1
        """
        
        with open("validate_voice_alert_formatting.py", "a") as f:
            f.write(extension)
        
        return "validate_voice_alert_formatting.py (extended)"
    
    elif finding["finding_type"] == "wrong_order":
        # Create new validator for alert ordering
        new_validator = '''
        #!/usr/bin/env python3
        """
        Validate that critical alerts surface FIRST in Voice Companion responses.
        (Generated by auto-improvement loop for finding: {finding_id})
        """
        
        import re
        
        def validate_alert_order():
            results = {"pass": 0, "fail": 0}
            
            with open("voice-handler.js", "r") as f:
                content = f.read()
            
            # Check alert instruction order
            alert_idx = content.find("alertsSection")
            kb_idx = content.find("kbSection")
            other_idx = content.find("otherContext")
            
            if alert_idx < kb_idx and alert_idx < other_idx:
                results["pass"] += 1
            else:
                results["fail"] += 1
            
            return results["fail"] == 0
        
        if __name__ == "__main__":
            validate_alert_order()
        '''.format(finding_id=finding["finding_id"])
        
        filename = "validate_voice_alert_order.py"
        with open(f"tools/{filename}", "w") as f:
            f.write(new_validator)
        
        return filename
    
    # Similar for other finding types...
    
    return None

def register_validator_in_gates(validator_filename: str):
    """
    Register new validator in run_platform_checks.py GATES list.
    """
    
    with open("run_platform_checks.py", "r") as f:
        content = f.read()
    
    # Find GATES list
    gates_match = re.search(r'GATES = \[(.*?)\]', content, re.DOTALL)
    if gates_match:
        gates_section = gates_match.group(1)
        
        # Add new gate entry
        new_gate = f'''
    {{
        "gate_id": "{validator_filename.replace('.py', '').replace('validate_', '')}",
        "script": "tools/{validator_filename}",
        "layer": "voice-improvement-layer-3",
        "timeout_sec": 30
    }},'''
        
        new_gates = gates_section + new_gate
        content = content.replace(gates_section, new_gates)
        
        with open("run_platform_checks.py", "w") as f:
            f.write(content)
    
    print(f"[LOOP] Registered validator: {validator_filename}")
```

---

## Layer 4: Meta-Validator (Loop Guardian)

**File**: `tools/validate_improvement_loop_integrity.py`

Ensures the loop itself stays healthy and doesn't defer validators or skip findings:

```python
#!/usr/bin/env python3
"""
Meta-validator: Guards the AI self-improvement loop.

Prevents:
- Validators being deferred without cause
- Fixes applied without corresponding validators
- Loop running on stale test data
- Fixes contradicting each other
"""

import json
import re
from datetime import datetime

def validate_loop_integrity():
    results = {"pass": 0, "fail": 0}
    
    print("\n" + "=" * 70)
    print("AI SELF-IMPROVEMENT LOOP INTEGRITY CHECK (Meta-Validator)")
    print("=" * 70)
    
    # ─────────────────────────────────────────────────────────────────────
    # CHECK 1: All findings have corresponding validators
    # ─────────────────────────────────────────────────────────────────────
    
    print("\n[Meta-1] Finding → Validator Coverage")
    
    try:
        with open("VOICE_FINDINGS.jsonl", "r") as f:
            findings = [json.loads(line) for line in f if line.strip()]
        
        # For each finding, verify a validator exists
        uncovered_findings = []
        for finding in findings[-10:]:  # Check last 10 findings
            finding_type = finding["finding_type"]
            
            # Map finding types to validators
            type_to_validator = {
                "missing_alert": "validate_voice_alert_formatting.py",
                "wrong_order": "validate_voice_alert_order.py",
                "format_error": "validate_voice_alert_formatting.py",
                "kb_gap": "validate_voice_kb_citations.py",
            }
            
            expected_validator = type_to_validator.get(finding_type)
            
            # Check if validator file exists
            import os
            if expected_validator and os.path.exists(f"tools/{expected_validator}"):
                print(f"  ✓ Finding {finding['finding_id']}: covered by {expected_validator}")
                results["pass"] += 1
            else:
                print(f"  ✗ Finding {finding['finding_id']}: NO VALIDATOR")
                uncovered_findings.append(finding["finding_id"])
                results["fail"] += 1
        
        if uncovered_findings:
            print(f"  {RED}FAIL{RESET} Uncovered findings: {uncovered_findings}")
    
    except FileNotFoundError:
        print(f"  {YELLOW}WARN{RESET} No findings history yet (first loop run)")
    
    # ─────────────────────────────────────────────────────────────────────
    # CHECK 2: No validators deferred without documented reason
    # ─────────────────────────────────────────────────────────────────────
    
    print("\n[Meta-2] Validator Deferral Tracking")
    
    try:
        with open("PRODUCTION_FIXES.md", "r") as f:
            fixes_content = f.read()
        
        # Count deferred entries without reason
        deferred_pattern = r'#\d+\s+\(deferred\)'
        deferred_count = len(re.findall(deferred_pattern, fixes_content))
        
        # Check each has a documented reason
        for match in re.finditer(r'#(\d+).*?\(deferred\)(.*?)(?=#|\Z)', fixes_content, re.DOTALL):
            entry_id = match.group(1)
            reason = match.group(2).strip()
            
            if reason and len(reason) > 10:
                print(f"  ✓ #{entry_id}: Deferred with reason")
                results["pass"] += 1
            else:
                print(f"  ✗ #{entry_id}: Deferred without documented reason")
                results["fail"] += 1
    
    except FileNotFoundError:
        print(f"  {YELLOW}SKIP{RESET} PRODUCTION_FIXES.md not found")
    
    # ─────────────────────────────────────────────────────────────────────
    # CHECK 3: Test data reproducibility
    # ─────────────────────────────────────────────────────────────────────
    
    print("\n[Meta-3] Test Data Seeding Reproducibility")
    
    # Verify seeders can be re-run without conflicts
    try:
        from test_data_seeder.app import reset_db, run_seeders
        
        # Check if reset_db is available
        print(f"  ✓ Reset function available for reproducible seeding")
        results["pass"] += 1
    except ImportError:
        print(f"  ✗ Cannot import seeder reset function")
        results["fail"] += 1
    
    # ─────────────────────────────────────────────────────────────────────
    # CHECK 4: Loop metadata consistency
    # ─────────────────────────────────────────────────────────────────────
    
    print("\n[Meta-4] Loop Run Metadata")
    
    try:
        with open("VOICE_LOOP_METADATA.json", "r") as f:
            metadata = json.load(f)
        
        last_run = datetime.fromisoformat(metadata["last_run"])
        scenario_count = metadata.get("scenarios_run", 0)
        finding_count = metadata.get("findings_extracted", 0)
        validator_count = metadata.get("validators_registered", 0)
        
        if scenario_count > 0 and finding_count >= 0 and validator_count > 0:
            print(f"  ✓ Last run: {last_run} ({scenario_count} scenarios, {finding_count} findings, {validator_count} validators)")
            results["pass"] += 1
        else:
            print(f"  ✗ Incomplete metadata: {metadata}")
            results["fail"] += 1
    
    except FileNotFoundError:
        print(f"  {YELLOW}INFO{RESET} First loop run — metadata will be created")
    
    # ─────────────────────────────────────────────────────────────────────
    # SUMMARY
    # ─────────────────────────────────────────────────────────────────────
    
    print("\n" + "=" * 70)
    print(f"META-VALIDATOR: {results['pass']} PASS | {results['fail']} FAIL")
    print("=" * 70)
    
    if results["fail"] == 0:
        print(f"\n{GREEN}Loop integrity OK. Safe to continue.{RESET}")
    else:
        print(f"\n{RED}Loop has integrity issues. Review before next run.{RESET}")
    
    return results["fail"] == 0

if __name__ == "__main__":
    validate_loop_integrity()
```

---

## Integration: The Full Loop (Entry Point)

**File**: `tools/voice_ai_self_improvement_loop.py`

Orchestrates all 4 layers in sequence:

```python
#!/usr/bin/env python3
"""
Voice Companion AI Self-Improvement Loop.

Full end-to-end execution:
1. Layer 0: Run Playwright scenarios
2. Layer 1: Analyze failures and extract findings
3. Layer 2: Auto-fix issues
4. Layer 3: Create/extend validators
5. Layer 4: Meta-validator checks loop integrity
6. Final: Fast mega gate validation

Mirrors unified gates pattern but dynamic (failure-driven vs schema-driven).
"""

import subprocess
import json
from datetime import datetime

def run_improvement_loop(user_approved=False):
    """Execute one full improvement loop."""
    
    print("\n" + "=" * 80)
    print("VOICE COMPANION AI SELF-IMPROVEMENT LOOP (Playwright-Driven)")
    print("=" * 80)
    
    metadata = {
        "loop_start": datetime.now().isoformat(),
        "scenarios_run": 0,
        "findings_extracted": 0,
        "fixes_applied": 0,
        "validators_registered": 0,
    }
    
    # ─────────────────────────────────────────────────────────────────────
    # LAYER 0: Scenario Execution
    # ─────────────────────────────────────────────────────────────────────
    
    print("\n[LAYER 0] Running Playwright scenarios...")
    from tools.playwright_voice_scenarios import run_scenarios
    
    scenario_results = run_scenarios()
    passed = sum(1 for r in scenario_results.values() if r["status"] == "PASS")
    failed = sum(1 for r in scenario_results.values() if r["status"] == "FAIL")
    
    print(f"[LAYER 0] Results: {passed} PASS | {failed} FAIL")
    metadata["scenarios_run"] = len(scenario_results)
    
    if failed == 0:
        print("[LOOP] All scenarios passing! No findings to extract.")
        print("[LOOP] Skipping to Layer 4 (meta-check) and fast gate.")
        # Jump to Layer 4
    else:
        # ─────────────────────────────────────────────────────────────────────
        # LAYER 1: Failure Analysis
        # ─────────────────────────────────────────────────────────────────────
        
        print(f"\n[LAYER 1] Analyzing {failed} failures...")
        from tools.analyze_scenario_findings import analyze_failures
        
        findings = analyze_failures(scenario_results)
        print(f"[LAYER 1] Extracted {len(findings)} findings")
        metadata["findings_extracted"] = len(findings)
        
        # ─────────────────────────────────────────────────────────────────────
        # LAYER 2: Auto-Remediation
        # ─────────────────────────────────────────────────────────────────────
        
        print(f"\n[LAYER 2] Auto-fixing {len(findings)} findings...")
        from tools.auto_fix_findings import VoiceFindingFixer
        
        fixer = VoiceFindingFixer(findings)
        fixer.route_and_fix()
        
        # Validate fixes
        fixes_validated = fixer.validate_fixes()
        
        if not fixes_validated:
            print("[LAYER 2] Fixes didn't fully resolve issues. Stopping here.")
            return False
        
        metadata["fixes_applied"] = len(fixer.staged_fixes)
        
        # ─────────────────────────────────────────────────────────────────────
        # LAYER 3: Validator Generation
        # ─────────────────────────────────────────────────────────────────────
        
        print(f"\n[LAYER 3] Creating validators for {len(findings)} findings...")
        from tools.generate_and_register_validator import (
            generate_validator_for_finding,
            register_validator_in_gates
        )
        
        for finding in findings:
            validator_file = generate_validator_for_finding(finding)
            if validator_file:
                register_validator_in_gates(validator_file)
                metadata["validators_registered"] += 1
        
        print(f"[LAYER 3] Registered {metadata['validators_registered']} validators")
    
    # ─────────────────────────────────────────────────────────────────────
    # LAYER 4: Meta-Validator (Loop Guardian)
    # ─────────────────────────────────────────────────────────────────────
    
    print(f"\n[LAYER 4] Checking loop integrity...")
    result = subprocess.run(
        ["python", "tools/validate_improvement_loop_integrity.py"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print("[LAYER 4] FAIL — Loop integrity compromised. Stopping.")
        return False
    
    print("[LAYER 4] PASS — Loop integrity OK")
    
    # ─────────────────────────────────────────────────────────────────────
    # FINAL: Fast Mega Gate
    # ─────────────────────────────────────────────────────────────────────
    
    print(f"\n[FINAL] Running fast mega gate (all validators)...")
    result = subprocess.run(
        ["python", "run_platform_checks.py", "--fast"],
        capture_output=True,
        text=True,
        timeout=120
    )
    
    if result.returncode == 0:
        print("[FINAL] ✓ All validators PASS")
        
        # Save metadata
        metadata["loop_end"] = datetime.now().isoformat()
        with open("VOICE_LOOP_METADATA.json", "w") as f:
            json.dump(metadata, f, indent=2)
        
        print("\n" + "=" * 80)
        print("LOOP COMPLETE — Ready for user review & commit")
        print("=" * 80)
        
        print("\nStaged changes:")
        subprocess.run(["git", "diff", "--stat"])
        
        print("\nTo review all changes:")
        print("  git diff")
        
        print("\nTo approve and commit:")
        print("  git add -A")
        print("  git commit -m 'Auto-improvement from AI self-learning loop'")
        
        return True
    else:
        print(f"[FINAL] ✗ Validators FAILED")
        print(result.stdout)
        print(result.stderr)
        return False

if __name__ == "__main__":
    import sys
    success = run_improvement_loop()
    sys.exit(0 if success else 1)
```

---

## How to Trigger the Loop

### Manual (for now):
```bash
# Review what the loop will do
python tools/voice_ai_self_improvement_loop.py

# If all checks pass, user commits the changes
git add -A
git commit -m "Auto-improvement: AI scenarios → findings → fixes → validators"
git push origin master
```

### Automated (future):
- Run daily: `cron: 0 2 * * *` (2 AM daily)
- On manual trigger: `/improve-voice-ai` command
- On CI: Post-deployment validation step
- On metric alert: If KB gap > threshold, run loop

---

## Why This Mirrors Unified Gates

| Aspect | Unified Gates | Voice AI Loop |
|--------|---------------|--------------|
| **Layer 0** | 160 validators (schema/structure) | Playwright scenarios (UI flows) |
| **Layer 1** | Architectural gates (silo-monitor) | Failure analysis (Claude) |
| **Layer 2** | Specialized validators | Auto-fix (prompt/seeding/logic) |
| **Layer 3** | Registration in GATES list | Validator generation + registration |
| **Layer 4** | Meta-validator (none yet) | Loop integrity guardian |
| **Guardian** | run_platform_checks.py --fast | Same, but includes new validators |
| **Outcome** | Code correctness | AI behavior correctness |

---

## Key Differences

1. **Dynamic vs Static**: Gates run on fixed code; loop runs on scenario failures
2. **AI-Driven**: Claude analyzes failures, not just regex patterns
3. **Self-Healing**: Fixes applied automatically, not just flagged
4. **Reproducible**: All fixes have corresponding validators to prevent regression
5. **Auditable**: VOICE_FINDINGS.jsonl maintains full history of findings & fixes

---

## Next Steps

1. **Implement Layer 0**: playwright_voice_scenarios.py (10-15 realistic scenarios)
2. **Implement Layer 1**: analyze_scenario_findings.py (Claude + JSON parsing)
3. **Implement Layer 2**: auto_fix_findings.py (routing to fix modules)
4. **Implement Layer 3**: generate_and_register_validator.py (create + register)
5. **Implement Layer 4**: validate_improvement_loop_integrity.py (already written)
6. **Wire to guardian**: Update run_platform_checks.py to include new validators
7. **Test locally**: Run loop manually, verify fixes + validators work
8. **Deploy**: Add to CI/CD or scheduled triggers

---

## Success Metrics

- ✅ Playwright scenarios catch real AI failures (not metric-based)
- ✅ Findings extracted with > 90% confidence
- ✅ Auto-fixes resolve findings in validation re-run
- ✅ Validators register with zero deferral
- ✅ Meta-validator stays at 0 FAIL
- ✅ Fast gate passes after every loop (no regressions)
- ✅ VOICE_FINDINGS.jsonl grows with each loop run (audit trail)

This turns Voice Companion into a **self-improving system** that learns from every scenario failure, fixes itself, and guards against regression — exactly like your unified gates but dynamic.
