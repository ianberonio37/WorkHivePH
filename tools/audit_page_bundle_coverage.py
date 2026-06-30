#!/usr/bin/env python3
# audit-scope-allow: this scans the validate_*.py SUITE (not HTML/edge code) to answer
# "after a page's inline <script> is extracted to an external .js bundle, which validators
# silently lose JS-pattern coverage?" — it is not a column/capture consumer-scan, so the
# feedback_audit_scanner_scope _shared/subdir rule does not apply.
"""
Page-bundle coverage auditor (Arc L / L1).
==========================================
When a page (e.g. engineering-design.html) has its big inline <script> extracted to an
external bundle (engineering-design.js), every Python validator that scans the page's
TEXT for JS-LEVEL constructs silently loses coverage of that code — UNLESS it also reads
the .js. This auditor classifies every validate_*.py (root + tools/) deterministically:

  js-fix      : references the page .html (literal or *.html-glob discovery) AND searches
                for >=1 JS-level construct AND does NOT already read the .js  -> NEEDS FIX
  auto-js     : appends ROOT.glob("*.js") to its MAIN scan list -> .js auto-covered, no fix
  html-only   : searches only HTML-structure patterns (meta/headings/canonical/alt/aria/css)
                -> adding the .js would FALSELY demand head-markup on a JS file; do NOT add
  no-ref      : never references the page

Run:  python tools/audit_page_bundle_coverage.py [page-stem]   (default: engineering-design)
"""
from __future__ import annotations
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STEM = sys.argv[1] if len(sys.argv) > 1 else "engineering-design"
HTML = f"{STEM}.html"
JS = f"{STEM}.js"

# High-signal JS-level constructs. These appear in a Python validator ONLY as search
# patterns (regex/string literals against page content), essentially never as Python code.
JS_TOKENS = [
    "db.from(", ".from('", '.from("', ".select(", ".insert(", ".upsert(", ".update(",
    ".delete(", ".rpc(", ".channel(", ".subscribe(", ".on('", '.on("', "innerHTML",
    "outerHTML", "insertAdjacentHTML", "setInterval", "setTimeout", "clearInterval",
    "addEventListener", "removeEventListener", "getElementById", "querySelector",
    "localStorage", "sessionStorage", "insertAdjacentHTML", "functions.invoke(",
    ".eq(", ".gte(", ".ilike(", ".textContent", "URLSearchParams", "searchParams",
    "classList", "trapFocus", "showToast", "Promise.all", "JSON.stringify",
    "toLocaleDateString", "renderSourceChip", "onclick", "new Function(", "eval(",
]
# HTML-structure patterns — if a validator searches ONLY these, the moved JS is out of scope.
HTML_TOKENS = [
    "<meta", "<h([1-6]", "<h1", "<h2", "<h3", "rel=\"canonical\"", "rel='canonical'",
    "viewport", " alt=", "aria-", "<link", "<title", "og:title", "og:image",
    "<img", "data-rag-tile", "<input", "<button", "role=\"dialog\"", "position:fixed",
]

def scan(p: Path):
    txt = p.read_text(encoding="utf-8", errors="replace")
    refs_html = (f'"{HTML}"' in txt) or (f"'{HTML}'" in txt)
    discovers_html = bool(re.search(r'glob\(\s*["\']\*\.html', txt))
    has_js_literal = (f'"{JS}"' in txt) or (f"'{JS}'" in txt)
    # does it APPEND *.js to a scan list (main scan), heuristic: a glob("*.js") whose result
    # is concatenated/extended into a list (not only inside a *_scope/in_scope check fn)?
    globs_js = bool(re.search(r'glob\(\s*["\']\*\.js', txt))
    # crude: auto-js if it globs *.js AND that glob feeds the iterated page list
    # (appears with + / += / extend / for ... in glob). Distinguish from scope-only by
    # checking the glob is NOT solely inside a function named *scope*/*in_scope*.
    auto_js = False
    if globs_js:
        for m in re.finditer(r'.*glob\(\s*["\']\*\.js.*', txt):
            line = m.group(0)
            if re.search(r'\+\s*\w*glob|\bextend\(|\+=\s*|for\s+\w+\s+in\s+.*glob', line):
                auto_js = True
    js_hits = sorted({t for t in JS_TOKENS if t in txt})
    html_hits = sorted({t for t in HTML_TOKENS if t in txt})
    return refs_html, discovers_html, has_js_literal, globs_js, auto_js, js_hits, html_hits

def main():
    targets = sorted(ROOT.glob("validate_*.py")) + sorted((ROOT / "tools").glob("validate_*.py"))
    rows = []
    for p in targets:
        refs_html, disc_html, has_js, globs_js, auto_js, js_hits, html_hits = scan(p)
        considered = refs_html or disc_html
        if not considered:
            verdict = "no-ref"
        elif has_js or auto_js:
            verdict = "covered" if (has_js or auto_js) else "?"
        elif js_hits:
            verdict = "js-fix"
        elif html_hits:
            verdict = "html-only"
        else:
            verdict = "review"
        rows.append((p.name, verdict, refs_html, disc_html, has_js, auto_js, globs_js, js_hits, html_hits))

    def pr(title, pred):
        sel = [r for r in rows if pred(r)]
        print(f"\n=== {title} ({len(sel)}) ===")
        for name, v, rh, dh, hj, aj, gj, jh, hh in sel:
            tag = []
            if dh: tag.append("html-glob")
            if gj: tag.append("globs-js")
            if aj: tag.append("AUTO-JS")
            print(f"  {name:45} {','.join(tag) or '-':22} js={jh[:6]}")

    print(f"Page-bundle coverage audit for {HTML} -> {JS}")
    print(f"  validators inspected: {len(rows)}")
    pr("NEEDS FIX (refs .html, searches JS constructs, no .js yet)",
       lambda r: r[1] == "js-fix")
    pr("COVERED (already reads .js literal or auto-globs *.js into scan)",
       lambda r: r[4] or r[5])
    pr("HTML-ONLY (do NOT add .js — would falsely demand head-markup)",
       lambda r: r[1] == "html-only")
    pr("REVIEW (refs .html but no clear JS or HTML tokens)",
       lambda r: r[1] == "review")

if __name__ == "__main__":
    main()
