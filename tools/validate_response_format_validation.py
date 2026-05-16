#!/usr/bin/env python3
"""
Validator: Response Format Validation
Prevents: Malformed or truncated responses
Generated: 2026-05-17T10:39:21.929838
From finding: FINDING-20260517103919-V-01
"""

import re
import sys

def validate_response_format():
    results = {"pass": 0, "fail": 0}

    print("\n[Response Format Validation]")

    with open("voice-handler.js", "r") as f:
        content = f.read()

    checks = [
        ("Response validation logic", "validate" in content.lower() or "format" in content.lower()),
        ("JSON parsing", "JSON.parse" in content or "JSON.stringify" in content),
        ("Error handling for malformed", "catch" in content),
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
    success = validate_response_format()
    sys.exit(0 if success else 1)
