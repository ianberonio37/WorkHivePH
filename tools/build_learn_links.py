"""build_learn_links.py - learn_links.json from wh_pages.LEARN_ARTICLES, the catalog it says it comes from.

learn-link.js reads learn_links.json ({"<page>.html": [{slug, title}, ...]}) and every tool page offers
its first guide. The file said "generated from wh_pages.LEARN_ARTICLES" and nothing generated it: on
2026-10-23 it still filed the LOTO guide under Audit, three and a half weeks after the catalog moved it
to the Logbook, the power-rates guide was missing from Engineering Design, and the nine guides the
catalog had never listed were in neither. This is the generator; --check is the drift test that
validate_pull_help_coverage runs.

A guide is filed under its tool_path's PAGE (the query of a deep link such as /index.html?companion=1
is dropped: learn-link.js looks a page up by its file name). Pages keep the order they first appear in
the catalog, and each page's guides keep catalog order, so a page's first guide - the one its chip
offers - is the first one the catalog lists for it.

  python tools/build_learn_links.py            write learn_links.json
  python tools/build_learn_links.py --check    exit 1 when the file differs from the catalog
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "learn_links.json"


def build() -> dict:
    sys.path.insert(0, str(ROOT))
    import wh_pages
    links: dict = {}
    for slug, title, tool_path, _name in wh_pages.LEARN_ARTICLES:
        page = tool_path.split("?", 1)[0].lstrip("/")
        links.setdefault(page, []).append({"slug": slug, "title": title})
    return links


def render(links: dict) -> str:
    return json.dumps(links, indent=2, ensure_ascii=False) + "\n"


def drift() -> list[str]:
    """What differs between the file and the catalog, page by page (empty = in step)."""
    want = build()
    try:
        have = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        return ["learn_links.json is missing or unreadable"]
    out = []
    for page in sorted(set(want) | set(have)):
        w = [g["slug"] for g in want.get(page, [])]
        h = [g.get("slug") for g in have.get(page, []) or []]
        if w != h:
            out.append(f"{page}: catalog {w} - file {h}")
    if not out and render(want) != OUT.read_text(encoding="utf-8"):
        out.append("the titles or the page order differ from the catalog")
    return out


def main() -> int:
    if "--check" in sys.argv:
        d = drift()
        for line in d:
            print("  drift:", line)
        print("learn_links.json " + ("differs from the catalog - run python tools/build_learn_links.py"
                                     if d else "matches wh_pages.LEARN_ARTICLES"))
        return 1 if d else 0
    links = build()
    OUT.write_text(render(links), encoding="utf-8", newline="\n")
    print(f"wrote learn_links.json: {sum(len(v) for v in links.values())} guides on {len(links)} pages")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
