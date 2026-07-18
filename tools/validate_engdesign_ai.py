#!/usr/bin/env python3
"""
Validator: Engineering-Design AI egress integrity (deep-arc P5, client + calc-agent).

Locks the AI-integrity fixes so they can't regress:

  AI-4  Both AI edge-fn calls are bounded by a client timeout (invokeWithTimeout), not a bare
        db.functions.invoke that can hang the spinner forever.
  AI-5  LOADING_MESSAGES are honest about the 2-stage pipeline — no overstated claims that the
        AI "validates inputs" / "checks compliance" (it computes, then drafts prose).
  AI-7  The report preview carries an AI-drafted disclosure (role="note", "AI-drafted").
  AI-8  friendlyAiError() exists and no failure path dumps `'Error: ' + err.message` to a toast.
  AI-1  engineering-calc-agent grounds the spoken narration (narrationQuotesResult) and calls it.

NOTE: edge-fn deploy is Ian-gated; this asserts the SOURCE contract (the local edge runtime
serves from source). AI-2/AI-3/AI-6 (BOM grounding, parse-hardening, citation-allowlist) remain
queued as documented in ENGINEERING_DESIGN_DEEP_ARC.md.

Static + hermetic. Run: python tools/validate_engdesign_ai.py   Self-test: --self-test
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
CALC_AGENT = os.path.join(ROOT, "supabase", "functions", "engineering-calc-agent", "index.ts")

OVERSTATED = ["Validating inputs against design parameters", "Checking compliance with applicable standards",
              "Running standards-grade analysis"]


def run():
    js = open(JS, encoding="utf-8").read()
    html = open(HTML, encoding="utf-8").read()
    ts = open(CALC_AGENT, encoding="utf-8").read() if os.path.exists(CALC_AGENT) else ""
    problems = []

    # AI-4: timeout wrapper exists and the two invokes use it (no bare invoke of these fns)
    if "function invokeWithTimeout(" not in js:
        problems.append("AI-4: invokeWithTimeout() missing")
    for fn in ("engineering-calc-agent", "engineering-bom-sow"):
        if re.search(r"db\.functions\.invoke\(\s*['\"]" + re.escape(fn) + r"['\"]", js):
            problems.append(f"AI-4: bare db.functions.invoke('{fn}') — must use invokeWithTimeout")

    # AI-5: no overstated loading claims
    for phrase in OVERSTATED:
        if phrase in js:
            problems.append(f"AI-5: overstated loading copy still present: '{phrase}'")

    # AI-7: AI-drafted disclosure in the report preview
    if not re.search(r'role="note"[^>]*>[\s\S]{0,200}AI-drafted', html):
        problems.append("AI-7: AI-drafted disclosure note missing from report preview")

    # AI-8: friendly errors, no raw provider message
    if "function friendlyAiError(" not in js:
        problems.append("AI-8: friendlyAiError() missing")
    if re.search(r"showToast\(\s*['\"]Error: ['\"]\s*\+\s*err\.message", js):
        problems.append("AI-8: a failure path still dumps `'Error: ' + err.message` to a toast")

    # AI-1: calc-agent grounds the narration
    if ts:
        if "function narrationQuotesResult(" not in ts:
            problems.append("AI-1: narrationQuotesResult() missing in engineering-calc-agent")
        elif "narrationQuotesResult(" not in ts.replace("function narrationQuotesResult(", ""):
            problems.append("AI-1: narrationQuotesResult() defined but never called")

    print("=" * 60)
    print("Engineering-Design AI egress integrity gate (deep-arc P5)")
    print("=" * 60)
    if problems:
        print(f"FAIL — {len(problems)} AI-integrity problem(s):")
        for p in problems:
            print("  x", p)
        return 1
    print("PASS — AI calls bounded (AI-4), honest copy (AI-5), disclosure (AI-7),")
    print("       friendly errors (AI-8), narration grounded (AI-1).")
    return 0


def self_test():
    ok = True
    if not re.search(r"showToast\(\s*['\"]Error: ['\"]\s*\+\s*err\.message", "showToast('Error: ' + err.message, 5000)"):
        print("self-test: raw-error regex broken"); ok = False
    if re.search(r"db\.functions\.invoke\(\s*['\"]engineering-calc-agent['\"]", "invokeWithTimeout('engineering-calc-agent',{})"):
        print("self-test: bare-invoke false positive"); ok = False
    print("SELF-TEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    sys.exit(run())
