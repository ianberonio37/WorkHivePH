#!/usr/bin/env python3
"""
Validator: Alert Priority Ordering
Prevents: Alerts not surfacing first in Voice responses
Generated: 2026-05-17T10:36:10.687526
From finding: FINDING-20260517103441-V-01
"""

import re
import sys

def validate_alert_ordering():
    results = {"pass": 0, "fail": 0}

    print("\n[Alert Ordering]")

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
            print(f"  [PASS] {check_name}")
            results["pass"] += 1
        else:
            print(f"  [FAIL] {check_name}")
            results["fail"] += 1

    return results["fail"] == 0

if __name__ == "__main__":
    success = validate_alert_ordering()
    sys.exit(0 if success else 1)
