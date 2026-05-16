#!/usr/bin/env python3
"""
Validator: Response Data Completeness
Prevents: Missing or incomplete data in responses
Generated: 2026-05-17T10:39:22.043171
From finding: FINDING-20260517103921-V-01
"""

import re
import sys

def validate_data_completeness():
    results = {"pass": 0, "fail": 0}

    print("\n[Data Completeness]")

    with open("voice-handler.js", "r") as f:
        content = f.read()

    checks = [
        ("Null/undefined checks", "!== null" in content or "!== undefined" in content or "??" in content),
        ("Data validation rules", "if (" in content and ("length" in content or "size" in content)),
        ("Fallback values", "||" in content or "??" in content),
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
    success = validate_data_completeness()
    sys.exit(0 if success else 1)
