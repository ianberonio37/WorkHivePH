"""sentinel_freshness.py - v3 axis: stale-selector / dead-route detection.

For each tests/*.spec.ts, extract page.goto() URLs and cross-reference them
against actual HTML files at project root. Routes that don't map to a file
are stale (the page was renamed/retired and the spec wasn't updated).

This catches the common drift bug: a page gets refactored, but the spec
still references the old URL. Test passes by accident because Playwright
treats 404 as a navigation, and the test's assertions don't load the new
page's selectors.

Pure deterministic. See SENTINEL_ARCHITECTURE.md.
"""

import sys
import re
import json
import datetime
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = ROOT / "tests"
REPORT_FILE = ROOT / "sentinel_freshness_report.json"

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"

EXEMPT_FILES = {
    "_db-cleanup.ts", "_fixtures.ts", "_helpers.ts", "_smoke-template.ts",
}

GOTO_RE = re.compile(r"""\.goto\s*\(\s*['"`]([^'"`]+)['"`]""")


def collect_html_pages(root: Path) -> set:
    """Set of every .html file at project root (without extension)."""
    return {p.stem for p in root.glob("*.html")}


def url_to_page_name(url: str) -> str | None:
    """Map a route like '/workhive/logbook.html' -> 'logbook'."""
    if url.startswith("http://") or url.startswith("https://"):
        return None
    cleaned = url.split("?")[0].split("#")[0]
    cleaned = cleaned.rstrip("/")
    if cleaned.endswith(".html"):
        cleaned = cleaned[:-5]
    parts = [p for p in cleaned.split("/") if p]
    if not parts:
        return None
    name = parts[-1]
    if name in {"workhive", ""}:
        return None
    return name


def analyze_spec(path: Path, html_pages: set) -> dict:
    src = path.read_text(encoding="utf-8", errors="ignore")
    gotos = GOTO_RE.findall(src)
    stale = []
    fresh = []
    for url in gotos:
        page = url_to_page_name(url)
        if page is None:
            continue
        if page in html_pages:
            fresh.append(url)
        else:
            stale.append(url)
    return {
        "file": path.name,
        "total_gotos": len(gotos),
        "fresh_count": len(fresh),
        "stale_count": len(stale),
        "stale_urls": sorted(set(stale)),
    }


def main():
    print()
    print(f"{BOLD}SENTINEL - FRESHNESS (v3){RESET}")
    print("-" * 60)

    if not TESTS_DIR.exists():
        print(f"  {RED}tests/ not found{RESET}")
        return 1

    html_pages = collect_html_pages(ROOT)
    print(f"  HTML pages indexed: {len(html_pages)}")

    specs = sorted(TESTS_DIR.glob("*.spec.ts"))
    results = []
    total_gotos = 0
    total_stale = 0

    for spec in specs:
        if spec.name in EXEMPT_FILES:
            continue
        r = analyze_spec(spec, html_pages)
        results.append(r)
        total_gotos += r["total_gotos"]
        total_stale += r["stale_count"]

    stale_pct = round(100 * total_stale / total_gotos, 1) if total_gotos else 0.0
    pct_color = GREEN if stale_pct < 5 else YELLOW if stale_pct < 15 else RED

    print(f"  {BOLD}Specs analyzed:{RESET}     {len(results)}")
    print(f"  {BOLD}Total page.goto():{RESET}  {total_gotos}")
    print(f"  {BOLD}Stale routes:{RESET}       {total_stale} ({pct_color}{stale_pct}%{RESET})")
    print()

    with_stale = [r for r in results if r["stale_count"] > 0]
    if with_stale:
        print(f"  {BOLD}Specs with stale routes (first 15):{RESET}")
        for r in with_stale[:15]:
            print(f"    {YELLOW}STALE{RESET}  {r['file']}  ({r['stale_count']} stale)")
            for url in r["stale_urls"][:3]:
                print(f"           - {url}")
        if len(with_stale) > 15:
            print(f"    ... and {len(with_stale) - 15} more specs (see report)")
        print()
    else:
        print(f"  {GREEN}No stale routes found - all page.goto() URLs map to live HTML files{RESET}")
        print()

    REPORT_FILE.write_text(json.dumps({
        "timestamp": datetime.datetime.now().isoformat(),
        "sentinel": "sentinel_freshness",
        "version": "v3",
        "summary": {
            "total_specs": len(results),
            "total_gotos": total_gotos,
            "stale_routes": total_stale,
            "stale_pct": stale_pct,
            "html_pages_indexed": len(html_pages),
        },
        "results": results,
    }, indent=2), encoding="utf-8")

    print(f"  Report -> {REPORT_FILE.name}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
