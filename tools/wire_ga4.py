"""
Wire the GA4 snippet (Measurement ID + custom event helper) into all 27
public WorkHive pages in one pass.

Idempotent: re-runs only modify pages that don't already have the snippet,
or that have a different Measurement ID. Pass --check to dry-run.

Usage:
    python tools/wire_ga4.py G-XXXXXXXXXX           # wire it
    python tools/wire_ga4.py G-XXXXXXXXXX --check   # dry-run, report only
    python tools/wire_ga4.py --remove               # strip GA4 from all pages

The 6 custom events live in /wh-ga4.js (already at project root, served
from / on the live site). The wiring here ONLY injects the gtag config
+ the <script src="/wh-ga4.js"> tag into <head>.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from wh_pages import all_public_pages

# Page list sourced from wh_pages so the GA4 wiring scope auto-grows when
# a new article is added to the catalog.
PAGES = all_public_pages()

GA4_BLOCK_START = "<!-- WorkHive GA4 -->"
GA4_BLOCK_END   = "<!-- /WorkHive GA4 -->"

# Existing block matcher (across newlines)
EXISTING_RE = re.compile(
    re.escape(GA4_BLOCK_START) + r".*?" + re.escape(GA4_BLOCK_END) + r"\s*",
    re.DOTALL,
)


def snippet_for(ga4_id: str) -> str:
    """Return the GA4 + wh-ga4.js snippet for the given Measurement ID."""
    return (
        f"{GA4_BLOCK_START}\n"
        f'  <script async src="https://www.googletagmanager.com/gtag/js?id={ga4_id}"></script>\n'
        f'  <script>\n'
        f'    window.dataLayer = window.dataLayer || [];\n'
        f'    function gtag(){{dataLayer.push(arguments);}}\n'
        f"    gtag('js', new Date());\n"
        f"    gtag('config', '{ga4_id}', {{ anonymize_ip: true }});\n"
        f"  </script>\n"
        f'  <script src="/wh-ga4.js" defer></script>\n'
        f"  {GA4_BLOCK_END}\n"
    )


def wire_page(path: Path, ga4_id: str, check_only: bool = False) -> str:
    """Return one of: 'inserted', 'updated', 'unchanged', 'missing-head', 'missing-file'."""
    if not path.is_file():
        return "missing-file"

    html = path.read_text(encoding="utf-8")
    desired = snippet_for(ga4_id)

    existing_match = EXISTING_RE.search(html)
    if existing_match:
        if existing_match.group(0).strip() == desired.strip():
            return "unchanged"
        # Different Measurement ID or formatting drift -> replace in place
        new_html = EXISTING_RE.sub(desired, html, count=1)
        if not check_only:
            path.write_text(new_html, encoding="utf-8")
        return "updated"

    # No existing block. Inject right before </head>.
    if "</head>" not in html:
        return "missing-head"
    new_html = html.replace("</head>", desired + "</head>", 1)
    if not check_only:
        path.write_text(new_html, encoding="utf-8")
    return "inserted"


def remove_page(path: Path, check_only: bool = False) -> str:
    if not path.is_file():
        return "missing-file"
    html = path.read_text(encoding="utf-8")
    if not EXISTING_RE.search(html):
        return "absent"
    new_html = EXISTING_RE.sub("", html, count=1)
    if not check_only:
        path.write_text(new_html, encoding="utf-8")
    return "removed"


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    check_only = "--check" in args
    remove     = "--remove" in args
    ga4_id     = next((a for a in args if a.startswith("G-")), None)

    if not remove and not ga4_id:
        print("ERROR: pass a Measurement ID like 'G-XXXXXXXXXX' or --remove.")
        sys.exit(2)

    if ga4_id and not re.fullmatch(r"G-[A-Z0-9]{6,12}", ga4_id):
        print(f"ERROR: '{ga4_id}' does not look like a GA4 Measurement ID.")
        print("       Expected format: G-XXXXXXXXXX (G- prefix + 6-12 alphanumerics)")
        sys.exit(2)

    counts = {}
    for rel in PAGES:
        path = ROOT / rel.replace("/", "\\")
        if remove:
            result = remove_page(path, check_only=check_only)
        else:
            result = wire_page(path, ga4_id, check_only=check_only)
        counts[result] = counts.get(result, 0) + 1
        marker = "[OK]"
        if result in ("missing-file", "missing-head"):
            marker = "[!!]"
        print(f"  {marker} {result:>14}  {rel}")

    print()
    if check_only:
        print("DRY-RUN (no files modified).")
    print("Summary:", " | ".join(f"{v} {k}" for k, v in sorted(counts.items())))
    if "missing-file" in counts or "missing-head" in counts:
        sys.exit(3)


if __name__ == "__main__":
    main()
