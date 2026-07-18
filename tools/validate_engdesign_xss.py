#!/usr/bin/env python3
"""
Validator: Engineering-Design XSS / output-encoding hardening (deep-arc P4).

Locks three output-handling fixes in engineering-design.js so the classes can't regress:

  I-7  No DB row is serialized into an inline event handler. The history "View" button used
       onclick='viewHistoryReport(${JSON.stringify(row).replace(/'/g,"&#39;")})' — stuffing
       user/AI-controlled fields (project_name/inputs/narrative) into an onclick attribute with
       hand-rolled single-char escaping (OWASP XSS anti-pattern). Fixed: rows keyed by id, the
       button passes only the uuid. Gate: no `onclick` may contain `JSON.stringify`.

  I-6  Every AI `narrative` field interpolated into report HTML must be escHtml/e-wrapped. Six
       renderers used `${narrative?.field || fallback}` — the AI value inserted RAW when present
       (stored-XSS on report/history re-render). Fixed: wrapped in escHtml(). Gate: no raw
       `${narrative?.field || ...}` or `${narrative?.field}` value interpolation.

  I-5  Both persist paths call validateBeforeSave() (shape allow-list before insert).

Static + hermetic. Run: python tools/validate_engdesign_xss.py   Self-test: --self-test
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

# I-6: raw narrative-VALUE interpolations (not escHtml/e-wrapped). The safe forms are
# `${escHtml(narrative...)}`, `${e(narrative...)}`, and the conditional `${narrative?.x ? `...` : ''}`
# (whose inner uses e()). The dangerous forms interpolate the value directly:
RAW_NARRATIVE = [
    (r"\$\{\s*narrative\??\.\w+\s*\|\|", "raw narrative value with `|| fallback` (wrap in escHtml)"),
    (r"\$\{\s*narrative\??\.\w+\s*\}",   "raw narrative value interpolated directly (wrap in escHtml)"),
]


def _called_in(js, fn, caller):
    m = re.search(r"function\s+" + re.escape(caller) + r"\s*\([^)]*\)\s*\{", js)
    if not m:
        return False
    i = js.index("{", m.start()); depth = 0; j = i
    while j < len(js):
        if js[j] == "{": depth += 1
        elif js[j] == "}":
            depth -= 1
            if depth == 0: break
        j += 1
    return (fn + "(") in js[i:j + 1]


def run():
    js = open(JS, encoding="utf-8").read()
    problems = []

    # I-7: no JSON.stringify inside an inline event handler
    for m in re.finditer(r"onclick\s*=\s*(['\"]).*?JSON\.stringify", js):
        ln = js.count("\n", 0, m.start()) + 1
        problems.append(f"I-7: onclick contains JSON.stringify (serialized row into attribute) @ line {ln}")

    # I-6: raw narrative interpolation
    for pat, desc in RAW_NARRATIVE:
        for m in re.finditer(pat, js):
            ln = js.count("\n", 0, m.start()) + 1
            problems.append(f"I-6: {desc} @ line {ln}")

    # I-5: validateBeforeSave exists + wired into both save paths
    if "function validateBeforeSave(" not in js:
        problems.append("I-5: validateBeforeSave() missing")
    else:
        for caller in ("saveCalc", "saveWithBomSow"):
            if not _called_in(js, "validateBeforeSave", caller):
                problems.append(f"I-5: validateBeforeSave() not called from {caller}()")

    print("=" * 60)
    print("Engineering-Design XSS / output-encoding gate (deep-arc P4)")
    print("=" * 60)
    if problems:
        print(f"FAIL — {len(problems)} output-handling problem(s):")
        for p in problems:
            print("  x", p)
        return 1
    print("PASS — no row-into-onclick (I-7), no raw narrative interpolation (I-6),")
    print("       validateBeforeSave wired into both save paths (I-5).")
    return 0


def self_test():
    ok = True
    # a raw narrative pattern must be caught
    if not re.search(RAW_NARRATIVE[0][0], "x = `${narrative?.objective || 'z'}`"):
        print("self-test: raw-narrative regex broken"); ok = False
    # an escHtml-wrapped one must NOT match the raw pattern
    if re.search(RAW_NARRATIVE[0][0], "x = `${escHtml(narrative?.objective || 'z')}`"):
        print("self-test: escHtml false-positive"); ok = False
    # onclick+JSON.stringify caught
    if not re.search(r"onclick\s*=\s*(['\"]).*?JSON\.stringify", "onclick='f(${JSON.stringify(r)})'"):
        print("self-test: onclick regex broken"); ok = False
    print("SELF-TEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    sys.exit(run())
