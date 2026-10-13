#!/usr/bin/env python3
"""
Validator: Visual Defect Confidence Scoring
Prevents: a photo-drafted defect entry that hides how sure the model was.
Generated: 2026-06-09 (FINDING-20260609223732-A-01). Rewritten 2026-10-07 (LM-V walk).

WHY IT WAS REWRITTEN: the original checked `visual-defect.html`, a page that was never built, and SKIPPED with
exit 0 when it was missing - a gate that passed on every board while checking nothing. Photo defect capture lives
on logbook.html (#vdc-capture-btn -> visual-defect-capture), so the checks now read the surface a person uses:

  1. visual-defect-capture clamps the model's confidence into [0, 1] (a model can return 87 or "high").
  2. it writes its own analyze-time fault_knowledge row only above a confidence floor, and records ai_confidence.
  3. its prompt tells the model to report low confidence (and ask for a retake) when the image is unclear.
  4. logbook.html shows the draft's confidence to the person beside the failure mode it drafted.

A missing file is a FAIL, never a skip: the surface this gate protects must exist.
"""

import os
import re
import sys

FN = os.path.join("supabase", "functions", "visual-defect-capture", "index.ts")
PAGE = "logbook.html"


def _read(p):
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def checks(fn_src, page_src):
    out = []
    if fn_src is None:
        return [("visual-defect-capture exists", False)]
    if page_src is None:
        return [("logbook.html exists", False)]
    out.append(("the function clamps confidence into [0, 1]",
                bool(re.search(r"confidence\s*:\s*Math\.max\(\s*0\s*,\s*Math\.min\(\s*1\s*,", fn_src))))
    out.append(("the analyze-time knowledge row is gated on a confidence floor",
                bool(re.search(r"draft\.confidence\s*>=\s*0?\.\d+", fn_src))))
    out.append(("the analyze-time knowledge row records ai_confidence",
                bool(re.search(r"ai_confidence\s*:\s*draft\.confidence", fn_src))))
    out.append(("the prompt asks for low confidence on an unclear image",
                bool(re.search(r"unclear[^\n]{0,120}confidence\s*<\s*0?\.\d", fn_src, re.I))))
    out.append(("logbook.html shows the draft's confidence to the person",
                bool(re.search(r"draft\.confidence", page_src)) and bool(re.search(r"Confidence:\s*\$\{", page_src))))
    return out


def validate_visual_confidence():
    print("\n[Visual Defect Confidence]")
    res = checks(_read(FN), _read(PAGE))
    bad = 0
    for name, ok in res:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        bad += 0 if ok else 1
    return bad == 0


def selftest():
    fn = _read(FN) or ""
    pg = _read(PAGE) or ""
    cases = [
        ("current files", fn, pg, True),
        ("missing function", None, pg, False),
        ("missing page", fn, None, False),
        ("no clamp", fn.replace("Math.max(0, Math.min(1,", "(("), pg, False),
        ("no floor", re.sub(r"draft\.confidence\s*>=\s*0?\.\d+", "true", fn), pg, False),
        ("page hides confidence", fn, pg.replace("Confidence: ${", "Shown: ${"), False),
    ]
    ok = True
    for label, f, p, want in cases:
        got = all(x for _, x in checks(f, p))
        flag = got == want
        ok &= flag
        print(f"  [{'ok' if flag else 'WRONG'}] {label}: {'pass' if got else 'fail'} (want {'pass' if want else 'fail'})")
    return ok


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(0 if selftest() else 1)
    sys.exit(0 if validate_visual_confidence() else 1)
