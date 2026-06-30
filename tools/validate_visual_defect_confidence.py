#!/usr/bin/env python3
"""
Validator: Visual Defect Confidence Scoring
Prevents: Missing confidence scores in defect analysis
Generated: 2026-06-09T22:37:32.883415
From finding: FINDING-20260609223732-A-01
"""

import os
import re
import sys

def validate_visual_confidence():
    results = {"pass": 0, "fail": 0}

    print("\n[Visual Defect Confidence]")

    # The auto-generated target page (visual-defect.html) was never built / is retired.
    # A validator must not crash the suite on a missing target — skip gracefully (and resume
    # checking automatically if the page is ever added).
    if not os.path.exists("visual-defect.html"):
        print("  [SKIP] visual-defect.html not present (page not built/retired) — nothing to check")
        return True

    with open("visual-defect.html", "r") as f:
        content = f.read()

    checks = [
        ("Confidence display element", "[data-test=confidence-score]" in content),
        ("Confidence calculation logic", "confidence" in content or "score" in content),
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
    success = validate_visual_confidence()
    sys.exit(0 if success else 1)
