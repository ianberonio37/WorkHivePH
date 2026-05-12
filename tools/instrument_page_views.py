"""Phase 0 - Founder Console: instrument live HTML pages with logPageView(db).

For each live .html page in the project root that creates a Supabase client,
insert a single `logPageView(db);` call right after the createClient line.
Idempotent: skips pages already instrumented.

Run: python tools/instrument_page_views.py [--dry-run]

Live pages = top-level .html files, excluding:
  - *.backup.html / *.backup2.html / *-test.html / *-v3-test.html (dev copies)
  - node_modules / test-data-seeder / video_marketing_app (subtrees)
  - symbol-gallery.html (static reference, no createClient)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# Anchor: a `const|let|var <var> = [window.]supabase.createClient(...)` line.
# Single-line and multi-line forms both match because `[^)]+` consumes
# everything up to the first closing paren, including newlines.
# We insert `logPageView(<var>);` right after the matched statement.
CREATE_CLIENT_RE = re.compile(
    r"^(?P<indent>\s*)(?:const|let|var)\s+"
    r"(?P<var>_?[a-zA-Z][_a-zA-Z0-9]*)"
    r"\s*=\s*(?:window\.)?supabase\.createClient\([^)]+\);?\s*$",
    re.MULTILINE,
)

# Idempotency check - if any of these substrings exist, skip the file.
ALREADY_INSTRUMENTED = ("logPageView(db", "logEvent(db, 'page_view'")

EXCLUDE_NAMES = {
    "index.backup.html",
    "index.backup2.html",
    "logbook.backup.html",
    "index-v3-test.html",
    "index-hive-test.html",
    "index-native-test.html",
    "engineering-design-test.html",
}


def find_live_pages() -> list[Path]:
    pages: list[Path] = []
    for p in sorted(ROOT.glob("*.html")):
        if p.name in EXCLUDE_NAMES:
            continue
        pages.append(p)
    return pages


def instrument(path: Path, dry_run: bool) -> str:
    """Return one of: 'instrumented', 'skip-already', 'skip-no-anchor'."""
    text = path.read_text(encoding="utf-8")
    if any(marker in text for marker in ALREADY_INSTRUMENTED):
        return "skip-already"

    match = CREATE_CLIENT_RE.search(text)
    if not match:
        return "skip-no-anchor"

    indent = match.group("indent")
    var = match.group("var")
    insert_at = match.end()
    new_text = (
        text[:insert_at]
        + f"\n{indent}logPageView({var});"
        + text[insert_at:]
    )
    if not dry_run:
        path.write_text(new_text, encoding="utf-8")
    return "instrumented"


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    pages = find_live_pages()
    results: dict[str, list[str]] = {
        "instrumented": [],
        "skip-already": [],
        "skip-no-anchor": [],
    }
    for p in pages:
        status = instrument(p, dry_run)
        results[status].append(p.name)

    total = sum(len(v) for v in results.values())
    print(f"Phase 0 page instrumentation - {total} pages scanned"
          + (" (DRY RUN)" if dry_run else ""))
    print(f"  instrumented:    {len(results['instrumented'])}")
    print(f"  skip-already:    {len(results['skip-already'])}")
    print(f"  skip-no-anchor:  {len(results['skip-no-anchor'])}")
    print()
    if results["instrumented"]:
        print("Instrumented:")
        for n in results["instrumented"]:
            print(f"  + {n}")
        print()
    if results["skip-no-anchor"]:
        print("No createClient anchor (manual review needed):")
        for n in results["skip-no-anchor"]:
            print(f"  ? {n}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
