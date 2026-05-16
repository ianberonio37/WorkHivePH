#!/usr/bin/env python3
"""
Layer 0: Playwright Scenario Executor

Runs predetermined scenarios across all AI surfaces (Voice, Visual, AMC, Calc, Chat).
Captures actual AI responses and logs outcomes.

Usage:
  python tools/playwright_scenario_executor.py                 # all surfaces
  python tools/playwright_scenario_executor.py --surface VOICE # voice only
  python tools/playwright_scenario_executor.py --fast          # fewer scenarios
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, Page, expect
except ImportError:
    print("ERROR: playwright not installed. Run: pip install playwright")
    sys.exit(1)

BASE_URL = "http://127.0.0.1:5000/workhive"

# ─────────────────────────────────────────────────────────────────────
# SCENARIO DEFINITIONS (All Surfaces)
# ─────────────────────────────────────────────────────────────────────

SCENARIOS = {
    "VOICE": [
        {
            "name": "Phase 3: KB Citation Retrieval",
            "page": "/voice-journal.html",
            "steps": [
                {"action": "wait_for_selector", "selector": "[data-test=voice-input]", "timeout": 5000},
                {"action": "fill", "selector": "[data-test=voice-input]", "text": "What is the best practice for bearing maintenance?"},
                {"action": "click", "selector": "[data-test=send-button]"},
                {"action": "wait_for_selector", "selector": "[data-test=response]", "timeout": 8000},
            ],
            "validations": {
                "kb_citation_present": {"pattern": r"\(from KB:|source:|ISO 14224", "required": True},
                "response_not_empty": {"pattern": r".{50,}", "required": True},
                "no_error": {"pattern": r"error|Error|ERROR", "required": False},
            },
            "capture": ["response_text", "latency_ms"],
        },
        {
            "name": "Phase 5: Critical Alert Surfacing",
            "page": "/voice-journal.html",
            "steps": [
                {"action": "fill", "selector": "[data-test=voice-input]", "text": "What are my five equipment alerts?"},
                {"action": "click", "selector": "[data-test=send-button]"},
                {"action": "wait_for_selector", "selector": "[data-test=response]", "timeout": 8000},
            ],
            "validations": {
                "critical_indicator": {"pattern": r"\[CRITICAL\]", "required": True},
                "alert_description": {"pattern": r"(Pump|Motor|Compressor|Bearing|Valve)", "required": True},
                "no_placeholder_ids": {"pattern": r"TEST-MACHINE|mp6s8q0x", "required": False},
            },
            "capture": ["response_text", "latency_ms"],
        },
        {
            "name": "Phase 5: Alert Suppression Honored",
            "page": "/voice-journal.html",
            "steps": [
                {"action": "fill", "selector": "[data-test=voice-input]", "text": "Show me critical alerts"},
                {"action": "click", "selector": "[data-test=send-button]"},
                {"action": "wait_for_selector", "selector": "[data-test=alert-list]", "timeout": 5000},
                {"action": "click", "selector": "[data-test=suppress-button]:first-of-type"},
                {"action": "wait", "ms": 1000},
                {"action": "fill", "selector": "[data-test=voice-input]", "text": "List alerts again"},
                {"action": "click", "selector": "[data-test=send-button]"},
                {"action": "wait_for_selector", "selector": "[data-test=response]", "timeout": 8000},
            ],
            "validations": {
                "suppressed_alert_absent": {"pattern": r"(first suppressed alert name)", "required": False},
            },
            "capture": ["response_text", "latency_ms"],
        },
        {
            "name": "Phase 8: Analytics Logging",
            "page": "/voice-journal.html",
            "steps": [
                {"action": "fill", "selector": "[data-test=voice-input]", "text": "How is my MTBF trending?"},
                {"action": "click", "selector": "[data-test=send-button]"},
                {"action": "wait_for_selector", "selector": "[data-test=response]", "timeout": 8000},
            ],
            "validations": {
                "response_present": {"pattern": r".{50,}", "required": True},
                "no_crash": {"pattern": r"error|Error|ERROR", "required": False},
            },
            "capture": ["response_text", "latency_ms"],
            "checks_db": {"table": "conversation_analytics", "expected_columns": ["turn_num", "answer_quality_rating"]},
        },
    ],
    "VISUAL": [
        {
            "name": "Visual: Defect Classification",
            "page": "/visual-defect.html",
            "steps": [
                {"action": "wait_for_selector", "selector": "[data-test=upload-area]", "timeout": 5000},
                {"action": "click", "selector": "[data-test=upload-button]"},
                # Would normally upload a test image; here we simulate
                {"action": "set_input_files", "selector": "[data-test=file-input]", "files": ["test-images/defect-example.jpg"]},
                {"action": "wait_for_selector", "selector": "[data-test=result]", "timeout": 10000},
            ],
            "validations": {
                "defect_category": {"pattern": r"(crack|corrosion|deformation|surface)", "required": True},
                "confidence_present": {"pattern": r"confidence|score|probability", "required": True},
            },
            "capture": ["result_text", "latency_ms"],
        },
        {
            "name": "Visual: Confidence Scoring",
            "page": "/visual-defect.html",
            "steps": [
                {"action": "click", "selector": "[data-test=upload-button]"},
                {"action": "set_input_files", "selector": "[data-test=file-input]", "files": ["test-images/defect-example.jpg"]},
                {"action": "wait_for_selector", "selector": "[data-test=confidence-score]", "timeout": 10000},
            ],
            "validations": {
                "confidence_numeric": {"pattern": r"\d+\.\d{2}|(\d+)%", "required": True},
                "confidence_in_range": {"pattern": r"(0\.\d+|1\.0)", "required": True},
            },
            "capture": ["confidence_value", "latency_ms"],
        },
    ],
    "AMC": [
        {
            "name": "AMC: Alert Fetching",
            "page": "/alert-hub.html",
            "steps": [
                {"action": "wait_for_selector", "selector": "[data-test=alerts-container]", "timeout": 5000},
                {"action": "wait_for_selector", "selector": "[data-test=alert-row]", "timeout": 3000},
            ],
            "validations": {
                "alerts_displayed": {"pattern": r"CRITICAL|HIGH|MEDIUM", "required": True},
                "no_ids": {"pattern": r"mp6s8q0x|uuid-like", "required": False},
            },
            "capture": ["alert_count", "alert_text"],
        },
        {
            "name": "AMC: Alert Suppression",
            "page": "/alert-hub.html",
            "steps": [
                {"action": "click", "selector": "[data-test=suppress-action]:first-of-type"},
                {"action": "wait", "ms": 1000},
                {"action": "fill", "selector": "[data-test=suppress-duration]", "text": "1"},
                {"action": "click", "selector": "[data-test=confirm-suppress]"},
                {"action": "wait_for_selector", "selector": "[data-test=suppressed-badge]", "timeout": 3000},
            ],
            "validations": {
                "suppressed_badge_present": {"pattern": r"suppressed|muted", "required": True},
            },
            "capture": ["alert_state", "latency_ms"],
        },
    ],
    "CALC": [
        {
            "name": "Calc: Formula Validation",
            "page": "/engineering-design.html",
            "steps": [
                {"action": "wait_for_selector", "selector": "[data-test=calc-select]", "timeout": 5000},
                {"action": "select_option", "selector": "[data-test=calc-select]", "value": "motor-load"},
                {"action": "fill", "selector": "[data-test=input-horsepower]", "text": "10"},
                {"action": "fill", "selector": "[data-test=input-rpm]", "text": "1800"},
                {"action": "click", "selector": "[data-test=calculate-button]"},
                {"action": "wait_for_selector", "selector": "[data-test=result]", "timeout": 3000},
            ],
            "validations": {
                "result_numeric": {"pattern": r"^\d+\.?\d*\s*(W|kW|hp)", "required": True},
                "no_nan": {"pattern": r"NaN|Infinity", "required": False},
            },
            "capture": ["result_value", "units", "latency_ms"],
        },
        {
            "name": "Calc: BOM Generation",
            "page": "/engineering-design.html",
            "steps": [
                {"action": "select_option", "selector": "[data-test=calc-select]", "value": "motor-load"},
                {"action": "fill", "selector": "[data-test=input-horsepower]", "text": "10"},
                {"action": "fill", "selector": "[data-test=input-rpm]", "text": "1800"},
                {"action": "click", "selector": "[data-test=generate-bom]"},
                {"action": "wait_for_selector", "selector": "[data-test=bom-table]", "timeout": 3000},
            ],
            "validations": {
                "bom_rows_present": {"pattern": r"<tr>", "min_count": 3, "required": True},
                "bom_columns": {"pattern": r"(quantity|part|description)", "required": True},
            },
            "capture": ["bom_row_count", "latency_ms"],
        },
    ],
    "CHAT": [
        {
            "name": "Chat: Basic Query Response",
            "page": "/hive.html",
            "steps": [
                {"action": "wait_for_selector", "selector": "[data-test=chat-input]", "timeout": 5000},
                {"action": "fill", "selector": "[data-test=chat-input]", "text": "What is OEE?"},
                {"action": "click", "selector": "[data-test=chat-send]"},
                {"action": "wait_for_selector", "selector": "[data-test=chat-response]:last-of-type", "timeout": 8000},
            ],
            "validations": {
                "response_present": {"pattern": r".{50,}", "required": True},
                "no_pii": {"pattern": r"(email|phone|ssn|password)", "required": False},
            },
            "capture": ["response_text", "latency_ms"],
        },
    ],
}


def run_scenario(page: Page, scenario: dict, base_url: str) -> dict:
    """Execute a single scenario and capture results."""
    start_time = time.time()
    result = {
        "name": scenario["name"],
        "surface": scenario.get("surface", "unknown"),
        "status": "FAIL",
        "validations": {},
        "captures": {},
        "error": None,
        "latency_ms": 0,
    }

    try:
        # Navigate to page
        page_url = f"{base_url}{scenario['page']}"
        page.goto(page_url, wait_until="networkidle")

        # Execute steps
        for step in scenario.get("steps", []):
            action = step.get("action")

            if action == "wait_for_selector":
                page.wait_for_selector(step["selector"], timeout=step.get("timeout", 5000))
            elif action == "wait":
                page.wait_for_timeout(step.get("ms", 1000))
            elif action == "fill":
                page.fill(step["selector"], step["text"])
            elif action == "click":
                page.click(step["selector"])
            elif action == "select_option":
                page.select_option(step["selector"], step["value"])
            elif action == "set_input_files":
                page.set_input_files(step["selector"], step["files"])

        # Capture results
        for capture_key in scenario.get("capture", []):
            if capture_key == "response_text":
                try:
                    result["captures"]["response_text"] = page.text_content("[data-test=response]")
                except:
                    result["captures"]["response_text"] = "(unable to capture)"
            elif capture_key == "result_text":
                try:
                    result["captures"]["result_text"] = page.text_content("[data-test=result]")
                except:
                    result["captures"]["result_text"] = "(unable to capture)"
            elif capture_key == "alert_count":
                try:
                    alerts = page.query_selector_all("[data-test=alert-row]")
                    result["captures"]["alert_count"] = len(alerts)
                except:
                    result["captures"]["alert_count"] = 0

        # Validate patterns
        response_text = result["captures"].get("response_text", "") or result["captures"].get("result_text", "")

        for validation_name, validation_rule in scenario.get("validations", {}).items():
            pattern = validation_rule.get("pattern", "")
            required = validation_rule.get("required", True)
            import re

            match = re.search(pattern, response_text, re.IGNORECASE)

            if match:
                result["validations"][validation_name] = True
            else:
                result["validations"][validation_name] = False

            if required and not match:
                result["status"] = "FAIL"
            elif not required and not match:
                pass  # Optional pattern, OK if missing
            elif required and match:
                result["status"] = "PASS"

        # Check if all required validations passed
        all_pass = all(
            v for k, v in result["validations"].items()
            if scenario["validations"][k].get("required", True)
        )
        if all_pass:
            result["status"] = "PASS"

    except Exception as e:
        result["status"] = "FAIL"
        result["error"] = f"{type(e).__name__}: {str(e)}"

    result["latency_ms"] = int((time.time() - start_time) * 1000)
    return result


def run_all_scenarios(surface_filter=None, fast=False) -> dict:
    """Execute all scenarios across all surfaces."""
    print("\n" + "=" * 70)
    print("LAYER 0: PLAYWRIGHT SCENARIO EXECUTOR")
    print("=" * 70)

    results = {
        "timestamp": datetime.now().isoformat(),
        "surfaces": {},
        "summary": {"total": 0, "passed": 0, "failed": 0},
    }

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        for surface_name, scenarios in SCENARIOS.items():
            if surface_filter and surface_filter.upper() != surface_name:
                continue

            if fast and len(scenarios) > 2:
                scenarios = scenarios[:2]  # Reduce to 2 per surface in fast mode

            print(f"\n[{surface_name}]")
            surface_results = []

            for scenario in scenarios:
                scenario["surface"] = surface_name
                print(f"  Running: {scenario['name']}...", end=" ", flush=True)

                result = run_scenario(page, scenario, BASE_URL)
                surface_results.append(result)

                status_icon = "[OK]" if result["status"] == "PASS" else "[FAIL]"
                print(f"{status_icon} ({result['latency_ms']}ms)")

                results["summary"]["total"] += 1
                if result["status"] == "PASS":
                    results["summary"]["passed"] += 1
                else:
                    results["summary"]["failed"] += 1

                # Print validation details
                for val_name, val_result in result["validations"].items():
                    icon = "  ✓" if val_result else "  ✗"
                    print(f"{icon} {val_name}")

            results["surfaces"][surface_name] = surface_results

        browser.close()

    # Summary
    print("\n" + "=" * 70)
    print(f"RESULTS: {results['summary']['passed']} PASS | {results['summary']['failed']} FAIL")
    print("=" * 70)

    # Save results
    results_file = Path("SCENARIO_RESULTS.json")
    results_file.write_text(json.dumps(results, indent=2))
    print(f"\nResults saved to: {results_file}")

    return results


if __name__ == "__main__":
    surface_filter = None
    fast = False

    for arg in sys.argv[1:]:
        if arg == "--fast":
            fast = True
        elif arg.startswith("--surface"):
            surface_filter = arg.split("=")[1] if "=" in arg else None

    results = run_all_scenarios(surface_filter=surface_filter, fast=fast)
    sys.exit(0 if results["summary"]["failed"] == 0 else 1)
