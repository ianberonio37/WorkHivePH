"""
Wayfinding Pill CLS-Reserve Validator (L0, absolute — baseline 0).
==================================================================
wayfinding.js (loaded post-paint via nav-hub) injects a floating "Back" pill on
"bare" pages and reserves its band by setting `document.body.style.paddingTop`
inside a requestAnimationFrame — i.e. AFTER first paint. In isolation that fires
before the paint settles (no shift), but under full-sweep / slow-load contention
it lands LATE and shifts the whole page down ~64px = ~0.1 CLS. That is the
"rotating I1 flicker" that failed a DIFFERENT bare page each sweep
(inventory -> ph-intelligence -> audit-log -> ...) — an INTERMITTENT, contention-
dependent regression the dynamic rubric sweep cannot reliably catch.

The fix (2026-07-23) is a STATIC `body { padding-top: calc(64px + env(safe-area-
inset-top,0px)) }` in the page's own <head>, present at first paint so
wayfinding's `if (band > cur)` skips (layout unchanged). This gate LOCKS it: any
page that WILL get the pill must ship that static reserve.

A page gets the pill IFF (mirrors wayfinding.js build():127/134/147/108):
  - it is NOT the home page (index.html);            [IS_HOME -> return]
  - it loads nav-hub.js (which lazy-loads wayfinding);
  - it has NO in-layout back affordance
    (.back-btn / [data-wh-back] / .back-link / .home-link / .breadcrumb /
     [aria-label="breadcrumb"|"Back"]);              [existing chrome -> return]
  - it has a <main> or <h1> for wayfinding to anchor. [no main -> return]
A page that is NOT a pill-page must NOT be forced to carry the reserve (a 64px
void), so it is simply skipped.

Absolute check (baseline 0): every pill-page must carry the reserve. Output:
pill_reserve_report.json. Exit 1 on any violation.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH = ROOT / "pill_reserve_report.json"

# Sentinel binding: name the L2 test test('pill_reserve: ...') for coverage credit.
CHECK_NAMES = ["pill_reserve"]

# Home page(s) — wayfinding returns early (IS_HOME), no pill.
HOME_PAGES = {"index.html"}

LOADS_NAVHUB_RE  = re.compile(r"nav-hub\.js")
# In-layout back affordance that makes wayfinding SKIP the pill (so no reserve needed).
BACK_AFFORDANCE_RE = re.compile(
    r"""class\s*=\s*["'][^"']*\b(?:back-btn|back-link|home-link|breadcrumb)\b"""
    r"""|data-wh-back"""
    r"""|aria-label\s*=\s*["'](?:breadcrumb|Back)["']""",
    re.IGNORECASE,
)
HAS_ANCHOR_RE = re.compile(r"<main[\s>]|<h1[\s>]", re.IGNORECASE)
# The static reserve: padding-top: calc( ... 64px ... env(safe-area-inset-top ...
RESERVE_RE = re.compile(
    r"padding-top\s*:\s*calc\([^;{}]*\b64px\b[^;{}]*env\(\s*safe-area-inset-top",
    re.IGNORECASE,
)


def _is_pill_page(name: str, body: str) -> bool:
    if name in HOME_PAGES:
        return False
    if not LOADS_NAVHUB_RE.search(body):
        return False
    if BACK_AFFORDANCE_RE.search(body):
        return False
    if not HAS_ANCHOR_RE.search(body):
        return False
    return True


def main() -> int:
    pill_pages, violations, scanned = [], [], 0
    for path in sorted(ROOT.glob("*.html")):
        n = path.name
        if n.startswith("_") or ".backup." in n or n.endswith("-test.html"):
            continue
        scanned += 1
        body = path.read_text(encoding="utf-8", errors="replace")
        if not _is_pill_page(n, body):
            continue
        pill_pages.append(n)
        if not RESERVE_RE.search(body):
            violations.append(n)

    REPORT_PATH.write_text(json.dumps({
        "summary": {"html_scanned": scanned, "pill_pages": len(pill_pages), "violations": len(violations)},
        "pill_pages": pill_pages,
        "violations": violations,
    }, indent=2), encoding="utf-8")

    print("\nWayfinding Pill CLS-Reserve Validator (L0)")
    print("=" * 56)
    print(f"  html scanned:  {scanned}")
    print(f"  pill-pages:    {len(pill_pages)}")
    print(f"  violations:    {len(violations)}  (must be 0)")
    if not violations:
        print("\n  PASS — every pill-page ships the static back-pill band reserve.")
        return 0
    print("\n  FAIL — pill-pages MISSING the static reserve (will flicker CLS ~0.1 under contention):")
    for n in violations:
        print(f"    {n}  -> add to <head>: body{{padding-top:calc(64px + env(safe-area-inset-top,0px))}}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
