#!/usr/bin/env python3
"""
Layer -0.5: Auto-Scenario Generator

Reads NEW_SURFACES_REPORT.json (from discover_ai_surfaces.py) and uses
Groq to draft Playwright scenarios for each newly-discovered surface.

Output:
  - tools/auto_scenarios.py — Python module with AUTO_SCENARIOS dict
  - AUTO_GENERATED_SCENARIOS.json — metadata about what was generated

The main playwright_scenario_executor.py imports auto_scenarios.AUTO_SCENARIOS
and merges them with manual SCENARIOS dict.

Usage:
  python tools/auto_generate_scenarios.py
"""

import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from loop_helpers import call_claude_free, extract_json_from_text

ROOT = Path(__file__).resolve().parent.parent
NEW_REPORT_PATH = ROOT / "NEW_SURFACES_REPORT.json"
AUTO_SCENARIOS_PATH = ROOT / "tools" / "auto_scenarios.py"
GENERATED_META_PATH = ROOT / "AUTO_GENERATED_SCENARIOS.json"


PROMPT_TEMPLATE = """You are a Playwright test author for an industrial maintenance platform.

A new AI-powered HTML page was discovered: {page_name}

Discovery findings:
- Verdict label IDs: {verdict_labels}
- Verdict box IDs: {verdict_boxes}
- Source chip IDs: {source_chips}
- Edge functions called: {edge_functions}
- AI RPCs called: {ai_rpcs}
- Interactive (mic/chat): {interactive}

Write a Python dict for a Playwright scenario that:
1. Loads the page at /{page_name}
2. Waits for the verdict element to appear
3. Validates that the verdict has non-empty, non-"loading" text
4. Captures the verdict text

Return ONLY valid JSON in this exact format:

{{
  "name": "{surface_name}: <one-line description>",
  "page": "/{page_name}",
  "steps": [
    {{"action": "wait_for_selector", "selector": "#<verdict-or-box-id>", "timeout": 8000}},
    {{"action": "wait", "ms": 5000}}
  ],
  "validations": {{
    "verdict_loaded": {{"selector": "#<verdict-or-box-id>", "type": "exists", "required": true}},
    "verdict_has_text": {{"selector": "#<verdict-label-id>", "type": "has_text", "required": true}}
  }},
  "captures": [
    {{"key": "verdict_text", "selector": "#<verdict-label-id>"}}
  ]
}}

Use the actual selectors from the findings above. Return ONLY the JSON, no explanation.
"""


def surface_name_from_page(page_name: str) -> str:
    """Convert page name to surface name (e.g., 'predictive.html' -> 'PREDICTIVE')."""
    return page_name.replace(".html", "").replace("-", "_").upper()


def generate_scenario_for_surface(page_name: str, findings: dict) -> dict:
    """Use Groq to draft a Playwright scenario for one new surface."""
    surface_name = surface_name_from_page(page_name)

    prompt = PROMPT_TEMPLATE.format(
        page_name=page_name,
        verdict_labels=findings.get("verdict_labels", []),
        verdict_boxes=findings.get("verdict_boxes", []),
        source_chips=findings.get("source_chips", []),
        edge_functions=findings.get("edge_functions", []),
        ai_rpcs=findings.get("ai_rpcs", []),
        interactive=findings.get("interactive", False),
        surface_name=surface_name,
    )

    response = call_claude_free(prompt, max_tokens=800)
    if not response:
        print(f"  [WARN] No Groq response for {page_name}")
        return None

    scenario = extract_json_from_text(response)
    if not scenario or not isinstance(scenario, dict):
        print(f"  [WARN] Could not parse scenario for {page_name}")
        return None

    # Validate scenario shape
    required_keys = {"name", "page", "steps", "validations"}
    if not required_keys.issubset(scenario.keys()):
        print(f"  [WARN] Scenario missing required keys for {page_name}")
        return None

    return {
        "surface_name": surface_name,
        "scenario": scenario,
        "generated_at": datetime.now().isoformat(),
        "source_findings": findings,
    }


def write_auto_scenarios_module(scenarios: dict):
    """Write tools/auto_scenarios.py with AUTO_SCENARIOS dict."""
    header = '''#!/usr/bin/env python3
"""
AUTO-GENERATED scenarios from Layer -1 discovery.

DO NOT edit manually — re-run tools/auto_generate_scenarios.py to refresh.
These scenarios are merged with manual SCENARIOS in playwright_scenario_executor.py.

Generated: {timestamp}
Count: {count} auto-generated scenario(s)
"""

AUTO_SCENARIOS = {scenarios_repr}
'''.format(
        timestamp=datetime.now().isoformat(),
        count=len(scenarios),
        scenarios_repr=json.dumps(scenarios, indent=4),
    )

    AUTO_SCENARIOS_PATH.write_text(header, encoding="utf-8")


def main():
    print("=" * 70)
    print("LAYER -0.5: AUTO-SCENARIO GENERATOR")
    print("=" * 70)

    if not NEW_REPORT_PATH.exists():
        print(f"\n[INFO] No {NEW_REPORT_PATH.name} found.")
        print("Run discover_ai_surfaces.py first.")
        # Still write empty auto_scenarios.py so import doesn't break
        write_auto_scenarios_module({})
        return

    try:
        report = json.loads(NEW_REPORT_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[ERROR] Could not read {NEW_REPORT_PATH.name}: {e}")
        return

    new_surfaces = report.get("new_surfaces", [])

    if not new_surfaces:
        print("\nNo new surfaces to generate scenarios for.")
        # Write empty so previous auto_scenarios isn't accidentally re-used
        write_auto_scenarios_module({})
        return

    print(f"\nGenerating scenarios for {len(new_surfaces)} new surface(s)...\n")

    generated = {}
    meta = []

    for entry in new_surfaces:
        page_name = entry["name"]
        findings = entry["data"]

        print(f"  → {page_name}...", end=" ", flush=True)

        result = generate_scenario_for_surface(page_name, findings)
        if result:
            # Store the scenario list (executor expects list per surface)
            generated[result["surface_name"]] = [result["scenario"]]
            meta.append({
                "surface": result["surface_name"],
                "page": page_name,
                "generated_at": result["generated_at"],
            })
            print("OK")
        else:
            print("FAILED")

    # Write auto_scenarios module
    write_auto_scenarios_module(generated)

    # Save metadata
    GENERATED_META_PATH.write_text(json.dumps({
        "timestamp": datetime.now().isoformat(),
        "generated_count": len(generated),
        "scenarios": meta,
    }, indent=2), encoding="utf-8")

    print("\n" + "=" * 70)
    print(f"AUTO-GENERATED: {len(generated)} scenario(s)")
    print("=" * 70)
    print(f"\nWritten: {AUTO_SCENARIOS_PATH.relative_to(ROOT)}")
    print(f"Meta:    {GENERATED_META_PATH.name}")


if __name__ == "__main__":
    main()
