#!/usr/bin/env python3
"""
Layer 1: Failure Analysis & Finding Extraction

Uses free AI (Groq/Cerebras/SambaNova/OpenRouter) to analyze scenario failures.
Categorizes by finding_type, root_cause, and suggested fix.

Input: SCENARIO_RESULTS.json from Layer 0
Output: SCENARIO_FINDINGS.jsonl (one finding per line)

API Usage: Free tier only — set GROQ_API_KEY, CEREBRAS_API_KEY, SAMBANOVA_API_KEY, or OPENROUTER_API_KEY
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Add tools directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from loop_helpers import call_claude_free, load_json_file, save_jsonl_file, log_message, extract_json_from_text

# Finding type registry (used to classify findings)
FINDING_TYPES = {
    "missing_kb_context": "KB chunks not included in response",
    "missing_alert": "Alert data not surfaced in response",
    "wrong_order": "Critical content not prioritized (alerts/errors first)",
    "format_error": "Response format incorrect (IDs instead of text, truncated, etc)",
    "confidence_low": "Confidence score below acceptable threshold",
    "latency_high": "Response time exceeds SLA (>5s)",
    "hallucination": "AI response contains made-up information",
    "pii_exposure": "Personally identifiable information in response",
    "incomplete_data": "Expected data missing from response",
    "schema_mismatch": "Response structure doesn't match expected schema",
}

def analyze_failure(scenario_result: dict) -> list:
    """
    Use Claude to analyze a failed scenario and extract findings.

    Returns list of findings (usually 1-3 per failure).
    """
    findings = []

    if scenario_result["status"] == "PASS":
        return findings  # No findings for passing scenarios

    scenario_name = scenario_result["name"]
    surface = scenario_result["surface"]
    validations = scenario_result["validations"]
    captures = scenario_result["captures"]
    error = scenario_result.get("error")

    # Build analysis prompt
    failed_checks = [k for k, v in validations.items() if not v]
    passed_checks = [k for k, v in validations.items() if v]

    prompt = f"""
    Analyze this AI scenario failure and extract findings.

    SCENARIO
    --------
    Surface: {surface}
    Name: {scenario_name}

    VALIDATION RESULTS
    ------------------
    Passed: {', '.join(passed_checks) or '(none)'}
    Failed: {', '.join(failed_checks) or '(none)'}

    CAPTURED DATA
    ---------------
    {json.dumps(captures, indent=2)[:1000]}

    ERROR (if any)
    ---------------
    {error or '(none)'}

    TASK
    ------
    Extract findings from this failure. For each finding, return JSON:
    {{
      "finding_type": "one of: {', '.join(FINDING_TYPES.keys())}",
      "description": "Human-readable description of what's wrong",
      "root_cause": "Why is it wrong (prompt gap, stale data, schema issue, logic bug, etc)",
      "suggested_fix_type": "one of: prompt_update, seeding, rpc_change, logic_fix, migration",
      "fix_target": "Which file/function to fix (e.g., voice-handler.js:1601)",
      "confidence": 0.0-1.0 (how confident you are in the diagnosis)
    }}

    Return an array of findings (usually 1-3). If unable to diagnose, return empty array [].
    """

    try:
        response_text = call_claude_free(prompt)

        if response_text:
            # Extract JSON from response
            extracted_findings = extract_json_from_text(response_text)

            if isinstance(extracted_findings, list):
                for idx, finding in enumerate(extracted_findings):
                    if not isinstance(finding, dict):
                        continue

                    finding_id = f"FINDING-{datetime.now().strftime('%Y%m%d%H%M%S')}-{surface[0]}-{idx:02d}"

                    full_finding = {
                        "finding_id": finding_id,
                        "scenario": scenario_name,
                        "surface": surface,
                        "timestamp": datetime.now().isoformat(),
                        **finding,  # Unpack Claude's analysis
                        "evidence": {
                            "failed_checks": failed_checks,
                            "captured_data_sample": str(captures)[:200],
                        }
                    }

                    findings.append(full_finding)
                    confidence = finding.get('confidence', 0)
                    print(f"    -> {finding_id}: {finding.get('finding_type', 'unknown')} ({confidence:.0%})")
            else:
                print(f"    -> Could not parse Claude response for {scenario_name}")
        else:
            print(f"    -> No response from AI for {scenario_name}")
    except Exception as e:
        print(f"    -> Analysis error: {type(e).__name__}: {e}")

    return findings


def analyze_all_failures(results_file="SCENARIO_RESULTS.json") -> list:
    """
    Load scenario results and analyze all failures.
    Returns: list of all findings across all failed scenarios.
    """
    print("\n" + "=" * 70)
    print("LAYER 1: FAILURE ANALYSIS & FINDING EXTRACTION")
    print("=" * 70)

    results_path = Path(results_file)
    if not results_path.exists():
        print(f"ERROR: {results_file} not found")
        print("Run Layer 0 first: python tools/playwright_scenario_executor.py")
        return []

    with open(results_path) as f:
        results = json.load(f)

    all_findings = []
    total_scenarios = results["summary"]["total"]
    failed_scenarios = results["summary"]["failed"]

    print(f"\nAnalyzing {failed_scenarios} failures from {total_scenarios} scenarios...\n")

    for surface_name, surface_results in results.get("surfaces", {}).items():
        failed = [r for r in surface_results if r["status"] == "FAIL"]

        if not failed:
            print(f"[{surface_name}] All passing, no analysis needed")
            continue

        print(f"[{surface_name}] Analyzing {len(failed)} failures...")

        for scenario_result in failed:
            print(f"  {scenario_result['name']}...", end=" ", flush=True)
            findings = analyze_failure(scenario_result)
            all_findings.extend(findings)

    # Save findings
    findings_file = Path("SCENARIO_FINDINGS.jsonl")
    save_jsonl_file(str(findings_file), all_findings, append=True)

    # Summary
    print("\n" + "=" * 70)
    print(f"FINDINGS: {len(all_findings)} extracted")
    print("=" * 70)

    if all_findings:
        print("\nFinding Summary:")
        by_type = {}
        for f in all_findings:
            ftype = f.get("finding_type", "unknown")
            by_type[ftype] = by_type.get(ftype, 0) + 1

        for ftype, count in sorted(by_type.items()):
            print(f"  • {ftype}: {count}")

        print(f"\nFull findings saved to: {findings_file}")

    return all_findings


if __name__ == "__main__":
    results_file = sys.argv[1] if len(sys.argv) > 1 else "SCENARIO_RESULTS.json"
    findings = analyze_all_failures(results_file)
    sys.exit(0 if len(findings) == 0 else 0)  # Always exit 0, findings are expected
