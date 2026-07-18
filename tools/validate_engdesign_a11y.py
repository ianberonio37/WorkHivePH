#!/usr/bin/env python3
"""
Validator: Engineering-Design report ACCESSIBILITY fixes (deep-arc P3).

Locks the specific a11y regressions found + fixed by the live axe deepwalk of the RENDERED
report (the platform's empty-state axe scan structurally missed them — the report only exists
after a calc runs). Static ratchet over the two source files so each fix can't silently revert:

  U-1  headline .res-value must NOT use var(--wh-orange-dark) (#d88a0e = 2.68:1 on cream).
  U-4  no light-gray-on-white report text: color:#999 / #888 / #aaa must be gone (were 2.8:1).
  U-6  .btn-primary and .btn-ghost carry min-height:44px (report action buttons were 37px).
  U-2  labelizeInputs() exists AND is called from selectCalcType() (inputs get real names).
  U-3  announceStatus() exists AND is called from showReport() (SC 4.1.3 status message).
  U-8  labelizeReportEditables() exists AND is called from showReport() (editable field names).

Live-verified this session: axe WCAG2.2-AA on the post-calc report = 0 violations (was 4
contrast + would-be 7 unnamed-textbox). This gate is the durable code-level lock.

Static + hermetic. Run: python tools/validate_engdesign_a11y.py   Self-test: --self-test
"""
import os
import re
import sys

try:
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(ROOT, "engineering-design.js")
HTML = os.path.join(ROOT, "engineering-design.html")


def _called_in(js, fn, caller):
    """True if function `caller` exists and its body calls `fn(`."""
    m = re.search(r"function\s+" + re.escape(caller) + r"\s*\([^)]*\)\s*\{", js)
    if not m:
        return False
    # balanced body
    i = js.index("{", m.start()); depth = 0; j = i
    while j < len(js):
        if js[j] == "{": depth += 1
        elif js[j] == "}":
            depth -= 1
            if depth == 0: break
        j += 1
    body = js[i:j + 1]
    return (fn + "(") in body


def run():
    js = open(JS, encoding="utf-8").read()
    html = open(HTML, encoding="utf-8").read()
    problems = []

    # U-4: light-gray TEXT on the white report/doc panels fails AA (measured: #999=2.84:1; #888=3.5:1
    # and #aaa=2.3:1 at the 12px caption sizes used). Verified report-only (the dark UI uses rgba,
    # 0 hex grays in the shell; 0 `background:#888`), so all were darkened to #595959/#6b6b6b. This
    # asserts the whole class stays gone. (`#999` as a `solid #999` BORDER is decoration, not text —
    # matched only on `color:` so borders are not flagged.)
    for gray in ("#999", "#888", "#aaa"):
        n = len(re.findall(r"color:\s*" + re.escape(gray) + r"\b", js))
        if n:
            problems.append(f"U-4 contrast: {n}x `color:{gray}` TEXT remain on white report panels (< 4.5:1 at caption sizes)")

    # U-1: headline result value must not use the failing orange token
    m = re.search(r"\.res-value\s*\{[^}]*\}", html)
    if m and "var(--wh-orange-dark)" in m.group(0):
        problems.append("U-1 contrast: .res-value still uses var(--wh-orange-dark) (#d88a0e = 2.68:1 on cream)")

    # U-6: 44px min target on the button base classes
    for cls in (".btn-primary", ".btn-ghost"):
        mm = re.search(re.escape(cls) + r"\s*\{[^}]*\}", html)
        if not mm or "min-height: 44px" not in mm.group(0):
            problems.append(f"U-6 target-size: {cls} missing min-height: 44px")

    # U-2 / U-3 / U-8: the runtime a11y passes exist AND are wired
    if "function labelizeInputs(" not in js:
        problems.append("U-2: labelizeInputs() missing")
    elif not _called_in(js, "labelizeInputs", "selectCalcType"):
        problems.append("U-2: labelizeInputs() not called from selectCalcType()")
    if "function announceStatus(" not in js:
        problems.append("U-3: announceStatus() missing")
    elif not _called_in(js, "announceStatus", "showReport"):
        problems.append("U-3: announceStatus() not called from showReport()")
    if "function labelizeReportEditables(" not in js:
        problems.append("U-8: labelizeReportEditables() missing")
    elif not _called_in(js, "labelizeReportEditables", "showReport"):
        problems.append("U-8: labelizeReportEditables() not called from showReport()")

    print("=" * 62)
    print("Engineering-Design report a11y gate (deep-arc P3)")
    print("=" * 62)
    if problems:
        print(f"FAIL — {len(problems)} a11y regression(s):")
        for p in problems:
            print("  x", p)
        return 1
    print("PASS — contrast fixed (U-1/U-4), 44px targets (U-6), and the")
    print("       labelize/announce passes are wired (U-2/U-3/U-8).")
    return 0


def self_test():
    ok = True
    js = "function selectCalcType(id){ renderInputForm(id); labelizeInputs(); }"
    if not _called_in(js, "labelizeInputs", "selectCalcType"):
        print("self-test: _called_in positive broken"); ok = False
    if _called_in(js, "announceStatus", "selectCalcType"):
        print("self-test: _called_in negative broken"); ok = False
    print("SELF-TEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    sys.exit(run())
