#!/usr/bin/env python3
"""
reference-pages-uncapped — "cap is not a total" on the surfaces the DB-backed cap gates never scan
(P-C lens, 2026-09-05: P160 validator-catalog, P131 design-system, P155 founder-console).

A list read with `.limit(N)` or a render with `.slice(0, N)` silently turns "N" into the number the
page paints. On these pages that is honest only if, within CONTEXT lines of the capped site, EITHER
  (a) a disclosure the reader can see is rendered — "latest N", "showing", "first N", "were loaded" — OR
  (b) the site is annotated `cap-ok:` with the reason no total is painted (rows only, a sum under the
      cap that a psql recipe holds, ...).
Every reference page is scanned in full; a site with neither is a FAIL naming file:line.
Exit 0 = PASS, 1 = FAIL. `--self-test` proves the gate bites on a synthetic offender.
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = [
    "validator-catalog.html", "symbol-gallery.html", "design-system.html", "architecture.html",
    "learn/index.html", "offline-fallback.html", "llm-observability.html", "founder-console.html",
    # P-C "cap is not a total" on the DB pages (2026-09-05, P122..P158): the same disclosure rule
    "agentic-rag-observability.html", "ai-quality.html", "marketplace-admin.html", "platform-actions.html", "analytics.html",
    "alert-hub.html", "project-report.html", "skillmatrix.html", "achievements.html", "community.html", "plant-connections.html",
]
CAP_RE = re.compile(r"\.limit\(\s*(\d+)\s*\)|\.slice\(\s*0\s*,\s*(\d+)\s*\)")
DISCLOSE_RE = re.compile(r"latest\s+\$?\{?[\d,]+|showing|first\s+\$?\{?[\d,]+|were loaded|shown\b|cap-ok:", re.I)
CONTEXT = 60          # lines either side of the capped site
MIN_N = 10            # a slice(0, 3) is a preview, not a cap on a list
DATE_SLICES = {10, 16, 19}   # slice(0, 10|16|19) is an ISO date / minute / timestamp cut, not a list cap
# a count/badge sink: setCount(...), or a textContent/innerText assignment into an element whose id names a count/badge
BADGE_RE = re.compile(r"setCount\(|getElementById\('[a-z-]*(count|badge|total)[a-z-]*'\)\.(textContent|innerText)\s*=", re.I)
# a '+' disclosure on the painted line: '50+', "'+'", or a `>= N ?` cap branch
PLUS_RE = re.compile(r"\d+\+|'\+'|\+'|>=\s*\d+\s*\?")


def audit(src: str, name: str) -> list[str]:
    lines = src.split("\n")
    bad: list[str] = []
    for i, line in enumerate(lines):
        if line.lstrip().startswith(('//', '*', '<!--')):
            continue   # a comment that mentions a cap is not a cap
        for m in CAP_RE.finditer(line):
            n = int(m.group(1) or m.group(2))
            if n < MIN_N or (m.group(2) and n in DATE_SLICES):
                continue
            # .slice(0, N) on a STRING (a question snippet, a name) is text truncation, not a list cap: the receiver ends
            # in a string-shaped expression - (x || ''), escHtml(...), String(...), .name/.title/.question
            before = line[max(0, m.start() - 48):m.start()]
            if m.group(2) and re.search(r"(\|\|\s*''\)|escHtml\([^)]*\)|String\([^)]*\)|`|\.(question|name|title|subject|text|body|message|note|label|rationale)\b)\s*$", before):
                continue
            lo, hi = max(0, i - CONTEXT), min(len(lines), i + CONTEXT + 1)
            window = "\n".join(lines[lo:hi])
            if not DISCLOSE_RE.search(window):
                bad.append(f"{name}:{i + 1} caps at {n} with no disclosure/cap-ok within {CONTEXT} lines")
            # A BADGE fed from a capped read is a COUNT claim even when the site is annotated 'cap-ok: rows only' (2026-09-05:
            # platform-actions painted the GCash badge from the 20-row page). Within the window AFTER the read, a count/badge
            # painted from `.length` must carry a '+' disclosure, unless the read itself asks for `count: 'exact'`.
            stmt = chr(10).join(lines[max(0, i - 6):i + 1])
            if "count: 'exact'" in stmt or 'count: "exact"' in stmt:
                continue
            for k in range(i + 1, min(len(lines), i + CONTEXT + 1)):
                l2 = lines[k]
                if l2.lstrip().startswith(('//', '*', '<!--')):
                    continue
                if BADGE_RE.search(l2) and '.length' in l2 and not PLUS_RE.search(l2):
                    bad.append(f"{name}:{k + 1} paints a count/badge from .length of the read capped at {n} (line {i + 1}) with no '+' disclosure and no count: 'exact'")
                    break
    return bad


def self_test() -> None:
    good = "const rows = await db.from('x').select('*').limit(50);\n// cap-ok: rows only, no total painted\n"
    assert audit(good, "good") == [], "annotated site must pass"
    good2 = "list.innerHTML = rows.slice(0, 100).map(r).join('') + (rows.length > 100 ? 'Showing first 100 of ' + rows.length : '');\n"
    assert audit(good2, "good2") == [], "disclosed site must pass"
    bad = "\n" * 70 + "const rows = await db.from('x').select('*').limit(500);\n" + "\n" * 70
    assert audit(bad, "bad"), "an undisclosed cap must FAIL"
    assert audit("x.slice(0, 3)", "tiny") == [], "a 3-item preview is not a cap"
    assert audit("ts = (health.timestamp || '').slice(0, 19)", "date") == [], "an ISO timestamp cut is not a cap"
    badge_bad = "const q = db.from('x').select('*').limit(20);   // cap-ok: rows only" + chr(10) + ("x" + chr(10)) * 3 + "setCount('gcash-count', rows.length, 'warn');" + chr(10)
    assert any('count/badge' in x for x in audit(badge_bad, "badge_bad")), "a badge painted from a capped read must FAIL even under cap-ok"
    badge_ok = "const q = db.from('x').select('*', { count: 'exact' }).limit(20);   // cap-ok: rows only" + chr(10) + ("x" + chr(10)) * 3 + "setCount('gcash-count', rows.length, 'warn');" + chr(10)
    assert audit(badge_ok, "badge_ok") == [], "an exact-count read may feed a badge"
    badge_plus = "const q = db.from('x').select('*').limit(50);   // cap-ok: rows only" + chr(10) + ("x" + chr(10)) * 3 + "setCount('drafts-count', rows.length >= 50 ? '50+' : rows.length, 'warn');" + chr(10)
    assert audit(badge_plus, "badge_plus") == [], "a '+'-disclosed badge passes"
    print("self-test OK: bites on an undisclosed .limit(500) and on a badge painted from a capped read; passes disclosed / annotated / tiny / exact-count / '+' sites")


def main() -> int:
    if "--self-test" in sys.argv:
        self_test(); return 0
    bad: list[str] = []
    scanned = 0
    for p in PAGES:
        f = ROOT / p
        if not f.exists():
            bad.append(f"{p}: MISSING (roster drift)"); continue
        scanned += 1
        bad += audit(io.open(f, encoding="utf-8", errors="replace").read(), p)
    if bad:
        print(f"FAIL reference-pages-uncapped - {len(bad)} capped read(s) paint a cap as a total or say nothing:")
        for b in bad[:20]:
            print("  " + b)
        return 1
    print(f"PASS reference-pages-uncapped - {scanned} pages scanned; every list cap is disclosed or annotated cap-ok.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
