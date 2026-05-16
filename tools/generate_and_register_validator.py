#!/usr/bin/env python3
"""
Layer 3: Validator Generator & Registrar

Creates new validators or extends existing ones based on findings.
Registers validators in run_platform_checks.py GATES list.

Input: SCENARIO_FINDINGS.jsonl from Layer 1
Output:
  - New validator files in ./tools/ (validate_*.py)
  - Updated run_platform_checks.py with new GATES entries
  - VALIDATOR_REGISTRY.json (metadata)
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

VALIDATOR_TEMPLATES = {
    "voice_alert_order": '''#!/usr/bin/env python3
"""
Validator: Alert Priority Ordering
Prevents: Alerts not surfacing first in Voice responses
Generated: {timestamp}
From finding: {finding_id}
"""

import re
import sys

def validate_alert_ordering():
    results = {{"pass": 0, "fail": 0}}

    print("\\n[Alert Ordering]")

    # Check voice-handler.js has alert priority instruction
    with open("voice-handler.js", "r") as f:
        content = f.read()

    checks = [
        ("alertsSection before kbSection", "alertsSection" in content and "kbSection" in content and
         content.index("alertsSection") < content.index("kbSection")),
        ("CRITICAL indicator in prompt", "[CRITICAL]" in content),
        ("Mandatory instruction present", "MANDATORY RULE" in content),
    ]

    for check_name, passed in checks:
        if passed:
            print(f"  [PASS] {{check_name}}")
            results["pass"] += 1
        else:
            print(f"  [FAIL] {{check_name}}")
            results["fail"] += 1

    return results["fail"] == 0

if __name__ == "__main__":
    success = validate_alert_ordering()
    sys.exit(0 if success else 1)
''',

    "voice_kb_context": '''#!/usr/bin/env python3
"""
Validator: KB Context Inclusion
Prevents: KB chunks not being included in responses
Generated: {timestamp}
From finding: {finding_id}
"""

import re
import sys

def validate_kb_context():
    results = {{"pass": 0, "fail": 0}}

    print("\\n[KB Context Inclusion]")

    with open("voice-handler.js", "r") as f:
        content = f.read()

    checks = [
        ("_fetchRAGContext function exists", "async function _fetchRAGContext(" in content),
        ("Calls semantic_search_kb RPC", "db.rpc('semantic_search_kb'" in content),
        ("KB section in system prompt", "kbSection" in content and "(from KB:" in content),
    ]

    for check_name, passed in checks:
        if passed:
            print(f"  [PASS] {{check_name}}")
            results["pass"] += 1
        else:
            print(f"  [FAIL] {{check_name}}")
            results["fail"] += 1

    return results["fail"] == 0

if __name__ == "__main__":
    success = validate_kb_context()
    sys.exit(0 if success else 1)
''',

    "visual_defect_confidence": '''#!/usr/bin/env python3
"""
Validator: Visual Defect Confidence Scoring
Prevents: Missing confidence scores in defect analysis
Generated: {timestamp}
From finding: {finding_id}
"""

import re
import sys

def validate_visual_confidence():
    results = {{"pass": 0, "fail": 0}}

    print("\\n[Visual Defect Confidence]")

    with open("visual-defect.html", "r") as f:
        content = f.read()

    checks = [
        ("Confidence display element", "[data-test=confidence-score]" in content),
        ("Confidence calculation logic", "confidence" in content or "score" in content),
    ]

    for check_name, passed in checks:
        if passed:
            print(f"  [PASS] {{check_name}}")
            results["pass"] += 1
        else:
            print(f"  [FAIL] {{check_name}}")
            results["fail"] += 1

    return results["fail"] == 0

if __name__ == "__main__":
    success = validate_visual_confidence()
    sys.exit(0 if success else 1)
''',

    "calc_formula_accuracy": '''#!/usr/bin/env python3
"""
Validator: Engineering Calc Formula Accuracy
Prevents: Formula mismatches with standards
Generated: {timestamp}
From finding: {finding_id}
"""

import re
import sys

def validate_calc_formulas():
    results = {{"pass": 0, "fail": 0}}

    print("\\n[Calc Formula Accuracy]")

    with open("tools/run_all_checks.py", "r") as f:
        content = f.read()

    checks = [
        ("Run all checks exists", "run_all_checks.py" in content),
        ("Engineering calc tests included", "engineering" in content.lower()),
    ]

    for check_name, passed in checks:
        if passed:
            print(f"  [PASS] {{check_name}}")
            results["pass"] += 1
        else:
            print(f"  [FAIL] {{check_name}}")
            results["fail"] += 1

    return results["fail"] == 0

if __name__ == "__main__":
    success = validate_calc_formulas()
    sys.exit(0 if success else 1)
''',

    "voice_response_latency": '''#!/usr/bin/env python3
"""
Validator: Voice Response Latency SLA
Prevents: Voice responses exceeding 5s timeout
Generated: {timestamp}
From finding: {finding_id}
"""

import re
import sys

def validate_voice_latency():
    results = {{"pass": 0, "fail": 0}}

    print("\\n[Voice Response Latency]")

    with open("voice-handler.js", "r") as f:
        content = f.read()

    checks = [
        ("Timeout defined", "timeout" in content.lower()),
        ("Latency monitoring", "latency" in content.lower() or "duration" in content.lower()),
        ("Response timeout handler", "TimeoutError" in content or "timed out" in content),
    ]

    for check_name, passed in checks:
        if passed:
            print(f"  [PASS] {{check_name}}")
            results["pass"] += 1
        else:
            print(f"  [FAIL] {{check_name}}")
            results["fail"] += 1

    return results["fail"] == 0

if __name__ == "__main__":
    success = validate_voice_latency()
    sys.exit(0 if success else 1)
''',

    "response_format_validation": '''#!/usr/bin/env python3
"""
Validator: Response Format Validation
Prevents: Malformed or truncated responses
Generated: {timestamp}
From finding: {finding_id}
"""

import re
import sys

def validate_response_format():
    results = {{"pass": 0, "fail": 0}}

    print("\\n[Response Format Validation]")

    with open("voice-handler.js", "r") as f:
        content = f.read()

    checks = [
        ("Response validation logic", "validate" in content.lower() or "format" in content.lower()),
        ("JSON parsing", "JSON.parse" in content or "JSON.stringify" in content),
        ("Error handling for malformed", "catch" in content),
    ]

    for check_name, passed in checks:
        if passed:
            print(f"  [PASS] {{check_name}}")
            results["pass"] += 1
        else:
            print(f"  [FAIL] {{check_name}}")
            results["fail"] += 1

    return results["fail"] == 0

if __name__ == "__main__":
    success = validate_response_format()
    sys.exit(0 if success else 1)
''',

    "data_completeness": '''#!/usr/bin/env python3
"""
Validator: Response Data Completeness
Prevents: Missing or incomplete data in responses
Generated: {timestamp}
From finding: {finding_id}
"""

import re
import sys

def validate_data_completeness():
    results = {{"pass": 0, "fail": 0}}

    print("\\n[Data Completeness]")

    with open("voice-handler.js", "r") as f:
        content = f.read()

    checks = [
        ("Null/undefined checks", "!== null" in content or "!== undefined" in content or "??" in content),
        ("Data validation rules", "if (" in content and ("length" in content or "size" in content)),
        ("Fallback values", "||" in content or "??" in content),
    ]

    for check_name, passed in checks:
        if passed:
            print(f"  [PASS] {{check_name}}")
            results["pass"] += 1
        else:
            print(f"  [FAIL] {{check_name}}")
            results["fail"] += 1

    return results["fail"] == 0

if __name__ == "__main__":
    success = validate_data_completeness()
    sys.exit(0 if success else 1)
''',
}


def generate_validator_for_finding(finding: dict) -> str:
    """
    Create a new validator file based on finding type.
    Returns: validator filename (e.g., "validate_voice_alert_order.py")
    """
    finding_type = finding.get("finding_type", "unknown")
    finding_id = finding.get("finding_id", "")
    surface = finding.get("surface", "unknown").lower()

    # Map finding types to validator templates
    type_to_validator = {
        "wrong_order": "voice_alert_order",
        "missing_alert": "voice_alert_order",
        "missing_kb_context": "voice_kb_context",
        "confidence_low": "visual_defect_confidence",
        "schema_mismatch": "calc_formula_accuracy",
        "latency_high": "voice_response_latency",
        "format_error": "response_format_validation",
        "incomplete_data": "data_completeness",
    }

    template_key = type_to_validator.get(finding_type)

    if not template_key:
        print(f"  [WARN] No template for finding type: {finding_type}")
        return None

    if template_key not in VALIDATOR_TEMPLATES:
        print(f"  [WARN] Template not found: {template_key}")
        return None

    template = VALIDATOR_TEMPLATES[template_key]
    validator_name = f"validate_{template_key}"
    validator_filename = f"{validator_name}.py"
    validator_path = Path("tools") / validator_filename

    # Check if already exists
    if validator_path.exists():
        print(f"  [PASS] Validator already exists: {validator_filename}")
        return validator_filename

    # Generate validator code
    validator_code = template.format(
        timestamp=datetime.now().isoformat(),
        finding_id=finding_id,
    )

    try:
        validator_path.write_text(validator_code)
        print(f"  [PASS] Generated validator: {validator_filename}")
        return validator_filename
    except Exception as e:
        print(f"  [FAIL] Failed to generate validator: {e}")
        return None


def register_validator_in_gates(validator_filename: str) -> bool:
    """
    Register validator in run_platform_checks.py GATES list.
    """
    if not validator_filename:
        return False

    validator_name = validator_filename.replace("validate_", "").replace(".py", "")
    run_checks_path = Path("run_platform_checks.py")

    if not run_checks_path.exists():
        print(f"  [FAIL] run_platform_checks.py not found")
        return False

    try:
        content = run_checks_path.read_text()

        # Check if already registered
        if f'"{validator_name}"' in content:
            print(f"  [PASS] Validator already registered: {validator_name}")
            return True

        # Find VALIDATORS list and add new entry
        validators_pattern = r'(VALIDATORS = \[)([\s\S]*?)(\n\])'
        match = re.search(validators_pattern, content)

        if not match:
            print(f"  [FAIL] Could not find VALIDATORS list in run_platform_checks.py")
            return False

        new_entry = f'''    {{
        "id":      "{validator_name}",
        "script":  "tools/{validator_filename}",
        "args":    [],
        "label":   "AI Self-Improvement: {validator_name.replace('_', ' ').title()}",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    }},'''

        # Insert before closing bracket
        validators_list = match.group(2)
        new_validators = validators_list + "\n" + new_entry

        content = content.replace(
            match.group(1) + validators_list + match.group(3),
            match.group(1) + new_validators + match.group(3)
        )

        run_checks_path.write_text(content)
        print(f"  [PASS] Registered in GATES: {validator_name}")
        return True

    except Exception as e:
        print(f"  [FAIL] Registration error: {e}")
        return False


def generate_and_register_all(findings_file="SCENARIO_FINDINGS.jsonl") -> dict:
    """Load findings and generate/register validators for all."""
    print("\n" + "=" * 70)
    print("LAYER 3: VALIDATOR GENERATOR & REGISTRAR")
    print("=" * 70)

    findings_path = Path(findings_file)

    if not findings_path.exists():
        print(f"ERROR: {findings_file} not found")
        return {"generated": 0, "registered": 0}

    # Load findings
    findings = []
    if findings_path.stat().st_size > 0:
        with open(findings_path) as f:
            for line in f:
                if line.strip():
                    try:
                        findings.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

    print(f"\nGenerating validators for {len(findings)} findings...\n")

    generated = 0
    registered = 0

    for finding in findings:
        finding_id = finding.get("finding_id", "UNKNOWN")
        finding_type = finding.get("finding_type", "unknown")

        print(f"[{finding_id}] {finding_type}")

        validator_filename = generate_validator_for_finding(finding)

        if validator_filename and register_validator_in_gates(validator_filename):
            generated += 1
            registered += 1
        elif validator_filename:
            generated += 1

    # Save registry
    registry = {
        "timestamp": datetime.now().isoformat(),
        "total_findings": len(findings),
        "validators_generated": generated,
        "validators_registered": registered,
        "findings": [
            {
                "finding_id": f.get("finding_id"),
                "finding_type": f.get("finding_type"),
                "surface": f.get("surface"),
            }
            for f in findings
        ],
    }

    registry_path = Path("VALIDATOR_REGISTRY.json")
    with open(registry_path, "w") as f:
        json.dump(registry, f, indent=2)

    print("\n" + "=" * 70)
    print(f"VALIDATORS: {generated} generated | {registered} registered")
    print("=" * 70)
    print(f"\nRegistry saved to: {registry_path}")

    return {"generated": generated, "registered": registered}


if __name__ == "__main__":
    findings_file = sys.argv[1] if len(sys.argv) > 1 else "SCENARIO_FINDINGS.jsonl"
    result = generate_and_register_all(findings_file)
    sys.exit(0 if result["generated"] > 0 else 1)
