#!/usr/bin/env python3
"""
validate_source_chip_freshness.py — a page that can render from a SAVED copy must not tell the
reader the number is live.

THE CLASS: the source chip is the platform's provenance UI. Reporting freshness is its only job, so
a chip that overstates it is worse than no chip — the reader trusts it precisely where they cannot
check.

WALKED 2026-07-28 (PM deepwalk, PM5). analytics.html renders `analytics_snapshots` — the first view
of the PHT day computes and saves, every later view replays the saved copy and only the Refresh
button recomputes. That is a deliberate, good feature. But the chip read:

    freshness: 'Live recomputation each refresh'

...on every load, including the replay. Measured: the KPI numbers were on screen at 0 ms, up to ~24
hours old, under a chip promising they were live. The concrete consequence for this arc: a
technician completes a PM, opens analytics, and compliance has not moved — with nothing on the page
saying the figure predates their work.

The existing `Source-chip truth` dimension in canonical_status.py checks that a chip names views the
page actually READS. It says nothing about whether the FRESHNESS claim is true, which is how this
shipped green.

WHAT THIS ASSERTS: if a page reads a snapshot/cache TABLE (`*_snapshots`, `*_cache`) or replays a
stored payload, then its `freshness:` value must be COMPUTED — a variable or expression that can say
"saved copy" — not a hardcoded string claiming liveness. A page with no cache path may keep a
literal, because for it the literal is true.

Static/fast. Self-test: --selftest pins both the offending and the fixed shape.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GREEN = "\033[92m"; RED = "\033[91m"; RESET = "\033[0m"; BOLD = "\033[1m"
ROOT = Path(__file__).resolve().parent.parent

# A hardcoded claim that the figure was computed for THIS view.
LIVE_CLAIM_RE = re.compile(
    r"""freshness:\s*(?:_t\(\s*)?['"]([^'"]*(?:live|real[- ]?time|each refresh|just now|"""
    r"""kada refresh|bawat refresh)[^'"]*)['"]""",
    re.I)

# Evidence the page can render from something it stored earlier.
CACHE_READ_RE = re.compile(r"""\.from\(\s*['"](\w*(?:_snapshots|_cache))['"]""", re.I)


def scan_page(path: Path):
    """Return (offending_claims, cache_table) for one page."""
    txt = path.read_text(encoding="utf-8", errors="replace")
    cache = CACHE_READ_RE.search(txt)
    if not cache:
        return [], None
    return LIVE_CLAIM_RE.findall(txt), cache.group(1)


def run_all():
    problems = []
    scanned = 0
    for path in sorted(ROOT.glob("*.html")):
        if path.name.startswith("."):
            continue
        claims, table = scan_page(path)
        if table:
            scanned += 1
        for claim in claims:
            problems.append(
                f"{path.name}: renders from `{table}` yet hardcodes freshness "
                f"“{claim}” — a replayed copy would carry a claim of liveness it cannot "
                f"support. Compute the string from whether this render came from the store.")
    return problems, scanned


def run_selftest():
    """Pin both shapes so the gate cannot rot into a no-op."""
    problems = []
    offending = """db.from('analytics_snapshots').select('payload');
                   renderSourceChip({ freshness: 'Live recomputation each refresh' });"""
    fixed = """db.from('analytics_snapshots').select('payload');
               renderSourceChip({ freshness: _freshness });"""
    if not (CACHE_READ_RE.search(offending) and LIVE_CLAIM_RE.search(offending)):
        problems.append("the pre-fix shape (a snapshot read + a hardcoded live claim) is no longer "
                        "detected — the gate would not have caught the bug it exists for")
    if LIVE_CLAIM_RE.search(fixed):
        problems.append("a COMPUTED freshness value is being flagged — the gate would punish the fix")
    no_cache = "renderSourceChip({ freshness: 'Live recomputation each refresh' });"
    if CACHE_READ_RE.search(no_cache):
        problems.append("a page with no cache read is being treated as cached — too broad")
    return problems


def main():
    if "--selftest" in sys.argv:
        probs = run_selftest()
        print("SELFTEST PASS" if not probs else "SELFTEST FAIL:\n  " + "\n  ".join(probs))
        return 1 if probs else 0

    print(f"\n{BOLD}SOURCE-CHIP FRESHNESS (a saved copy must not claim to be live){RESET}")
    print("-" * 62)
    problems, scanned = run_all()
    for p in problems:
        print(f"  {RED}FAIL{RESET}  {p}")
    if not problems:
        print(f"  {GREEN}PASS{RESET}  {scanned} page(s) render from a stored copy; none claims "
              f"liveness in a hardcoded chip")
    (ROOT / "source_chip_freshness_report.json").write_text(
        json.dumps({"validator": "source_chip_freshness",
                    "cached_pages": scanned, "fail": len(problems),
                    "problems": problems}, indent=2), encoding="utf-8")
    print(f"\n  Summary: {0 if problems else 1} pass · {len(problems)} fail")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
